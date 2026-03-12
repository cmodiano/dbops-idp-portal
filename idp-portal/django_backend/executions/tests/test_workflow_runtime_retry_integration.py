"""
Integration tests for WorkflowRuntime retry with Celery — Story 16.4, 20.3

Story 20.3: Retry uses Celery apply_async(countdown=...) instead of time.sleep().
First attempt is synchronous; subsequent retries are scheduled as Celery tasks.

Tests full workflow execution with retry steps:
1. Workflow with retry step: first attempt succeeds → normal flow
2. Workflow with retry step: first attempt fails, retry scheduled → error path
3. Workflow with retry step: permanent error → on_error_step_ids without retry
4. Workflow with retry step: audit trail for first attempt
"""

import pytest
from unittest.mock import patch
from django.utils import timezone

from executions.workflow_runtime import (
    WorkflowRuntime,
    StepResult,
    StepOutcome,
)
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from core.models import AuditActionType
from tests.factories import UserFactory, ActionFactory


@pytest.mark.django_db
class TestWorkflowRetryIntegrationSuccessFirstAttempt:
    """Integration: Workflow with retry step succeeds on first attempt."""

    def setup_method(self):
        self.user = UserFactory(username="integ_retry_success_user")
        self.ref_action = ActionFactory(
            name="Ref Action Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_workflow_retry_success_on_first_attempt(self, mock_audit):
        """Workflow with retry enabled succeeds at attempt 1 → proceeds normally."""
        action = ActionFactory(
            name="Retry Success Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = [
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Retryable Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": ["step-final"],
                "on_error_step_ids": ["step-error"],
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
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
        ]
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        assert final_status == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Retryable Step" in step_names
        assert "Final Step" in step_names
        assert "Error Handler" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationFailureSchedulesCelery:
    """Integration: First attempt fails, Celery retry scheduled, error path taken."""

    def setup_method(self):
        self.user = UserFactory(username="integ_retry_celery_user")
        self.ref_action = ActionFactory(
            name="Ref Action Celery Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_workflow_retry_failure_schedules_celery_and_follows_error_path(self, mock_audit, mock_apply_async):
        """First attempt fails → Celery task scheduled, workflow follows error path."""
        action = ActionFactory(
            name="Retry Celery Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = [
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Always Fail Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": ["step-ok"],
                "on_error_step_ids": ["step-error"],
                "retry_enabled": True,
                "retry_max_attempts": 3,
                "retry_interval_seconds": 5,
                "retry_backoff_multiplier": 2.0,
            },
            {
                "step_id": "step-ok",
                "order": 2,
                "name": "Success Path",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
            },
        ]
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

        # Celery task was scheduled for retry
        mock_apply_async.assert_called_once()

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Error Handler" in step_names
        assert "Success Path" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationPermanentError:
    """Integration: Permanent error → on_error_step_ids without retry."""

    def setup_method(self):
        self.user = UserFactory(username="integ_retry_perm_user")
        self.ref_action = ActionFactory(
            name="Ref Action Perm Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_permanent_error_routes_to_error_handler_without_retry(self, mock_audit, mock_apply_async):
        """Permanent error on first attempt → immediately routes to error handler."""
        action = ActionFactory(
            name="Perm Error Integ Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = [
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Perm Fail Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": ["step-ok"],
                "on_error_step_ids": ["step-error"],
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
                "on_success_step_ids": [],
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
            },
        ]
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

        # No Celery task scheduled (permanent error)
        mock_apply_async.assert_not_called()

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Error Handler" in step_names
        assert "Success Path (skipped)" not in step_names


@pytest.mark.django_db
class TestWorkflowRetryIntegrationAuditTrail:
    """Integration: Audit trail for retry workflow with Celery."""

    def setup_method(self):
        self.user = UserFactory(username="integ_retry_audit_user")
        self.ref_action = ActionFactory(
            name="Ref Action Audit Integ",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @patch("executions.tasks.retry_workflow_step.apply_async")
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_audit_trail_for_retry_workflow_with_celery(self, mock_audit, mock_apply_async):
        """AC5: First attempt failure is logged with retry_method=celery."""
        action = ActionFactory(
            name="Audit Trail Integ Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = [
            {
                "step_id": "step-retry",
                "order": 1,
                "name": "Retry Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
                "retry_enabled": True,
                "retry_max_attempts": 3,
                "retry_interval_seconds": 10,
                "retry_backoff_multiplier": 2.0,
            },
        ]
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

        # Workflow fails (no error handler, retry scheduled but not completed yet)
        assert final_status == ExecutionStatus.FAILED

        # Verify audit trail entries
        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        # Should have:
        # - 1 RETRY_ATTEMPT (first failed attempt, retry scheduled)
        # - 1 EXECUTION_FAILED (from run() final audit)
        assert action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT) == 1

        # Verify the attempt has retry_method=celery
        attempt_entry = [c for c in audit_calls
                         if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT][0]
        assert attempt_entry.kwargs['details']['attempt'] == 1
        assert attempt_entry.kwargs['details']['retry_method'] == 'celery'
        assert attempt_entry.kwargs['details']['next_wait_seconds'] == 10
