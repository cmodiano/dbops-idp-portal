"""
Tests de couverture pour executions/tasks/gates.py — branches non couvertes.
Codecov: gates.py 48.57% patch coverage.
"""
import pytest
from unittest.mock import MagicMock, patch


from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from executions.tasks.gates import (
    evaluate_waiting_gates,
    _transition_step_to_running,
    _update_waiting_context,
    _handle_gate_timeout,
    resume_container_workflow_from_gate,
)
from tests.factories import ActionFactory, ExecutionFactory, ExecutionStepFactory, UserFactory


@pytest.mark.django_db
class TestResumeContainerWorkflowGenericException:
    """resume_container_workflow_from_gate — exception générique → outcome error."""

    def test_generic_exception_returns_error_outcome(self):
        """Exception non-DoesNotExist → {'outcome': 'error', 'error': str(exc)}."""
        with patch('executions.cancellation_cache.is_cancelled', return_value=False):
            with patch.object(Execution.objects, 'select_related') as mock_qs:
                mock_qs.return_value.get.side_effect = RuntimeError("Unexpected DB error")
                result = resume_container_workflow_from_gate.run(
                    execution_id=1, on_success_step_ids='step-1'
                )

        assert result['outcome'] == 'error'
        assert 'Unexpected DB error' in result['error']


@pytest.mark.django_db
class TestTransitionStepToRunningAlreadyRunning:
    """_transition_step_to_running — step déjà RUNNING (updated == 0) → early return."""

    def test_step_already_running_returns_early(self):
        """Atomic update returns 0 (another worker transitioned) → warning + return."""

        user = UserFactory(username='gate_user', profile='DBA')
        action = ActionFactory(execution_steps=[{'name': 'Gate', 'step_type': 'gate'}])
        execution = ExecutionFactory(action=action, status=ExecutionStatus.RUNNING, user=user)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_name='Gate',
        )
        step.set_output({'gate_conditions': [{'type': 'maintenance_window'}]})
        step.save()

        gate_status = {'gates': [], 'timeout_triggered': False}

        with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
            # Simulate another worker already transitioned: update returns 0
            mock_filter.return_value.update.return_value = 0

            with patch('executions.services.runnable_steps.RunnableStepService', MagicMock()):
                with patch('executions.services.workflow_events.WorkflowEventService', MagicMock()):
                    _transition_step_to_running(step, gate_status, 'corr-123')

        step.refresh_from_db()
        # Step should still be WAITING (we didn't update it)
        assert step.status == ExecutionStepStatus.WAITING


@pytest.mark.django_db
class TestUpdateWaitingContextEmitFailure:
    """_update_waiting_context — WorkflowEventService.emit_step_output_updated raises."""

    def test_emit_step_output_updated_failure_logged_continues(self):
        """emit_step_output_updated raises → error logged, step output still saved."""
        user = UserFactory(username='update_ctx_user', profile='DBA')
        action = ActionFactory(execution_steps=[])
        execution = ExecutionFactory(action=action, status=ExecutionStatus.RUNNING, user=user)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({
            'gate_conditions': [{'type': 'maintenance_window'}],
            'gate_status': [],
        })
        step.save()

        gate_status = {
            'gates': [{'type': 'maintenance_window', 'satisfied': False, 'reason': 'Outside window'}],
            'timeout_triggered': False,
        }

        with patch('executions.services.workflow_events.WorkflowEventService') as mock_events:
            mock_events.emit_step_output_updated.side_effect = RuntimeError("Emit failed")

            _update_waiting_context(step, gate_status, 'corr-123')

        step.refresh_from_db()
        output = step.get_output()
        assert 'last_evaluated_at' in output
        assert 'gate_status' in output


@pytest.mark.django_db
class TestHandleGateTimeoutFailedPath:
    """_handle_gate_timeout — timeout_action=FAILED → execution marked FAILED."""

    def test_timeout_failed_marks_execution_failed(self):
        """timeout_action=FAILED → execution status FAILED."""
        user = UserFactory(username='timeout_user', profile='DBA')
        action = ActionFactory(execution_steps=[{'name': 'Gate', 'step_type': 'gate'}])
        execution = ExecutionFactory(action=action, status=ExecutionStatus.RUNNING, user=user)
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_name='Gate',
        )
        step.set_output({'gate_conditions': []})
        step.save()

        gate_status = {
            'timeout_triggered': True,
            'action': 'FAILED',
            'timeout_hours': 48,
        }

        with patch('executions.services.runnable_steps.RunnableStepService', MagicMock()):
            with patch('executions.services.workflow_events.WorkflowEventService', MagicMock()):
                _handle_gate_timeout(step, gate_status, 'corr-123')

        step.refresh_from_db()
        execution.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert execution.status == ExecutionStatus.FAILED


@pytest.mark.django_db
class TestEvaluateWaitingGatesErrorPersistFailed:
    """evaluate_waiting_gates — error persist to step output fails → logged, continues."""

    def test_error_persist_failed_logged_task_continues(self):
        """GateEvaluator raises → step.save fails in error persist block → error logged."""
        step = ExecutionStepFactory(
            execution=ExecutionFactory(status=ExecutionStatus.RUNNING),
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({'gate_conditions': [{'type': 'maintenance_window'}]})
        step.save()

        save_call_count = [0]
        original_save = ExecutionStep.save

        def save_that_fails_once(self, *args, **kwargs):
            save_call_count[0] += 1
            if save_call_count[0] == 1:
                raise RuntimeError("DB save failed")
            return original_save(self, *args, **kwargs)

        with patch('executions.gate_evaluator.GateEvaluator') as mock_eval_cls:
            mock_eval_cls.return_value.evaluate.side_effect = RuntimeError("Evaluation error")
            with patch.object(ExecutionStep, 'save', save_that_fails_once):
                result = evaluate_waiting_gates()

        assert result['errors'] == 1
        assert result['waiting_steps'] == 1


@pytest.mark.django_db
class TestGetNextStepIdByOrder:
    """_get_next_step_by_order — helper used in _handle_gate_timeout."""

    def test_get_next_step_id_excludes_parallel_members(self):
        """Excludes parallel_group member steps from next step lookup."""
        from executions.tasks.gates import _get_next_step_by_order

        steps = [
            {'step_id': 's1', 'order': 1, 'step_type': 'platform'},
            {'step_id': 'pg-1', 'order': 2, 'step_type': 'parallel_group', 'parallel_steps': ['p1', 'p2']},
            {'step_id': 'p1', 'order': 3, 'step_type': 'platform'},
            {'step_id': 'p2', 'order': 4, 'step_type': 'platform'},
            {'step_id': 's3', 'order': 5, 'step_type': 'platform'},
        ]
        current = {'step_id': 'pg-1', 'order': 2}
        next_step = _get_next_step_by_order(steps, current)
        next_id = next_step.get('step_id') if next_step else None
        assert next_id == 's3'
        assert next_id != 'p1'
        assert next_id != 'p2'
