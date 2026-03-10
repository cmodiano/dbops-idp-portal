"""
Story 61.7 — Enrichissement audit approbation/rejet
Vérifie que EXECUTION_APPROVED et EXECUTION_REJECTED incluent action_name, targets, parameters.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import AuditLog
from executions.models import (
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStepType,
)
from tests.factories import (
    ActionFactory,
    ExecutionFactory,
    ExecutionTargetFactory,
    IntegrationFactory,
    UserFactory,
)


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
        "on_success_step_ids": ["next-step"],
        "on_error_step_ids": ["error-step"],
    })
    step.save()
    return step


@pytest.mark.django_db
class TestApproveAuditContext(TestCase):
    """AC1 : EXECUTION_APPROVED (PENDING_APPROVAL) contient action_name, targets, parameters."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="approver_61_7", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap", name="AAP 61-7 Approve")
        self.action = ActionFactory(status="published", integration=self.integration)

    def _approve(self, execution_id):
        with patch("executions.views.approval_views.ExecutionService.launch_workflow"):
            return self.client.post(f"/api/v1/executions/{execution_id}/approve/")

    def _get_audit(self, execution_id):
        return AuditLog.objects.filter(
            action_type="EXECUTION_APPROVED",
            entity_id=execution_id,
        ).first()

    def test_approve_includes_targets_and_parameters(self):
        """AC1 — targets et parameters présents dans details."""
        requester = UserFactory(username="req_approve_ctx_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        ExecutionTargetFactory(
            execution=execution,
            target_type="SERVER",
            target_id="srv-prod-01",
            target_name="oracle-prod-01",
        )

        response = self._approve(execution.id)
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        # action_name déjà présent avant la story — vérifié pour non-régression
        self.assertIn("action_name", details)
        self.assertEqual(details["action_name"], self.action.name)

        # Nouveaux champs AC1
        self.assertIn("targets", details)
        self.assertIn("oracle-prod-01", details["targets"])
        self.assertIn("parameters", details)

    def test_approve_targets_absent_when_no_targets(self):
        """AC7 — targets absent si l'exécution n'a pas de targets."""
        requester = UserFactory(username="req_approve_notarget_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        # Aucun ExecutionTarget créé

        response = self._approve(execution.id)
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        details = json.loads(audit.details)
        self.assertNotIn("targets", details)

    def test_approve_parameters_absent_when_no_parameters(self):
        """AC8 — parameters absent si l'exécution n'a pas de paramètres."""
        requester = UserFactory(username="req_approve_noparam_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
            parameters=None,
        )

        response = self._approve(execution.id)
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        details = json.loads(audit.details)
        self.assertNotIn("parameters", details)


@pytest.mark.django_db
class TestRejectAuditContext(TestCase):
    """AC2 : EXECUTION_REJECTED (PENDING_APPROVAL) contient action_name, targets, parameters."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="rejector_61_7", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap", name="AAP 61-7 Reject")
        self.action = ActionFactory(status="published", integration=self.integration)

    def _reject(self, execution_id, reason=""):
        return self.client.post(
            f"/api/v1/executions/{execution_id}/reject/",
            data={"rejection_reason": reason},
            format="json",
        )

    def _get_audit(self, execution_id):
        return AuditLog.objects.filter(
            action_type="EXECUTION_REJECTED",
            entity_id=execution_id,
        ).first()

    def test_reject_includes_targets_and_parameters(self):
        """AC2 — targets et parameters présents dans details."""
        requester = UserFactory(username="req_reject_ctx_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )
        ExecutionTargetFactory(
            execution=execution,
            target_type="DATABASE",
            target_id="db-prod-01",
            target_name="oracle-prod-db",
        )

        response = self._reject(execution.id, reason="Fenêtre de maintenance dépassée")
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        self.assertIn("action_name", details)
        self.assertIn("targets", details)
        self.assertIn("oracle-prod-db", details["targets"])
        self.assertIn("parameters", details)
        # rejection_reason toujours présent (non-régression)
        self.assertEqual(details["rejection_reason"], "Fenêtre de maintenance dépassée")

    def test_reject_targets_absent_when_no_targets(self):
        """AC7 — targets absent si pas de targets."""
        requester = UserFactory(username="req_reject_notarget_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
        )

        response = self._reject(execution.id)
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        details = json.loads(audit.details)
        self.assertNotIn("targets", details)

    def test_reject_parameters_absent_when_no_parameters(self):
        """AC8 — parameters absent si pas de paramètres."""
        requester = UserFactory(username="req_reject_noparam_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.PENDING_APPROVAL,
            environment="prod",
            parameters=None,
        )

        response = self._reject(execution.id)
        self.assertEqual(response.status_code, 200)

        audit = self._get_audit(execution.id)
        details = json.loads(audit.details)
        self.assertNotIn("parameters", details)


@pytest.mark.django_db
class TestStepApproveAuditContext(TestCase):
    """AC5, AC6 : ApproveStepView et RejectStepView incluent action_name, targets, parameters."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="step_approver_61_7", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap", name="AAP 61-7 Step")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval",
                "name": "request-approval",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": ["next-step"],
                "on_error_step_ids": ["error-step"],
            }],
        )

    def _make_execution_with_step(self, with_target=True, with_parameters=True):
        execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        if not with_parameters:
            execution.parameters = None
            execution.save(update_fields=["parameters"])
        if with_target:
            ExecutionTargetFactory(
                execution=execution,
                target_type="SERVER",
                target_id="srv-step-01",
                target_name="oracle-step-01",
            )
        step = _make_approval_step(execution)
        return execution, step

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_approve_step_includes_action_name_targets_parameters(self, _mock_perm):
        """AC5 — ApproveStepView : details contient action_name, targets, parameters."""
        execution, step = self._make_execution_with_step(with_target=True, with_parameters=True)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            {"comment": "LGTM"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_APPROVED",
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        self.assertIn("action_name", details)
        self.assertEqual(details["action_name"], self.action.name)
        self.assertIn("targets", details)
        self.assertIn("oracle-step-01", details["targets"])
        self.assertIn("parameters", details)

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_reject_step_includes_action_name_targets_parameters(self, _mock_perm):
        """AC6 — RejectStepView : details contient action_name, targets, parameters."""
        execution, step = self._make_execution_with_step(with_target=True, with_parameters=True)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/reject/",
            {"comment": "Non conforme"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_REJECTED",
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        self.assertIn("action_name", details)
        self.assertEqual(details["action_name"], self.action.name)
        self.assertIn("targets", details)
        self.assertIn("oracle-step-01", details["targets"])
        self.assertIn("parameters", details)

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_approve_step_targets_absent_when_no_targets(self, _mock_perm):
        """AC7 — ApproveStepView : targets absent si pas de targets."""
        execution, step = self._make_execution_with_step(with_target=False, with_parameters=True)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_APPROVED",
            entity_id=execution.id,
        ).first()
        details = json.loads(audit.details)
        self.assertNotIn("targets", details)

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_approve_step_parameters_absent_when_no_parameters(self, _mock_perm):
        """AC8 — ApproveStepView : parameters absent si pas de paramètres."""
        execution, step = self._make_execution_with_step(with_target=False, with_parameters=False)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_APPROVED",
            entity_id=execution.id,
        ).first()
        details = json.loads(audit.details)
        self.assertNotIn("parameters", details)


@pytest.mark.django_db
class TestLegacyBackwardCompatAuditContext(TestCase):
    """AC3, AC4 : Chemins backward compat (ApproveExecutionView/RejectExecutionView via step gate)
    incluent action_name, targets, parameters dans les details d'audit."""

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="bc_approver_61_7", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap", name="AAP 61-7 BC")
        self.action = ActionFactory(status="published", integration=self.integration)

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_approve_via_backward_compat_includes_action_name_targets_parameters(self, _mock_perm):
        """AC3 — ApproveExecutionView backward compat : details contient action_name, targets, parameters."""
        requester = UserFactory(username="req_bc_approve_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTargetFactory(
            execution=execution,
            target_type="SERVER",
            target_id="srv-bc-01",
            target_name="oracle-bc-01",
        )
        _make_approval_step(execution)

        response = self.client.post(f"/api/v1/executions/{execution.id}/approve/")
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_APPROVED",
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        self.assertIn("action_name", details)
        self.assertEqual(details["action_name"], self.action.name)
        self.assertIn("targets", details)
        self.assertIn("oracle-bc-01", details["targets"])
        self.assertIn("parameters", details)
        self.assertTrue(details.get("via_legacy_endpoint"))

    @patch("executions.views.approval_views._check_approver_permission", return_value=True)
    def test_reject_via_backward_compat_includes_action_name_targets_parameters(self, _mock_perm):
        """AC4 — RejectExecutionView backward compat : details contient action_name, targets, parameters."""
        requester = UserFactory(username="req_bc_reject_61_7", profile="DBA")
        execution = ExecutionFactory(
            action=self.action,
            user=requester,
            status=ExecutionStatus.RUNNING,
        )
        ExecutionTargetFactory(
            execution=execution,
            target_type="DATABASE",
            target_id="db-bc-01",
            target_name="oracle-bc-db",
        )
        _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            data={"rejection_reason": "Fenêtre de maintenance fermée"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        audit = AuditLog.objects.filter(
            action_type="EXECUTION_REJECTED",
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)

        self.assertIn("action_name", details)
        self.assertEqual(details["action_name"], self.action.name)
        self.assertIn("targets", details)
        self.assertIn("oracle-bc-db", details["targets"])
        self.assertIn("parameters", details)
        self.assertTrue(details.get("via_legacy_endpoint"))
