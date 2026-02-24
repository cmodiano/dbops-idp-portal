"""Tests pour executions/views/scheduled_views.py — Story 39.5.

Couvre les branches manquantes NON présentes dans :
- test_scheduled_views_format.py  (format GET nominal)
- test_scheduled_execution_put.py (PUT)

Nouvelles branches : GET pagination/RBAC/filters, POST, PATCH,
                     RecurringPattern, ValidateCron, CronNextExecutions.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from executions.models import (
    ScheduledExecutionStatus,
)
from tests.factories import (
    ActionFactory,
    ExecutionFactory,
    RecurringPatternFactory,
    ScheduledExecutionFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# ScheduledExecutionsView — GET  (branches manquantes)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.get_allowed_action_ids_for_user")
class TestScheduledExecutionsGetBranches(TestCase):
    """Branches GET non couvertes par test_scheduled_views_format.py."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="sched_get_user", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 2.1 pagination invalide — limit <= 0
    def test_invalid_limit_zero(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        response = self.client.get("/api/v1/scheduled-executions/?limit=0")
        self.assertEqual(response.status_code, 400)

    # 2.1 pagination invalide — offset négatif
    def test_invalid_offset_negative(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        response = self.client.get("/api/v1/scheduled-executions/?offset=-1")
        self.assertEqual(response.status_code, 400)

    # 2.1 pagination invalide — limit > 100
    def test_invalid_limit_over_100(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        response = self.client.get("/api/v1/scheduled-executions/?limit=101")
        self.assertEqual(response.status_code, 400)

    # 2.2 non-admin : RBAC filter (allowed_action_ids not None)
    def test_non_admin_rbac_filter_applied(self, mock_allowed, mock_validate):
        non_admin = UserFactory(username="sched_non_admin", profile="BUSINESS")
        self.client.force_authenticate(user=non_admin)
        # allowed_action_ids = [] → aucune action autorisée
        mock_allowed.return_value = []
        se = ScheduledExecutionFactory(user=non_admin, action=self.action)
        response = self.client.get("/api/v1/scheduled-executions/")
        self.assertEqual(response.status_code, 200)
        # Avec allowed_action_ids=[], aucun résultat attendu pour cet utilisateur
        ids_returned = [item["scheduled_execution_id"] for item in response.json()["data"]]
        self.assertNotIn(se.id, ids_returned)

    # 2.3 non-admin : allowed_action_ids=None → aucun filtre
    def test_non_admin_allowed_none_no_filter(self, mock_allowed, mock_validate):
        non_admin = UserFactory(username="sched_non_admin2", profile="BUSINESS")
        self.client.force_authenticate(user=non_admin)
        # allowed_action_ids = None → pas de filtre appliqué
        mock_allowed.return_value = None
        ScheduledExecutionFactory(user=non_admin, action=self.action)
        response = self.client.get("/api/v1/scheduled-executions/")
        self.assertEqual(response.status_code, 200)
        # Doit retourner des données
        self.assertGreaterEqual(len(response.json()["data"]), 1)

    # 2.4 status invalide → 422 (InvalidStateError)
    def test_invalid_status_raises_invalid_state(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        response = self.client.get("/api/v1/scheduled-executions/?status=INVALID_STATUS_XYZ")
        self.assertIn(response.status_code, [400, 422])

    # 2.5 filtre action_id
    def test_filter_action_id(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        action2 = ActionFactory(status="published")
        ScheduledExecutionFactory(user=self.user, action=self.action)
        ScheduledExecutionFactory(user=self.user, action=action2)
        response = self.client.get(f"/api/v1/scheduled-executions/?action_id={action2.id}")
        self.assertEqual(response.status_code, 200)
        for item in response.json()["data"]:
            self.assertEqual(item["action_id"], action2.id)

    # 2.6 scheduled_from / scheduled_to → Q filter
    def test_filter_scheduled_from_to(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        future = timezone.now() + timedelta(days=5)
        ScheduledExecutionFactory(user=self.user, action=self.action, scheduled_at=future)
        # Utiliser format sans timezone pour éviter problèmes de parsing
        future_str = future.strftime("%Y-%m-%dT%H:%M:%S")
        response = self.client.get(
            f"/api/v1/scheduled-executions/?scheduled_from={future_str}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    # 2.7 admin → available_actions inclut toutes les actions
    def test_admin_available_actions_all(self, mock_allowed, mock_validate):
        mock_allowed.return_value = None
        admin = UserFactory(username="sched_admin_user", profile="DBOPS")
        self.client.force_authenticate(user=admin)
        ScheduledExecutionFactory(user=admin, action=self.action)
        response = self.client.get("/api/v1/scheduled-executions/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("available_actions", response.json())


# ---------------------------------------------------------------------------
# ScheduledExecutionsView — POST
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduledExecutionsPost(TestCase):
    """POST /api/v1/scheduled-executions/ — branches manquantes."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="sched_post_user", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 2.8 action_id manquant → 400
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_missing_action_id(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={"environment": "dev", "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.8 environment manquant → 400
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_missing_environment(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={"action_id": self.action.id, "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.9 scheduled_at ET recurring_pattern → 400
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_both_scheduled_at_and_recurring(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={
                "action_id": self.action.id,
                "environment": "dev",
                "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat(),
                "recurring_pattern": {"pattern_type": "daily", "pattern_config": {}},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.10 ni scheduled_at ni recurring_pattern → 400
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_neither_scheduled_at_nor_recurring(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={"action_id": self.action.id, "environment": "dev"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.11 action_id invalide (ValueError/TypeError) → 400
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_invalid_action_id_type(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={
                "action_id": "not-an-int",
                "environment": "dev",
                "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.12 action introuvable (DoesNotExist) → 404
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_action_not_found(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={
                "action_id": 999999,
                "environment": "dev",
                "scheduled_at": (timezone.now() + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # 2.13 scheduled_at dans le passé → 400 (INVALID_SCHEDULED_DATE)
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_scheduled_at_in_past(self, mock_validate):
        mock_validate.return_value = None
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={"action_id": self.action.id, "environment": "dev", "scheduled_at": past},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        # L'erreur est dans error.code ou code selon le handler
        code = body.get("code", "") or body.get("error", {}).get("code", "")
        self.assertIn("INVALID_SCHEDULED_DATE", code)

    # 2.14 one-time valide → 201
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_one_time_valid(self, mock_validate):
        mock_validate.return_value = None
        future = (timezone.now() + timedelta(hours=2)).isoformat()
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={"action_id": self.action.id, "environment": "dev", "scheduled_at": future},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("data", response.json())

    # 2.15 avec recurring_pattern → 201
    @patch("executions.views.scheduled_views.validate_environment_against_inventory")
    def test_post_with_recurring_pattern(self, mock_validate):
        mock_validate.return_value = None
        response = self.client.post(
            "/api/v1/scheduled-executions/",
            data={
                "action_id": self.action.id,
                "environment": "dev",
                "recurring_pattern": {
                    "pattern_type": "daily",
                    "pattern_config": {"hour": 9, "minute": 0},
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("data", response.json())


# ---------------------------------------------------------------------------
# ScheduledExecutionUpdateView — PATCH
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.get_allowed_action_ids_for_user", return_value=None)
class TestScheduledExecutionPatch(TestCase):
    """PATCH /api/v1/scheduled-executions/{id}/ — branches manquantes."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="sched_patch_user", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 2.16 id introuvable → 404
    def test_patch_not_found(self, mock_allowed, mock_validate):
        response = self.client.patch(
            "/api/v1/scheduled-executions/999999/",
            data={"status": "cancelled"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # 2.17 non-propriétaire/non-admin → 403
    def test_patch_forbidden_non_owner(self, mock_allowed, mock_validate):
        # Créer SE appartenant à un autre user
        other_user = UserFactory(username="sched_other_patch_owner", profile="DBA")
        se = ScheduledExecutionFactory(user=other_user, action=self.action)
        # Authentifier en tant que BUSINESS non-admin (pas propriétaire)
        business = UserFactory(username="sched_business_patch", profile="BUSINESS")
        self.client.force_authenticate(user=business)
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "cancelled"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    # 2.18 statut != PENDING → 422 (InvalidStateError)
    def test_patch_not_pending_raises_invalid_state(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="executed")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "cancelled"},
            format="json",
        )
        self.assertIn(response.status_code, [400, 422])

    # 2.19 status=cancelled → CANCELLED, 200
    @patch("executions.views.scheduled_views.SchedulingService")
    def test_patch_cancelled_ok(self, mock_svc_cls, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")

        def mock_cancel(sid, user_id):
            se.status = ScheduledExecutionStatus.CANCELLED
            se.save(update_fields=["status"])
            return se

        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.side_effect = mock_cancel
        mock_svc_cls.return_value = mock_svc

        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "cancelled"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        se.refresh_from_db()
        self.assertEqual(se.status, ScheduledExecutionStatus.CANCELLED)

    # 2.20 status=executed sans execution_id → 400
    def test_patch_executed_no_execution_id(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "executed"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.21 status=executed, execution_id invalide → 400
    def test_patch_executed_invalid_execution_id(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "executed", "execution_id": "not-int"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.22 status=executed, sans recurring → EXECUTED, 200
    def test_patch_executed_no_recurring(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        exec_ = ExecutionFactory(action=self.action, user=self.user, environment="dev")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "executed", "execution_id": exec_.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        se.refresh_from_db()
        self.assertEqual(se.status, ScheduledExecutionStatus.EXECUTED)

    # 2.23 status=executed, recurring actif → PENDING + next_execution_date recalculée
    def test_patch_executed_recurring_active_stays_pending(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type="daily",
            is_active=1,
            pattern_config='{"hour": 9, "minute": 0}',
        )
        exec_ = ExecutionFactory(action=self.action, user=self.user, environment="dev")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "executed", "execution_id": exec_.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        se.refresh_from_db()
        # Avec recurring actif, reste PENDING
        self.assertEqual(se.status, ScheduledExecutionStatus.PENDING)

    # 2.24 status invalide → 400
    def test_patch_invalid_status(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"status": "invalid_status_xyz"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# ScheduledExecutionUpdateView — PUT
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.get_allowed_action_ids_for_user", return_value=None)
class TestScheduledExecutionPut(TestCase):
    """PUT /api/v1/scheduled-executions/{id}/ — branches manquantes."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="sched_put_user", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 2.25 id introuvable → 404
    def test_put_not_found(self, mock_allowed, mock_validate):
        response = self.client.put(
            "/api/v1/scheduled-executions/999999/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # 2.26 non-propriétaire/non-admin → 403
    def test_put_forbidden_non_owner(self, mock_allowed, mock_validate):
        other = UserFactory(username="sched_other_put_owner", profile="DBA")
        se = ScheduledExecutionFactory(user=other, action=self.action)
        # Authentifier un BUSINESS non-admin, non-propriétaire
        business = UserFactory(username="sched_business_put", profile="BUSINESS")
        self.client.force_authenticate(user=business)
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    # 2.27 statut != PENDING → 422
    def test_put_not_pending_raises(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="executed")
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={},
            format="json",
        )
        self.assertIn(response.status_code, [400, 422])

    # 2.28 scheduled_at update (sans recurring)
    def test_put_scheduled_at_update(self, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        new_dt = (timezone.now() + timedelta(days=3)).isoformat()
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"scheduled_at": new_dt},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    # 2.29 environment update → normalisé
    def test_put_environment_update(self, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"environment": "PROD"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    # 2.30 target_names=[] → _targets vidé
    @patch("executions.views.scheduled_views.InventoryService")
    def test_put_target_names_empty_clears_targets(self, mock_inv_cls, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"target_names": []},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    # 2.31 target_names non-liste → 400
    @patch("executions.views.scheduled_views.InventoryService")
    def test_put_target_names_not_list(self, mock_inv_cls, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"target_names": "not-a-list"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.34 parameters merge (sans _-prefix)
    def test_put_parameters_merge(self, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={"parameters": {"my_param": "value"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    # 2.35 recurring_pattern update (rp existe)
    def test_put_recurring_pattern_update(self, mock_allowed, mock_validate):
        mock_validate.return_value = None
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status="pending")
        RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type="daily",
            is_active=1,
        )
        response = self.client.put(
            f"/api/v1/scheduled-executions/{se.id}/",
            data={
                "recurring_pattern": {
                    "pattern_type": "weekly",
                    "pattern_config": {"day_of_week": 1, "hour": 8},
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# ScheduledExecutionRecurringPatternView — PATCH
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@patch("executions.views.scheduled_views.validate_environment_against_inventory")
@patch("executions.views.scheduled_views.get_allowed_action_ids_for_user", return_value=None)
class TestScheduledExecutionRecurringPatternPatch(TestCase):
    """PATCH /api/v1/scheduled-executions/{id}/recurring-pattern/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="sched_rp_user", profile="DBA")
        self.action = ActionFactory(status="published")
        self.client.force_authenticate(user=self.user)

    # 2.36 id introuvable → 404
    def test_recurring_patch_not_found(self, mock_allowed, mock_validate):
        response = self.client.patch(
            "/api/v1/scheduled-executions/999999/recurring-pattern/",
            data={"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # 2.37 non-propriétaire/non-admin → 403
    def test_recurring_patch_forbidden(self, mock_allowed, mock_validate):
        other = UserFactory(username="sched_rp_other_owner", profile="DBA")
        se = ScheduledExecutionFactory(user=other, action=self.action)
        RecurringPatternFactory(scheduled_execution=se)
        # Authentifier BUSINESS non-admin, non-propriétaire
        business = UserFactory(username="sched_rp_business", profile="BUSINESS")
        self.client.force_authenticate(user=business)
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/recurring-pattern/",
            data={"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    # 2.38 pas de recurring pattern → 404
    def test_recurring_patch_no_pattern(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action)
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/recurring-pattern/",
            data={"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    # 2.39 is_active manquant → 400
    def test_recurring_patch_missing_is_active(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action)
        RecurringPatternFactory(scheduled_execution=se)
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/recurring-pattern/",
            data={},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # 2.40 is_active=true → next_execution_date recalculée
    def test_recurring_patch_activate(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action)
        rp = RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type="daily",
            is_active=0,
            pattern_config='{"hour": 9, "minute": 0}',
        )
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/recurring-pattern/",
            data={"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        rp.refresh_from_db()
        self.assertEqual(rp.is_active, 1)
        self.assertIsNotNone(rp.next_execution_date)

    # 2.41 is_active=false → pas de recalcul
    def test_recurring_patch_deactivate(self, mock_allowed, mock_validate):
        se = ScheduledExecutionFactory(user=self.user, action=self.action)
        old_date = timezone.now() + timedelta(days=1)
        rp = RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type="daily",
            is_active=1,
            next_execution_date=old_date,
        )
        response = self.client.patch(
            f"/api/v1/scheduled-executions/{se.id}/recurring-pattern/",
            data={"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        rp.refresh_from_db()
        self.assertEqual(rp.is_active, 0)


# ---------------------------------------------------------------------------
# ScheduledExecutionValidateCronView — GET
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidateCronView(TestCase):
    """GET /api/v1/scheduled-executions/validate-cron/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="cron_validate_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

    # 2.42 expression manquante → 400
    def test_validate_cron_missing_expression(self):
        response = self.client.get("/api/v1/scheduled-executions/validate-cron/")
        self.assertEqual(response.status_code, 400)

    # 2.43 expression invalide → {"valid": False}
    def test_validate_cron_invalid_expression(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron/?expression=99+99+*+*+*"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["valid"])

    # 2.44 expression valide → {"valid": True}
    def test_validate_cron_valid_expression(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron/?expression=0+9+*+*+1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["valid"])

    # 2.45 CroniterBadCronError → {"valid": False}
    @patch("executions.views.scheduled_views.croniter")
    def test_validate_cron_croniter_exception(self, mock_croniter):
        from croniter import CroniterBadCronError
        mock_croniter.is_valid.side_effect = CroniterBadCronError("bad cron")
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron/?expression=bad_cron"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["valid"])


# ---------------------------------------------------------------------------
# ScheduledExecutionCronNextExecutionsView — GET
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCronNextExecutionsView(TestCase):
    """GET /api/v1/scheduled-executions/cron-next-executions/"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username="cron_next_user", profile="DBA")
        self.client.force_authenticate(user=self.user)

    # 2.46 count < 1 → 400
    def test_count_less_than_1(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/cron-next-executions/?expression=0+9+*+*+1&count=0"
        )
        self.assertEqual(response.status_code, 400)

    # 2.46 count > 10 → 400
    def test_count_greater_than_10(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/cron-next-executions/?expression=0+9+*+*+1&count=11"
        )
        self.assertEqual(response.status_code, 400)

    # 2.47 expression invalide → 400
    def test_invalid_cron_expression(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/cron-next-executions/?expression=99+99+*+*+*&count=3"
        )
        self.assertEqual(response.status_code, 400)

    # 2.48 valide → liste de `count` prochaines exécutions
    def test_valid_cron_returns_next_executions(self):
        response = self.client.get(
            "/api/v1/scheduled-executions/cron-next-executions/?expression=0+9+*+*+1&count=3"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("executions", data)
        self.assertEqual(len(data["executions"]), 3)
