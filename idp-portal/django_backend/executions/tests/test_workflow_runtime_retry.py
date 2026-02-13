"""
Unit tests for WorkflowRuntime retry with exponential backoff - Story 16.4, 20.3

Story 20.3: Retry uses Celery apply_async(countdown=...) instead of time.sleep().
First attempt is synchronous; subsequent retries are scheduled as Celery tasks.

Tests AC1-AC5:
- AC1: Retry with exponential backoff (delay calculation via Celery countdown)
- AC2: Success at attempt N stops retrying immediately
- AC3: Permanent error stops retrying immediately
- AC4: Cancellation during retry exits cleanly
- AC5: Audit trail for each retry attempt
"""

import pytest
from unittest.mock import patch

from executions.workflow_runtime import (
    WorkflowRuntime,
    StepResult,
    StepOutcome,
)
from executions.models import Execution, ExecutionStatus
from catalog.models import ActionStatus, ActionItemType
from core.models import AuditActionType
from tests.factories import UserFactory, ActionFactory


@pytest.mark.django_db
class TestIsRetryableError:
    """Test _is_retryable_error() classification (AC3)."""

    def setup_method(self):
        self.user = UserFactory(username="retry_test_user")
        self.ref_action = ActionFactory(
            name="Ref Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()
        self.execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.runtime = WorkflowRuntime(self.execution)

    def test_empty_error_is_retryable(self):
        """Empty/None error message defaults to retryable."""
        result_empty = StepResult(outcome=StepOutcome.ERROR, error_message="")
        result_none = StepResult(outcome=StepOutcome.ERROR, error_message=None)
        assert self.runtime._is_retryable_error(result_empty) is True
        assert self.runtime._is_retryable_error(result_none) is True

    def test_validation_error_is_not_retryable(self):
        """Validation errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Validation failed: field X is required")
        assert self.runtime._is_retryable_error(result) is False

    def test_permission_error_is_not_retryable(self):
        """Permission errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Permission denied for user")
        assert self.runtime._is_retryable_error(result) is False

    def test_not_found_error_is_not_retryable(self):
        """Not found errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Action not found")
        assert self.runtime._is_retryable_error(result) is False

    def test_unauthorized_error_is_not_retryable(self):
        """Unauthorized errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Unauthorized access")
        assert self.runtime._is_retryable_error(result) is False

    def test_forbidden_error_is_not_retryable(self):
        """Forbidden errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Forbidden: access denied")
        assert self.runtime._is_retryable_error(result) is False

    def test_bad_request_error_is_not_retryable(self):
        """Bad request errors are permanent."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Bad request: invalid payload")
        assert self.runtime._is_retryable_error(result) is False

    def test_http_4xx_errors_are_not_retryable(self):
        """HTTP 4xx status codes are permanent."""
        result_400 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 400 error")
        result_401 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 401 error")
        result_403 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 403 error")
        result_404 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 404 error")
        assert self.runtime._is_retryable_error(result_400) is False
        assert self.runtime._is_retryable_error(result_401) is False
        assert self.runtime._is_retryable_error(result_403) is False
        assert self.runtime._is_retryable_error(result_404) is False

    def test_timeout_error_is_retryable(self):
        """Timeout errors are temporary."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Connection timeout after 30s")
        assert self.runtime._is_retryable_error(result) is True

    def test_connection_error_is_retryable(self):
        """Connection errors are temporary."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Connection refused to host")
        assert self.runtime._is_retryable_error(result) is True

    def test_http_5xx_errors_are_retryable(self):
        """HTTP 5xx status codes are temporary."""
        result_500 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 500 internal server error")
        result_502 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 502 bad gateway")
        result_503 = StepResult(outcome=StepOutcome.ERROR, error_message="HTTP 503 service unavailable")
        assert self.runtime._is_retryable_error(result_500) is True
        assert self.runtime._is_retryable_error(result_502) is True
        assert self.runtime._is_retryable_error(result_503) is True

    def test_generic_error_is_retryable(self):
        """Generic exceptions are retryable by default."""
        result = StepResult(outcome=StepOutcome.ERROR, error_message="Something unexpected happened")
        assert self.runtime._is_retryable_error(result) is True

    def test_error_type_in_details_takes_priority(self):
        """H2 FIX: error_type in error_details should take priority over string matching."""
        result_perm = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Something went wrong",
            error_details={'error_type': 'validation'}
        )
        assert self.runtime._is_retryable_error(result_perm) is False

        result_perm2 = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Operation failed",
            error_details={'error_type': 'permission'}
        )
        assert self.runtime._is_retryable_error(result_perm2) is False

        result_retry = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Connection timeout",
            error_details={'error_type': 'network'}
        )
        assert self.runtime._is_retryable_error(result_retry) is True


@pytest.mark.django_db
class TestExecuteStepWithRetryDisabled:
    """Test _execute_step_with_retry() when retry is disabled (bypass)."""

    def setup_method(self):
        self.user = UserFactory(username="retry_disabled_user")
        self.ref_action = ActionFactory(
            name="Ref Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="No Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    def test_retry_disabled_calls_execute_step_once(self):
        """When retry_enabled is false, _execute_step is called directly."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        runtime = WorkflowRuntime(execution)
        step = {"step_id": "s1", "order": 1, "name": "Step 1",
                "referenced_action_id": self.ref_action.id,
                "retry_enabled": False}

        with patch.object(runtime, '_execute_step', return_value=StepResult(outcome=StepOutcome.SUCCESS)) as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_success
        mock_exec.assert_called_once_with(step)

    def test_retry_missing_calls_execute_step_once(self):
        """When retry_enabled key is absent, _execute_step is called directly."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        runtime = WorkflowRuntime(execution)
        step = {"step_id": "s1", "order": 1, "name": "Step 1",
                "referenced_action_id": self.ref_action.id}

        with patch.object(runtime, '_execute_step', return_value=StepResult(outcome=StepOutcome.SUCCESS)) as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_success
        mock_exec.assert_called_once_with(step)


@pytest.mark.django_db
class TestExecuteStepWithRetryBackoff:
    """Test retry with Celery-based exponential backoff (AC1, AC2) - Story 20.3."""

    def setup_method(self):
        self.user = UserFactory(username="retry_backoff_user")
        self.ref_action = ActionFactory(
            name="Ref Action Backoff",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Backoff Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_retry_schedules_celery_task_on_failure(self, mock_audit, mock_apply_async):
        """AC1-AC2: First attempt fails → Celery task scheduled with countdown."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 5,
            "retry_interval_seconds": 30,
            "retry_backoff_multiplier": 1.5,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Connection timeout"
        )):
            result = runtime._execute_step_with_retry(step)

        # Result indicates retry was scheduled
        assert result.is_error
        assert result.error_details['retry_scheduled'] is True
        assert result.error_details['next_attempt'] == 2
        assert result.error_details['delay_seconds'] == 30  # interval_seconds for attempt 2

        # Verify Celery apply_async was called with correct countdown
        mock_apply_async.assert_called_once()
        call_kwargs = mock_apply_async.call_args
        assert call_kwargs.kwargs['countdown'] == 30
        assert call_kwargs.kwargs['args'] == [execution.id, step, 2]

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_success_at_attempt_1_no_celery_task(self, mock_audit, mock_apply_async):
        """AC2: Success at attempt 1 — no Celery task scheduled."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 5,
            "retry_interval_seconds": 60,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.SUCCESS, output={"ok": True}
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_success
        assert result.output == {"ok": True}
        mock_apply_async.assert_not_called()

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_max_attempts_1_no_retry(self, mock_audit, mock_apply_async):
        """Edge case: max_attempts=1 means no actual retry, just one attempt."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 1,
            "retry_interval_seconds": 60,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Fail"
        )) as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        mock_exec.assert_called_once()
        mock_apply_async.assert_not_called()  # No Celery task for single attempt


@pytest.mark.django_db
class TestExecuteStepWithRetryPermanentError:
    """Test permanent error detection stops retry immediately (AC3)."""

    def setup_method(self):
        self.user = UserFactory(username="retry_perm_user")
        self.ref_action = ActionFactory(
            name="Ref Action Perm",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Perm Error Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_permanent_error_stops_immediately(self, mock_audit, mock_apply_async):
        """AC3: Permanent error at attempt 1 → no retry scheduled."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 5,
            "retry_interval_seconds": 60,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Validation failed: field X"
        )) as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        assert "Validation" in result.error_message
        mock_exec.assert_called_once()  # Only 1 attempt
        mock_apply_async.assert_not_called()  # No Celery task


@pytest.mark.django_db
class TestExecuteStepWithRetryCancellation:
    """Test cancellation during retry (AC4)."""

    def setup_method(self):
        self.user = UserFactory(username="retry_cancel_user")
        self.ref_action = ActionFactory(
            name="Ref Action Cancel",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Cancel Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_cancellation_before_first_attempt(self, mock_audit):
        """AC4: If execution is cancelled before first attempt, exit immediately."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 5,
            "retry_interval_seconds": 60,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step') as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        assert "cancelled" in result.error_message.lower()
        mock_exec.assert_not_called()  # Step never executed


@pytest.mark.django_db
class TestExecuteStepWithRetryAuditTrail:
    """Test audit trail entries for retry attempts (AC5) — Story 20.3."""

    def setup_method(self):
        self.user = UserFactory(username="retry_audit_user")
        self.ref_action = ActionFactory(
            name="Ref Action Audit",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = ActionFactory(
            name="Audit Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_first_attempt_failure_schedules_retry(self, mock_audit, mock_apply_async):
        """AC5: First attempt failure logs RETRY_ATTEMPT + schedules Celery task."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 3,
            "retry_interval_seconds": 10,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Timeout"
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        # 1 RETRY_ATTEMPT for the first failed attempt
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 1

        # Verify attempt details
        attempt_call = [c for c in audit_calls
                        if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT][0]
        assert attempt_call.kwargs['details']['attempt'] == 1
        assert attempt_call.kwargs['details']['retry_method'] == 'celery'
        assert attempt_call.kwargs['details']['next_wait_seconds'] == 10

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_exhaustion_max_attempts_1(self, mock_audit, mock_apply_async):
        """AC5: max_attempts=1 → RETRY_EXHAUSTED after single failure."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 1,
            "retry_interval_seconds": 10,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Service down"
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED) == 1
        exhausted_call = [c for c in audit_calls
                          if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED][0]
        assert exhausted_call.kwargs['details']['max_attempts'] == 1
        assert exhausted_call.kwargs['details']['final_error'] == "Service down"

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_permanent_error_aborted(self, mock_audit, mock_apply_async):
        """AC5: Audit logs RETRY_ABORTED for permanent errors."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 5,
            "retry_interval_seconds": 60,
            "retry_backoff_multiplier": 2.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Validation failed"
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ABORTED) == 1
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 0

        aborted_call = [c for c in audit_calls
                        if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ABORTED][0]
        assert aborted_call.kwargs['details']['reason'] == 'non_retryable_error'
