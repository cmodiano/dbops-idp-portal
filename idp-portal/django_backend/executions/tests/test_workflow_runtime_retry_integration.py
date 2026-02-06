"""
Integration tests for WorkflowRuntime retry with exponential backoff - Story 16.4

Tests full workflow execution with retry steps:
1. Workflow with retry step: success after 2 attempts
2. Workflow with retry step: failure after max_attempts → on_error_step_id
3. Workflow with retry step: permanent error → on_error_step_id without retry
4. Workflow with retry step: complete audit trail (all attempts logged)
"""

import pytest
from unittest.mock import patch, MagicMock
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
class TestWorkflowRetryIntegrationSuccessAfterRetries:
    """Integration: Workflow with retry step succeeds after 2 attempts."""

    def setup_method(self):
        self.user = User.objects.create(username="integ_retry_success_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_workflow_retry_success_after_2_attempts(self, mock_audit, mock_sleep):
        """Workflow with retry step succeeds at attempt 2, then proceeds to next step."""
        action = Action.objects.create(
            name="Retry Success Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.set_execution_steps([
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Retryable Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": "step-final",
                "on_error_step_id": "step-error",
                "retry_enabled": True,
                "retry_max_attempts": 3,
                "retry_interval_seconds": 10,
                "retry_backoff_multiplier": 2.0,
            },
            {
                "step_id": "step-final",
                "order": 2,
                "name": "Final Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
        ])
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)

        # Mock _execute_step: fail first call, succeed all subsequent
        original_execute = runtime._execute_step
        call_counter = {"count": 0}

        def mock_execute(step):
            call_counter["count"] += 1
            if step.get("step_id") == "step-retry" and call_counter["count"] == 1:
                # Simulate failure on first attempt
                runtime._step_order_counter += 1
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=runtime._step_order_counter,
                    step_name=step.get('name'),
                    step_type='platform',
                    status=ExecutionStepStatus.FAILED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    error_message="Connection timeout",
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message="Connection timeout",
                )
            return original_execute(step)

        runtime._execute_step = mock_execute
        final_status = runtime.run()

        assert final_status == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        # Verify "step-final" was executed (not "step-error")
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Retryable Step" in step_names  # Failed attempt
        assert "Retryable Step" in step_names  # Also the successful retry
        assert "Final Step" in step_names
        assert "Error Handler" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationExhaustion:
    """Integration: Workflow with retry step fails after max_attempts → on_error_step_id."""

    def setup_method(self):
        self.user = User.objects.create(username="integ_retry_exhaust_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Exhaust",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_workflow_retry_exhaustion_routes_to_error_handler(self, mock_audit, mock_sleep):
        """All retry attempts fail → workflow follows on_error_step_id."""
        action = Action.objects.create(
            name="Retry Exhaust Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.set_execution_steps([
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Always Fail Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": "step-ok",
                "on_error_step_id": "step-error",
                "retry_enabled": True,
                "retry_max_attempts": 2,
                "retry_interval_seconds": 5,
                "retry_backoff_multiplier": 2.0,
            },
            {
                "step_id": "step-ok",
                "order": 2,
                "name": "Success Path (skipped)",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
        ])
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        original_execute = runtime._execute_step

        def mock_execute(step):
            if step.get("step_id") == "step-retry":
                runtime._step_order_counter += 1
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=runtime._step_order_counter,
                    step_name=step.get('name'),
                    step_type='platform',
                    status=ExecutionStepStatus.FAILED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    error_message="Service unavailable",
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message="Service unavailable",
                )
            return original_execute(step)

        runtime._execute_step = mock_execute
        final_status = runtime.run()

        # Error handler runs and succeeds → workflow completes
        assert final_status == ExecutionStatus.COMPLETED

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Error Handler" in step_names
        assert "Success Path (skipped)" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationPermanentError:
    """Integration: Permanent error → on_error_step_id without retry."""

    def setup_method(self):
        self.user = User.objects.create(username="integ_retry_perm_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Perm Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_permanent_error_routes_to_error_handler_without_retry(self, mock_audit, mock_sleep):
        """Permanent error on first attempt → immediately routes to error handler."""
        action = Action.objects.create(
            name="Perm Error Integ Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.set_execution_steps([
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Perm Fail Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": "step-ok",
                "on_error_step_id": "step-error",
                "retry_enabled": True,
                "retry_max_attempts": 5,
                "retry_interval_seconds": 60,
                "retry_backoff_multiplier": 2.0,
            },
            {
                "step_id": "step-ok",
                "order": 2,
                "name": "Success Path (skipped)",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
        ])
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        original_execute = runtime._execute_step
        execute_count = {"retry_step": 0}

        def mock_execute(step):
            if step.get("step_id") == "step-retry":
                execute_count["retry_step"] += 1
                runtime._step_order_counter += 1
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=runtime._step_order_counter,
                    step_name=step.get('name'),
                    step_type='platform',
                    status=ExecutionStepStatus.FAILED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    error_message="Validation failed: missing required field",
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message="Validation failed: missing required field",
                )
            return original_execute(step)

        runtime._execute_step = mock_execute
        final_status = runtime.run()

        assert final_status == ExecutionStatus.COMPLETED  # error handler succeeded

        # Only 1 attempt on the retry step (permanent error)
        assert execute_count["retry_step"] == 1

        # No sleep calls (immediate abort)
        mock_sleep.assert_not_called()

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Error Handler" in step_names
        assert "Success Path (skipped)" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationAuditTrail:
    """Integration: Complete audit trail for retry workflow."""

    def setup_method(self):
        self.user = User.objects.create(username="integ_retry_audit_user")
        self.ref_action = Action.objects.create(
            name="Ref Action Audit Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.workflow_runtime.time.sleep")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_complete_audit_trail_for_retry_workflow(self, mock_audit, mock_sleep):
        """AC5: All retry attempts are individually logged in audit trail."""
        action = Action.objects.create(
            name="Audit Trail Integ Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.set_execution_steps([
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Retry Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
                "retry_enabled": True,
                "retry_max_attempts": 3,
                "retry_interval_seconds": 10,
                "retry_backoff_multiplier": 2.0,
            },
        ])
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        original_execute = runtime._execute_step

        def mock_execute(step):
            if step.get("step_id") == "step-retry":
                runtime._step_order_counter += 1
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=runtime._step_order_counter,
                    step_name=step.get('name'),
                    step_type='platform',
                    status=ExecutionStepStatus.FAILED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    error_message="Timeout",
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message="Timeout",
                )
            return original_execute(step)

        runtime._execute_step = mock_execute
        final_status = runtime.run()

        # Workflow fails (no error handler, all retries exhausted)
        assert final_status == ExecutionStatus.FAILED

        # Verify audit trail entries
        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        # Should have:
        # - 3 RETRY_ATTEMPT (one per failed attempt)
        # - 1 RETRY_EXHAUSTED
        # - 1 EXECUTION_FAILED (from run() final audit)
        retry_attempt_count = action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT)
        retry_exhausted_count = action_types.count(AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED)

        assert retry_attempt_count == 3
        assert retry_exhausted_count == 1

        # Verify each attempt has correct attempt_number
        attempt_entries = [c for c in audit_calls
                          if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT]
        for i, entry in enumerate(attempt_entries, 1):
            assert entry.kwargs['details']['attempt'] == i
            assert entry.kwargs['details']['max_attempts'] == 3
            assert entry.kwargs['details']['result'] == 'error'
            assert entry.kwargs['details']['error'] == 'Timeout'
