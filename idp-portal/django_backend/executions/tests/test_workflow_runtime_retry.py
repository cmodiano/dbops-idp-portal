"""
Unit tests for WorkflowRuntime retry with exponential backoff - Story 16.4

Tests AC1-AC5:
- AC1: Retry with exponential backoff (delay calculation)
- AC2: Success at attempt N stops retrying immediately
- AC3: Permanent error stops retrying immediately
- AC4: Cancellation during retry exits cleanly
- AC5: Audit trail for each retry attempt
"""

import pytest
from unittest.mock import patch, MagicMock, call
from django.utils import timezone

from executions.workflow_runtime import (
    WorkflowRuntime,
    StepResult,
    StepOutcome,
)
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from catalog.models import Action, ActionStatus, ActionItemType
from core.models import AuditActionType
from idp_auth.models import User


@pytest.mark.django_db
class TestIsRetryableError:
    """Test _is_retryable_error() classification (AC3)."""

    def setup_method(self):
        self.user = User.objects.create(username="retry_test_user")
        self.ref_action = Action.objects.create(
            name="Ref Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
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
        # This error message is generic but error_type says it's permanent (validation)
        result_perm = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Something went wrong",
            error_details={'error_type': 'validation'}
        )
        assert self.runtime._is_retryable_error(result_perm) is False

        # This error message is generic but error_type says it's permanent (permission)
        result_perm2 = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Operation failed",
            error_details={'error_type': 'permission'}
        )
        assert self.runtime._is_retryable_error(result_perm2) is False

        # Edge case: error_type is present but doesn't match validation/permission patterns
        # In this case, fallback to string matching (which is retryable here)
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
        self.user = User.objects.create(username="retry_disabled_user")
        self.ref_action = Action.objects.create(
            name="Ref Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="No Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
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
    """Test retry with exponential backoff (AC1, AC2)."""

    def setup_method(self):
        self.user = User.objects.create(username="retry_backoff_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Backoff",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="Backoff Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_retry_backoff_delay_calculation(self, mock_audit, mock_sleep):
        """AC1: Verify exponential backoff delay calculation.

        With interval=30, multiplier=1.5, max_attempts=5:
        - Attempt 1: delay=0 (immediate)
        - Attempt 2: delay=30 (30 * 1.5^0)
        - Attempt 3: delay=45 (30 * 1.5^1)
        - Attempt 4: delay=67.5 (30 * 1.5^2)
        - Attempt 5: delay=101.25 (30 * 1.5^3)
        """
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

        # All attempts fail
        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Connection timeout"
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        # Verify sleep calls (attempts 2-5)
        assert mock_sleep.call_count == 4
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays[0] == 30.0      # 30 * 1.5^0
        assert delays[1] == 45.0      # 30 * 1.5^1
        assert delays[2] == 67.5      # 30 * 1.5^2
        assert delays[3] == 101.25    # 30 * 1.5^3

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_success_at_attempt_2_stops_retrying(self, mock_audit, mock_sleep):
        """AC2: Success at attempt 2 stops retrying immediately."""
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

        call_count = 0

        def mock_execute(s):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return StepResult(outcome=StepOutcome.ERROR, error_message="Timeout")
            return StepResult(outcome=StepOutcome.SUCCESS, output={"ok": True})

        with patch.object(runtime, '_execute_step', side_effect=mock_execute):
            result = runtime._execute_step_with_retry(step)

        assert result.is_success
        assert result.output == {"ok": True}
        assert call_count == 2
        # Only 1 sleep (before attempt 2)
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args.args[0] == 60.0  # 60 * 2.0^0

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_exhaustion_after_max_attempts(self, mock_audit, mock_sleep):
        """AC1: All attempts fail → returns last error result."""
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
            outcome=StepOutcome.ERROR, error_message="Service unavailable"
        )) as mock_exec:
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        assert result.error_message == "Service unavailable"
        assert mock_exec.call_count == 3
        # 2 sleeps (before attempts 2 and 3)
        assert mock_sleep.call_count == 2

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_fixed_delay_when_multiplier_is_1(self, mock_audit, mock_sleep):
        """Edge case: backoff_multiplier=1.0 means fixed delay."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        runtime = WorkflowRuntime(execution)

        step = {
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "retry_enabled": True,
            "retry_max_attempts": 4,
            "retry_interval_seconds": 15,
            "retry_backoff_multiplier": 1.0,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Timeout"
        )):
            runtime._execute_step_with_retry(step)

        # All delays should be 15s (fixed)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert all(d == 15.0 for d in delays)

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_max_attempts_1_no_retry(self, mock_audit, mock_sleep):
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
        assert mock_exec.call_count == 1
        assert mock_sleep.call_count == 0  # No sleep for single attempt


@pytest.mark.django_db
class TestExecuteStepWithRetryPermanentError:
    """Test permanent error detection stops retry immediately (AC3)."""

    def setup_method(self):
        self.user = User.objects.create(username="retry_perm_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Perm",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="Perm Error Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_permanent_error_stops_immediately(self, mock_audit, mock_sleep):
        """AC3: Permanent error at attempt 1 → no retry."""
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
        mock_sleep.assert_not_called()  # No sleep


@pytest.mark.django_db
class TestExecuteStepWithRetryCancellation:
    """Test cancellation during retry (AC4)."""

    def setup_method(self):
        self.user = User.objects.create(username="retry_cancel_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Cancel",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="Cancel Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_cancellation_before_first_attempt(self, mock_audit, mock_sleep):
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

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_cancellation_between_attempts(self, mock_audit, mock_sleep):
        """AC4: If execution is cancelled between attempts, exit cleanly."""
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

        call_count = 0

        def mock_execute(s):
            nonlocal call_count
            call_count += 1
            # After first attempt, simulate cancellation
            execution.status = ExecutionStatus.CANCELLED
            execution.save()
            return StepResult(outcome=StepOutcome.ERROR, error_message="Timeout")

        with patch.object(runtime, '_execute_step', side_effect=mock_execute):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error
        assert "cancelled" in result.error_message.lower()
        assert call_count == 1  # Only one attempt before cancellation detected


@pytest.mark.django_db
class TestExecuteStepWithRetryAuditTrail:
    """Test audit trail entries for retry attempts (AC5)."""

    def setup_method(self):
        self.user = User.objects.create(username="retry_audit_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Audit",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name="Audit Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.set_execution_steps([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_id": None,
        }])
        self.action.save()

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_success_after_retries(self, mock_audit, mock_sleep):
        """AC5: Audit logs attempt failures + final success."""
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

        call_count = 0

        def mock_execute(s):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return StepResult(outcome=StepOutcome.ERROR, error_message="Timeout")
            return StepResult(outcome=StepOutcome.SUCCESS)

        with patch.object(runtime, '_execute_step', side_effect=mock_execute):
            result = runtime._execute_step_with_retry(step)

        assert result.is_success

        # Verify audit calls:
        # - 2 RETRY_ATTEMPT entries (failed attempts 1,2)
        # - 1 RETRY_SUCCESS entry (success at attempt 3)
        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 2
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_SUCCESS) == 1

        # Verify attempt details in RETRY_ATTEMPT entries
        attempt_calls = [c for c in audit_calls
                         if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT]
        assert attempt_calls[0].kwargs['details']['attempt'] == 1
        assert attempt_calls[1].kwargs['details']['attempt'] == 2

        # Verify success entry details
        success_call = [c for c in audit_calls
                        if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_SUCCESS][0]
        assert success_call.kwargs['details']['attempt'] == 3
        assert success_call.kwargs['details']['result'] == 'success'

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_exhaustion(self, mock_audit, mock_sleep):
        """AC5: Audit logs all failed attempts + exhaustion entry."""
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
            outcome=StepOutcome.ERROR, error_message="Service down"
        )):
            result = runtime._execute_step_with_retry(step)

        assert result.is_error

        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        # 3 RETRY_ATTEMPT + 1 RETRY_EXHAUSTED
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 3
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED) == 1

        # Verify exhaustion entry details
        exhausted_call = [c for c in audit_calls
                          if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED][0]
        assert exhausted_call.kwargs['details']['max_attempts'] == 3
        assert exhausted_call.kwargs['details']['final_error'] == "Service down"

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_permanent_error_aborted(self, mock_audit, mock_sleep):
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

        # Only 1 RETRY_ABORTED, no RETRY_ATTEMPT (stopped immediately)
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ABORTED) == 1
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 0

        aborted_call = [c for c in audit_calls
                        if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ABORTED][0]
        assert aborted_call.kwargs['details']['reason'] == 'non_retryable_error'

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_includes_next_wait_seconds(self, mock_audit, mock_sleep):
        """AC5: Each attempt audit entry includes next_wait_seconds."""
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
            "retry_interval_seconds": 30,
            "retry_backoff_multiplier": 1.5,
        }

        with patch.object(runtime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.ERROR, error_message="Timeout"
        )):
            runtime._execute_step_with_retry(step)

        attempt_calls = [c for c in mock_audit.call_args_list
                         if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT]

        # Attempt 1: next_wait = 30 * 1.5^0 = 30
        assert attempt_calls[0].kwargs['details']['next_wait_seconds'] == 30.0
        # Attempt 2: next_wait = 30 * 1.5^1 = 45
        assert attempt_calls[1].kwargs['details']['next_wait_seconds'] == 45.0
        # Attempt 3 (last): next_wait = 0 (no more attempts)
        assert attempt_calls[2].kwargs['details']['next_wait_seconds'] == 0
