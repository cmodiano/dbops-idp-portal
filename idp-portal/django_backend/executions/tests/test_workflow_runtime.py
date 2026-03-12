"""
Unit tests for WorkflowRuntime - Story 16.3

Tests AC1-AC5:
- AC1: Branching on success (on_success_step_ids)
- AC2: Branching on error (on_error_step_ids)
- AC4: Convergence (same next step from success/error)
- AC5: Loop detection (max 100 transitions)

Test structure follows red-green-refactor:
1. Write failing tests first (RED)
2. Implement to make them pass (GREEN)
3. Refactor if needed
"""

import pytest
from unittest.mock import patch
from django.utils import timezone

from executions.workflow_runtime import (
    WorkflowRuntime,
    WorkflowExecutionState,
    StepResult,
    StepOutcome,
    MAX_STEP_TRANSITIONS,
)
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory, IntegrationFactory


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
        self.user = UserFactory(
            username="test_user"
        )

        self.action = ActionFactory(
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
                "on_success_step_ids": ["step-2"],
                "on_error_step_ids": ["step-error"],
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Second Step",
                "on_success_step_ids": [],  # End workflow on success
                "on_error_step_ids": ["step-error"],
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
        ]
        self.action.execution_steps = (workflow_steps)
        self.action.save()

        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        self.runtime = WorkflowRuntime(self.execution)

    def test_resolve_next_step_on_success(self):
        """AC1: Follow on_success_step_ids on success."""
        step = self.runtime.steps_by_id["step-1"]
        next_step_id = self.runtime._resolve_next_step(step, StepOutcome.SUCCESS)

        assert next_step_id == "step-2"

    def test_resolve_next_step_on_error(self):
        """AC2: Follow on_error_step_ids on error."""
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
            "on_success_step_ids": ["step-common"],
            "on_error_step_ids": ["step-common"],
        }
        self.runtime.steps_by_id["step-conv"] = convergence_step

        next_on_success = self.runtime._resolve_next_step(convergence_step, StepOutcome.SUCCESS)
        next_on_error = self.runtime._resolve_next_step(convergence_step, StepOutcome.ERROR)

        assert next_on_success == "step-common"
        assert next_on_error == "step-common"
        assert next_on_success == next_on_error  # Convergence

    def test_resolve_next_step_linear_without_branches(self):
        """Linear workflow without branch fields uses order."""
        # Create linear workflow (no on_success_step_ids/on_error_step_ids)
        linear_action = ActionFactory(
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
        linear_action.execution_steps = (linear_steps)
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

    def test_resolve_next_step_partial_branches_falls_back_on_success(self):
        """
        If only on_error_step_ids exists, a SUCCESS outcome must NOT terminate (linear fallback).
        """
        action = ActionFactory(
            name="Partial Branch Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        steps = [
            {"step_id": "step-1", "order": 1, "name": "Step 1", "on_error_step_ids": ["step-err"]},
            {"step_id": "step-2", "order": 2, "name": "Step 2"},  # linear continuation expected
            {"step_id": "step-err", "order": 99, "name": "Err"},
        ]
        action.execution_steps = (steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = WorkflowRuntime(execution)

        next_step_id = runtime._resolve_next_step(runtime.steps_by_id["step-1"], StepOutcome.SUCCESS)
        assert next_step_id == "step-2"

@pytest.mark.django_db
class TestWorkflowRuntimeExecution:
    """Test complete workflow execution (integration)."""

    def setup_method(self):
        """Create test workflow."""
        self.user = UserFactory(
            username="test_user"
        )

    def test_workflow_execution_success_path(self):
        """Test successful workflow execution following success path."""
        # Create referenced actions for workflow steps
        ref_action_1 = ActionFactory(
            name="Ref Action 1",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        ref_action_2 = ActionFactory(
            name="Ref Action 2",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

        # Story 47.3: actions need integration — fail-fast otherwise
        integration = IntegrationFactory.create(type="aap")
        ref_action_1.integration = integration
        ref_action_1.save()
        ref_action_2.integration = integration
        ref_action_2.save()

        action = ActionFactory(
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
                "referenced_action_id": ref_action_1.id,
                "on_success_step_ids": ["step-2"],
                "on_error_step_ids": [],
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Second Step",
                "referenced_action_id": ref_action_2.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
        ]
        action.execution_steps = (workflow_steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        with patch("executions.workflow_runtime.AuditService.create_entry") as create_entry:
            with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
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

        # AC4: path trace recorded in audit
        assert create_entry.called
        details = create_entry.call_args.kwargs["details"]
        assert "path_trace" in details
        assert isinstance(details["path_trace"], list)

    def test_workflow_execution_error_path(self):
        """Test workflow execution following error path."""
        # Create referenced actions for workflow steps
        ref_action_1 = ActionFactory(
            name="Ref Fail Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        ref_action_2 = ActionFactory(
            name="Ref Success Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        ref_action_err = ActionFactory(
            name="Ref Error Handler",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

        # Story 47.3: error handler action needs integration for async dispatch
        integration = IntegrationFactory.create(type="aap")
        ref_action_err.integration = integration
        ref_action_err.save()

        action = ActionFactory(
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
                "referenced_action_id": ref_action_1.id,
                "on_success_step_ids": ["step-2"],
                "on_error_step_ids": ["step-error"],
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Success Step (skipped)",
                "referenced_action_id": ref_action_2.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
            {
                "step_id": "step-error",
                "order": 3,
                "name": "Error Handler",
                "referenced_action_id": ref_action_err.id,
                "on_success_step_ids": [],
                "on_error_step_ids": [],
            },
        ]
        action.execution_steps = (workflow_steps)
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

        with patch("executions.workflow_runtime.AuditService.create_entry") as create_entry:
            with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
                final_status = runtime.run()

        # Should complete (error handler ran successfully)
        assert final_status == ExecutionStatus.COMPLETED

        # Verify error handler was executed (not step-2)
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = [s.step_name for s in steps]
        assert "Failing Step" in step_names
        assert "Error Handler" in step_names
        assert "Success Step (skipped)" not in step_names  # Should be skipped

        # AC4: path trace includes an error outcome for step-1
        details = create_entry.call_args.kwargs["details"]
        assert any(t["step_id"] == "step-1" and t["outcome"] == StepOutcome.ERROR.value for t in details["path_trace"])

    def test_workflow_loop_detection(self):
        """AC5: Detect infinite loop and fail after 100 transitions."""
        # Create referenced actions for workflow steps
        ref_action_1 = ActionFactory(
            name="Ref Loop Action 1",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        ref_action_2 = ActionFactory(
            name="Ref Loop Action 2",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

        # Story 47.3: actions need integration — steps must succeed to trigger the loop
        integration = IntegrationFactory.create(type="aap")
        ref_action_1.integration = integration
        ref_action_1.save()
        ref_action_2.integration = integration
        ref_action_2.save()

        action = ActionFactory(
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
                "referenced_action_id": ref_action_1.id,
                "on_success_step_ids": ["step-2"],
                "on_error_step_ids": [],
            },
            {
                "step_id": "step-2",
                "order": 2,
                "name": "Step 2",
                "referenced_action_id": ref_action_2.id,
                "on_success_step_ids": ["step-1"],  # Loop back
                "on_error_step_ids": [],
            },
        ]
        action.execution_steps = (workflow_steps)
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        with patch("executions.workflow_runtime.AuditService.create_entry"):
            with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
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
        action = ActionFactory(
            name="Empty Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        # No steps
        action.execution_steps = ([])
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

        runtime = WorkflowRuntime(execution)
        with patch("executions.workflow_runtime.AuditService.create_entry"):
            final_status = runtime.run()

        # Should fail
        assert final_status == ExecutionStatus.FAILED

        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED


@pytest.mark.django_db
class TestWorkflowRuntimeStory412StepParameters:
    """Story 4.12 AC5/AC6: workflow_step_parameters injection and audit in step output."""

    def setup_method(self):
        self.user = UserFactory(username="story412_user")

        # Create referenced actions for workflow steps
        self.ref_action_1 = ActionFactory(
            name="Referenced Action 1",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.ref_action_2 = ActionFactory(
            name="Referenced Action 2",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

        # Create workflow with steps referencing the actions
        self.action = ActionFactory(
            name="Workflow With Params",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        # Story 47.3: actions need integration — fail-fast otherwise
        integration = IntegrationFactory.create(type="aap")
        self.ref_action_1.integration = integration
        self.ref_action_1.save()
        self.ref_action_2.integration = integration
        self.ref_action_2.save()

        self.action.execution_steps = ([
            {
                "step_id": "s1",
                "order": 1,
                "name": "Step 1",
                "referenced_action_id": self.ref_action_1.id,
                "on_success_step_ids": ["s2"],
            },
            {
                "step_id": "s2",
                "order": 2,
                "name": "Step 2",
                "referenced_action_id": self.ref_action_2.id,
                "on_success_step_ids": [],
            },
        ])
        self.action.save()

    def test_get_step_parameters_returns_params_for_step_order(self):
        """_get_step_parameters returns parameters for the step's order key."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters({
            "workflow_step_parameters": {
                "1": {"parameters": {"a": "one"}},
                "2": {"parameters": {"b": "two"}},
            }
        })
        execution.save()

        runtime = WorkflowRuntime(execution)
        step1 = {"step_id": "s1", "order": 1, "name": "Step 1"}
        step2 = {"step_id": "s2", "order": 2, "name": "Step 2"}

        assert runtime._get_step_parameters(step1) == {"a": "one"}
        assert runtime._get_step_parameters(step2) == {"b": "two"}

    def test_get_step_parameters_returns_empty_when_no_wsp(self):
        """_get_step_parameters returns {} when execution has no workflow_step_parameters."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = WorkflowRuntime(execution)
        step1 = {"step_id": "s1", "order": 1, "name": "Step 1"}
        assert runtime._get_step_parameters(step1) == {}

    def test_step_output_includes_parameters_used_and_delegated_from_workflow(self):
        """AC5/AC6: Step output contains parameters_used and delegated_from_workflow."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters({
            "workflow_step_parameters": {
                "1": {"parameters": {"x": "step1_val"}},
                "2": {"parameters": {"y": "step2_val"}},
            }
        })
        execution.save()

        runtime = WorkflowRuntime(execution)
        with patch("executions.workflow_runtime.AuditService.create_entry"):
            with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
                runtime.run()

        steps = ExecutionStep.objects.filter(execution=execution).order_by("step_order")
        assert steps.count() == 2
        out1 = steps[0].get_output() or {}
        out2 = steps[1].get_output() or {}
        assert out1.get("parameters_used") == {"x": "step1_val"}
        assert out1.get("delegated_from_workflow") is True
        assert out2.get("parameters_used") == {"y": "step2_val"}
        assert out2.get("delegated_from_workflow") is True

    def test_step_loads_referenced_action_and_dispatches_async(self):
        """AC5 UPDATED (Story 47.3): Step loads referenced action and dispatches async trigger.

        Story 47.3 supprime le chemin simulé : avec integration → async dispatch.
        """
        from tests.factories import IntegrationFactory
        # Create a referenced action with platform AAP and an integration
        ref_action = ActionFactory(
            name="Referenced AAP Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        integration = IntegrationFactory.create(type="aap")
        ref_action.integration = integration

        # Create workflow with step referencing the action
        workflow = ActionFactory(
            name="Workflow AC5 Test",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        workflow.execution_steps = ([
            {
                "step_id": "s1",
                "order": 1,
                "name": "Run AAP Action",
                "referenced_action_id": ref_action.id,
                "on_success_step_ids": [],
            }
        ])
        workflow.save()

        # Create execution with step parameters
        user = UserFactory(username="ac5_test_user")
        execution = Execution.objects.create(
            action=workflow,
            user=user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        execution.set_parameters({
            "workflow_step_parameters": {
                "1": {"parameters": {"database": "PROD01", "action": "restart"}},
            }
        })
        execution.save()

        # Run workflow
        runtime = WorkflowRuntime(execution)
        with patch("executions.workflow_runtime.AuditService.create_entry"):
            with patch("executions.tasks.trigger.trigger_platform_job.apply_async") as mock_apply:
                with patch("catalog.models.Action.objects") as mock_qs:
                    mock_qs.select_related.return_value.get.return_value = ref_action
                    runtime.run()

        # Verify step is RUNNING (async dispatched — trigger_platform_job gère la suite)
        step = ExecutionStep.objects.filter(execution=execution).first()
        assert step is not None
        output = step.get_output() or {}

        # AC5 Updated: Verify adapter async dispatch was prepared
        assert output.get("adapter_ready") is True
        assert output.get("async_dispatched") is True
        assert output.get("delegated_from_workflow") is True
        assert output.get("referenced_action_id") == ref_action.id
        assert output.get("referenced_action_name") == "Referenced AAP Action"
        assert output.get("parameters_used") == {"database": "PROD01", "action": "restart"}
        mock_apply.assert_called_once()


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


@pytest.mark.django_db
class TestCallPlatformAdapter:
    """Story 30.15 AC2/AC3: _call_platform_adapter real adapter call and fallback."""

    def setup_method(self):
        self.user = UserFactory(username="adapter_test_user")
        self.ref_action = ActionFactory(
            name="Adapter Test Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )
        self.workflow = ActionFactory(
            name="Adapter Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.workflow.execution_steps = ([{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "referenced_action_id": self.ref_action.id,
            "on_success_step_ids": [],
        }])
        self.workflow.save()
        self.execution = Execution.objects.create(
            action=self.workflow, user=self.user,
            environment="dev", status=ExecutionStatus.SUBMITTED,
        )
        self.runtime = WorkflowRuntime(self.execution)

    def test_no_integration_raises_value_error(self):
        """Story 47.3 fail-fast: sans integration, lève ValueError (plus de succès simulé)."""
        step = ExecutionStep.objects.create(
            execution=self.execution, step_order=1,
            step_name="Test", step_type="platform",
            status=ExecutionStepStatus.RUNNING,
        )
        import pytest
        with pytest.raises(ValueError) as exc_info:
            self.runtime._call_platform_adapter(
                self.ref_action, None, {"parameters": {}}, step,
            )
        assert "No integration configured" in str(exc_info.value)

    def test_adapter_call_success(self):
        """When adapter exists and works, return real adapter result."""
        from unittest.mock import AsyncMock, MagicMock
        step = ExecutionStep.objects.create(
            execution=self.execution, step_order=1,
            step_name="Test", step_type="platform",
            status=ExecutionStepStatus.RUNNING,
        )
        integration = MagicMock()
        integration.base_url = "https://aap.example.com"
        integration.get_config.return_value = {}

        mock_adapter = MagicMock()
        mock_adapter.trigger = AsyncMock(return_value={
            "platform_job_id": "42", "status": "launched",
        })

        with patch("adapters.get_platform_adapter", return_value=mock_adapter):
            with patch("adapters.utils.build_auth_headers", return_value={"Authorization": "Bearer x"}):
                result = self.runtime._call_platform_adapter(
                    self.ref_action, integration,
                    {"parameters": {}, "correlation_id": "test-123"},
                    step,
                )
        assert result["platform_job_id"] == "42"
        assert result.get("simulated") is None

    def test_adapter_call_failure_reraises_exception(self):
        """Story 47.3 fail-fast: adapter raises → exception re-raised (plus de succès simulé)."""
        from unittest.mock import MagicMock
        import pytest
        step = ExecutionStep.objects.create(
            execution=self.execution, step_order=1,
            step_name="Test", step_type="platform",
            status=ExecutionStepStatus.RUNNING,
        )
        integration = MagicMock()
        integration.base_url = "https://aap.example.com"
        integration.get_config.return_value = {}

        with patch("adapters.get_platform_adapter", side_effect=ImportError("no adapter")):
            with patch("adapters.utils.build_auth_headers", return_value={}):
                with pytest.raises(ImportError) as exc_info:
                    self.runtime._call_platform_adapter(
                        self.ref_action, integration,
                        {"parameters": {}}, step,
                    )
        assert "no adapter" in str(exc_info.value)
