"""Tests pour executions/views/approval_views.py — Story 39.5, Story 59.1.

Branches NON couvertes dans test_approval_endpoints.py :
- PendingApprovalsView.get() : count_only, pagination invalide, non-DBA
- ApproveExecutionView.post() : launch failure → LAUNCH_FAILED, update_status None → 404
- RejectExecutionView.post()  : update_status None → branche else (direct save)

Story 59.1 (SEC-1) :
- _check_approver_permission() fail-secure : approver_profile_ids absent/vide → False + warning loggé
"""
from __future__ import annotations

import structlog.testing
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from executions.models import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStepType,
)
from executions.services import ExecutionService
from executions.views.approval_views import ApproveExecutionView, RejectExecutionView, _check_approver_permission
from tests.factories import ActionFactory, ExecutionFactory, ExecutionTargetFactory, IntegrationFactory, UserFactory


# ---------------------------------------------------------------------------
# PendingApprovalsView — GET
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPendingApprovalsViewExtra(TestCase):
    """Branches non couvertes dans test_approval_endpoints.py."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="approvals_admin_extra", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap", name="Test AAP Extra")
        self.action = ActionFactory(status="published", integration=self.integration)

    # 3.1 count_only=true → {"count": N}, pas de pagination
    def test_count_only_returns_count_without_pagination(self):
        ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        response = self.client.get("/api/v1/executions/pending-approvals/?count_only=true")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("count", body)
        self.assertNotIn("data", body)
        self.assertNotIn("pagination", body)

    # 3.2 count_only=false, pagination valide → data + pagination
    def test_list_valid_pagination_returns_data_and_pagination(self):
        ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        response = self.client.get("/api/v1/executions/pending-approvals/?count_only=false")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("data", body)
        self.assertIn("pagination", body)

    # 3.3 pagination invalide (limit <= 0) → 400
    def test_list_invalid_pagination_limit_zero(self):
        response = self.client.get("/api/v1/executions/pending-approvals/?limit=0")
        self.assertEqual(response.status_code, 400)

    # 3.3 pagination invalide (offset < 0) → 400
    def test_list_invalid_pagination_offset_negative(self):
        response = self.client.get("/api/v1/executions/pending-approvals/?offset=-1")
        self.assertEqual(response.status_code, 400)

    # 3.4 non-DBA/DBOPS → 403
    def test_list_non_dba_returns_403(self):
        business = UserFactory(username="business_approvals_extra", profile="BUSINESS")
        client = APIClient()
        client.force_authenticate(user=business)
        response = client.get("/api/v1/executions/pending-approvals/")
        self.assertEqual(response.status_code, 403)

    # Story 58.2: AC5 — targets présents dans la réponse sérialisée (prefetch_related)
    def test_list_response_includes_targets(self):
        """Vérifier que targets est présent dans la réponse sérialisée (AC5 Story 58.2)."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        ExecutionTargetFactory(
            execution=execution,
            target_type="SERVER",
            target_id="srv-prod-01",
            target_name="oracle-prod-01",
        )

        response = self.client.get("/api/v1/executions/pending-approvals/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("data", body)
        self.assertEqual(len(body["data"]), 1)
        exec_data = body["data"][0]
        self.assertIn("targets", exec_data)
        self.assertEqual(len(exec_data["targets"]), 1)
        target = exec_data["targets"][0]
        self.assertEqual(target["target_id"], "srv-prod-01")
        self.assertEqual(target["target_name"], "oracle-prod-01")
        self.assertEqual(target["target_type"], "SERVER")

    # Story 57.12: RUNNING + step WAITING approval_granted → apparaît dans la liste
    def test_list_includes_running_with_waiting_approval_step(self):
        """Exécution RUNNING avec step WAITING approval_granted doit apparaître."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name="request-approval",
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({
            "gate_conditions": [{"type": "approval_granted", "timeout_hours": 72}],
            "context_from": ["tf-plan"],
        })
        step.save()

        response = self.client.get("/api/v1/executions/pending-approvals/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("data", body)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["id"], execution.id)
        self.assertEqual(body["data"][0]["status"], ExecutionStatus.RUNNING)

        # count_only doit inclure aussi
        count_resp = self.client.get("/api/v1/executions/pending-approvals/?count_only=true")
        self.assertEqual(count_resp.status_code, 200)
        self.assertEqual(count_resp.json()["count"], 1)


# ---------------------------------------------------------------------------
# ApproveExecutionView — POST (branches manquantes)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestApproveExecutionViewExtra(TestCase):
    """Branches launch failure et update_status=None."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="approver_extra", profile="DBOPS")
        self.integration = IntegrationFactory(type="aap", name="Test AAP Approve")
        self.action = ActionFactory(status="published", integration=self.integration)
        self.client.force_authenticate(user=self.admin)
        # Réinitialiser _execution_service_class
        ApproveExecutionView._execution_service_class = ExecutionService

    def tearDown(self):
        ApproveExecutionView._execution_service_class = ExecutionService

    # 3.5 launch_workflow échoue → INTEGRATION_ERROR → 400 (LAUNCH_FAILED)
    def test_approve_launch_failure_returns_400_launch_failed(self):
        """Si launch_workflow lève une exception → INTEGRATION_ERROR → 400 LAUNCH_FAILED."""
        requester = UserFactory(username="requester_lf_extra", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="production",
        )

        # Utiliser une classe mock (pas un lambda — évite le binding de self)
        class _MockSvcLaunchFail:
            def update_status(self_svc, *args, **kwargs):
                return execution

        ApproveExecutionView._execution_service_class = _MockSvcLaunchFail

        with patch(
            "executions.views.approval_views.ExecutionService.launch_workflow",
            side_effect=RuntimeError("adapter down"),
        ):
            response = self.client.post(f"/api/v1/executions/{execution.id}/approve/")

        self.assertEqual(response.status_code, 400)
        body = response.json()
        code = body.get("code", "") or body.get("error", {}).get("code", "")
        self.assertIn("LAUNCH_FAILED", code)

    # 3.6 update_status retourne None → 404
    def test_approve_update_status_returns_none_gives_404(self):
        """Si update_status retourne None → NotFoundError → 404."""
        requester = UserFactory(username="requester_none_extra", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="production",
        )

        class _MockSvcUpdateNone:
            def update_status(self_svc, *args, **kwargs):
                return None  # Simule retour None

        ApproveExecutionView._execution_service_class = _MockSvcUpdateNone

        response = self.client.post(f"/api/v1/executions/{execution.id}/approve/")
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# RejectExecutionView — POST (branche else)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRejectExecutionViewExtra(TestCase):
    """Branche update_status None → direct save."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="rejector_extra", profile="DBOPS")
        self.integration = IntegrationFactory(type="aap", name="Test AAP Reject")
        self.action = ActionFactory(status="published", integration=self.integration)
        self.client.force_authenticate(user=self.admin)
        RejectExecutionView._execution_service_class = ExecutionService

    def tearDown(self):
        RejectExecutionView._execution_service_class = ExecutionService

    # 3.7 update_status retourne None → branche else (direct save)
    def test_reject_update_status_none_uses_direct_save(self):
        """Si update_status retourne None → branche else : direct save sur l'objet."""
        requester = UserFactory(username="requester_reject_none", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="production",
        )

        class _MockSvcRejectNone:
            def update_status(self_svc, *args, **kwargs):
                return None  # Simule retour None → branche else

        RejectExecutionView._execution_service_class = _MockSvcRejectNone

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            data={"rejection_reason": "Branche else test"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.REJECTED)
        self.assertEqual(execution.error_message, "Branche else test")


# ---------------------------------------------------------------------------
# Story 59.1 — _check_approver_permission fail-secure (SEC-1)
# ---------------------------------------------------------------------------

def _make_mock_user(profile_id=None, is_approver=False):
    """Helper : crée un user mock avec profil ORM."""
    user = MagicMock()
    user.is_authenticated = True
    if profile_id is not None:
        profile = MagicMock()
        profile.id = profile_id
        profile.is_approver_bool = is_approver
        user.profile = profile
    else:
        user.profile = None
    # Désactiver M2M profiles et ad_groups pour isolation
    del user.profiles
    del user.ad_groups
    return user


class TestCheckApproverPermissionFailSecure59_1(TestCase):
    """Tests unitaires Story 59.1 — fail-secure pour _check_approver_permission."""

    def test_absent_approver_profile_ids_returns_false(self):
        """AC1+4 : approver_profile_ids absent dans step_config → False."""
        user = _make_mock_user(profile_id=1, is_approver=True)
        result = _check_approver_permission(user, {})
        self.assertFalse(result)

    def test_empty_approver_profile_ids_returns_false(self):
        """AC1+4 : approver_profile_ids=[] → False."""
        user = _make_mock_user(profile_id=1, is_approver=True)
        result = _check_approver_permission(user, {'approver_profile_ids': []})
        self.assertFalse(result)

    def test_null_approver_profile_ids_returns_false(self):
        """AC1 : approver_profile_ids=None → False (falsy)."""
        user = _make_mock_user(profile_id=1, is_approver=True)
        result = _check_approver_permission(user, {'approver_profile_ids': None})
        self.assertFalse(result)

    def test_authorized_user_with_nonempty_approver_ids_returns_true(self):
        """AC4 (régression) : approver_profile_ids non vide + user autorisé → True."""
        user = _make_mock_user(profile_id=1, is_approver=False)
        result = _check_approver_permission(user, {'approver_profile_ids': [1, 2, 3]})
        self.assertTrue(result)

    def test_unauthorized_user_with_nonempty_approver_ids_returns_false(self):
        """AC4 (régression) : approver_profile_ids non vide + user non autorisé → False."""
        user = _make_mock_user(profile_id=99, is_approver=True)
        result = _check_approver_permission(user, {'approver_profile_ids': [1, 2, 3]})
        self.assertFalse(result)

    def test_warning_logged_when_approver_profile_ids_absent(self):
        """AC2 : warning structlog loggé quand approver_profile_ids absent."""
        user = _make_mock_user(profile_id=1, is_approver=True)
        with structlog.testing.capture_logs() as cap_logs:
            _check_approver_permission(user, {})
        self.assertEqual(len(cap_logs), 1)
        self.assertEqual(cap_logs[0]['log_level'], 'warning')
        self.assertEqual(cap_logs[0]['event'], 'approver_permission_fail_secure')

    def test_warning_logged_when_approver_profile_ids_empty(self):
        """AC2 : warning structlog loggé quand approver_profile_ids vide."""
        user = _make_mock_user(profile_id=1, is_approver=True)
        with structlog.testing.capture_logs() as cap_logs:
            _check_approver_permission(user, {'approver_profile_ids': []})
        self.assertEqual(len(cap_logs), 1)
        self.assertEqual(cap_logs[0]['log_level'], 'warning')
        self.assertEqual(cap_logs[0]['event'], 'approver_permission_fail_secure')

    def test_no_warning_when_approver_profile_ids_present(self):
        """Pas de warning quand approver_profile_ids est configuré."""
        user = _make_mock_user(profile_id=1, is_approver=False)
        with structlog.testing.capture_logs() as cap_logs:
            _check_approver_permission(user, {'approver_profile_ids': [1]})
        self.assertEqual(len(cap_logs), 0)
