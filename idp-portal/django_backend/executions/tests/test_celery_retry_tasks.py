"""
Unit tests for Celery retry_workflow_step task — Story 20.3

Tests the asynchronous retry task that replaces time.sleep() with
Celery apply_async(countdown=...).
"""

import pytest
from unittest.mock import patch, MagicMock

from executions.tasks import retry_workflow_step
from executions.workflow_runtime import StepResult, StepOutcome, WorkflowRuntime
from executions.models import Execution, ExecutionStatus
from catalog.models import ActionStatus, ActionItemType
from core.models import AuditActionType
from tests.factories import UserFactory, ActionFactory


@pytest.mark.django_db
class TestRetryWorkflowStepTask:
    """Tests for the retry_workflow_step Celery task."""

    def setup_method(self):
        self.user = UserFactory(username="celery_task_user")
        self.ref_action = ActionFactory(
            name="Ref Action Celery",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Celery Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = [{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 3,
            "retry_interval_seconds": 10,
            "retry_backoff_multiplier": 2.0,
        }]
        self.action.save()
        self.step = self.action.execution_steps[0]

    @patch("executions.tasks.AuditService.create_entry")
    def test_task_success_on_retry(self, mock_audit):
        """Task succeeds on a retry attempt — returns success."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.SUCCESS,
            output={"result": "ok"},
        )):
            result = retry_workflow_step(execution.id, self.step, 2)

        assert result['outcome'] == 'success'
        assert result['output'] == {"result": "ok"}

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]
        assert AuditActionType.EXECUTION_STEP_RETRY_SUCCESS in action_types

    @patch("executions.tasks.AuditService.create_entry")
    def test_task_permanent_error_stops(self, mock_audit):
        """Task encounters permanent error — stops without scheduling retry."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Validation failed: missing field",
        )):
            result = retry_workflow_step(execution.id, self.step, 2)

        assert result['outcome'] == 'error'
        assert 'Validation' in result['error_message']

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]
        assert AuditActionType.EXECUTION_STEP_RETRY_ABORTED in action_types

    @patch("executions.tasks.AuditService.create_entry")
    def test_task_cancelled_execution(self, mock_audit):
        """Task detects cancelled execution — exits without executing step."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )

        result = retry_workflow_step(execution.id, self.step, 2)

        assert result['outcome'] == 'error'
        assert 'cancelled' in result['error_message'].lower()

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.tasks.AuditService.create_entry")
    def test_task_schedules_next_retry(self, mock_audit, mock_apply_async):
        """Task fails with retryable error — schedules next attempt."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Connection timeout",
        )), patch.object(WorkflowRuntime, '_is_retryable_error', return_value=True):
            result = retry_workflow_step(execution.id, self.step, 2)

        assert result['outcome'] == 'retry_scheduled'
        assert result['next_attempt'] == 3
        # Delay for attempt 3: 10 * 2.0^(2-1) = 20.0
        assert result['delay_seconds'] == 20.0

        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args.kwargs
        assert call_kwargs['countdown'] == 20.0
        assert call_kwargs['args'] == [execution.id, self.step, 3]

    @patch("executions.tasks.AuditService.create_entry")
    def test_task_max_attempts_exhausted(self, mock_audit):
        """Task at max_attempts — returns exhausted."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Service unavailable",
        )), patch.object(WorkflowRuntime, '_is_retryable_error', return_value=True):
            # attempt=3 == retry_max_attempts=3
            result = retry_workflow_step(execution.id, self.step, 3)

        assert result['outcome'] == 'error'
        assert result['error_message'] == "Service unavailable"

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]
        assert AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED in action_types

    def test_task_execution_not_found(self):
        """Task with non-existent execution_id — returns error."""
        result = retry_workflow_step(99999, self.step, 2)

        assert result['outcome'] == 'error'
        assert '99999' in result['error_message']

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.tasks.AuditService.create_entry")
    def test_task_backoff_calculation(self, mock_audit, mock_apply_async):
        """Verify exponential backoff delay calculation in task.

        With interval=10, multiplier=2.0:
        - attempt 2 → delay = 10 * 2.0^(2-1) = 20.0
        """
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Timeout",
        )), patch.object(WorkflowRuntime, '_is_retryable_error', return_value=True):
            result = retry_workflow_step(execution.id, self.step, 2)

        assert result['delay_seconds'] == 20.0  # 10 * 2.0^1

    @patch("executions.tasks.AuditService.create_entry")
    def test_task_audit_trail_for_retry_attempt(self, mock_audit):
        """Verify audit trail includes retry_method='celery' for scheduled retries."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Timeout",
        )), patch.object(WorkflowRuntime, '_is_retryable_error', return_value=True), \
             patch("executions.tasks.retry_workflow_step.apply_async"):
            retry_workflow_step(execution.id, self.step, 2)

        attempt_calls = [c for c in mock_audit.call_args_list
                         if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT]
        assert len(attempt_calls) == 1
        assert attempt_calls[0].kwargs['details']['retry_method'] == 'celery'
        assert attempt_calls[0].kwargs['details']['attempt'] == 2
