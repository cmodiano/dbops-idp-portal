"""
Tests pour DashboardStatsApprobationsView — Story 60.6.
Source duale ADR-007: Execution.approved_at (legacy) + ExecutionStep gate (nouveau).
"""
from __future__ import annotations

from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tests.factories import ActionFactory, ExecutionFactory, ExecutionStepFactory, UserFactory

URL = '/api/v1/dashboard/stats-approbations/'


@pytest.mark.django_db
class TestDashboardStatsApprobationsPermissions:

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


@pytest.mark.django_db
class TestDashboardStatsApprobationsStructure:

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
        assert 'approved_count' in data
        assert 'rejected_count' in data
        assert 'approval_rate' in data
        assert 'avg_approval_delay_s' in data

    def test_all_fields_have_correct_types(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert isinstance(data['approved_count'], int)
        assert isinstance(data['rejected_count'], int)
        # approval_rate et avg_approval_delay_s sont None quand aucune donnée
        assert data['approval_rate'] is None
        assert data['avg_approval_delay_s'] is None

    def test_non_null_fields_have_float_types(self):
        """Avec des données, approval_rate et avg_approval_delay_s sont des floats."""
        now = timezone.now()
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action, user=self.user, status='COMPLETED',
            approved_at=now + timedelta(seconds=3600),
        )
        response = self.client.get(URL)
        data = response.data['data']
        assert isinstance(data['approval_rate'], float)
        assert isinstance(data['avg_approval_delay_s'], float)


@pytest.mark.django_db
class TestDashboardStatsApprobationsApprovedCount:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_approved_count_legacy_path(self):
        """Execution.approved_at non-null + status COMPLETED → comptée comme approuvée."""
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action,
            status='COMPLETED',
            approved_at=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] >= 1

    def test_approved_count_new_gate_path(self):
        """Gate step COMPLETED avec approved_at non-null → execution comptée comme approuvée."""
        now = timezone.now()
        action = ActionFactory.create()
        execution = ExecutionFactory.create(
            action=action,
            status='COMPLETED',
            approved_at=None,  # pas de legacy
        )
        ExecutionStepFactory.create(
            execution=execution,
            step_type='gate',
            status='COMPLETED',
            approved_at=now - timedelta(hours=2),
        )
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] >= 1

    def test_approved_count_zero_with_no_approved(self):
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] == 0

    def test_completed_without_approval_not_counted(self):
        """COMPLETED sans approved_at ni gate step → ne compte PAS dans approved_count."""
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action,
            status='COMPLETED',
            approved_at=None,
        )
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] == 0


@pytest.mark.django_db
class TestDashboardStatsApprobationsRejectedCount:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_rejected_count_via_status_rejected(self):
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action,
            status='REJECTED',
        )
        response = self.client.get(URL)
        assert response.data['data']['rejected_count'] >= 1

    def test_rejected_count_zero_with_no_rejected(self):
        response = self.client.get(URL)
        assert response.data['data']['rejected_count'] == 0


@pytest.mark.django_db
class TestDashboardStatsApprobationsRate:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_approval_rate_null_when_no_decisions(self):
        response = self.client.get(URL)
        assert response.data['data']['approval_rate'] is None

    def test_approval_rate_100_when_all_approved(self):
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action, status='COMPLETED',
            approved_at=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(URL)
        assert response.data['data']['approval_rate'] == 100.0

    def test_approval_rate_0_when_all_rejected(self):
        action = ActionFactory.create()
        ExecutionFactory.create(
            action=action, status='REJECTED',
        )
        response = self.client.get(URL)
        assert response.data['data']['approval_rate'] == 0.0

    def test_approval_rate_computed_correctly(self):
        """3 approuvées + 1 rejetée → taux = 75.0%"""
        now = timezone.now()
        action = ActionFactory.create()
        for _ in range(3):
            ExecutionFactory.create(
                action=action, status='COMPLETED',
                approved_at=now - timedelta(hours=1),
            )
        ExecutionFactory.create(
            action=action, status='REJECTED',
        )
        response = self.client.get(URL)
        assert response.data['data']['approval_rate'] == 75.0


@pytest.mark.django_db
class TestDashboardStatsApprobationsDelay:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_avg_delay_null_when_no_approved(self):
        response = self.client.get(URL)
        assert response.data['data']['avg_approval_delay_s'] is None

    def test_avg_delay_legacy_path(self):
        """Délai = approved_at - created_at via Execution.approved_at.
        approved_at dans le futur (> created_at auto_now_add) → delta positif.
        """
        now = timezone.now()
        action = ActionFactory.create()
        # created_at est auto_now_add (≈ now) donc approved_at doit être > now
        approved = now + timedelta(seconds=3600)  # 1h après now
        ExecutionFactory.create(
            action=action, status='COMPLETED',
            approved_at=approved,
        )
        response = self.client.get(URL)
        delay = response.data['data']['avg_approval_delay_s']
        assert delay is not None
        assert delay >= 3600.0  # au moins 3600s (delta exact dépend de auto_now_add)

    def test_avg_delay_gate_step_path(self):
        """Délai = step.approved_at - execution.created_at via gate step ADR-007.
        step.approved_at dans le futur (> created_at auto_now_add) → delta positif.
        """
        now = timezone.now()
        action = ActionFactory.create()
        # created_at est auto_now_add (≈ now) donc step_approved doit être > now
        step_approved = now + timedelta(seconds=1800)  # 30min après now
        execution = ExecutionFactory.create(
            action=action, status='COMPLETED',
            approved_at=None,  # pas de legacy
        )
        ExecutionStepFactory.create(
            execution=execution,
            step_type='gate',
            status='COMPLETED',
            approved_at=step_approved,
        )
        response = self.client.get(URL)
        delay = response.data['data']['avg_approval_delay_s']
        assert delay is not None
        assert delay >= 1799.0  # au moins ~1800s (tolérance timing/float)

    def test_avg_delay_excludes_negative_deltas(self):
        """Délai négatif (approved_at < created_at) doit être exclu.
        created_at est auto_now_add≈now ; approved_at très dans le passé → delta toujours négatif.
        """
        now = timezone.now()
        action = ActionFactory.create()
        # approved_at largement dans le passé → delta négatif vs created_at≈now
        ExecutionFactory.create(
            action=action, status='COMPLETED',
            approved_at=now - timedelta(days=2),
        )
        response = self.client.get(URL)
        assert response.data['data']['avg_approval_delay_s'] is None


@pytest.mark.django_db
class TestDashboardStatsApprobationsRBAC:

    def setup_method(self):
        self.client = APIClient()

    def test_dba_sees_only_own_executions(self):
        now = timezone.now()
        dba = UserFactory.create(profile='DBA')
        other = UserFactory.create(profile='DBA')
        action = ActionFactory.create()
        # Approbation appartenant au DBA
        ExecutionFactory.create(
            user=dba, action=action, status='COMPLETED',
            approved_at=now - timedelta(hours=1),
        )
        # Approbation appartenant à l'autre utilisateur (ne doit pas être visible)
        ExecutionFactory.create(
            user=other, action=action, status='COMPLETED',
            approved_at=now - timedelta(hours=1),
        )
        self.client.force_authenticate(user=dba)
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] == 1

    def test_dbops_sees_all_executions(self):
        now = timezone.now()
        dbops = UserFactory.create(profile='DBOPS')
        dba = UserFactory.create(profile='DBA')
        action = ActionFactory.create()
        for user in [dbops, dba]:
            ExecutionFactory.create(
                user=user, action=action, status='COMPLETED',
                approved_at=now - timedelta(hours=1),
            )
        self.client.force_authenticate(user=dbops)
        response = self.client.get(URL)
        assert response.data['data']['approved_count'] >= 2


@pytest.mark.django_db
class TestDashboardStatsApprobationsPeriodParams:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_invalid_days_returns_400(self):
        response = self.client.get(URL, {'days': 'invalid'})
        assert response.status_code == 400

    def test_zero_days_returns_400(self):
        response = self.client.get(URL, {'days': '0'})
        assert response.status_code == 400

    def test_negative_days_returns_400(self):
        response = self.client.get(URL, {'days': '-5'})
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
