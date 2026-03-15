"""Tests pour ApproveStepView, RejectStepView et backward compat — Story 57.8."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from executions.models import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStepType,
)
from tests.factories import ActionFactory, ExecutionFactory, IntegrationFactory, UserFactory


def _make_approval_step(execution, step_name="request-approval", step_order=1):
    """Crée un step WAITING avec gate_conditions approval_granted."""
    step = ExecutionStep.objects.create(
        execution=execution,
        step_order=step_order,
        step_name=step_name,
        step_type=ExecutionStepType.GATE,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        "gate_conditions": [{"type": "approval_granted", "timeout_hours": 72}],
        "context_from": ["tf-plan"],
    })
    step.save()
    return step


@pytest.mark.django_db
class TestApproveStepView(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="step_approver_57_8", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval",
                "name": "request-approval",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": ["execute-action"],
                "on_error_step_ids": ["notify-rejected"],
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step(self.execution)

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_approve_step_success_with_successor(self, mock_perm):
        """AC#1 : approve → 202 accepted, commande écrite (story 78.5).

        Story 78.5: L'endpoint écrit une commande durable ; le step reste WAITING
        jusqu'au traitement par le command processor.
        """
        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            {"comment": "LGTM"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"]["status"], "accepted")
        self.assertIn("command_id", data["data"])

        # Story 78.5: commande écrite, step non traité inline
        self.step.refresh_from_db()
        self.assertEqual(self.step.status, ExecutionStepStatus.WAITING)

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_approve_step_success_last_step_completes_execution(self, mock_perm):
        """AC#1 : approve sans on_success_step_ids → 202 accepted, commande écrite (story 78.5)."""
        self.action.execution_steps = [{
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
            # pas de on_success_step_ids
        }]
        self.action.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            {"comment": "OK"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")

    def test_approve_step_not_waiting_returns_400(self):
        """AC#3 : step non WAITING → 400."""
        self.step.status = ExecutionStepStatus.RUNNING
        self.step.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_step_wrong_gate_type_returns_400(self):
        """AC#3 : step WAITING mais gate maintenance_window → 400."""
        self.step.set_output({"gate_conditions": [{"type": "maintenance_window"}]})
        self.step.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_approve_step_not_found_returns_404(self):
        """Step inexistant → 404."""
        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/99999/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_step_wrong_execution_returns_404(self):
        """Step d'une autre exécution → 404 (pas de fuite)."""
        other_exec = ExecutionFactory(action=self.action, user=self.admin)
        response = self.client.post(
            f"/api/v1/executions/{other_exec.id}/steps/{self.step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_step_non_approver_is_forbidden(self):
        """Story 58.4 : utilisateur sans profil is_approver → 403 Forbidden."""
        non_admin = UserFactory(username="regular_user_57_8", profile="READ_ONLY")
        self.client.force_authenticate(user=non_admin)
        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class TestRejectStepView(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="step_rejector_57_8", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval",
                "name": "request-approval",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": ["execute-action"],
                "on_error_step_ids": ["notify-rejected"],
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step(self.execution)

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_reject_step_success_with_error_path(self, mock_perm):
        """AC#2 : reject → 202 accepted, commande écrite (story 78.5)."""
        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
            {"comment": "Rejected"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"]["status"], "accepted")
        self.assertIn("command_id", data["data"])

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_reject_step_no_error_path_fails_execution(self, mock_perm):
        """AC#2 : reject sans on_error_step_ids → 202 accepted, commande écrite (story 78.5)."""
        self.action.execution_steps = [{
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
            # pas de on_error_step_ids
        }]
        self.action.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")

    def test_reject_step_not_waiting_returns_400(self):
        """AC#3 : step non WAITING → 400."""
        self.step.status = ExecutionStepStatus.RUNNING
        self.step.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)


@pytest.mark.django_db
class TestApproveExecutionBackwardCompat(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="compat_approver_57_8", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval",
                "name": "request-approval",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": ["execute-action"],
            }]
        )

    def test_no_waiting_step_returns_400(self):
        """ADR-007: execution without WAITING approval step -> 400 NO_PENDING_APPROVAL."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.SUBMITTED,
        )
        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_backward_compat_finds_first_waiting_approval_step(self, mock_perm):
        """AC#4 : exécution RUNNING avec step WAITING → 202 accepted, commande écrite (story 78.5)."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")

    def test_backward_compat_no_waiting_step_raises_original_error(self):
        """AC#4 : exécution RUNNING sans step WAITING approval_granted → 400 original."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        # No WAITING step with approval_granted

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_auto_approval_gate_non_admin_is_forbidden(self):
        """ADR-007: auto-approval-gate + user non-admin -> 403 Forbidden."""
        non_admin = UserFactory(username="non_admin_approve_58_4", profile="READ_ONLY")
        self.client.force_authenticate(user=non_admin)
        execution = ExecutionFactory(
            action=self.action,
            user=non_admin,
            status=ExecutionStatus.SUBMITTED,
        )
        # Create auto-approval-gate step
        step = ExecutionStep.objects.create(
            execution=execution,
            step_order=0,
            step_name="Approval Gate",
            config_step_id="auto-approval-gate",
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({
            "gate_conditions": [{"type": "approval_granted"}],
            "gate_status": [{"type": "approval_granted", "satisfied": False}],
        })
        step.save()

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_step_gate_non_approver_is_forbidden(self):
        """Story 58.4 AC3 : RUNNING + step gate + user non-approbateur → 403 Forbidden."""
        non_approver = UserFactory(username="non_approver_step_gate_58_4", profile="READ_ONLY")
        self.client.force_authenticate(user=non_approver)
        execution = ExecutionFactory(
            action=self.action,
            user=non_approver,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        with patch('executions.views.approval_views._check_approver_permission', return_value=False):
            response = self.client.post(
                f"/api/v1/executions/{execution.id}/approve/",
                format='json',
            )
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class TestRejectExecutionBackwardCompat(TestCase):
    """Tests backward compat pour RejectExecutionView — Story 58.1."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="compat_rejector_58_1", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval",
                "name": "request-approval",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": ["execute-action"],
                "on_error_step_ids": ["notify-rejected"],
            }]
        )

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_running_execution_with_waiting_step_reject_with_error_path(self, mock_perm):
        """AC#1 : RUNNING + step WAITING → 202 accepted, commande écrite (story 78.5)."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            {"rejection_reason": "Non conforme"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"]["status"], "accepted")
        self.assertIn("command_id", data["data"])

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_running_execution_with_waiting_step_reject_no_error_path(self, mock_perm):
        """AC#1 : RUNNING + step WAITING sans on_error_step_ids → 202 accepted (story 78.5)."""
        self.action.execution_steps = [{
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
            # pas de on_error_step_id
        }]
        self.action.save()

        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")

    def test_running_execution_no_waiting_step_returns_400(self):
        """AC#4 : RUNNING sans step WAITING approval_granted -> 400 NO_PENDING_APPROVAL."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        # Pas de step WAITING avec approval_granted

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("error", {}).get("code"), "NO_PENDING_APPROVAL")

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    def test_rejection_reason_captured_in_approval_comment(self, mock_perm):
        """AC#1 : rejection avec rejection_reason → 202 accepted, commande écrite (story 78.5)."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            {"rejection_reason": "Audit requis"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["data"]["status"], "accepted")

    def test_auto_approval_gate_non_admin_is_forbidden_reject(self):
        """ADR-007: auto-approval-gate + user non-admin -> 403 Forbidden (reject)."""
        non_admin = UserFactory(username="non_admin_reject_58_4", profile="READ_ONLY")
        self.client.force_authenticate(user=non_admin)
        execution = ExecutionFactory(
            action=self.action,
            user=non_admin,
            status=ExecutionStatus.SUBMITTED,
        )
        step = ExecutionStep.objects.create(
            execution=execution,
            step_order=0,
            step_name="Approval Gate",
            config_step_id="auto-approval-gate",
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({
            "gate_conditions": [{"type": "approval_granted"}],
            "gate_status": [{"type": "approval_granted", "satisfied": False}],
        })
        step.save()

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_step_gate_non_approver_is_forbidden_reject(self):
        """Story 58.4 AC3 : RUNNING + step gate + user non-approbateur → 403 Forbidden (reject)."""
        non_approver = UserFactory(username="non_approver_step_gate_reject_58_4", profile="READ_ONLY")
        self.client.force_authenticate(user=non_approver)
        execution = ExecutionFactory(
            action=self.action,
            user=non_approver,
            status=ExecutionStatus.RUNNING,
        )
        _make_approval_step(execution)

        with patch('executions.views.approval_views._check_approver_permission', return_value=False):
            response = self.client.post(
                f"/api/v1/executions/{execution.id}/reject/",
                format='json',
            )
        self.assertEqual(response.status_code, 403)
