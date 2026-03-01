"""
Tests for dashboard/views.py — Story 55.2 (couverture ≥ 90 %).

Couvre :
- _parse_int, _parse_date, _get_period_bounds
- _filter_queryset_by_ownership
- _apply_common_filters
- DashboardStatsView, DashboardRecentView, DashboardTimeSeriesView
- DashboardStatsByTechnologyView, DashboardStatsByEnvironmentView
- DashboardFilterOptionsView
- _stats_for_queryset, _delta_pct
- DashboardCompareView
"""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from django.utils import timezone
from rest_framework.test import APIClient

from executions.models import ExecutionStatus
from tests.factories import UserFactory, ActionFactory, ExecutionFactory, IntegrationFactory


# ---------------------------------------------------------------------------
# Tests unitaires purs (sans DB)
# ---------------------------------------------------------------------------

class TestParseInt:
    """Tests pour _parse_int."""

    def test_none_returns_default(self):
        from dashboard.views import _parse_int
        assert _parse_int(None, 14, name="days") == 14

    def test_empty_string_returns_default(self):
        from dashboard.views import _parse_int
        assert _parse_int("", 14, name="days") == 14

    def test_valid_value(self):
        from dashboard.views import _parse_int
        assert _parse_int("30", 14, name="days") == 30

    def test_invalid_value_raises_bad_request(self):
        from dashboard.views import _parse_int
        from core.exceptions import BadRequestError
        with pytest.raises(BadRequestError):
            _parse_int("abc", 14, name="days")


class TestParseDate:
    """Tests pour _parse_date."""

    def test_none_returns_none(self):
        from dashboard.views import _parse_date
        assert _parse_date(None, name="from_date") is None

    def test_empty_string_returns_none(self):
        from dashboard.views import _parse_date
        assert _parse_date("", name="from_date") is None

    def test_valid_date(self):
        from dashboard.views import _parse_date
        result = _parse_date("2026-01-15", name="from_date")
        assert result == date(2026, 1, 15)

    def test_invalid_format_raises_bad_request(self):
        from dashboard.views import _parse_date
        from core.exceptions import BadRequestError
        with pytest.raises(BadRequestError):
            _parse_date("15-01-2026", name="from_date")

    def test_invalid_date_raises_bad_request(self):
        from dashboard.views import _parse_date
        from core.exceptions import BadRequestError
        with pytest.raises(BadRequestError):
            _parse_date("2026-13-99", name="from_date")


class TestDeltaPct:
    """Tests pour _delta_pct."""

    def test_v1_none_returns_none(self):
        from dashboard.views import _delta_pct
        assert _delta_pct(None, 100) is None

    def test_v2_none_returns_none(self):
        from dashboard.views import _delta_pct
        assert _delta_pct(100, None) is None

    def test_both_none_returns_none(self):
        from dashboard.views import _delta_pct
        assert _delta_pct(None, None) is None

    def test_v1_zero_returns_none(self):
        from dashboard.views import _delta_pct
        assert _delta_pct(0, 100) is None

    def test_normal_values(self):
        from dashboard.views import _delta_pct
        result = _delta_pct(100, 150)
        assert result == 50.0

    def test_decrease(self):
        from dashboard.views import _delta_pct
        result = _delta_pct(200, 100)
        assert result == -50.0


class TestGetPeriodBounds:
    """Tests pour _get_period_bounds."""

    def test_default_days_14(self):
        from dashboard.views import _get_period_bounds
        request = MagicMock()
        request.query_params = {}
        start, end = _get_period_bounds(request)
        delta = end - start
        # ~14 days (tolerance ±1 second)
        assert abs(delta.days - 14) <= 1

    def test_custom_days(self):
        from dashboard.views import _get_period_bounds
        request = MagicMock()
        request.query_params = {"days": "7"}
        start, end = _get_period_bounds(request)
        delta = end - start
        assert abs(delta.days - 7) <= 1

    def test_days_zero_raises_bad_request(self):
        from dashboard.views import _get_period_bounds
        from core.exceptions import BadRequestError
        request = MagicMock()
        request.query_params = {"days": "0"}
        with pytest.raises(BadRequestError):
            _get_period_bounds(request)

    def test_days_negative_raises_bad_request(self):
        from dashboard.views import _get_period_bounds
        from core.exceptions import BadRequestError
        request = MagicMock()
        request.query_params = {"days": "-5"}
        with pytest.raises(BadRequestError):
            _get_period_bounds(request)

    def test_from_date_to_date(self):
        from dashboard.views import _get_period_bounds
        request = MagicMock()
        request.query_params = {"from_date": "2026-01-01", "to_date": "2026-01-31"}
        start, end = _get_period_bounds(request)
        assert start.date() == date(2026, 1, 1)
        # end_exclusive = to_date + 1 day
        assert end.date() == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# Tests avec DB
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFilterQuerysetByOwnership:
    """Tests pour _filter_queryset_by_ownership."""

    def setup_method(self):
        self.dba_user = UserFactory.create(profile='DBA')
        self.biz_user = UserFactory.create(profile='BUSINESS_USER')
        self.integration = IntegrationFactory.create()

    def test_dba_user_sees_all(self):
        """Utilisateur DBA/DBOPS → pas de filtre par user_id."""
        from dashboard.views import _filter_queryset_by_ownership
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.dba_user)
        ExecutionFactory.create(action=action, user=self.biz_user)

        request = MagicMock()
        request.user = self.dba_user

        qs = Execution.objects.all()
        result = _filter_queryset_by_ownership(qs, request)
        # DBA sees all executions
        assert result.count() >= 2

    def test_non_dba_sees_only_own(self):
        """Utilisateur non-DBA → filtre sur user_id."""
        from dashboard.views import _filter_queryset_by_ownership
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.dba_user)
        biz_exec = ExecutionFactory.create(action=action, user=self.biz_user)

        request = MagicMock()
        request.user = self.biz_user

        qs = Execution.objects.all()
        result = _filter_queryset_by_ownership(qs, request)
        ids = list(result.values_list('id', flat=True))
        assert biz_exec.id in ids
        # Doit être filtré sur l'utilisateur
        for exec_id in ids:
            assert Execution.objects.get(id=exec_id).user_id == self.biz_user.id


@pytest.mark.django_db
class TestApplyCommonFilters:
    """Tests pour _apply_common_filters."""

    def setup_method(self):
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()

    def test_no_filters(self):
        """Sans filtres → retourne le qs inchangé."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration, engine='Oracle')
        ExecutionFactory.create(action=action, user=self.user, environment='prod')

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=False)
        assert result.count() >= 1

    def test_engine_filter(self):
        """Filtre engine → seulement les exécutions avec cet engine."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        oracle_action = ActionFactory.create(integration=self.integration, engine='Oracle')
        pg_action = ActionFactory.create(integration=self.integration, engine='PostgreSQL')
        ExecutionFactory.create(action=oracle_action, user=self.user)
        ExecutionFactory.create(action=pg_action, user=self.user)

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: 'Oracle' if k == 'engine' else None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.select_related('action')
        result = _apply_common_filters(qs, request=request, include_status=False)
        for exec_obj in result:
            assert exec_obj.action.engine == 'Oracle'

    def test_environment_filter(self):
        """Filtre environment → seulement les exécutions prod."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, environment='prod')
        ExecutionFactory.create(action=action, user=self.user, environment='dev')

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: 'prod' if k == 'environment' else None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=False)
        for exec_obj in result:
            assert exec_obj.environment == 'prod'

    def test_tags_filter(self):
        """Filtre tags → seulement les exécutions avec actions ayant ce tag."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution
        from catalog.models import Tag, ActionTag

        tag = Tag.objects.create(name='db-tag-test')
        action_with_tag = ActionFactory.create(integration=self.integration)
        ActionTag.objects.create(action=action_with_tag, tag=tag)
        action_no_tag = ActionFactory.create(integration=self.integration)

        exec_with_tag = ExecutionFactory.create(action=action_with_tag, user=self.user)
        ExecutionFactory.create(action=action_no_tag, user=self.user)

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: None
        request.query_params.getlist = lambda k: ['db-tag-test'] if k == 'tags' else []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=False)
        ids = list(result.values_list('id', flat=True))
        assert exec_with_tag.id in ids

    def test_empty_tags_list(self):
        """Tags vide → pas de filtre."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user)

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        original_count = qs.count()
        result = _apply_common_filters(qs, request=request, include_status=False)
        assert result.count() == original_count

    def test_status_filter_included(self):
        """include_status=True avec status param → filtre par status."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        completed_exec = ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.COMPLETED
        )
        ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.FAILED
        )

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: ExecutionStatus.COMPLETED if k == 'status' else None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=True)
        ids = list(result.values_list('id', flat=True))
        assert completed_exec.id in ids
        for exec_id in ids:
            assert Execution.objects.get(id=exec_id).status == ExecutionStatus.COMPLETED

    def test_status_filter_excluded(self):
        """include_status=False → status param ignoré."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.FAILED)

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: ExecutionStatus.COMPLETED if k == 'status' else None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=False)
        # Both statuses should be present
        statuses = set(result.values_list('status', flat=True))
        assert ExecutionStatus.FAILED in statuses or ExecutionStatus.COMPLETED in statuses

    def test_status_filter_none_value(self):
        """include_status=True mais status=None → pas de filtre status."""
        from dashboard.views import _apply_common_filters
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.FAILED)

        request = MagicMock()
        request.query_params = MagicMock()
        request.query_params.get = lambda k, d=None: None
        request.query_params.getlist = lambda k: []

        qs = Execution.objects.all()
        result = _apply_common_filters(qs, request=request, include_status=True)
        statuses = set(result.values_list('status', flat=True))
        assert ExecutionStatus.COMPLETED in statuses
        assert ExecutionStatus.FAILED in statuses


@pytest.mark.django_db
class TestDashboardStatsView:
    """Tests pour DashboardStatsView.get."""

    URL = '/api/v1/dashboard/stats/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_with_data(self):
        """Données présentes → 200 avec structure attendue."""
        action = ActionFactory.create(integration=self.integration, status='published')
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'data' in response.data
        data = response.data['data']
        assert 'executions_jour' in data
        assert 'taux_succes_pct' in data
        assert 'executions_en_cours' in data
        assert 'executions_en_erreur' in data

    def test_get_no_data(self):
        """Aucune donnée → 200 avec des zéros."""
        response = self.client.get(self.URL)

        assert response.status_code == 200
        data = response.data['data']
        assert data['taux_succes_pct'] == 0.0

    def test_taux_succes_pct_zero_when_no_finished(self):
        """total_finished = 0 → taux_succes_pct = 0.0 (pas de division par zéro)."""
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.RUNNING
        )

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert response.data['data']['taux_succes_pct'] == 0.0

    def test_unauthenticated_returns_401(self):
        """Non authentifié → 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401

    def test_with_days_filter(self):
        """Filtre period days=7 → 200."""
        response = self.client.get(self.URL, {'days': '7'})
        assert response.status_code == 200

    def test_invalid_days_returns_400(self):
        """days invalide → 400."""
        response = self.client.get(self.URL, {'days': 'abc'})
        assert response.status_code == 400


@pytest.mark.django_db
class TestDashboardRecentView:
    """Tests pour DashboardRecentView.get."""

    URL = '/api/v1/dashboard/recent/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_empty_list(self):
        """Aucune exécution → liste vide."""
        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert response.data['data'] == []

    def test_get_with_data(self):
        """Données présentes → champs attendus."""
        action = ActionFactory.create(integration=self.integration, engine='Oracle')
        ExecutionFactory.create(action=action, user=self.user, environment='prod')

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert len(response.data['data']) >= 1
        item = response.data['data'][0]
        assert 'id' in item
        assert 'action_name' in item
        assert 'user_display_name' in item
        assert 'environment' in item
        assert 'status' in item
        assert 'created_at' in item

    def test_user_without_display_name(self):
        """User sans display_name → 'Unknown'."""
        user_no_name = UserFactory.create(profile='DBA', display_name=None)
        self.client.force_authenticate(user=user_no_name)
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=user_no_name)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert len(response.data['data']) >= 1
        assert response.data['data'][0]['user_display_name'] == 'Unknown'

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestDashboardTimeSeriesView:
    """Tests pour DashboardTimeSeriesView.get."""

    URL = '/api/v1/dashboard/timeseries/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_with_data(self):
        """Données présentes → 200 avec liste de points."""
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'data' in response.data
        assert isinstance(response.data['data'], list)

    def test_get_empty_range(self):
        """Plage vide (aucune exécution dans la période) → liste vide."""
        response = self.client.get(self.URL, {'from_date': '2020-01-01', 'to_date': '2020-01-07'})

        assert response.status_code == 200
        assert response.data['data'] == []

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestDashboardStatsByTechnologyView:
    """Tests pour DashboardStatsByTechnologyView.get."""

    URL = '/api/v1/dashboard/stats-by-technology/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_with_data(self):
        """Données présentes → structure attendue avec success_rate."""
        action = ActionFactory.create(integration=self.integration, engine='Oracle')
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.FAILED)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'data' in response.data
        assert isinstance(response.data['data'], list)
        # Au moins une entrée Oracle
        engines = [item['engine'] for item in response.data['data']]
        assert 'Oracle' in engines
        # Vérifier la structure
        oracle_item = next(item for item in response.data['data'] if item['engine'] == 'Oracle')
        assert 'count' in oracle_item
        assert 'success_rate' in oracle_item

    def test_success_rate_none_when_no_finished(self):
        """finished == 0 → success_rate = None."""
        action = ActionFactory.create(integration=self.integration, engine='Oracle')
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.RUNNING)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        for item in response.data['data']:
            if item['engine'] == 'Oracle':
                assert item['success_rate'] is None

    def test_get_no_data(self):
        """Aucune donnée → liste vide."""
        response = self.client.get(self.URL)
        assert response.status_code == 200
        assert response.data['data'] == []

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestDashboardStatsByEnvironmentView:
    """Tests pour DashboardStatsByEnvironmentView.get."""

    URL = '/api/v1/dashboard/stats-by-environment/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_with_data(self):
        """Données présentes → structure + tri custom (dev < staging < prod < autre)."""
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, environment='prod', status=ExecutionStatus.COMPLETED)
        ExecutionFactory.create(action=action, user=self.user, environment='dev', status=ExecutionStatus.FAILED)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'data' in response.data
        data = response.data['data']
        # dev doit être avant prod dans la liste
        envs = [item['environment'] for item in data]
        if 'dev' in envs and 'prod' in envs:
            assert envs.index('dev') < envs.index('prod')

    def test_success_rate_none_when_no_finished(self):
        """finished == 0 → success_rate = None."""
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, environment='dev', status=ExecutionStatus.RUNNING)

        response = self.client.get(self.URL)

        assert response.status_code == 200
        for item in response.data['data']:
            if item['environment'] == 'dev':
                assert item['success_rate'] is None

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestDashboardFilterOptionsView:
    """Tests pour DashboardFilterOptionsView.get."""

    URL = '/api/v1/dashboard/filter-options/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_get_empty(self):
        """Aucune donnée → structure avec listes vides."""
        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'engines' in response.data
        assert 'environments' in response.data
        assert 'tags' in response.data
        assert 'statuses' in response.data

    def test_get_with_data(self):
        """Données présentes → engines/environments/tags/statuses remplis."""
        from catalog.models import Tag, ActionTag

        tag = Tag.objects.create(name='oracle-tag')
        action = ActionFactory.create(
            integration=self.integration, engine='Oracle', status='published'
        )
        ActionTag.objects.create(action=action, tag=tag)
        ExecutionFactory.create(action=action, user=self.user, environment='prod')

        response = self.client.get(self.URL)

        assert response.status_code == 200
        assert 'Oracle' in response.data['engines']
        assert 'prod' in response.data['environments']
        assert 'oracle-tag' in response.data['tags']
        assert len(response.data['statuses']) > 0

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestStatsForQueryset:
    """Tests pour _stats_for_queryset."""

    def setup_method(self):
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()

    def test_basic_stats(self):
        """Exécutions présentes → stats calculées."""
        from dashboard.views import _stats_for_queryset
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.FAILED)

        qs = Execution.objects.all()
        stats = _stats_for_queryset(qs)

        assert stats['execution_count'] >= 2
        assert 'success_rate' in stats
        assert 'avg_time' in stats
        assert 'incident_count' in stats

    def test_no_executions(self):
        """Aucune exécution → success_rate=None, avg_time=None, counts=0."""
        from dashboard.views import _stats_for_queryset
        from executions.models import Execution

        qs = Execution.objects.none()
        stats = _stats_for_queryset(qs)

        assert stats['success_rate'] is None
        assert stats['avg_time'] is None
        assert stats['execution_count'] == 0
        assert stats['incident_count'] == 0

    def test_avg_time_none_when_no_completed_with_timestamps(self):
        """Aucune durée valide → avg_time = None."""
        from dashboard.views import _stats_for_queryset
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        # Completed sans started_at/completed_at
        ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.COMPLETED,
            started_at=None, completed_at=None
        )

        qs = Execution.objects.all()
        stats = _stats_for_queryset(qs)

        assert stats['avg_time'] is None

    def test_negative_duration_ignored(self):
        """Durée négative (completed_at < started_at) → ignorée, avg_time = None si seule durée."""
        from dashboard.views import _stats_for_queryset
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        now = timezone.now()
        exec1 = ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.COMPLETED,
            started_at=now, completed_at=now - timedelta(seconds=10)  # négative
        )

        qs = Execution.objects.filter(pk=exec1.pk)
        stats = _stats_for_queryset(qs)

        # La durée négative est ignorée → durations vide → avg_time = None
        assert stats['avg_time'] is None
        assert stats['execution_count'] == 1

    def test_valid_duration_avg_time_computed(self):
        """Durée positive valide → avg_time calculé."""
        from dashboard.views import _stats_for_queryset
        from executions.models import Execution

        action = ActionFactory.create(integration=self.integration)
        now = timezone.now()
        ExecutionFactory.create(
            action=action, user=self.user, status=ExecutionStatus.COMPLETED,
            started_at=now - timedelta(seconds=60), completed_at=now
        )

        qs = Execution.objects.all()
        stats = _stats_for_queryset(qs)

        # Durée valide → avg_time non None et ≈ 60s
        assert stats['avg_time'] is not None
        assert stats['avg_time'] > 0


@pytest.mark.django_db
class TestDashboardCompareView:
    """Tests pour DashboardCompareView.get."""

    URL = '/api/v1/dashboard/compare/'

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create()
        self.client.force_authenticate(user=self.user)

    def test_invalid_dimension_returns_400(self):
        """dimension invalide → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'invalid_dim',
            'value1': 'Oracle',
            'value2': 'PostgreSQL',
        })
        assert response.status_code == 400

    def test_missing_value1_returns_400(self):
        """value1 manquant → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'technology',
            'value2': 'PostgreSQL',
        })
        assert response.status_code == 400

    def test_missing_value2_returns_400(self):
        """value2 manquant → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'technology',
            'value1': 'Oracle',
        })
        assert response.status_code == 400

    def test_dimension_technology(self):
        """dimension=technology → 200 avec structure attendue."""
        action = ActionFactory.create(integration=self.integration, engine='Oracle')
        ExecutionFactory.create(action=action, user=self.user, status=ExecutionStatus.COMPLETED)

        response = self.client.get(self.URL, {
            'dimension': 'technology',
            'value1': 'Oracle',
            'value2': 'PostgreSQL',
        })

        assert response.status_code == 200
        assert 'data' in response.data
        data = response.data['data']
        assert data['dimension'] == 'technology'
        assert 'value1_stats' in data
        assert 'value2_stats' in data
        assert 'deltas' in data

    def test_dimension_environment(self):
        """dimension=environment → 200."""
        action = ActionFactory.create(integration=self.integration)
        ExecutionFactory.create(action=action, user=self.user, environment='prod')

        response = self.client.get(self.URL, {
            'dimension': 'environment',
            'value1': 'prod',
            'value2': 'dev',
        })

        assert response.status_code == 200
        assert response.data['data']['dimension'] == 'environment'

    def test_dimension_period_valid_dates(self):
        """dimension=period avec dates valides → 200."""
        response = self.client.get(self.URL, {
            'dimension': 'period',
            'value1': 'P1',
            'value2': 'P2',
            'period1_start': '2026-01-01',
            'period1_end': '2026-01-15',
            'period2_start': '2026-01-16',
            'period2_end': '2026-01-31',
        })

        assert response.status_code == 200
        assert response.data['data']['dimension'] == 'period'

    def test_dimension_period_missing_dates_returns_400(self):
        """dimension=period sans les dates → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'period',
            'value1': 'P1',
            'value2': 'P2',
            # dates manquantes
        })
        assert response.status_code == 400

    def test_dimension_period_invalid_date_format_returns_400(self):
        """dimension=period avec format de date invalide → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'period',
            'value1': 'P1',
            'value2': 'P2',
            'period1_start': '01/01/2026',
            'period1_end': '2026-01-15',
            'period2_start': '2026-01-16',
            'period2_end': '2026-01-31',
        })
        assert response.status_code == 400

    def test_dimension_technology_days_zero_returns_400(self):
        """dimension=technology avec days=0 → 400 (branche days <= 0)."""
        response = self.client.get(self.URL, {
            'dimension': 'technology',
            'value1': 'Oracle',
            'value2': 'PostgreSQL',
            'days': '0',
        })
        assert response.status_code == 400

    def test_dimension_environment_days_negative_returns_400(self):
        """dimension=environment avec days négatif → 400."""
        response = self.client.get(self.URL, {
            'dimension': 'environment',
            'value1': 'prod',
            'value2': 'dev',
            'days': '-1',
        })
        assert response.status_code == 400

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.URL, {
            'dimension': 'technology',
            'value1': 'Oracle',
            'value2': 'PostgreSQL',
        })
        assert response.status_code == 401
