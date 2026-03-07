"""Tests Story 58.4 AC3 — ApproveStepView et RejectStepView avec approver_profile_ids.

Ces tests vérifient que :
- User avec profil dans approver_profile_ids → 200 OK
- User sans profil dans approver_profile_ids → 403 Forbidden
- Step sans approver_profile_ids, user is_approver=True → 200 OK
- Step sans approver_profile_ids, user non-is_approver → 403 Forbidden
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
from tests.factories import ActionFactory, ExecutionFactory, IntegrationFactory


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
    })
    step.save()
    return step


def _make_profile(name="Approver Profile", is_approver=True):
    """Crée un profil Profile ORM."""
    return Profile.objects.create(
        name=name,
        ad_group=f"GRP-{name.upper().replace(' ', '-')}",
        is_admin=0,
        is_approver=1 if is_approver else 0,
    )


def _make_user_with_profile(username, profile_orm):
    """Crée un User avec un Profile ORM attaché via le champ 'profile'."""
    from idp_auth.models import User
    user = User.objects.create(username=username, profile=profile_orm)
    return user


@pytest.mark.django_db
class TestApproveStepViewPermission58_4(TestCase):
    """Tests pour ApproveStepView avec approver_profile_ids — Story 58.4 AC3."""

    def setUp(self):
        self.client = APIClient()
        self.integration = IntegrationFactory(type="aap")

    def _make_action_with_approver_ids(self, approver_profile_ids=None):
        step_config = {
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
        }
        if approver_profile_ids is not None:
            step_config["approver_profile_ids"] = approver_profile_ids
        return ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[step_config],
        )

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_user_with_profile_in_approver_list_can_approve(self, mock_resume):
        """User avec profil dans approver_profile_ids → 200 OK."""
        profile = _make_profile("DBA Approver", is_approver=False)
        user = _make_user_with_profile("approver_58_4_a", profile)
        self.client.force_authenticate(user=user)

        action = self._make_action_with_approver_ids(approver_profile_ids=[profile.id])
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_user_without_profile_in_approver_list_is_forbidden(self):
        """User sans profil dans approver_profile_ids → 403 Forbidden."""
        profile_allowed = _make_profile("Allowed Profile", is_approver=True)
        profile_user = _make_profile("User Profile", is_approver=True)
        user = _make_user_with_profile("non_approver_58_4_b", profile_user)
        self.client.force_authenticate(user=user)

        # Step config allows only profile_allowed, not profile_user
        action = self._make_action_with_approver_ids(approver_profile_ids=[profile_allowed.id])
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_fallback_user_with_is_approver_can_approve(self, mock_resume):
        """Step sans approver_profile_ids, user is_approver=True → 200 OK."""
        profile = _make_profile("Fallback Approver", is_approver=True)
        user = _make_user_with_profile("fallback_approver_58_4_c", profile)
        self.client.force_authenticate(user=user)

        action = self._make_action_with_approver_ids(approver_profile_ids=None)
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_fallback_user_without_is_approver_is_forbidden(self):
        """Step sans approver_profile_ids, user non is_approver → 403 Forbidden."""
        profile = _make_profile("Regular Profile", is_approver=False)
        user = _make_user_with_profile("non_approver_fallback_58_4_d", profile)
        self.client.force_authenticate(user=user)

        action = self._make_action_with_approver_ids(approver_profile_ids=None)
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/approve/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class TestRejectStepViewPermission58_4(TestCase):
    """Tests pour RejectStepView avec approver_profile_ids — Story 58.4 AC3."""

    def setUp(self):
        self.client = APIClient()
        self.integration = IntegrationFactory(type="aap")

    def _make_action_with_approver_ids(self, approver_profile_ids=None):
        step_config = {
            "step_id": "request-approval",
            "name": "request-approval",
            "step_type": "gate",
            "gate_type": "approval",
        }
        if approver_profile_ids is not None:
            step_config["approver_profile_ids"] = approver_profile_ids
        return ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[step_config],
        )

    @patch('executions.views.approval_views.resume_container_workflow_from_gate')
    def test_user_with_profile_in_approver_list_can_reject(self, mock_resume):
        """User avec profil dans approver_profile_ids → 200 OK pour reject."""
        profile = _make_profile("Reject Approver", is_approver=False)
        user = _make_user_with_profile("reject_approver_58_4_e", profile)
        self.client.force_authenticate(user=user)

        action = self._make_action_with_approver_ids(approver_profile_ids=[profile.id])
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/reject/",
            {"comment": "Rejeté"},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_user_without_profile_in_approver_list_cannot_reject(self):
        """User sans profil dans approver_profile_ids → 403 Forbidden pour reject."""
        profile_allowed = _make_profile("Reject Allowed Profile", is_approver=True)
        profile_user = _make_profile("Reject User Profile", is_approver=True)
        user = _make_user_with_profile("reject_non_approver_58_4_f", profile_user)
        self.client.force_authenticate(user=user)

        action = self._make_action_with_approver_ids(approver_profile_ids=[profile_allowed.id])
        execution = ExecutionFactory(action=action, user=user, status=ExecutionStatus.RUNNING)
        step = _make_approval_step(execution)

        response = self.client.post(
            f"/api/v1/executions/{execution.id}/steps/{step.id}/reject/",
            format='json',
        )
        self.assertEqual(response.status_code, 403)
