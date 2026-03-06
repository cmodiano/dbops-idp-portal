"""
Tests pour admin_analytics/views.py — Story 55.2 (couverture ≥ 90 %).

Couvre :
- AdminAnalyticsView.get : permissions, paramètre days, structure réponse, données réelles
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from catalog.models import ActionStatus
from tests.factories import UserFactory, ActionFactory, ExecutionFactory, IntegrationFactory


@pytest.mark.django_db
class TestAdminAnalyticsViewPermissions:
    """Tests de permissions pour AdminAnalyticsView."""

    URL = '/api/v1/admin/analytics/'

    def setup_method(self):
        self.client = APIClient()
        self.integration = IntegrationFactory.create()
        # Profile records are created by conftest._ensure_admin_profiles (autouse fixture)

    def test_dbops_user_gets_200(self):
        """Utilisateur DBOPS → 200."""
        user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.URL)

        assert response.status_code == 200

    def test_dba_user_gets_403(self):
        """Utilisateur DBA (pas DBOPS) → 403."""
        user = UserFactory.create(profile='DBA')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.URL)

        assert response.status_code == 403

    def test_business_user_gets_403(self):
        """Utilisateur BUSINESS_USER → 403."""
        user = UserFactory.create(profile='BUSINESS_USER')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.URL)

        assert response.status_code == 403

    def test_unauthenticated_gets_401(self):
        """Non authentifié → 401."""
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestAdminAnalyticsViewDaysParam:
    """Tests du paramètre days pour AdminAnalyticsView."""

    URL = '/api/v1/admin/analytics/'

    def setup_method(self):
        self.client = APIClient()
        # Profile records are created by conftest._ensure_admin_profiles (autouse fixture)
        self.user = UserFactory.create(profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def test_default_days_90(self):
        """Sans paramètre → utilise days=90 par défaut → 200."""
        response = self.client.get(self.URL)
        assert response.status_code == 200

    def test_valid_days_value(self):
        """days=30 valide → 200."""
        response = self.client.get(self.URL, {'days': '30'})
        assert response.status_code == 200

    def test_invalid_days_non_int_returns_400(self):
        """days non entier → BadRequestError → 400."""
        response = self.client.get(self.URL, {'days': 'abc'})
        assert response.status_code == 400

    def test_days_zero_returns_400(self):
        """days=0 → BadRequestError → 400."""
        response = self.client.get(self.URL, {'days': '0'})
        assert response.status_code == 400

    def test_days_negative_returns_400(self):
        """days négatif → BadRequestError → 400."""
        response = self.client.get(self.URL, {'days': '-1'})
        assert response.status_code == 400

    def test_days_3650_ok(self):
        """days=3650 (limite haute) → 200."""
        response = self.client.get(self.URL, {'days': '3650'})
        assert response.status_code == 200

    def test_days_3651_returns_400(self):
        """days=3651 (au-delà de la limite) → BadRequestError → 400."""
        response = self.client.get(self.URL, {'days': '3651'})
        assert response.status_code == 400


@pytest.mark.django_db
class TestAdminAnalyticsViewResponseStructure:
    """Tests de structure de la réponse pour AdminAnalyticsView."""

    URL = '/api/v1/admin/analytics/'

    def setup_method(self):
        self.client = APIClient()
        # Profile records are created by conftest._ensure_admin_profiles (autouse fixture)
        self.user = UserFactory.create(profile='DBOPS')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_response_structure(self):
        """Réponse → structure {data: {total_published_actions, executions_by_engine, executions_by_profile, adoption_trend}}."""
        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'data' in response.data
        data = response.data['data']
        assert 'total_published_actions' in data
        assert 'executions_by_engine' in data
        assert 'executions_by_profile' in data
        assert 'adoption_trend' in data

    def test_total_published_actions_counted(self):
        """total_published_actions compte les actions publiées."""
        ActionFactory.create(
            integration=self.integration, status=ActionStatus.PUBLISHED
        )
        ActionFactory.create(
            integration=self.integration, status=ActionStatus.DRAFT
        )

        response = self.client.get(self.URL)

        assert response.status_code == 200
        # Au moins 1 action published
        assert response.data['data']['total_published_actions'] >= 1

    def test_executions_by_engine_grouping(self):
        """executions_by_engine contient le groupement par engine."""
        action = ActionFactory.create(
            integration=self.integration, engine='Oracle', status=ActionStatus.PUBLISHED
        )
        ExecutionFactory.create(action=action, user=self.user)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        engines = [item['engine'] for item in response.data['data']['executions_by_engine']]
        assert 'Oracle' in engines

    def test_executions_by_profile_grouping(self):
        """executions_by_profile contient le groupement par profile."""
        action = ActionFactory.create(integration=self.integration, status=ActionStatus.PUBLISHED)
        ExecutionFactory.create(action=action, user=self.user)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        profiles = [item['profile'] for item in response.data['data']['executions_by_profile']]
        assert 'DBOPS' in profiles

    def test_adoption_trend_weekly(self):
        """adoption_trend : entrées avec week_start et engine."""
        action = ActionFactory.create(
            integration=self.integration, engine='Oracle', status=ActionStatus.PUBLISHED
        )
        ExecutionFactory.create(action=action, user=self.user)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        trend = response.data['data']['adoption_trend']
        assert isinstance(trend, list)
        # L'exécution créée maintenant doit tomber dans la période par défaut (90 jours)
        assert len(trend) >= 1, "L'adoption_trend doit contenir au moins une entrée (exécution créée dans la période)"
        item = trend[0]
        assert 'week_start' in item
        assert 'engine' in item
        assert 'count' in item
        # week_start est non None (filtré côté view) et au format ISO YYYY-MM-DD
        assert item['week_start'] is not None
        assert isinstance(item['week_start'], str)
        # Valider le format ISO YYYY-MM-DD
        import re
        assert re.match(r'^\d{4}-\d{2}-\d{2}$', item['week_start']), (
            f"week_start doit être au format YYYY-MM-DD, obtenu: {item['week_start']}"
        )
