"""Tests pour executions/views/list_views.py — Story 39.5.

Couvre : ExecutionsListView, ExecutionStatsView,
         ExecutionTimeSeriesView, ExecutionTagsView.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from executions.models import Execution, ExecutionStatus
from tests.factories import (
    ActionFactory,
    ExecutionFactory,
    TagFactory,
    ActionTagFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# ExecutionsListView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionsListView(TestCase):
    """GET /api/v1/executions/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="list_user_main", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 1.1 pagination invalide — limit <= 0
    def test_invalid_pagination_limit_zero(self):
        response = self.client.get("/api/v1/executions/?limit=0")
        self.assertEqual(response.status_code, 400)

    # 1.1 pagination invalide — limit négatif
    def test_invalid_pagination_limit_negative(self):
        response = self.client.get("/api/v1/executions/?limit=-5")
        self.assertEqual(response.status_code, 400)

    # 1.1 pagination invalide — offset négatif
    def test_invalid_pagination_offset_negative(self):
        response = self.client.get("/api/v1/executions/?offset=-1")
        self.assertEqual(response.status_code, 400)

    # 1.2 scope=mine → filtre par user
    def test_scope_mine_returns_only_user_executions(self):
        ExecutionFactory(action=self.action, user=self.user, environment="dev")
        other_user = UserFactory(username="list_other_user")
        ExecutionFactory(action=self.action, user=other_user, environment="dev")

        response = self.client.get("/api/v1/executions/?scope=mine")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        for item in data:
            self.assertEqual(str(self.user.id), str(item["user_id"]))

    # 1.3 scope=all (admin) → toutes les exécutions
    def test_scope_all_admin_returns_all_executions(self):
        admin = UserFactory(username="list_admin_user", profile="DBOPS")
        self.client.force_authenticate(user=admin)
        other = UserFactory(username="list_other_for_all")
        ExecutionFactory(action=self.action, user=other, environment="dev")
        ExecutionFactory(action=self.action, user=admin, environment="dev")

        response = self.client.get("/api/v1/executions/?scope=all")
        self.assertEqual(response.status_code, 200)
        # au moins 2 exécutions retournées
        self.assertGreaterEqual(len(response.json()["data"]), 2)

    # 1.4 filtres status + action_id + dates combinés
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_combined_filters_pass_through(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get(
            "/api/v1/executions/?status=COMPLETED&action_id=1&start_date=2025-01-01&end_date=2025-12-31"
        )
        self.assertEqual(response.status_code, 200)
        mock_filters.assert_called_once()

    # 1.5 liste vide → data:[], pagination:{total:0}
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_empty_list(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get("/api/v1/executions/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"], [])
        self.assertEqual(body["pagination"]["total"], 0)

    # 1.6 non authentifié → 401
    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get("/api/v1/executions/")
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# ExecutionStatsView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionStatsView(TestCase):
    """GET /api/v1/executions/stats/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="stats_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

    # 1.7 sans filtres date → branche today_start
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_stats_no_dates_uses_today_branch(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        # start_d=None, end_d=None → branche today_start
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get("/api/v1/executions/stats/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("taux_succes_pct", data)
        self.assertEqual(data["taux_succes_pct"], 0.0)

    # 1.8 avec start_date/end_date → branche `if start_d or end_d`
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_stats_with_dates_uses_date_branch(self, mock_filters, mock_scope):
        from datetime import date
        mock_scope.return_value = (Execution.objects.none(), "mine")
        # Simuler start_d non-None
        mock_filters.return_value = (Execution.objects.none(), date(2025, 1, 1), date(2025, 12, 31))
        response = self.client.get(
            "/api/v1/executions/stats/?start_date=2025-01-01&end_date=2025-12-31"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("executions_jour", data)

    # 1.9 COMPLETED + FAILED → taux_succes_pct calculé
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_stats_taux_succes_calculated(self, mock_filters, mock_scope):
        action = ActionFactory(status="published")
        # Créer 1 COMPLETED et 1 FAILED
        exec1 = ExecutionFactory(user=self.user, action=action, environment="dev")
        exec2 = ExecutionFactory(user=self.user, action=action, environment="dev")
        exec1.status = ExecutionStatus.COMPLETED
        exec1.save(update_fields=["status"])
        exec2.status = ExecutionStatus.FAILED
        exec2.save(update_fields=["status"])

        qs = Execution.objects.filter(user=self.user)
        mock_scope.return_value = (qs, "mine")
        mock_filters.return_value = (qs, None, None)

        response = self.client.get("/api/v1/executions/stats/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["taux_succes_pct"], 50.0)

    # 1.10 aucune exécution terminée → taux_succes_pct=0.0
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_stats_no_finished_executions(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get("/api/v1/executions/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["taux_succes_pct"], 0.0)


# ---------------------------------------------------------------------------
# ExecutionTimeSeriesView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionTimeSeriesView(TestCase):
    """GET /api/v1/executions/timeseries/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="ts_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

    # 1.11 sans dates → défaut 7 jours
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_timeseries_default_7_days(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get("/api/v1/executions/timeseries/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])

    # 1.12 avec start_date/end_date → filtrage custom
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_timeseries_with_custom_dates(self, mock_filters, mock_scope):
        from datetime import date
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (
            Execution.objects.none(),
            date(2025, 1, 1),
            date(2025, 1, 31),
        )
        response = self.client.get(
            "/api/v1/executions/timeseries/?start_date=2025-01-01&end_date=2025-01-31"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    # 1.13 résultat vide → data:[]
    @patch("executions.views.list_views.apply_scope_filter")
    @patch("executions.views.list_views.apply_execution_filters")
    def test_timeseries_empty_result(self, mock_filters, mock_scope):
        mock_scope.return_value = (Execution.objects.none(), "mine")
        mock_filters.return_value = (Execution.objects.none(), None, None)
        response = self.client.get("/api/v1/executions/timeseries/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])


# ---------------------------------------------------------------------------
# ExecutionTagsView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionTagsView(TestCase):
    """GET /api/v1/executions/tags/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="tags_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

    # 1.14 aucune exécution → data:[]
    def test_tags_no_executions_returns_empty(self):
        # Aucune exécution créée dans setUp → la vue doit retourner une liste vide
        # Django TestCase isole chaque test par transaction rollback : pas de contamination cross-tests
        response = self.client.get("/api/v1/executions/tags/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())
        self.assertEqual(response.json()["data"], [])

    # 1.15 exécutions avec tags → liste triée sans doublons ni None
    def test_tags_with_executions_returns_sorted_unique_tags(self):
        action = ActionFactory(status="published")
        tag1 = TagFactory(name="alpha_tag")
        tag2 = TagFactory(name="beta_tag")
        ActionTagFactory(action=action, tag=tag1)
        ActionTagFactory(action=action, tag=tag2)
        ExecutionFactory(action=action, user=self.user, environment="dev")

        response = self.client.get("/api/v1/executions/tags/")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("alpha_tag", data)
        self.assertIn("beta_tag", data)
        # Aucun None dans la liste
        self.assertNotIn(None, data)
        # Liste triée (alpha avant beta)
        if "alpha_tag" in data and "beta_tag" in data:
            self.assertLess(data.index("alpha_tag"), data.index("beta_tag"))
