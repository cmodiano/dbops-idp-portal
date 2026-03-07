"""
Tests pour DashboardStatsPlanifieesView — Story 60.7.
Répartition des exécutions planifiées vs manuelles avec ventilation par type de récurrence.
Lien inversé : ScheduledExecution.execution_id → Execution.id.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from profiles.models import Profile
from tests.factories import (
    ActionFactory,
    ExecutionFactory,
    RecurringPatternFactory,
    ScheduledExecutionFactory,
    UserFactory,
)


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

URL = '/api/v1/dashboard/stats-planifiees/'


# ---------------------------------------------------------------------------
# 4.1 — Permissions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesPermissions:

    def setup_method(self):
        self.client = APIClient()

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
class TestDashboardStatsPlanifieesStructure:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_response_has_data_key(self):
        response = self.client.get(URL)
        assert response.status_code == 200
        assert 'data' in response.data

    def test_data_contains_all_expected_keys(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert 'scheduled_count' in data
        assert 'manual_count' in data
        assert 'scheduled_rate' in data
        assert 'by_recurrence_type' in data

    def test_all_count_fields_are_integers(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert isinstance(data['scheduled_count'], int)
        assert isinstance(data['manual_count'], int)
        assert isinstance(data['by_recurrence_type'], list)

    def test_scheduled_rate_is_none_when_no_executions(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_rate'] is None


# ---------------------------------------------------------------------------
# 4.3 — scheduled_count / manual_count
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesScheduledCount:

    def setup_method(self):
        _ensure_profiles()
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_scheduled_count_detects_via_scheduled_execution_id(self):
        """Une exécution liée à un ScheduledExecution via execution_id est comptée planifiée."""
        action = ActionFactory.create()
        exec_scheduled = ExecutionFactory.create(action=action)
        ScheduledExecutionFactory.create(execution_id=exec_scheduled.id)

        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_count'] >= 1

    def test_manual_count_excludes_scheduled(self):
        """Une exécution sans ScheduledExecution est comptée manuelle."""
        action = ActionFactory.create()
        ExecutionFactory.create(action=action)

        response = self.client.get(URL)
        data = response.data['data']
        assert data['manual_count'] >= 1

    def test_mixed_executions_correct_counts(self):
        """2 planifiées + 3 manuelles → counts corrects."""
        action = ActionFactory.create()
        for _ in range(2):
            exec_s = ExecutionFactory.create(action=action)
            ScheduledExecutionFactory.create(execution_id=exec_s.id)
        for _ in range(3):
            ExecutionFactory.create(action=action)

        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_count'] == 2
        assert data['manual_count'] == 3

    def test_scheduled_count_zero_when_no_scheduled_executions(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_count'] == 0
        assert data['manual_count'] == 0


# ---------------------------------------------------------------------------
# 4.4 — scheduled_rate
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesRate:

    def setup_method(self):
        _ensure_profiles()
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_scheduled_rate_computed_correctly(self):
        """2 planifiées + 2 manuelles → taux = 50.0%."""
        action = ActionFactory.create()
        for _ in range(2):
            exec_s = ExecutionFactory.create(action=action)
            ScheduledExecutionFactory.create(execution_id=exec_s.id)
        for _ in range(2):
            ExecutionFactory.create(action=action)

        response = self.client.get(URL)
        assert response.data['data']['scheduled_rate'] == 50.0

    def test_scheduled_rate_null_when_total_zero(self):
        response = self.client.get(URL)
        assert response.data['data']['scheduled_rate'] is None

    def test_scheduled_rate_100_when_all_scheduled(self):
        """Toutes les exécutions sont planifiées → taux = 100.0%."""
        action = ActionFactory.create()
        for _ in range(3):
            exec_s = ExecutionFactory.create(action=action)
            ScheduledExecutionFactory.create(execution_id=exec_s.id)

        response = self.client.get(URL)
        assert response.data['data']['scheduled_rate'] == 100.0

    def test_scheduled_rate_0_when_all_manual(self):
        """Aucune exécution planifiée → taux = 0.0%."""
        action = ActionFactory.create()
        for _ in range(3):
            ExecutionFactory.create(action=action)

        response = self.client.get(URL)
        assert response.data['data']['scheduled_rate'] == 0.0


# ---------------------------------------------------------------------------
# 4.5 — by_recurrence_type
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesRecurrenceType:

    def setup_method(self):
        _ensure_profiles()
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def _get_pattern_count(self, response, pattern_type):
        for item in response.data['data']['by_recurrence_type']:
            if item['pattern_type'] == pattern_type:
                return item['count']
        return 0

    def test_no_recurring_pattern_counted_as_one_time(self):
        """ScheduledExecution sans RecurringPattern → one_time."""
        action = ActionFactory.create()
        exec_s = ExecutionFactory.create(action=action)
        ScheduledExecutionFactory.create(execution_id=exec_s.id)

        response = self.client.get(URL)
        assert self._get_pattern_count(response, 'one_time') == 1

    def test_daily_recurring_pattern_counted(self):
        action = ActionFactory.create()
        exec_s = ExecutionFactory.create(action=action)
        se = ScheduledExecutionFactory.create(execution_id=exec_s.id)
        RecurringPatternFactory.create(scheduled_execution=se, pattern_type='daily')

        response = self.client.get(URL)
        assert self._get_pattern_count(response, 'daily') == 1

    def test_weekly_recurring_pattern_counted(self):
        action = ActionFactory.create()
        exec_s = ExecutionFactory.create(action=action)
        se = ScheduledExecutionFactory.create(execution_id=exec_s.id)
        RecurringPatternFactory.create(scheduled_execution=se, pattern_type='weekly')

        response = self.client.get(URL)
        assert self._get_pattern_count(response, 'weekly') == 1

    def test_cron_recurring_pattern_counted(self):
        action = ActionFactory.create()
        exec_s = ExecutionFactory.create(action=action)
        se = ScheduledExecutionFactory.create(execution_id=exec_s.id)
        RecurringPatternFactory.create(scheduled_execution=se, pattern_type='cron')

        response = self.client.get(URL)
        assert self._get_pattern_count(response, 'cron') == 1

    def test_mixed_pattern_types_correct_breakdown(self):
        """1 one_time + 2 daily + 1 weekly → ventilation correcte."""
        action = ActionFactory.create()

        # one_time : sans RecurringPattern
        exec_ot = ExecutionFactory.create(action=action)
        ScheduledExecutionFactory.create(execution_id=exec_ot.id)

        # daily x2
        for _ in range(2):
            exec_d = ExecutionFactory.create(action=action)
            se_d = ScheduledExecutionFactory.create(execution_id=exec_d.id)
            RecurringPatternFactory.create(scheduled_execution=se_d, pattern_type='daily')

        # weekly x1
        exec_w = ExecutionFactory.create(action=action)
        se_w = ScheduledExecutionFactory.create(execution_id=exec_w.id)
        RecurringPatternFactory.create(scheduled_execution=se_w, pattern_type='weekly')

        response = self.client.get(URL)
        assert self._get_pattern_count(response, 'one_time') == 1
        assert self._get_pattern_count(response, 'daily') == 2
        assert self._get_pattern_count(response, 'weekly') == 1


# ---------------------------------------------------------------------------
# 4.6 — RBAC
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesRBAC:

    def setup_method(self):
        _ensure_profiles()
        self.client = APIClient()

    def test_dba_sees_only_own_executions(self):
        """DBA voit uniquement ses propres exécutions (scope=mine)."""
        dba = UserFactory.create(profile='DBA')
        other = UserFactory.create(profile='DBA')
        action = ActionFactory.create()

        # Exécution planifiée appartenant au DBA
        exec_dba = ExecutionFactory.create(user=dba, action=action)
        ScheduledExecutionFactory.create(execution_id=exec_dba.id)

        # Exécution planifiée appartenant à l'autre (ne doit pas être visible)
        exec_other = ExecutionFactory.create(user=other, action=action)
        ScheduledExecutionFactory.create(execution_id=exec_other.id)

        self.client.force_authenticate(user=dba)
        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_count'] == 1
        assert data['manual_count'] == 0

    def test_dbops_sees_all_executions(self):
        """DBOPS voit toutes les exécutions (scope=all)."""
        dbops = UserFactory.create(profile='DBOPS')
        dba = UserFactory.create(profile='DBA')
        action = ActionFactory.create()

        for user in [dbops, dba]:
            exec_s = ExecutionFactory.create(user=user, action=action)
            ScheduledExecutionFactory.create(execution_id=exec_s.id)

        self.client.force_authenticate(user=dbops)
        response = self.client.get(URL)
        data = response.data['data']
        assert data['scheduled_count'] >= 2


# ---------------------------------------------------------------------------
# 4.7 — Paramètres de période invalides
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardStatsPlanifieesPeriodParams:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_invalid_days_returns_400(self):
        response = self.client.get(URL, {'days': 'invalid'})
        assert response.status_code == 400

    def test_negative_days_returns_400(self):
        response = self.client.get(URL, {'days': '-5'})
        assert response.status_code == 400

    def test_zero_days_returns_400(self):
        response = self.client.get(URL, {'days': '0'})
        assert response.status_code == 400

    def test_invalid_from_date_returns_400(self):
        response = self.client.get(URL, {'from_date': 'not-a-date'})
        assert response.status_code == 400

    def test_valid_days_returns_200(self):
        response = self.client.get(URL, {'days': '30'})
        assert response.status_code == 200

    def test_valid_from_date_to_date_returns_200(self):
        response = self.client.get(URL, {
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
        })
        assert response.status_code == 200
