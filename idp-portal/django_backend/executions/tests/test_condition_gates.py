"""
Unit tests for condition gates — Story 25.2

Tests:
- AC1: WAITING status in ExecutionStepStatus
- AC3: WorkflowRuntime creates ExecutionStep in WAITING if gate_conditions
- AC4: Waiting context stored in ExecutionStep.output
- AC5: Validation of gate_conditions schema
"""

import json
import pytest
from rest_framework.exceptions import ValidationError

from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from executions.gate_context import build_waiting_context
from executions.workflow_runtime import (
    WorkflowRuntime,
    StepResult,
    StepOutcome,
)
from catalog.models import ActionStatus, ActionItemType
from catalog.validators import validate_gate_conditions
from tests.factories import (
    UserFactory,
    ActionFactory,
    ExecutionFactory,
    ExecutionStepFactory,
    IntegrationFactory,
)


# =============================================================================
# AC1: WAITING status in ExecutionStepStatus
# =============================================================================


@pytest.mark.django_db
class TestWaitingStatus:
    """Test WAITING status is available on ExecutionStep."""

    def test_waiting_status_exists_in_choices(self):
        """ExecutionStepStatus contains WAITING."""
        assert hasattr(ExecutionStepStatus, 'WAITING')
        assert ExecutionStepStatus.WAITING == 'WAITING'

    def test_execution_step_can_be_created_with_waiting_status(self):
        """ExecutionStep can be created with status='WAITING'."""
        execution = ExecutionFactory()
        step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name="Deploy patch",
            step_type='platform',
            status=ExecutionStepStatus.WAITING,
        )
        assert step.status == 'WAITING'
        step.refresh_from_db()
        assert step.status == 'WAITING'

    def test_waiting_status_label(self):
        """WAITING status has correct label."""
        assert ExecutionStepStatus.WAITING.label == 'Waiting'


# =============================================================================
# AC5: Validation of gate_conditions
# =============================================================================


@pytest.mark.django_db
class TestValidateGateConditions:
    """Test validate_gate_conditions function."""

    def test_valid_maintenance_window(self):
        """Valid maintenance_window gate condition passes validation."""
        gate_conditions = [
            {
                'type': 'maintenance_window',
                'timeout_hours': 48,
                'on_timeout': 'FAIL',
            }
        ]
        validate_gate_conditions(gate_conditions)  # Should not raise

    def test_valid_time_window(self):
        """Valid time_window gate condition passes validation."""
        gate_conditions = [
            {
                'type': 'time_window',
                'after': '22:00',
                'before': '06:00',
                'timezone': 'America/Toronto',
                'timeout_hours': 24,
                'on_timeout': 'SKIP',
            }
        ]
        validate_gate_conditions(gate_conditions)

    def test_valid_approval_granted(self):
        """Valid approval_granted gate condition passes validation."""
        gate_conditions = [
            {
                'type': 'approval_granted',
                'description': 'Attendre approbation DBA',
                'timeout_hours': 48,
                'on_timeout': 'FAIL',
            }
        ]
        validate_gate_conditions(gate_conditions)

    def test_valid_target_state(self):
        """Valid target_state gate condition passes validation."""
        gate_conditions = [
            {
                'type': 'target_state',
                'required_state': 'MAINTENANCE',
                'timeout_hours': 12,
                'on_timeout': 'SKIP',
            }
        ]
        validate_gate_conditions(gate_conditions)

    def test_valid_empty_list(self):
        """Empty gate_conditions list is valid (no gates)."""
        validate_gate_conditions([])

    def test_valid_minimal_condition(self):
        """Condition with only type field is valid."""
        gate_conditions = [{'type': 'maintenance_window'}]
        validate_gate_conditions(gate_conditions)

    def test_valid_multiple_conditions(self):
        """Multiple gate conditions pass validation."""
        gate_conditions = [
            {'type': 'maintenance_window', 'timeout_hours': 72, 'on_timeout': 'FAIL'},
            {'type': 'approval_granted', 'timeout_hours': 48, 'on_timeout': 'FAIL'},
        ]
        validate_gate_conditions(gate_conditions)

    def test_invalid_not_a_list(self):
        """gate_conditions must be a list."""
        with pytest.raises(ValidationError, match="must be a list"):
            validate_gate_conditions("not a list")

    def test_invalid_type_missing(self):
        """Missing 'type' field raises ValidationError."""
        gate_conditions = [{'description': 'some gate'}]
        with pytest.raises(ValidationError, match="'type' field is required"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_type_unknown(self):
        """Unknown type value raises ValidationError."""
        gate_conditions = [{'type': 'unknown_type'}]
        with pytest.raises(ValidationError, match="'type' must be one of"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_timeout_hours_zero(self):
        """timeout_hours = 0 raises ValidationError."""
        gate_conditions = [{'type': 'maintenance_window', 'timeout_hours': 0}]
        with pytest.raises(ValidationError, match="'timeout_hours' must be a positive number"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_timeout_hours_negative(self):
        """Negative timeout_hours raises ValidationError."""
        gate_conditions = [{'type': 'maintenance_window', 'timeout_hours': -5}]
        with pytest.raises(ValidationError, match="'timeout_hours' must be a positive number"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_timeout_hours_string(self):
        """String timeout_hours raises ValidationError."""
        gate_conditions = [{'type': 'maintenance_window', 'timeout_hours': 'abc'}]
        with pytest.raises(ValidationError, match="'timeout_hours' must be a positive number"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_on_timeout_value(self):
        """Invalid on_timeout value raises ValidationError."""
        gate_conditions = [{'type': 'maintenance_window', 'on_timeout': 'RETRY'}]
        with pytest.raises(ValidationError, match="'on_timeout' must be one of"):
            validate_gate_conditions(gate_conditions)

    def test_invalid_condition_not_dict(self):
        """Non-dict condition in list raises ValidationError."""
        gate_conditions = ["not a dict"]
        with pytest.raises(ValidationError, match="must be an object"):
            validate_gate_conditions(gate_conditions)

    def test_multiple_errors_collected(self):
        """Multiple errors in different conditions are collected."""
        gate_conditions = [
            {'type': 'unknown'},
            {'description': 'missing type'},
            {'type': 'maintenance_window', 'timeout_hours': -1},
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_gate_conditions(gate_conditions)
        errors = exc_info.value.detail
        assert len(errors) == 3


# =============================================================================
# AC4: build_waiting_context
# =============================================================================


@pytest.mark.django_db
class TestBuildWaitingContext:
    """Test build_waiting_context function."""

    def test_basic_context(self):
        """Context contains waiting_since, gate_conditions, gate_status."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(
            execution=execution,
            step_order=1,
            step_name="Deploy",
            status=ExecutionStepStatus.WAITING,
        )

        gate_conditions = [
            {
                'type': 'maintenance_window',
                'timeout_hours': 48,
                'on_timeout': 'FAIL',
            }
        ]

        context = build_waiting_context(step, gate_conditions)

        assert 'waiting_since' in context
        assert context['gate_conditions'] == gate_conditions
        assert len(context['gate_status']) == 1
        assert context['gate_status'][0]['type'] == 'maintenance_window'
        assert context['gate_status'][0]['satisfied'] is False
        assert context['gate_status'][0]['reason'] == "En attente d'évaluation"
        assert context['gate_status'][0]['next_evaluation_at'] is None

    def test_multiple_conditions_context(self):
        """Context tracks status for each gate condition."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(
            execution=execution,
            step_order=1,
            status=ExecutionStepStatus.WAITING,
        )

        gate_conditions = [
            {'type': 'maintenance_window', 'timeout_hours': 72},
            {'type': 'approval_granted', 'timeout_hours': 48},
        ]

        context = build_waiting_context(step, gate_conditions)

        assert len(context['gate_status']) == 2
        assert context['gate_status'][0]['type'] == 'maintenance_window'
        assert context['gate_status'][1]['type'] == 'approval_granted'
        assert all(s['satisfied'] is False for s in context['gate_status'])

    def test_context_serializable_to_json(self):
        """Waiting context can be serialized to JSON."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(
            execution=execution,
            step_order=1,
            status=ExecutionStepStatus.WAITING,
        )

        context = build_waiting_context(step, [{'type': 'maintenance_window'}])
        json_str = json.dumps(context)
        parsed = json.loads(json_str)
        assert parsed['gate_conditions'][0]['type'] == 'maintenance_window'

    def test_context_stored_in_execution_step_output(self):
        """Context can be stored and retrieved via ExecutionStep.output."""
        execution = ExecutionFactory()
        step = ExecutionStepFactory(
            execution=execution,
            step_order=1,
            status=ExecutionStepStatus.WAITING,
        )

        gate_conditions = [{'type': 'maintenance_window', 'timeout_hours': 48}]
        context = build_waiting_context(step, gate_conditions)
        step.set_output(context)
        step.save()

        step.refresh_from_db()
        output = step.get_output()
        assert output is not None
        assert output['waiting_since'] is not None
        assert output['gate_conditions'][0]['type'] == 'maintenance_window'
        assert output['gate_status'][0]['satisfied'] is False


# =============================================================================
# AC3: WorkflowRuntime creates WAITING ExecutionStep
# =============================================================================


@pytest.mark.django_db
class TestWorkflowRuntimeGateConditions:
    """Test WorkflowRuntime behavior with gate_conditions."""

    def setup_method(self):
        """Create base user for workflow tests."""
        self.user = UserFactory(username="gate_test_user")

    def _create_ref_action(self, name="Ref Action"):
        """Create a referenced action with integration for workflow steps."""
        integration = IntegrationFactory()
        action = ActionFactory(
            name=name,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
        )
        return action

    def _create_workflow(self, execution_steps):
        """Create a workflow action and execution."""
        action = ActionFactory(
            name="Test Workflow Gates",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        action.execution_steps = execution_steps
        action.save()

        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )
        return execution

    def test_step_with_gate_conditions_creates_waiting_step(self):
        """If step has gate_conditions, ExecutionStep is created in WAITING."""
        ref_action = self._create_ref_action()

        execution = self._create_workflow([
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 48}
                ],
            }
        ])

        runtime = WorkflowRuntime(execution)
        step_def = runtime.workflow_steps[0]
        result = runtime._execute_step(step_def)

        assert result.outcome == StepOutcome.WAITING
        assert result.is_waiting is True

        step = ExecutionStep.objects.get(execution=execution, step_order=1)
        assert step.status == 'WAITING'

        output = step.get_output()
        assert output is not None
        assert output['waiting_since'] is not None
        assert output['gate_conditions'][0]['type'] == 'maintenance_window'
        assert output['gate_status'][0]['satisfied'] is False

    def test_step_without_gate_conditions_executes_normally(self):
        """If step has NO gate_conditions, ExecutionStep is created normally (not WAITING)."""
        ref_action = self._create_ref_action()

        execution = self._create_workflow([
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
            }
        ])

        runtime = WorkflowRuntime(execution)
        step_def = runtime.workflow_steps[0]

        # Story 47.2: avec integration → async dispatch. Mocker apply_async pour éviter
        # l'exécution ALWAYS_EAGER qui tenterait de vraiment appeler l'adapter AAP.
        from unittest.mock import patch
        with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
            result = runtime._execute_step(step_def)

        assert result.outcome == StepOutcome.SUCCESS

        step = ExecutionStep.objects.get(execution=execution, step_order=1)
        # Story 47.2: async dispatch → step reste RUNNING jusqu'à ce que trigger_platform_job complète
        assert step.status == 'RUNNING'

    def test_step_with_empty_gate_conditions_executes_normally(self):
        """Empty gate_conditions list means no gates — normal execution."""
        ref_action = self._create_ref_action()

        execution = self._create_workflow([
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
                'gate_conditions': [],
            }
        ])

        runtime = WorkflowRuntime(execution)
        step_def = runtime.workflow_steps[0]
        result = runtime._execute_step(step_def)

        assert result.outcome == StepOutcome.SUCCESS

    def test_workflow_stops_at_waiting_step(self):
        """Workflow run() stops when encountering a WAITING step and stays RUNNING."""
        ref_action1 = self._create_ref_action("Prepare Action")
        ref_action2 = self._create_ref_action("Deploy Action")

        execution = self._create_workflow([
            {
                'order': 1,
                'step_id': 'prepare',
                'name': 'Prepare',
                'type': 'platform',
                'referenced_action_id': ref_action1.id,
                'on_success_step_ids': ['deploy'],
            },
            {
                'order': 2,
                'step_id': 'deploy',
                'name': 'Deploy',
                'type': 'platform',
                'referenced_action_id': ref_action2.id,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 72}
                ],
                'on_success_step_ids': ['verify'],
            },
            {
                'order': 3,
                'step_id': 'verify',
                'name': 'Verify',
                'type': 'platform',
                'referenced_action_id': ref_action1.id,
            },
        ])

        runtime = WorkflowRuntime(execution)
        # Story 47.2: avec integration → async dispatch. Mocker apply_async pour éviter
        # l'exécution ALWAYS_EAGER qui tenterait de vraiment appeler l'adapter AAP.
        from unittest.mock import patch
        with patch("executions.tasks.trigger.trigger_platform_job.apply_async"):
            final_status = runtime.run()

        # Workflow should stay RUNNING (not COMPLETED or FAILED)
        assert final_status == ExecutionStatus.RUNNING

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert steps.count() == 2

        # First step async-dispatched → reste RUNNING jusqu'à ce que trigger_platform_job complète
        assert steps[0].status == 'RUNNING'

        # Second step is WAITING
        assert steps[1].status == 'WAITING'
        output = steps[1].get_output()
        assert output['gate_conditions'][0]['type'] == 'maintenance_window'

        # Third step should NOT have been created
        assert not ExecutionStep.objects.filter(
            execution=execution, step_name='Verify'
        ).exists()

    def test_waiting_step_does_not_set_completed_at(self):
        """When workflow pauses for WAITING, execution.completed_at is not set."""
        ref_action = self._create_ref_action()

        execution = self._create_workflow([
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy',
                'type': 'platform',
                'referenced_action_id': ref_action.id,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 48}
                ],
            }
        ])

        runtime = WorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        assert execution.status == 'RUNNING'

    def test_step_result_is_waiting_property(self):
        """StepResult.is_waiting property works correctly."""
        waiting_result = StepResult(outcome=StepOutcome.WAITING)
        assert waiting_result.is_waiting is True
        assert waiting_result.is_success is False
        assert waiting_result.is_error is False

        success_result = StepResult(outcome=StepOutcome.SUCCESS)
        assert success_result.is_waiting is False

        error_result = StepResult(outcome=StepOutcome.ERROR)
        assert error_result.is_waiting is False
