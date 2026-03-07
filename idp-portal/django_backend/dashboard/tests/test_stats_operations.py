"""
Tests pour DashboardStatsOperationsView — Story 60.5.
"""
from __future__ import annotations

from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tests.factories import ActionFactory, ExecutionFactory, UserFactory

URL = '/api/v1/dashboard/stats-operations/'


@pytest.mark.django_db
class TestDashboardStatsOperationsPermissions:

    def setup_method(self):
        self.client = APIClient()

    def test_unauthenticated_returns_401(self):
        response = self.client.get(URL)
        assert response.status_code == 401

    def test_standard_dba_user_returns_200(self):
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
class TestDashboardStatsOperationsStructure:

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
        assert 'avg_execution_time_s' in data
        assert 'top_actions_by_execution' in data
        assert 'top_actions_by_failure' in data
        assert 'by_platform' in data

    def test_all_aggregations_are_lists(self):
        response = self.client.get(URL)
        data = response.data['data']
        assert isinstance(data['top_actions_by_execution'], list)
        assert isinstance(data['top_actions_by_failure'], list)
        assert isinstance(data['by_platform'], list)


@pytest.mark.django_db
class TestDashboardStatsOperationsAvgTime:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_avg_time_null_with_no_executions(self):
        response = self.client.get(URL)
        assert response.data['data']['avg_execution_time_s'] is None

    def test_avg_time_computed_for_completed_executions(self):
        now = timezone.now()
        action = ActionFactory.create()
        ExecutionFactory.create(
            user=self.user, action=action,
            status='COMPLETED',
            started_at=now - timedelta(seconds=60),
            completed_at=now - timedelta(seconds=10),
            created_at=now - timedelta(days=1),
        )
        response = self.client.get(URL)
        avg = response.data['data']['avg_execution_time_s']
        assert avg is not None
        assert avg == 50.0

    def test_avg_time_null_if_no_completed_executions(self):
        now = timezone.now()
        action = ActionFactory.create()
        ExecutionFactory.create(
            user=self.user, action=action, status='FAILED',
            created_at=now - timedelta(days=1),
        )
        response = self.client.get(URL)
        assert response.data['data']['avg_execution_time_s'] is None

    def test_avg_time_excludes_executions_without_timestamps(self):
        now = timezone.now()
        action = ActionFactory.create()
        # COMPLETED sans timestamps → exclu du calcul
        ExecutionFactory.create(
            user=self.user, action=action, status='COMPLETED',
            started_at=None, completed_at=None,
            created_at=now - timedelta(days=1),
        )
        response = self.client.get(URL)
        assert response.data['data']['avg_execution_time_s'] is None


@pytest.mark.django_db
class TestDashboardStatsOperationsTopActions:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_top_actions_by_execution_sorted_desc(self):
        now = timezone.now()
        action_a = ActionFactory.create(name='ActionA')
        action_b = ActionFactory.create(name='ActionB')
        # ActionA : 3 exécutions, ActionB : 1
        for _ in range(3):
            ExecutionFactory.create(action=action_a, created_at=now - timedelta(days=1))
        ExecutionFactory.create(action=action_b, created_at=now - timedelta(days=1))

        response = self.client.get(URL)
        top = response.data['data']['top_actions_by_execution']
        assert len(top) >= 2
        assert top[0]['action_id'] == action_a.id
        assert top[0]['execution_count'] >= 3

    def test_top_actions_by_failure_sorted_desc(self):
        now = timezone.now()
        action_a = ActionFactory.create(name='FailA')
        action_b = ActionFactory.create(name='FailB')
        # ActionA : 2 failures, ActionB : 1
        for _ in range(2):
            ExecutionFactory.create(action=action_a, status='FAILED', created_at=now - timedelta(days=1))
        ExecutionFactory.create(action=action_b, status='FAILED', created_at=now - timedelta(days=1))

        response = self.client.get(URL)
        top = response.data['data']['top_actions_by_failure']
        assert len(top) >= 2
        assert top[0]['action_id'] == action_a.id
        assert top[0]['failure_count'] >= 2

    def test_top_n_limits_results(self):
        now = timezone.now()
        for i in range(6):
            a = ActionFactory.create(name=f'Action{i}')
            ExecutionFactory.create(action=a, created_at=now - timedelta(days=1))

        response = self.client.get(URL, {'top_n': '3'})
        top = response.data['data']['top_actions_by_execution']
        assert len(top) == 3, f"top_n=3 devrait retourner exactement 3 résultats, pas {len(top)}"


@pytest.mark.django_db
class TestDashboardStatsOperationsByPlatform:

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_by_platform_aggregates_correctly(self):
        now = timezone.now()
        action_aap = ActionFactory.create(platform='AAP')
        action_tower = ActionFactory.create(platform='Tower')
        ExecutionFactory.create(action=action_aap, created_at=now - timedelta(days=1))
        ExecutionFactory.create(action=action_aap, created_at=now - timedelta(days=1))
        ExecutionFactory.create(action=action_tower, created_at=now - timedelta(days=1))

        response = self.client.get(URL)
        by_platform = {item['platform']: item['count'] for item in response.data['data']['by_platform']}
        assert by_platform.get('AAP', 0) >= 2
        assert by_platform.get('Tower', 0) >= 1

    def test_empty_platform_shown_as_na(self):
        now = timezone.now()
        # platform field is NOT NULL in the DB; an empty string triggers the "or N/A" fallback
        action = ActionFactory.create(platform='')
        ExecutionFactory.create(action=action, created_at=now - timedelta(days=1))

        response = self.client.get(URL)
        by_platform = {item['platform']: item['count'] for item in response.data['data']['by_platform']}
        assert 'N/A' in by_platform


@pytest.mark.django_db
class TestDashboardStatsOperationsRBAC:

    def setup_method(self):
        self.client = APIClient()

    def test_dba_user_sees_only_own_executions(self):
        now = timezone.now()
        dba = UserFactory.create(profile='DBA')
        other = UserFactory.create(profile='DBA')
        action = ActionFactory.create()
        ExecutionFactory.create(user=dba, action=action, created_at=now - timedelta(days=1))
        ExecutionFactory.create(user=other, action=action, created_at=now - timedelta(days=1))

        self.client.force_authenticate(user=dba)
        response = self.client.get(URL)
        top = response.data['data']['top_actions_by_execution']
        # Le DBA ne voit que ses propres exécutions → exactement 1 exécution visible
        assert len(top) >= 1, "Le DBA devrait voir ses propres exécutions"
        assert top[0]['execution_count'] == 1

    def test_dbops_user_sees_all_executions(self):
        now = timezone.now()
        dbops = UserFactory.create(profile='DBOPS')
        dba = UserFactory.create(profile='DBA')
        action = ActionFactory.create()
        ExecutionFactory.create(user=dba, action=action, created_at=now - timedelta(days=1))
        ExecutionFactory.create(user=dbops, action=action, created_at=now - timedelta(days=1))

        self.client.force_authenticate(user=dbops)
        response = self.client.get(URL)
        top = response.data['data']['top_actions_by_execution']
        assert top[0]['execution_count'] >= 2


@pytest.mark.django_db
class TestDashboardStatsOperationsPeriodParams:

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
        response = self.client.get(URL, {'days': '-1'})
        assert response.status_code == 400

    def test_invalid_from_date_returns_400(self):
        response = self.client.get(URL, {'from_date': 'not-a-date'})
        assert response.status_code == 400

    def test_top_n_zero_returns_400(self):
        response = self.client.get(URL, {'top_n': '0'})
        assert response.status_code == 400

    def test_top_n_above_100_returns_400(self):
        response = self.client.get(URL, {'top_n': '101'})
        assert response.status_code == 400

    def test_valid_top_n_returns_200(self):
        response = self.client.get(URL, {'top_n': '10'})
        assert response.status_code == 200

    def test_valid_days_returns_200(self):
        response = self.client.get(URL, {'days': '30'})
        assert response.status_code == 200

    def test_valid_from_date_to_date_returns_200(self):
        response = self.client.get(URL, {
            'from_date': '2026-01-01',
            'to_date': '2026-01-31',
        })
        assert response.status_code == 200
