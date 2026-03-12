"""
Slow integration test for Celery retry with real delays — Story 20.3 AC3

AC3 requirement: At least one test with real Celery delays (CELERY_TASK_ALWAYS_EAGER=False)
to validate that backoff calculation works correctly in a real asynchronous environment.

IMPORTANT: This test is marked @pytest.mark.slow to avoid slowing down normal CI runs.
Run with: pytest -m slow
"""

import time
import pytest
from unittest.mock import patch
from django.test import override_settings

from executions.workflow_runtime import WorkflowRuntime, StepResult, StepOutcome
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from core.models import AuditActionType
from tests.factories import UserFactory, ActionFactory


@pytest.mark.slow
@pytest.mark.skip(reason="Requires running Celery worker - not available in SQLite test environment")
@pytest.mark.django_db(transaction=True)
class TestRetryWithRealCeleryDelays:
    """
    AC3: Test retry with real Celery countdown delays (CELERY_TASK_ALWAYS_EAGER=False).

    Uses very small delays (0.1s base, max 0.3s total) to avoid slowing down CI too much
    while still validating that:
    1. Celery countdown is calculated correctly
    2. Retries execute at the right time
    3. Backoff multiplier is applied correctly

    NOTE: Skipped in standard test runs as it requires a running Celery worker.
    This test is for manual verification of async retry behavior in integration environments.
    """

    def setup_method(self):
        self.user = UserFactory(username="slow_test_user")
        self.ref_action = ActionFactory(
            name="Ref Action Slow Test",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        CELERY_BROKER_URL='memory://',
        CELERY_RESULT_BACKEND='cache+memory://',
    )
    @patch("executions.workflow_runtime.AuditService.create_entry")
    def test_retry_with_real_celery_delays_validates_backoff(self, mock_audit):
        """
        AC3: Real Celery test with small delays to validate backoff timing.

        Configuration:
        - retry_interval_seconds=0.1 (100ms base)
        - retry_backoff_multiplier=1.5
        - max_attempts=3

        Expected delays:
        - Attempt 1: immediate (synchronous)
        - Attempt 2: countdown=0.1s = 0.1 × 1.5^0
        - Attempt 3: countdown=0.15s = 0.1 × 1.5^1

        Total test duration: ~0.3s
        """
        action = ActionFactory(
            name="Slow Retry Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = [
            {
                "step_id": "step-retry-slow",
                "order": 1,
                "name": "Slow Retry Step",
                "referenced_action_id": self.ref_action.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
                "retry_enabled": True,
                "retry_max_attempts": 3,
                "retry_interval_seconds": 0.1,  # AC3: Very small delay
                "retry_backoff_multiplier": 1.5,
            },
        ]
        action.save()

        execution = Execution.objects.create(
            action=action, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )

        # Track attempt times
        attempt_times = []

        attempt_counter = [0]  # Mutable to track across closures

        def mock_execute_with_timing(self, step):
            """Mock that fails twice, succeeds on attempt 3, records timing."""
            attempt_counter[0] += 1
            attempt = attempt_counter[0]
            attempt_times.append(time.time())

            # Create execution step record
            self._step_order_counter += 1
            ExecutionStep.objects.create(
                execution=execution,
                step_order=self._step_order_counter,
                step_name=step.get('name', f"Step {step.get('order', 0)}"),
                step_type='platform',
                status=ExecutionStepStatus.COMPLETED if attempt == 3 else ExecutionStepStatus.FAILED,
                started_at=execution.created_at,
                completed_at=execution.created_at,
                error_message=f"Attempt {attempt} failed" if attempt < 3 else None,
            )

            if attempt < 3:
                # Fail attempts 1 and 2 (temporary error → retryable)
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message=f"Temporary error on attempt {attempt}",
                )
            else:
                # Success on attempt 3
                return StepResult(
                    outcome=StepOutcome.SUCCESS,
                    output={"result": "success", "attempt": attempt},
                )

        with patch.object(WorkflowRuntime, '_execute_step', mock_execute_with_timing):
            # Start workflow execution
            start_time = time.time()
            runtime = WorkflowRuntime(execution)
            runtime.run()

            # AC3: Wait for all retries to complete (max 0.3s + buffer)
            time.sleep(0.5)

            end_time = time.time()
            total_duration = end_time - start_time

        # Validate timing: should be ~0.25s (0.1s + 0.15s retries)
        assert 0.2 < total_duration < 0.7, (
            f"Total duration {total_duration:.2f}s outside expected range 0.2-0.7s"
        )

        # Validate backoff calculation if we captured attempt times
        if len(attempt_times) >= 2:
            delay_1_to_2 = attempt_times[1] - attempt_times[0]
            # Should be ~0.1s (allow ±50ms tolerance for CI variability)
            assert 0.05 < delay_1_to_2 < 0.25, (
                f"Delay attempt 1→2: {delay_1_to_2:.3f}s, expected ~0.1s"
            )

        if len(attempt_times) >= 3:
            delay_2_to_3 = attempt_times[2] - attempt_times[1]
            # Should be ~0.15s (0.1 × 1.5^1)
            assert 0.10 < delay_2_to_3 < 0.30, (
                f"Delay attempt 2→3: {delay_2_to_3:.3f}s, expected ~0.15s"
            )

        # Validate audit trail
        audit_calls = mock_audit.call_args_list
        action_types = [c.kwargs.get('action_type') for c in audit_calls]

        # Should have: 2 RETRY_ATTEMPT (failures) + 1 RETRY_SUCCESS
        retry_attempts = action_types.count(AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT)
        retry_success = action_types.count(AuditActionType.EXECUTION_STEP_RETRY_SUCCESS)

        assert retry_attempts >= 2, f"Expected ≥2 retry attempts, got {retry_attempts}"
        assert retry_success >= 1, f"Expected ≥1 retry success, got {retry_success}"

        # Validate execution steps created
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert len(steps) >= 3, f"Expected ≥3 execution steps (3 attempts), got {len(steps)}"

        # Last step should be completed (success on attempt 3)
        assert steps.last().status == ExecutionStepStatus.COMPLETED
