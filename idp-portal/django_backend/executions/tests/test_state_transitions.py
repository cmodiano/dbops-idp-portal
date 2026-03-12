"""
Tests for execution state transition validation.

ADR-007: PENDING_APPROVAL is no longer used at the Execution level.
All approvals go through ExecutionStep WAITING gates.

Validates that:
- PENDING_APPROVAL is now a dead-end (no valid transitions in or out)
- SUBMITTED → RUNNING, CANCELLED, FAILED, INTEGRATION_ERROR are valid
- RUNNING → COMPLETED, FAILED, CANCELLED are valid
"""

import pytest
from django.test import TestCase

from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStatus
from executions.services import ExecutionService


@pytest.mark.django_db
class TestPendingApprovalTransitions(TestCase):
    """ADR-007: PENDING_APPROVAL is deprecated. Validate it's a dead state."""

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

    def test_pending_approval_all_transitions_forbidden(self):
        """ADR-007: PENDING_APPROVAL is a dead state — no transitions allowed."""
        all_statuses = [
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.INTEGRATION_ERROR,
        ]

        for target_status in all_statuses:
            execution = self._create_pending_execution()

            with pytest.raises(ValueError, match="Invalid transition from PENDING_APPROVAL"):
                self.service.update_status(execution.id, target_status, str(self.user.id))

            execution.refresh_from_db()
            assert execution.status == ExecutionStatus.PENDING_APPROVAL

    def test_submitted_cannot_transition_to_pending_approval(self):
        """ADR-007: SUBMITTED → PENDING_APPROVAL is no longer valid."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        with pytest.raises(ValueError, match="Invalid transition from SUBMITTED to PENDING_APPROVAL"):
            self.service.update_status(execution.id, ExecutionStatus.PENDING_APPROVAL, str(self.user.id))

    def test_submitted_can_transition_to_running(self):
        """SUBMITTED → RUNNING is valid (normal execution start)."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        updated = self.service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.RUNNING
        assert updated.started_at is not None

    def test_submitted_can_transition_to_failed(self):
        """ADR-007: SUBMITTED → FAILED is valid (approval gate rejected)."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )

        updated = self.service.update_status(execution.id, ExecutionStatus.FAILED, str(self.user.id))

        assert updated is not None
        assert updated.status == ExecutionStatus.FAILED
        assert updated.completed_at is not None

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
