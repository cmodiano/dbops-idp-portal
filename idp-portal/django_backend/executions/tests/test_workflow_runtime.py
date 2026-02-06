"""
Unit tests for WorkflowRuntime - Story 16.3

Tests AC1-AC5:
- AC1: Branching on success (on_success_step_id)
- AC2: Branching on error (on_error_step_id)
- AC4: Convergence (same next step from success/error)
- AC5: Loop detection (max 100 transitions)

Test structure follows red-green-refactor:
1. Write failing tests first (RED)
2. Implement to make them pass (GREEN)
3. Refactor if needed
"""

import pytest
from unittest.mock import Mock, patch
from django.utils import timezone

from executions.workflow_runtime import (
    WorkflowRuntime,
    WorkflowExecutionState,
    StepResult,
    StepOutcome,
    MAX_STEP_TRANSITIONS,
)
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from catalog.models import Action, ActionStatus, ActionItemType
from idp_auth.models import User


@pytest.mark.django_db
class TestWorkflowExecutionState:
    """Test WorkflowExecutionState tracking."""

    def test_initial_state(self):
        """Test initial state has no visits."""
        state = WorkflowExecutionState(execution_id=1)

        assert state.execution_id == 1
        assert state.current_step_id is None
        assert state.visited_counts == {}
        assert state.transition_count == 0
        assert state.last_step_outcome is None
        assert state.last_error is None

    def test_visit_step_increments_count(self):
        """Test visiting a step increments its count and total transitions."""
        state = WorkflowExecutionState(execution_id=1)

        state.visit_step("step-1")
        assert state.visited_counts["step-1"] == 1
        assert state.transition_count == 1

        state.visit_step("step-1")
        assert state.visited_counts["step-1"] == 2
        assert state.transition_count == 2

    def test_has_exceeded_max_transitions(self):
        """Test loop detection when max transitions exceeded (AC5)."""
        state = WorkflowExecutionState(execution_id=1)

        # Simulate many transitions
        for i in range(MAX_STEP_TRANSITIONS - 1):
            state.visit_step(f"step-{i % 3}")

        assert not state.has_exceeded_max_transitions()

        # One more should trigger
        state.visit_step("step-x")
        assert state.has_exceeded_max_transitions()


@pytest.mark.django_db
class TestWorkflowRuntimeResolveNextStep:
    """Test _resolve_next_step logic (AC1, AC2, AC4)."""

    def setup_method(self):
        """Create test workflow with branches."""
        self.user = User.objects.create(
            username="test_user"
        )

        self.action = Action.objects.create(
            name="Test Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # Workflow steps with branches (Story 16.2 format)
        workflow_steps = [
            {
                "step_id": "step-1",
                "order": 1,
                "name": "First Step",
                "on_success_step_id": "step-2",
                "on_error_step_id": "step-error",
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Second Step",
                "on_success_step_id": None,  # End workflow on success
                "on_error_step_id": "step-error",
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "on_success_step_id": None,  # End workflow
                "on_error_step_id": None,
            },
        ]
        self.action.set_execution_steps(workflow_steps)
        self.action.save()

        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        self.runtime = WorkflowRuntime(self.execution)

    def test_resolve_next_step_on_success(self):
        """AC1: Follow on_success_step_id on success."""
        step = self.runtime.steps_by_id["step-1"]
        next_step_id = self.runtime._resolve_next_step(step, StepOutcome.SUCCESS)

        assert next_step_id == "step-2"

    def test_resolve_next_step_on_error(self):
        """AC2: Follow on_error_step_id on error."""
        step = self.runtime.steps_by_id["step-1"]
        next_step_id = self.runtime._resolve_next_step(step, StepOutcome.ERROR)

        assert next_step_id == "step-error"

    def test_resolve_next_step_null_terminates(self):
        """AC1, AC2: NULL next_step_id terminates workflow."""
        step = self.runtime.steps_by_id["step-2"]
        next_step_id = self.runtime._resolve_next_step(step, StepOutcome.SUCCESS)

        assert next_step_id is None  # Workflow should terminate

    def test_resolve_next_step_convergence(self):
        """AC4: Same next step from success/error paths (convergence)."""
        # Create step with convergence: both paths lead to step-common
        convergence_step = {
            "step_id": "step-conv",
            "order": 10,
            "name": "Convergence Step",
            "on_success_step_id": "step-common",
            "on_error_step_id": "step-common",
        }
        self.runtime.steps_by_id["step-conv"] = convergence_step

        next_on_success = self.runtime._resolve_next_step(convergence_step, StepOutcome.SUCCESS)
        next_on_error = self.runtime._resolve_next_step(convergence_step, StepOutcome.ERROR)

        assert next_on_success == "step-common"
        assert next_on_error == "step-common"
        assert next_on_success == next_on_error  # Convergence

    def test_resolve_next_step_backward_compat_linear(self):
        """Backward compat: Linear workflow without branches."""
        # Create linear workflow (no on_success_step_id/on_error_step_id)
        linear_action = Action.objects.create(
            name="Linear Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        linear_steps = [
            {"step_id": "step-a", "order": 1, "name": "Step A"},
            {"step_id": "step-b", "order": 2, "name": "Step B"},
            {"step_id": "step-c", "order": 3, "name": "Step C"},
        ]
        linear_action.set_execution_steps(linear_steps)
        linear_action.save()

        linear_execution = Execution.objects.create(
            action=linear_action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        linear_runtime = WorkflowRuntime(linear_execution)

        # Should follow linear order (step-a -> step-b -> step-c -> None)
        step_a = linear_runtime.steps_by_id["step-a"]
        next_id = linear_runtime._resolve_next_step(step_a, StepOutcome.SUCCESS)
        assert next_id == "step-b"

        step_b = linear_runtime.steps_by_id["step-b"]
        next_id = linear_runtime._resolve_next_step(step_b, StepOutcome.SUCCESS)
        assert next_id == "step-c"

        step_c = linear_runtime.steps_by_id["step-c"]
        next_id = linear_runtime._resolve_next_step(step_c, StepOutcome.SUCCESS)
        assert next_id is None  # End of workflow


@pytest.mark.django_db
class TestWorkflowRuntimeExecution:
    """Test complete workflow execution (integration)."""

    def setup_method(self):
        """Create test workflow."""
        self.user = User.objects.create(
            username="test_user"
        )

    def test_workflow_execution_success_path(self):
        """Test successful workflow execution following success path."""
        action = Action.objects.create(
            name="Success Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # Simple success path: step-1 -> step-2 -> end
        workflow_steps = [
            {
                "step_id": "step-1",
                "order": 1,
                "name": "First Step",
                "on_success_step_id": "step-2",
                "on_error_step_id": None,
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Second Step",
                "on_success_step_id": None,  # End on success
                "on_error_step_id": None,
            },
        ]
        action.set_execution_steps(workflow_steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # Verify final status
        assert final_status == ExecutionStatus.COMPLETED

        # Verify execution updated
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.started_at is not None
        assert execution.completed_at is not None

        # Verify steps created
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert steps.count() == 2
        assert steps[0].step_name == "First Step"
        assert steps[1].step_name == "Second Step"

    def test_workflow_execution_error_path(self):
        """Test workflow execution following error path."""
        action = Action.objects.create(
            name="Error Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # Error path: step-1 (fail) -> step-error -> end
        workflow_steps = [
            {
                "step_id": "step-1",
                "order": 1,
                "name": "Failing Step",
                "on_success_step_id": "step-2",
                "on_error_step_id": "step-error",
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Success Step (skipped)",
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
        ]
        action.set_execution_steps(workflow_steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)

        # Mock _execute_step to simulate failure on step-1
        original_execute = runtime._execute_step
        def mock_execute(step):
            if step.get('step_id') == 'step-1':
                # Create ExecutionStep record for failing step
                runtime._step_order_counter += 1
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=runtime._step_order_counter,
                    step_name=step.get('name', 'Step'),
                    step_type='platform',
                    status=ExecutionStepStatus.FAILED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    error_message="Simulated error",
                )
                return StepResult(
                    outcome=StepOutcome.ERROR,
                    error_message="Simulated error",
                )
            return original_execute(step)

        runtime._execute_step = mock_execute

        final_status = runtime.run()

        # Should complete (error handler ran successfully)
        assert final_status == ExecutionStatus.COMPLETED

        # Verify error handler was executed (not step-2)
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Failing Step" in step_names
        assert "Error Handler" in step_names
        assert "Success Step (skipped)" not in step_names  # Should be skipped

    def test_workflow_loop_detection(self):
        """AC5: Detect infinite loop and fail after 100 transitions."""
        action = Action.objects.create(
            name="Loop Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # Create loop: step-1 -> step-2 -> step-1 (infinite)
        workflow_steps = [
            {
                "step_id": "step-1",
                "order": 1,
                "name": "Step 1",
                "on_success_step_id": "step-2",
                "on_error_step_id": None,
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Step 2",
                "on_success_step_id": "step-1",  # Loop back
                "on_error_step_id": None,
            },
        ]
        action.set_execution_steps(workflow_steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # Should fail due to loop detection
        assert final_status == ExecutionStatus.FAILED

        # Verify execution marked as failed
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

        # Verify loop detection triggered (MAX_STEP_TRANSITIONS transitions)
        assert runtime.state.transition_count == MAX_STEP_TRANSITIONS

        # Verify steps created (should be many due to loop)
        steps_count = ExecutionStep.objects.filter(execution=execution).count()
        assert steps_count == MAX_STEP_TRANSITIONS  # One step per transition

    def test_workflow_empty_fails(self):
        """Test workflow with no steps fails immediately."""
        action = Action.objects.create(
            name="Empty Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # No steps
        action.set_execution_steps([])
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        final_status = runtime.run()

        # Should fail
        assert final_status == ExecutionStatus.FAILED

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED


@pytest.mark.django_db
class TestStepResult:
    """Test StepResult dataclass."""

    def test_step_result_success(self):
        """Test successful step result."""
        result = StepResult(
            outcome=StepOutcome.SUCCESS,
            output={'key': 'value'}
        )

        assert result.is_success
        assert not result.is_error
        assert result.output == {'key': 'value'}
        assert result.error_message is None

    def test_step_result_error(self):
        """Test error step result."""
        result = StepResult(
            outcome=StepOutcome.ERROR,
            error_message="Something went wrong",
            error_details={'code': 500}
        )

        assert result.is_error
        assert not result.is_success
        assert result.error_message == "Something went wrong"
        assert result.error_details == {'code': 500}
