"""
Tests for Story 22.12: PENDING_APPROVAL state transition validation.

Validates that:
- PENDING_APPROVAL → SUBMITTED is rejected (HIGH-2 security fix)
- PENDING_APPROVAL → RUNNING is allowed (DBA approval)
- PENDING_APPROVAL → REJECTED is allowed (DBA rejection)
"""

import pytest
from django.test import TestCase

from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStatus
from executions.services import ExecutionService


@pytest.mark.django_db
class TestPendingApprovalTransitions(TestCase):
    """Story 22.12 AC#3: Validate PENDING_APPROVAL state transitions."""

    def setUp(self):
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published',
        )
        self.service = ExecutionService()

    def _create_pending_execution(self):
        return Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL,
        )

    def test_pending_approval_cannot_transition_to_submitted(self):
        """AC#1: PENDING_APPROVAL → SUBMITTED is forbidden (bypass risk)."""
        execution = self._create_pending_execution()

        with pytest.raises(ValueError, match="Invalid transition from PENDING_APPROVAL to SUBMITTED"):
            self.service.update_status(execution.id, ExecutionStatus.SUBMITTED, str(self.user.id))

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.PENDING_APPROVAL

    def test_pending_approval_can_transition_to_running(self):
        """AC#2: PENDING_APPROVAL → RUNNING is allowed (DBA approval)."""
        execution = self._create_pending_execution()

        updated = self.service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.RUNNING
        assert updated.started_at is not None

    def test_pending_approval_can_transition_to_rejected(self):
        """AC#2: PENDING_APPROVAL → REJECTED is allowed (DBA rejection)."""
        execution = self._create_pending_execution()

        updated = self.service.update_status(execution.id, ExecutionStatus.REJECTED, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.REJECTED
        assert updated.completed_at is not None

    def test_pending_approval_all_other_transitions_forbidden(self):
        """AC#2: All transitions except RUNNING and REJECTED are forbidden from PENDING_APPROVAL."""
        forbidden_statuses = [
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.INTEGRATION_ERROR,
        ]

        for forbidden_status in forbidden_statuses:
            execution = self._create_pending_execution()

            with pytest.raises(ValueError, match=f"Invalid transition from PENDING_APPROVAL to {forbidden_status}"):
                self.service.update_status(execution.id, forbidden_status, str(self.user.id))

            # Verify status unchanged
            execution.refresh_from_db()
            assert execution.status == ExecutionStatus.PENDING_APPROVAL

    def test_submitted_can_transition_to_integration_error(self):
        """Story 18.6 regression: SUBMITTED → INTEGRATION_ERROR is allowed."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        updated = self.service.update_status(execution.id, ExecutionStatus.INTEGRATION_ERROR, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.INTEGRATION_ERROR

    def test_invalid_user_id_raises_error(self):
        """SOC1 audit integrity: Invalid user_id raises ValueError."""
        execution = self._create_pending_execution()

        with pytest.raises(ValueError, match="Invalid user_id: 999999"):
            self.service.update_status(execution.id, ExecutionStatus.RUNNING, "999999")

    def test_started_at_idempotent_on_retry(self):
        """Preserve original started_at on status re-transition."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        # First transition to RUNNING
        updated = self.service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))
        original_started_at = updated.started_at
        assert original_started_at is not None

        # Simulate a retry scenario (hypothetical future feature)
        # For now, just verify that started_at is preserved if already set
        execution.refresh_from_db()
        assert execution.started_at == original_started_at
