"""
Tests pour DashboardStatsRetriesView — Story 60.8.
Statistiques sur les retries d'exécution via AuditLog.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from profiles.models import Profile
from tests.factories import (
    ActionFactory,
    AuditLogFactory,
    ExecutionFactory,
    UserFactory,
)

URL = '/api/v1/dashboard/stats-retries/'


def _ensure_profiles():
    """Crée les enregistrements Profile nécessaires à la résolution RBAC via _resolve_user_profiles."""
    Profile.objects.get_or_create(
        name='DBA',
        defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='DBOPS',
        defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
    )


# ---------------------------------------------------------------------------
# 4.1 — Permissions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesPermissions:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()

    def test_unauthenticated_returns_401(self):
        response = self.client.get(URL)
        assert response.status_code == 401

    def test_dba_user_returns_200(self):
        user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 200

    def test_dbops_user_returns_200(self):
        user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=user)
        response = self.client.get(URL)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# 4.2 — Structure de réponse
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesStructure:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_response_has_data_key(self):
        response = self.client.get(URL)
        assert response.status_code == 200
        assert 'data' in response.data

    def test_data_contains_all_expected_keys(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert 'total_executions' in data
        assert 'executions_with_retry_count' in data
        assert 'retry_rate' in data
        assert 'by_action' in data

    def test_total_executions_is_integer(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['total_executions'], int)

    def test_executions_with_retry_count_is_integer(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['executions_with_retry_count'], int)

    def test_retry_rate_is_none_when_no_executions(self):
        response = self.client.get(URL)
        assert response.data['data']['retry_rate'] is None

    def test_by_action_is_list(self):
        response = self.client.get(URL)
        assert isinstance(response.data['data']['by_action'], list)


# ---------------------------------------------------------------------------
# 4.3 — Comptage des retries via AuditLog
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesRetryCount:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)
        self.action = ActionFactory.create()

    def test_no_retry_audit_log_means_zero_retry_count(self):
        ExecutionFactory.create(action=self.action)
        response = self.client.get(URL)
        data = response.data['data']
        assert data['total_executions'] == 1
        assert data['executions_with_retry_count'] == 0

    def test_retry_attempt_audit_log_detected(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 1

    def test_retry_success_audit_log_detected(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_SUCCESS',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 1

    def test_retry_exhausted_audit_log_detected(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_EXHAUSTED',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 1

    def test_retry_aborted_audit_log_detected(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ABORTED',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 1

    def test_unrelated_audit_action_type_not_counted(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='ACTION_CREATED',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 0

    def test_wrong_entity_type_audit_log_not_counted(self):
        # AuditLog avec bon action_type retry mais entity_type != 'execution' → ignoré
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='action',  # mauvais entity_type
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['executions_with_retry_count'] == 0

    def test_multiple_audit_logs_same_execution_counted_once(self):
        execution = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=execution.id,
        )
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_EXHAUSTED',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        # Une seule exécution avec plusieurs AuditLog retry → compter 1 fois
        assert response.data['data']['executions_with_retry_count'] == 1


# ---------------------------------------------------------------------------
# 4.4 — Calcul du retry_rate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesRate:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)
        self.action = ActionFactory.create()

    def test_retry_rate_computed_correctly(self):
        # 1 exécution sur 2 a un retry → 50.0%
        exec1 = ExecutionFactory.create(action=self.action)
        ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec1.id,
        )
        response = self.client.get(URL)
        data = response.data['data']
        assert data['total_executions'] == 2
        assert data['executions_with_retry_count'] == 1
        assert data['retry_rate'] == 50.0

    def test_retry_rate_null_when_no_executions(self):
        response = self.client.get(URL)
        assert response.data['data']['retry_rate'] is None

    def test_retry_rate_100_when_all_have_retry(self):
        exec1 = ExecutionFactory.create(action=self.action)
        exec2 = ExecutionFactory.create(action=self.action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec1.id,
        )
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_SUCCESS',
            entity_type='execution',
            entity_id=exec2.id,
        )
        response = self.client.get(URL)
        assert response.data['data']['retry_rate'] == 100.0

    def test_retry_rate_0_when_no_retry(self):
        ExecutionFactory.create(action=self.action)
        ExecutionFactory.create(action=self.action)
        response = self.client.get(URL)
        data = response.data['data']
        assert data['total_executions'] == 2
        assert data['retry_rate'] == 0.0


# ---------------------------------------------------------------------------
# 4.5 — by_action
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesByAction:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_by_action_empty_when_no_retries(self):
        ActionFactory.create()
        response = self.client.get(URL)
        assert response.data['data']['by_action'] == []

    def test_by_action_contains_correct_action_name(self):
        action = ActionFactory.create(name='MonAction')
        execution = ExecutionFactory.create(action=action)
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=execution.id,
        )
        response = self.client.get(URL)
        by_action = response.data['data']['by_action']
        assert len(by_action) == 1
        assert by_action[0]['action_name'] == 'MonAction'
        assert by_action[0]['action_id'] == action.id
        assert by_action[0]['retry_count'] == 1

    def test_by_action_sorted_by_retry_count_desc(self):
        action1 = ActionFactory.create(name='ActionA')
        action2 = ActionFactory.create(name='ActionB')

        # action2 a 2 exécutions avec retry, action1 en a 1
        exec1 = ExecutionFactory.create(action=action1)
        exec2 = ExecutionFactory.create(action=action2)
        exec3 = ExecutionFactory.create(action=action2)

        for ex in [exec1, exec2, exec3]:
            AuditLogFactory.create(
                action_type='EXECUTION_STEP_RETRY_ATTEMPT',
                entity_type='execution',
                entity_id=ex.id,
            )

        response = self.client.get(URL)
        by_action = response.data['data']['by_action']
        assert len(by_action) == 2
        # ActionB (2 retries) doit être en premier
        assert by_action[0]['action_id'] == action2.id
        assert by_action[0]['retry_count'] == 2
        assert by_action[1]['action_id'] == action1.id
        assert by_action[1]['retry_count'] == 1

    def test_by_action_respects_top_n(self):
        # Créer 3 actions avec retries, demander top_n=2
        actions = [ActionFactory.create() for _ in range(3)]
        for action in actions:
            exec_ = ExecutionFactory.create(action=action)
            AuditLogFactory.create(
                action_type='EXECUTION_STEP_RETRY_ATTEMPT',
                entity_type='execution',
                entity_id=exec_.id,
            )
        response = self.client.get(URL, {'top_n': 2})
        assert response.status_code == 200
        assert len(response.data['data']['by_action']) == 2


# ---------------------------------------------------------------------------
# 4.6 — RBAC
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesRBAC:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.action = ActionFactory.create()

    def test_dba_sees_only_own_executions(self):
        dba_user = UserFactory.create(profile='DBA')
        other_user = UserFactory.create(profile='DBA')

        exec_dba = ExecutionFactory.create(action=self.action, user=dba_user)
        exec_other = ExecutionFactory.create(action=self.action, user=other_user)

        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec_dba.id,
        )
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec_other.id,
        )

        self.client.force_authenticate(user=dba_user)
        response = self.client.get(URL)
        data = response.data['data']
        # DBA ne voit que ses propres exécutions
        assert data['total_executions'] == 1
        assert data['executions_with_retry_count'] == 1

    def test_dbops_sees_all_executions(self):
        dbops_user = UserFactory.create(profile='DBOPS')
        dba_user = UserFactory.create(profile='DBA')

        exec1 = ExecutionFactory.create(action=self.action, user=dba_user)
        exec2 = ExecutionFactory.create(action=self.action, user=dbops_user)

        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec1.id,
        )
        AuditLogFactory.create(
            action_type='EXECUTION_STEP_RETRY_ATTEMPT',
            entity_type='execution',
            entity_id=exec2.id,
        )

        self.client.force_authenticate(user=dbops_user)
        response = self.client.get(URL)
        data = response.data['data']
        # DBOPS voit toutes les exécutions
        assert data['total_executions'] == 2
        assert data['executions_with_retry_count'] == 2


# ---------------------------------------------------------------------------
# 4.7 — Paramètres de période
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsRetriesPeriodParams:

    def setup_method(self):
        self.client = APIClient()
        _ensure_profiles()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_invalid_days_returns_400(self):
        response = self.client.get(URL, {'days': 'abc'})
        assert response.status_code == 400

    def test_zero_days_returns_400(self):
        response = self.client.get(URL, {'days': 0})
        assert response.status_code == 400

    def test_negative_days_returns_400(self):
        response = self.client.get(URL, {'days': -5})
        assert response.status_code == 400

    def test_invalid_from_date_returns_400(self):
        response = self.client.get(URL, {'from_date': 'not-a-date'})
        assert response.status_code == 400

    def test_invalid_top_n_zero_returns_400(self):
        response = self.client.get(URL, {'top_n': 0})
        assert response.status_code == 400

    def test_invalid_top_n_over_100_returns_400(self):
        response = self.client.get(URL, {'top_n': 101})
        assert response.status_code == 400

    def test_valid_days_returns_200(self):
        response = self.client.get(URL, {'days': 30})
        assert response.status_code == 200

    def test_valid_from_date_to_date_returns_200(self):
        response = self.client.get(URL, {'from_date': '2026-01-01', 'to_date': '2026-03-01'})
        assert response.status_code == 200

    def test_valid_top_n_min_returns_200(self):
        # top_n=1 est la borne inférieure valide
        response = self.client.get(URL, {'top_n': 1})
        assert response.status_code == 200

    def test_valid_top_n_max_returns_200(self):
        # top_n=100 est la borne supérieure valide
        response = self.client.get(URL, {'top_n': 100})
        assert response.status_code == 200
