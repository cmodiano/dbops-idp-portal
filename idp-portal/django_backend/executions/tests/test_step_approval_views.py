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
                "on_success_step_id": "execute-action",
                "on_error_step_id": "notify-rejected",
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step(self.execution)

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_approve_step_success_with_successor(self, mock_resume):
        """AC#1 : approve → COMPLETED + resume vers on_success_step_id."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
                {"comment": "LGTM"},
                format='json',
            )
        self.assertEqual(response.status_code, 200)

        self.step.refresh_from_db()
        self.assertEqual(self.step.status, ExecutionStepStatus.COMPLETED)
        self.assertEqual(self.step.approval_comment, "LGTM")
        self.assertIsNotNone(self.step.approved_by)
        self.assertIsNotNone(self.step.approved_at)

        data = response.json()
        self.assertIn("data", data)
        step_data = data["data"]
        self.assertEqual(step_data["status"], ExecutionStepStatus.COMPLETED)
        self.assertIn("approved_by_id", step_data)
        self.assertIn("approved_at", step_data)
        self.assertEqual(step_data["approval_comment"], "LGTM")

        # Vérifie que la tâche Celery de resume est bien déclenchée
        mock_resume.apply_async.assert_called_once_with(
            args=[self.execution.id, "execute-action"]
        )

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_approve_step_success_last_step_completes_execution(self, mock_resume):
        """AC#1 : approve sans on_success_step_id → execution COMPLETED, aucun resume."""
        self.action.execution_steps = [{
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
            # pas de on_success_step_id
        }]
        self.action.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
            {"comment": "OK"},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, ExecutionStatus.COMPLETED)
        # Aucun resume ne doit être déclenché (dernier step)
        mock_resume.apply_async.assert_not_called()

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

    def test_approve_step_requires_dba_dbops(self):
        """Utilisateur sans permission → 403."""
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
                "on_success_step_id": "execute-action",
                "on_error_step_id": "notify-rejected",
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step(self.execution)

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_reject_step_success_with_error_path(self, mock_resume):
        """AC#2 : reject avec on_error_step_id → step FAILED, resume appelée."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
                {"comment": "Rejected"},
                format='json',
            )
        self.assertEqual(response.status_code, 200)

        self.step.refresh_from_db()
        self.assertEqual(self.step.status, ExecutionStepStatus.FAILED)
        self.assertEqual(self.step.approval_comment, "Rejected")

        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"]["status"], ExecutionStepStatus.FAILED)
        self.assertEqual(data["data"]["approval_comment"], "Rejected")

        # Vérifie que la tâche Celery de resume est déclenchée avec le chemin d'erreur
        mock_resume.apply_async.assert_called_once_with(
            args=[self.execution.id, "notify-rejected"]
        )

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_reject_step_no_error_path_fails_execution(self, mock_resume):
        """AC#2 : reject sans on_error_step_id → execution FAILED, aucun resume."""
        self.action.execution_steps = [{
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
            # pas de on_error_step_id
        }]
        self.action.save()

        response = self.client.post(
            f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, ExecutionStatus.FAILED)
        self.assertEqual(self.execution.error_message, 'Step approval rejected')
        # Aucun resume ne doit être déclenché (pas de chemin d'erreur)
        mock_resume.apply_async.assert_not_called()

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
                "on_success_step_id": "execute-action",
            }]
        )

    def test_backward_compat_pending_approval_existing_path(self):
        """AC#4 : exécution PENDING_APPROVAL → comportement existant inchangé (→ RUNNING)."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        with patch('executions.views.approval_views.ExecutionService.launch_workflow'):
            response = self.client.post(
                f"/api/v1/executions/{execution.id}/approve/",
                format='json',
            )
        # Le chemin original PENDING_APPROVAL → RUNNING doit être utilisé
        self.assertEqual(response.status_code, 200)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_backward_compat_finds_first_waiting_approval_step(self, mock_resume):
        """AC#4 : exécution RUNNING avec step WAITING approval_granted → approuve le step."""
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        step.refresh_from_db()
        self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)

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
