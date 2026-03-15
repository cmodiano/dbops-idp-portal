"""Tests Story 77.5 : Side effects approve/reject déférés dans on_commit.

AC1 — emit_approval_granted et RunnableStepService.delete ne s'exécutent pas avant le commit.
AC2 — emit_approval_rejected et RunnableStepService.delete ne s'exécutent pas avant le commit.
AC3 — En cas de rollback, aucun side effect durable n'est émis.
"""
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
        "context_from": [],
    })
    step.save()
    return step


@pytest.mark.django_db
class TestStory775SideEffectsOnCommit(TestCase):
    """Tests AC1, AC2, AC3 : side effects approve/reject déférés via transaction.on_commit."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="approver_77_5", profile="DBOPS")
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
                "on_success_step_ids": [],
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step(self.execution)

    # ──────────────────────────────────────────────────────────────────────
    # AC1 — ApproveStepView
    # ──────────────────────────────────────────────────────────────────────

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_granted')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_approve_side_effects_not_called_before_commit(self, mock_delete, mock_emit, mock_perm):
        """AC1 : emit_approval_granted et delete ne s'exécutent PAS avant le commit."""
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
                {"comment": "LGTM"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        # Avant commit : aucun side effect ne doit avoir été appelé
        mock_emit.assert_not_called()
        mock_delete.assert_not_called()

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_granted')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_approve_side_effects_called_after_commit(self, mock_delete, mock_emit, mock_perm):
        """AC1 : emit_approval_granted et delete sont appelés APRÈS le commit."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
                {"comment": "LGTM"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        mock_emit.assert_called_once()
        mock_delete.assert_called_once_with(self.step.id)

    # ──────────────────────────────────────────────────────────────────────
    # AC2 — RejectStepView
    # ──────────────────────────────────────────────────────────────────────

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_rejected')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_reject_side_effects_not_called_before_commit(self, mock_delete, mock_emit, mock_perm):
        """AC2 : emit_approval_rejected et delete ne s'exécutent PAS avant le commit."""
        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
                {"comment": "Non approuvé"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        mock_emit.assert_not_called()
        mock_delete.assert_not_called()

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_rejected')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_reject_side_effects_called_after_commit(self, mock_delete, mock_emit, mock_perm):
        """AC2 : emit_approval_rejected et delete sont appelés APRÈS le commit."""
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
                {"comment": "Non approuvé"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        mock_emit.assert_called_once()
        mock_delete.assert_called_once_with(self.step.id)

    # ──────────────────────────────────────────────────────────────────────
    # AC3 — Pas d'émission en cas de rollback (approve)
    # ──────────────────────────────────────────────────────────────────────

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_granted')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_approve_rollback_no_side_effects(self, mock_delete, mock_emit, mock_perm):
        """AC3 — approve : les callbacks on_commit sont enregistrés mais pas exécutés (rollback simulé).

        Vérifie deux propriétés distinctes de test_approve_side_effects_not_called_before_commit :
        1. Au moins un callback on_commit a été enregistré (preuve que le pattern on_commit est actif)
        2. Les mocks ne sont pas appelés (callbacks non exécutés = équivalent rollback)
        """
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
                {"comment": "LGTM"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        # Le callback on_commit a bien été enregistré (pattern en place)
        self.assertGreater(len(callbacks), 0, "Expected at least one on_commit callback to be registered")
        # Mais non exécuté (simulate rollback : side effects durables non émis)
        mock_emit.assert_not_called()
        mock_delete.assert_not_called()

    # ──────────────────────────────────────────────────────────────────────
    # AC3 — Pas d'émission en cas de rollback (reject)
    # ──────────────────────────────────────────────────────────────────────

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_rejected')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_reject_rollback_no_side_effects(self, mock_delete, mock_emit, mock_perm):
        """AC3 — reject : les callbacks on_commit sont enregistrés mais pas exécutés (rollback simulé).

        Symétrique du test approve : vérifie que le chemin reject respecte également AC3.
        """
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/reject/",
                {"comment": "Non approuvé"},
                format='json',
            )
        self.assertEqual(response.status_code, 202)
        # Le callback on_commit a bien été enregistré (pattern en place)
        self.assertGreater(len(callbacks), 0, "Expected at least one on_commit callback to be registered")
        # Mais non exécuté (simulate rollback : side effects durables non émis)
        mock_emit.assert_not_called()
        mock_delete.assert_not_called()
