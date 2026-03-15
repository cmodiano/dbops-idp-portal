"""Tests d'intégration Story 58.4 — approver_profile_ids bout-en-bout.

Scénarios :
- AC3 : workflow step gate + approver_profile_ids → seul l'user avec profil X peut approuver
- AC5 : step sans approver_profile_ids → tout is_approver=True peut approuver
- AC5 : exécution PENDING_APPROVAL → seul admin peut approuver (behavior unchanged)
- Chemin legacy reject (AC3/AC5)
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
from profiles.models import Profile
from tests.factories import ActionFactory, ExecutionFactory, IntegrationFactory, UserFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(name, is_approver=True, is_admin=False):
    return Profile.objects.create(
        name=name,
        ad_group=f"GRP-{name.upper().replace(' ', '-')}",
        is_admin=1 if is_admin else 0,
        is_approver=1 if is_approver else 0,
    )


def _make_user_with_orm_profile(username, profile_orm):
    from idp_auth.models import User
    return User.objects.create(username=username, profile=profile_orm)


def _make_approval_step(execution, step_name="gate-step"):
    step = ExecutionStep.objects.create(
        execution=execution,
        step_order=1,
        step_name=step_name,
        step_type=ExecutionStepType.GATE,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        "gate_conditions": [{"type": "approval_granted", "timeout_hours": 72}],
    })
    step.save()
    return step


# ---------------------------------------------------------------------------
# Test 1 : Workflow step gate avec approver_profile_ids — seul le bon profil peut approuver
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIntegrationApproverProfileIds(TestCase):
    """AC3 : approver_profile_ids restreint les approbateurs à des profils spécifiques."""

    def setUp(self):
        self.client = APIClient()
        self.integration = IntegrationFactory(type="aap")

        # Deux profils : seul allowed_profile est dans approver_profile_ids
        self.allowed_profile = _make_profile("Integration Allowed", is_approver=False)
        self.other_profile = _make_profile("Integration Other", is_approver=True)

        self.allowed_user = _make_user_with_orm_profile("integ_allowed_user_58_4", self.allowed_profile)
        self.other_user = _make_user_with_orm_profile("integ_other_user_58_4", self.other_profile)

        # Action avec approver_profile_ids restreint au profil allowed
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "gate-step",
                "name": "gate-step",
                "step_type": "gate",
                "gate_type": "approval",
                "approver_profile_ids": [self.allowed_profile.id],
            }]
        )

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_user_with_allowed_profile_can_approve(self, mock_resume):
        """User avec profil dans approver_profile_ids peut approuver le step."""
        self.client.force_authenticate(user=self.allowed_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.allowed_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        step.refresh_from_db()
        self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)

    def test_user_without_allowed_profile_cannot_approve(self):
        """User avec profil hors approver_profile_ids → 403 Forbidden."""
        self.client.force_authenticate(user=self.other_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.other_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_user_with_allowed_profile_can_reject(self, mock_resume):
        """User avec profil dans approver_profile_ids peut rejeter le step."""
        self.client.force_authenticate(user=self.allowed_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.allowed_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/reject/",
            {"comment": "Refusé"},
            format='json',
        )
        self.assertEqual(response.status_code, 202)
        step.refresh_from_db()
        self.assertEqual(step.status, ExecutionStepStatus.FAILED)

    def test_user_without_allowed_profile_cannot_reject(self):
        """User avec profil hors approver_profile_ids → 403 Forbidden (reject)."""
        self.client.force_authenticate(user=self.other_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.other_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# Test 2 : Fail-secure — step sans approver_profile_ids → 403 (Story 59.1 SEC-1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestIntegrationRetroCompatNoApproverIds(TestCase):
    """Story 59.1 SEC-1 : step sans approver_profile_ids → fail-secure → 403 pour tout le monde."""

    def setUp(self):
        self.client = APIClient()
        self.integration = IntegrationFactory(type="aap")

        self.approver_profile = _make_profile("Retro Approver", is_approver=True)
        self.non_approver_profile = _make_profile("Retro NonApprover", is_approver=False)

        self.approver_user = _make_user_with_orm_profile("retro_approver_58_4", self.approver_profile)
        self.non_approver_user = _make_user_with_orm_profile("retro_non_approver_58_4", self.non_approver_profile)

        # Action SANS approver_profile_ids → fail-secure → 403 pour tout le monde
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "gate-step",
                "name": "gate-step",
                "step_type": "gate",
                "gate_type": "approval",
                # Pas de approver_profile_ids → fail-secure
            }]
        )

    def test_is_approver_user_cannot_approve_without_profile_restriction(self):
        """Story 59.1 SEC-1 : is_approver=True sans approver_profile_ids → 403 fail-secure."""
        self.client.force_authenticate(user=self.approver_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.approver_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_non_approver_user_cannot_approve_without_profile_restriction(self):
        """is_approver=False sans approver_profile_ids → 403 (comportement inchangé)."""
        self.client.force_authenticate(user=self.non_approver_user)
        execution = ExecutionFactory(
            action=self.action,
            user=self.non_approver_user,
            status=ExecutionStatus.RUNNING,
        )
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# Test 3 : ADR-007 — auto-approval-gate → seul admin peut approuver/rejeter
# ---------------------------------------------------------------------------

def _make_auto_approval_gate(execution):
    """Create an auto-approval-gate step (like _create_execution_atomic does)."""
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
    return step


@pytest.mark.django_db
class TestIntegrationRetroCompatPendingApproval(TestCase):
    """ADR-007: auto-approval-gate conserve la restriction admin (IsAdminUser)."""

    def setUp(self):
        self.client = APIClient()
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
        )

    def test_admin_user_can_approve_auto_approval_gate(self):
        """Admin (DBOPS) peut approuver via auto-approval-gate."""
        from executions.services import ExecutionService
        admin_user = UserFactory(username="integ_admin_approve_58_4", profile="DBOPS")
        self.client.force_authenticate(user=admin_user)
        execution = ExecutionFactory(
            action=self.action,
            user=admin_user,
            status=ExecutionStatus.SUBMITTED,
        )
        step = _make_auto_approval_gate(execution)

        def _mock_launch(exec_obj, correlation_id=None):
            exec_obj.status = ExecutionStatus.RUNNING
            exec_obj.save()

        with patch.object(ExecutionService, "launch_workflow", side_effect=_mock_launch):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/v1/executions/{execution.id}/approve/",
                    format='json',
                )
        self.assertEqual(response.status_code, 200)
        # Verify gate and execution state actually changed (test would fail if 200 without advancing)
        step.refresh_from_db()
        self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)
        execution.refresh_from_db()
        self.assertIn(
            execution.status,
            (ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED),
            "Execution must advance from SUBMITTED after approval",
        )

    def test_non_admin_user_cannot_approve_auto_approval_gate(self):
        """Non-admin ne peut PAS approuver via auto-approval-gate."""
        approver_profile = _make_profile("Approver Not Admin", is_approver=True, is_admin=False)
        approver_user = _make_user_with_orm_profile("integ_approver_no_admin_58_4", approver_profile)
        self.client.force_authenticate(user=approver_user)
        execution = ExecutionFactory(
            action=self.action,
            user=approver_user,
            status=ExecutionStatus.SUBMITTED,
        )
        _make_auto_approval_gate(execution)
        response = self.client.post(
            f"/api/v1/executions/{execution.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_reject_auto_approval_gate(self):
        """Admin peut rejeter via auto-approval-gate."""
        admin_user = UserFactory(username="integ_admin_reject_58_4", profile="DBOPS")
        self.client.force_authenticate(user=admin_user)
        execution = ExecutionFactory(
            action=self.action,
            user=admin_user,
            status=ExecutionStatus.SUBMITTED,
        )
        step = _make_auto_approval_gate(execution)
        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            {"rejection_reason": "Refus admin"},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        step.refresh_from_db()
        self.assertEqual(step.status, ExecutionStepStatus.FAILED)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

    def test_non_admin_user_cannot_reject_auto_approval_gate(self):
        """Non-admin ne peut pas rejeter via auto-approval-gate."""
        approver_profile = _make_profile("Approver Reject No Admin", is_approver=True, is_admin=False)
        approver_user = _make_user_with_orm_profile("integ_approver_no_admin_reject_58_4", approver_profile)
        self.client.force_authenticate(user=approver_user)
        execution = ExecutionFactory(
            action=self.action,
            user=approver_user,
            status=ExecutionStatus.SUBMITTED,
        )
        _make_auto_approval_gate(execution)
        response = self.client.post(
            f"/api/v1/executions/{execution.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)
