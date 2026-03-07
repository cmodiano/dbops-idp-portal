"""Tests de couverture pour executions/views/scheduled_views.py.

Objectif : atteindre ≥90% de couverture sur ce fichier.
Toutes les branches des cinq vues sont couvertes :
  - ScheduledExecutionsView (GET + POST)
  - ScheduledExecutionUpdateView (PATCH + PUT)
  - ScheduledExecutionRecurringPatternView (PATCH)
  - ScheduledExecutionValidateCronView (GET)
  - ScheduledExecutionCronNextExecutionsView (GET)

Note : On utilise APIRequestFactory + force_authenticate + view.as_view()(request)
directement pour éviter la résolution d'URL (qui nécessite drf_spectacular).
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from executions.views.scheduled_views import (
    ScheduledExecutionsView,
    ScheduledExecutionUpdateView,
    ScheduledExecutionRecurringPatternView,
    ScheduledExecutionValidateCronView,
    ScheduledExecutionCronNextExecutionsView,
)
from tests.factories import (
    ActionFactory,
    RecurringPatternFactory,
    ScheduledExecutionFactory,
    UserFactory,
)

factory = APIRequestFactory()


def _future(hours=2):
    return (timezone.now() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _past(hours=1):
    return (timezone.now() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


# ===========================================================================
# ScheduledExecutionsView — GET
# ===========================================================================

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.get_allowed_action_ids_for_user")
class TestScheduledExecutionsGet(TestCase):

    def setUp(self):
        self.dba_user = UserFactory(profile="DBA")
        self.action = ActionFactory(status="published", engine="Oracle", platform="AAP")
        self.view = ScheduledExecutionsView.as_view()

    def _get(self, user, params=""):
        request = factory.get(f"/scheduled-executions/{params}")
        force_authenticate(request, user=user)
        return self.view(request)

    # --- pagination invalide ------------------------------------------------

    def test_limit_zero_returns_400(self, mock_allowed, mock_validate):
        request = factory.get("/scheduled-executions/", {"limit": "0"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 400)

    def test_offset_negative_returns_400(self, mock_allowed, mock_validate):
        request = factory.get("/scheduled-executions/", {"offset": "-1"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 400)

    def test_limit_over_100_returns_400(self, mock_allowed, mock_validate):
        request = factory.get("/scheduled-executions/", {"limit": "101"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 400)

    # --- nominal DBA (admin sees all) ---------------------------------------

    def test_admin_get_nominal(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        request = factory.get("/scheduled-executions/")
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("data", resp.data)
        self.assertIn("pagination", resp.data)
        self.assertIn("available_actions", resp.data)

    # --- non-admin : RBAC filter appliqué -----------------------------------

    def test_non_admin_rbac_filter_applied(self, mock_allowed, mock_validate):
        non_admin = UserFactory(profile="BUSINESS")
        mock_allowed.return_value = []
        ScheduledExecutionFactory(user=non_admin, action=self.action)
        request = factory.get("/scheduled-executions/")
        force_authenticate(request, user=non_admin)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_allowed_none_no_filter(self, mock_allowed, mock_validate):
        non_admin = UserFactory(profile="BUSINESS")
        mock_allowed.return_value = None
        ScheduledExecutionFactory(user=non_admin, action=self.action)
        request = factory.get("/scheduled-executions/")
        force_authenticate(request, user=non_admin)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    # --- filtre statut ------------------------------------------------------

    def test_status_filter_valid(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action, status="pending")
        request = factory.get("/scheduled-executions/", {"status": "pending"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    def test_status_filter_invalid_returns_400(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        request = factory.get("/scheduled-executions/", {"status": "invalid_status"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 400)

    # --- filtre action_id ---------------------------------------------------

    def test_action_id_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        request = factory.get("/scheduled-executions/", {"action_id": str(self.action.id)})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    # --- filtre environment -------------------------------------------------

    def test_environment_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        mock_validate.return_value = None
        ScheduledExecutionFactory(action=self.action, environment="dev")
        request = factory.get("/scheduled-executions/", {"environment": "dev"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    # --- filtre engine/platform ---------------------------------------------

    def test_engine_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        request = factory.get("/scheduled-executions/", {"engine": "Oracle"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    def test_platform_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        request = factory.get("/scheduled-executions/", {"platform": "AAP"})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    # --- filtre scheduled_from / scheduled_to --------------------------------

    def test_scheduled_from_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        past = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        request = factory.get("/scheduled-executions/", {"scheduled_from": past})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)

    def test_scheduled_to_filter(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        ScheduledExecutionFactory(action=self.action)
        future = (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S")
        request = factory.get("/scheduled-executions/", {"scheduled_to": future})
        force_authenticate(request, user=self.dba_user)
        resp = self.view(request)
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# ScheduledExecutionsView — POST
# ===========================================================================

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.SchedulingService")
class TestScheduledExecutionsPost(TestCase):

    def setUp(self):
        self.dba_user = UserFactory(profile="DBA")
        self.action = ActionFactory(status="published")
        self.view = ScheduledExecutionsView.as_view()

    def _post(self, user, data):
        request = factory.post("/scheduled-executions/", data, format="json")
        force_authenticate(request, user=user)
        return self.view(request)

    def _make_se(self):
        return ScheduledExecutionFactory(user=self.dba_user, action=self.action)

    # --- champs requis manquants --------------------------------------------

    def test_missing_action_id_returns_400(self, mock_svc_cls, mock_validate):
        resp = self._post(self.dba_user, {"environment": "dev"})
        self.assertEqual(resp.status_code, 400)

    def test_missing_environment_returns_400(self, mock_svc_cls, mock_validate):
        resp = self._post(self.dba_user, {"action_id": self.action.id})
        self.assertEqual(resp.status_code, 400)

    # --- exclusivité scheduled_at / recurring_pattern -----------------------

    def test_both_scheduled_at_and_recurring_pattern_returns_400(self, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        admin_user = UserFactory(profile="DBOPS")
        resp = self._post(admin_user, {
            "action_id": self.action.id,
            "environment": "dev",
            "scheduled_at": _future(),
            "recurring_pattern": {"pattern_type": "daily", "pattern_config": {"time": "02:00"}},
        })
        self.assertEqual(resp.status_code, 400)

    def test_neither_scheduled_at_nor_recurring_pattern_returns_400(self, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        resp = self._post(self.dba_user, {"action_id": self.action.id, "environment": "dev"})
        self.assertEqual(resp.status_code, 400)

    # --- action introuvable ou invalide ------------------------------------

    def test_invalid_action_id_type_returns_400(self, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        resp = self._post(self.dba_user, {
            "action_id": "not-a-number",
            "environment": "dev",
            "scheduled_at": _future(),
        })
        self.assertEqual(resp.status_code, 400)

    def test_action_not_found_returns_404(self, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        resp = self._post(self.dba_user, {
            "action_id": 999999,
            "environment": "dev",
            "scheduled_at": _future(),
        })
        self.assertEqual(resp.status_code, 404)

    # --- scheduled_at dans le passé ----------------------------------------

    def test_scheduled_at_in_past_returns_400(self, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        resp = self._post(self.dba_user, {
            "action_id": self.action.id,
            "environment": "dev",
            "scheduled_at": _past(),
        })
        self.assertEqual(resp.status_code, 400)

    # --- création réussie avec scheduled_at --------------------------------

    @patch("executions.views.scheduled_views.get_correlation_id", return_value=None)
    def test_create_with_scheduled_at_returns_201(self, mock_cid, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        se = self._make_se()
        mock_svc = MagicMock()
        mock_svc.create_scheduled_execution.return_value = se
        mock_svc_cls.return_value = mock_svc
        resp = self._post(self.dba_user, {
            "action_id": self.action.id,
            "environment": "dev",
            "scheduled_at": _future(),
        })
        self.assertEqual(resp.status_code, 201)

    # --- création réussie avec correlation_id ------------------------------

    @patch("executions.views.scheduled_views.get_correlation_id", return_value="corr-123")
    def test_create_sets_correlation_id(self, mock_cid, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        se = self._make_se()
        mock_svc = MagicMock()
        mock_svc.create_scheduled_execution.return_value = se
        mock_svc_cls.return_value = mock_svc
        resp = self._post(self.dba_user, {
            "action_id": self.action.id,
            "environment": "dev",
            "scheduled_at": _future(),
        })
        self.assertEqual(resp.status_code, 201)

    # --- création avec recurring_pattern -----------------------------------

    @patch("executions.views.scheduled_views.get_correlation_id", return_value=None)
    @patch("executions.views.scheduled_views.calculate_next_execution_date")
    def test_create_with_recurring_pattern_returns_201(self, mock_calc, mock_cid, mock_svc_cls, mock_validate):
        mock_validate.return_value = None
        mock_calc.return_value = timezone.now() + timedelta(days=1)
        admin_user = UserFactory(profile="DBOPS")
        se = ScheduledExecutionFactory(user=admin_user, action=self.action)
        mock_svc = MagicMock()
        mock_svc.create_scheduled_execution.return_value = se
        mock_svc_cls.return_value = mock_svc
        resp = self._post(admin_user, {
            "action_id": self.action.id,
            "environment": "dev",
            "recurring_pattern": {"pattern_type": "daily", "pattern_config": {"time": "02:00"}},
        })
        self.assertEqual(resp.status_code, 201)


# ===========================================================================
# ScheduledExecutionUpdateView — PATCH
# ===========================================================================

@pytest.mark.django_db
@patch("executions.views.scheduled_views.SchedulingService")
class TestScheduledExecutionUpdatePatch(TestCase):

    def setUp(self):
        self.dba_user = UserFactory(profile="DBA")
        self.other_user = UserFactory(profile="BUSINESS")
        self.action = ActionFactory(status="published")
        self.view = ScheduledExecutionUpdateView.as_view()

    def _se(self, user=None, status="pending"):
        return ScheduledExecutionFactory(
            user=user or self.dba_user, action=self.action, status=status
        )

    def _patch(self, user, se_id, data):
        request = factory.patch(f"/scheduled-executions/{se_id}/", data, format="json")
        force_authenticate(request, user=user)
        return self.view(request, scheduled_execution_id=se_id)

    # --- not found ----------------------------------------------------------

    def test_patch_not_found_returns_404(self, mock_svc_cls):
        resp = self._patch(self.dba_user, 999999, {"status": "cancelled"})
        self.assertEqual(resp.status_code, 404)

    # --- forbidden ----------------------------------------------------------

    def test_patch_forbidden_for_non_owner_non_admin(self, mock_svc_cls):
        se = self._se(user=self.dba_user)
        resp = self._patch(self.other_user, se.id, {"status": "cancelled"})
        self.assertEqual(resp.status_code, 403)

    # --- not pending --------------------------------------------------------

    def test_patch_not_pending_returns_400(self, mock_svc_cls):
        se = self._se(user=self.dba_user, status="executed")
        resp = self._patch(self.dba_user, se.id, {"status": "cancelled"})
        self.assertEqual(resp.status_code, 400)

    # --- annulation réussie -------------------------------------------------

    def test_patch_cancel_success(self, mock_svc_cls):
        se = self._se()
        cancelled_se = self._se(status="cancelled")
        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.return_value = cancelled_se
        mock_svc_cls.return_value = mock_svc
        resp = self._patch(self.dba_user, se.id, {"status": "cancelled"})
        self.assertEqual(resp.status_code, 200)

    # --- annulation : cancel retourne None ----------------------------------

    def test_patch_cancel_service_returns_none(self, mock_svc_cls):
        se = self._se()
        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.return_value = None
        mock_svc_cls.return_value = mock_svc
        resp = self._patch(self.dba_user, se.id, {"status": "cancelled"})
        self.assertEqual(resp.status_code, 404)

    # --- executed : execution_id manquant -----------------------------------

    def test_patch_executed_missing_execution_id_returns_400(self, mock_svc_cls):
        se = self._se()
        resp = self._patch(self.dba_user, se.id, {"status": "executed"})
        self.assertEqual(resp.status_code, 400)

    # --- executed : execution_id invalide -----------------------------------

    def test_patch_executed_invalid_execution_id_returns_400(self, mock_svc_cls):
        se = self._se()
        resp = self._patch(self.dba_user, se.id, {"status": "executed", "execution_id": "abc"})
        self.assertEqual(resp.status_code, 400)

    # --- executed sans recurring_pattern ------------------------------------

    def test_patch_executed_success_no_recurring(self, mock_svc_cls):
        se = self._se()
        resp = self._patch(self.dba_user, se.id, {"status": "executed", "execution_id": 42})
        self.assertEqual(resp.status_code, 200)

    # --- executed avec recurring_pattern actif ------------------------------

    @patch("executions.views.scheduled_views.calculate_next_execution_date")
    def test_patch_executed_with_active_recurring(self, mock_calc, mock_svc_cls):
        se = self._se()
        RecurringPatternFactory(scheduled_execution=se, pattern_type="daily", is_active=1)
        mock_calc.return_value = timezone.now() + timedelta(days=1)
        resp = self._patch(self.dba_user, se.id, {"status": "executed", "execution_id": 99})
        self.assertEqual(resp.status_code, 200)

    # --- executed avec recurring_pattern inactif ----------------------------

    @patch("executions.views.scheduled_views.calculate_next_execution_date")
    def test_patch_executed_with_inactive_recurring(self, mock_calc, mock_svc_cls):
        se = self._se()
        RecurringPatternFactory(scheduled_execution=se, pattern_type="daily", is_active=0)
        mock_calc.return_value = timezone.now() + timedelta(days=1)
        resp = self._patch(self.dba_user, se.id, {"status": "executed", "execution_id": 77})
        self.assertEqual(resp.status_code, 200)

    # --- statut invalide ----------------------------------------------------

    def test_patch_invalid_status_returns_400(self, mock_svc_cls):
        se = self._se()
        resp = self._patch(self.dba_user, se.id, {"status": "bogus_status"})
        self.assertEqual(resp.status_code, 400)

    # --- default status = cancelled quand body vide ------------------------

    def test_patch_default_status_cancelled(self, mock_svc_cls):
        se = self._se()
        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.return_value = se
        mock_svc_cls.return_value = mock_svc
        resp = self._patch(self.dba_user, se.id, {})
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# ScheduledExecutionUpdateView — PUT
# ===========================================================================

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
class TestScheduledExecutionUpdatePut(TestCase):

    def setUp(self):
        self.dba_user = UserFactory(profile="DBA")
        self.other_user = UserFactory(profile="BUSINESS")
        self.action = ActionFactory(status="published")
        self.view = ScheduledExecutionUpdateView.as_view()

    def _se(self, user=None, status="pending"):
        return ScheduledExecutionFactory(
            user=user or self.dba_user, action=self.action, status=status
        )

    def _put(self, user, se_id, data):
        request = factory.put(f"/scheduled-executions/{se_id}/", data, format="json")
        force_authenticate(request, user=user)
        return self.view(request, scheduled_execution_id=se_id)

    # --- not found ----------------------------------------------------------

    def test_put_not_found_returns_404(self, mock_validate):
        resp = self._put(self.dba_user, 999999, {})
        self.assertEqual(resp.status_code, 404)

    # --- forbidden ----------------------------------------------------------

    def test_put_forbidden_for_non_owner(self, mock_validate):
        se = self._se(user=self.dba_user)
        resp = self._put(self.other_user, se.id, {})
        self.assertEqual(resp.status_code, 403)

    # --- not pending --------------------------------------------------------

    def test_put_not_pending_returns_400(self, mock_validate):
        se = self._se(user=self.dba_user, status="executed")
        resp = self._put(self.dba_user, se.id, {})
        self.assertEqual(resp.status_code, 400)

    # --- scheduled_at mise à jour -------------------------------------------

    def test_put_update_scheduled_at_success(self, mock_validate):
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"scheduled_at": _future(3)})
        self.assertEqual(resp.status_code, 200)

    # --- scheduled_at dans le passé -----------------------------------------

    def test_put_scheduled_at_in_past_returns_400(self, mock_validate):
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"scheduled_at": _past()})
        self.assertEqual(resp.status_code, 400)

    # --- Story 11.11 AC1: forbidden field updates return 400 ----------------

    def test_put_update_environment(self, mock_validate):
        """Story 11.11 AC1: environment is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"environment": "prod"})
        self.assertEqual(resp.status_code, 400)

    def test_put_update_parameters(self, mock_validate):
        """Story 11.11 AC1: parameters is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"parameters": {"key": "value"}})
        self.assertEqual(resp.status_code, 400)

    def test_put_target_names_empty_list(self, mock_validate):
        """Story 11.11 AC1: target_names is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": []})
        self.assertEqual(resp.status_code, 400)

    # --- target_names pas une liste -----------------------------------------

    def test_put_target_names_not_list_returns_400(self, mock_validate):
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": "not-a-list"})
        self.assertEqual(resp.status_code, 400)

    # --- Story 11.11 AC1: target_names is forbidden in PUT ------------------

    def test_put_target_names_forbidden_field(self, mock_validate):
        """Story 11.11 AC1: target_names is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": ["forbidden-host"]})
        self.assertEqual(resp.status_code, 400)

    def test_put_target_names_mixed_environments_forbidden(self, mock_validate):
        """Story 11.11 AC1: target_names is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": ["host-dev", "host-prod"]})
        self.assertEqual(resp.status_code, 400)

    def test_put_target_names_success_forbidden(self, mock_validate):
        """Story 11.11 AC1: target_names is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": ["host-dev"]})
        self.assertEqual(resp.status_code, 400)

    def test_put_inventory_service_error_forbidden(self, mock_validate):
        """Story 11.11 AC1: target_names is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        resp = self._put(self.dba_user, se.id, {"target_names": ["some-host"]})
        self.assertEqual(resp.status_code, 400)

    # --- Story 11.11 AC1: recurring_pattern is forbidden in PUT -------------

    def test_put_update_recurring_pattern(self, mock_validate):
        """Story 11.11 AC1: recurring_pattern is not modifiable via PUT → 400."""
        mock_validate.return_value = None
        se = self._se()
        RecurringPatternFactory(scheduled_execution=se, pattern_type="daily", is_active=1)
        resp = self._put(self.dba_user, se.id, {
            "recurring_pattern": {
                "pattern_type": "weekly",
                "pattern_config": {"day_of_week": 1, "time": "03:00"},
            }
        })
        self.assertEqual(resp.status_code, 400)


# ===========================================================================
# ScheduledExecutionRecurringPatternView — PATCH
# ===========================================================================

@pytest.mark.django_db
@patch("executions.views.scheduled_views.calculate_next_execution_date")
class TestScheduledExecutionRecurringPatternPatch(TestCase):

    def setUp(self):
        self.dba_user = UserFactory(profile="DBA")
        self.other_user = UserFactory(profile="BUSINESS")
        self.action = ActionFactory(status="published")
        self.view = ScheduledExecutionRecurringPatternView.as_view()

    def _patch(self, user, se_id, data):
        request = factory.patch(f"/scheduled-executions/{se_id}/recurring-pattern/", data, format="json")
        force_authenticate(request, user=user)
        return self.view(request, scheduled_execution_id=se_id)

    def _se_with_rp(self, user=None):
        se = ScheduledExecutionFactory(user=user or self.dba_user, action=self.action)
        rp = RecurringPatternFactory(scheduled_execution=se, is_active=0)
        return se, rp

    # --- not found ----------------------------------------------------------

    def test_patch_not_found(self, mock_calc):
        resp = self._patch(self.dba_user, 999999, {"is_active": True})
        self.assertEqual(resp.status_code, 404)

    # --- forbidden ----------------------------------------------------------

    def test_patch_recurring_forbidden(self, mock_calc):
        se, _ = self._se_with_rp(user=self.dba_user)
        resp = self._patch(self.other_user, se.id, {"is_active": True})
        self.assertEqual(resp.status_code, 403)

    # --- pas de recurring_pattern -------------------------------------------

    def test_patch_no_recurring_pattern(self, mock_calc):
        se = ScheduledExecutionFactory(user=self.dba_user, action=self.action)
        resp = self._patch(self.dba_user, se.id, {"is_active": True})
        self.assertEqual(resp.status_code, 404)

    # --- is_active manquant -------------------------------------------------

    def test_patch_missing_is_active(self, mock_calc):
        se, _ = self._se_with_rp()
        resp = self._patch(self.dba_user, se.id, {})
        self.assertEqual(resp.status_code, 400)

    # --- activation réussie (is_active=True) --------------------------------

    def test_patch_activate_success(self, mock_calc):
        mock_calc.return_value = timezone.now() + timedelta(days=1)
        se, _ = self._se_with_rp()
        resp = self._patch(self.dba_user, se.id, {"is_active": True})
        self.assertEqual(resp.status_code, 200)

    # --- désactivation réussie (is_active=False) ----------------------------

    def test_patch_deactivate_success(self, mock_calc):
        mock_calc.return_value = timezone.now() + timedelta(days=1)
        se = ScheduledExecutionFactory(user=self.dba_user, action=self.action)
        RecurringPatternFactory(scheduled_execution=se, is_active=1)
        resp = self._patch(self.dba_user, se.id, {"is_active": False})
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# ScheduledExecutionValidateCronView — GET
# ===========================================================================

@pytest.mark.django_db
class TestScheduledExecutionValidateCronView(TestCase):

    def setUp(self):
        self.user = UserFactory(profile="DBA")
        self.view = ScheduledExecutionValidateCronView.as_view()

    def _get(self, params=None):
        request = factory.get("/scheduled-executions/validate-cron/", params or {})
        force_authenticate(request, user=self.user)
        return self.view(request)

    def test_missing_expression_returns_400(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 400)

    def test_whitespace_only_expression_returns_400(self):
        resp = self._get({"expression": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_valid_cron_expression(self):
        resp = self._get({"expression": "0 2 * * *"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["data"]["valid"])

    def test_invalid_cron_expression(self):
        resp = self._get({"expression": "not-a-cron"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["data"]["valid"])

    def test_cron_expression_is_valid_false_branch(self):
        """When croniter.is_valid returns False, response has valid=False."""
        with patch("executions.views.scheduled_views.croniter") as mock_cron:
            mock_cron.is_valid.return_value = False
            resp = self._get({"expression": "0 2 * * *"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["data"]["valid"])

    @patch("executions.views.scheduled_views.croniter")
    def test_cron_raises_exception(self, mock_cron_cls):
        from croniter import CroniterBadCronError
        mock_cron_cls.is_valid.return_value = True
        mock_cron_cls.side_effect = CroniterBadCronError("bad")
        resp = self._get({"expression": "0 2 * * *"})
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# ScheduledExecutionCronNextExecutionsView — GET
# ===========================================================================

@pytest.mark.django_db
class TestScheduledExecutionCronNextExecutionsView(TestCase):

    def setUp(self):
        self.user = UserFactory(profile="DBA")
        self.view = ScheduledExecutionCronNextExecutionsView.as_view()

    def _get(self, params=None):
        request = factory.get("/scheduled-executions/cron-next-executions/", params or {})
        force_authenticate(request, user=self.user)
        return self.view(request)

    def test_count_less_than_1_returns_400(self):
        resp = self._get({"expression": "0 2 * * *", "count": "0"})
        self.assertEqual(resp.status_code, 400)

    def test_count_greater_than_10_returns_400(self):
        resp = self._get({"expression": "0 2 * * *", "count": "11"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_cron_expression_returns_400(self):
        resp = self._get({"expression": "invalid"})
        self.assertEqual(resp.status_code, 400)

    def test_empty_expression_returns_400(self):
        resp = self._get({})
        self.assertEqual(resp.status_code, 400)

    def test_valid_cron_returns_next_executions(self):
        resp = self._get({"expression": "0 2 * * *", "count": "3"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]["executions"]), 3)

    def test_default_count_is_5(self):
        resp = self._get({"expression": "0 2 * * *"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]["executions"]), 5)
