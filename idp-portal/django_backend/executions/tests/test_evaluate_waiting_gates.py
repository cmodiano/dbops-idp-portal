"""
Integration tests for evaluate_waiting_gates Celery task — Story 25.3 AC12

Tests:
- No WAITING steps → task completes without error
- WAITING step + conditions satisfied → RUNNING + audit trail
- WAITING step + conditions NOT satisfied → stays WAITING + output updated
- WAITING step + timeout expired → FAILED/SKIPPED + audit trail
- Parent execution COMPLETED → WAITING step NOT processed
- GateEvaluator error → step skipped, task continues
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone

from executions.models import (
    ExecutionStepStatus,
)
from executions.gate_evaluator import GateEvaluator
from executions.tasks import evaluate_waiting_gates
from core.models import AuditActionType, AuditLog
from tests.factories import (
    ExecutionFactory,
    ExecutionStepFactory,
    ExecutionTargetFactory,
)


def _create_waiting_step(gate_conditions, execution_status='RUNNING', created_at=None):
    """Create an ExecutionStep in WAITING status with gate_conditions."""
    execution = ExecutionFactory(status=execution_status)
    step = ExecutionStepFactory(
        execution=execution,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        'waiting_since': timezone.now().isoformat(),
        'gate_conditions': gate_conditions,
        'gate_status': [
            {'type': c['type'], 'satisfied': False, 'reason': "En attente"}
            for c in gate_conditions
        ],
    })
    if created_at:
        step.created_at = created_at
    step.save()
    return step


@pytest.mark.django_db
class TestEvaluateWaitingGatesTask:
    """Integration tests for the evaluate_waiting_gates Celery task."""

    def test_no_waiting_steps_completes_without_error(self):
        """AC12: No WAITING steps → task completes without error."""
        result = evaluate_waiting_gates()

        assert result['waiting_steps'] == 0
        assert result['unblocked'] == 0
        assert result['still_waiting'] == 0
        assert result['errors'] == 0

    def test_waiting_step_satisfied_transitions_to_running(self):
        """AC12: WAITING step + satisfied → RUNNING + audit trail."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        ExecutionTargetFactory(execution=step.execution, target_id='SERVER1')

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            }),
        ):
            mock_task = MagicMock()
            with patch('executions.tasks.retry_workflow_step') as mock_retry:
                mock_retry.apply_async = mock_task
                result = evaluate_waiting_gates()

        assert result['unblocked'] == 1
        assert result['still_waiting'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.RUNNING
        assert step.started_at is not None

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_GATE_SATISFIED,
            entity_id=step.execution_id,
        )
        assert audit.exists()

    def test_waiting_step_not_satisfied_stays_waiting(self):
        """AC12: WAITING step + NOT satisfied → stays WAITING + output updated."""
        step = _create_waiting_step([{'type': 'maintenance_window'}])

        next_start = timezone.now() + timedelta(hours=3)
        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [{
                    'type': 'maintenance_window',
                    'satisfied': False,
                    'reason': 'Outside window',
                    'next_possible_at': next_start.isoformat(),
                }],
                'timeout_triggered': False,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['still_waiting'] == 1
        assert result['unblocked'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.WAITING

        output = step.get_output()
        assert 'last_evaluated_at' in output

    def test_waiting_step_timeout_fail(self):
        """AC12: WAITING step + timeout → FAILED + audit trail."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'FAIL'}],
            created_at=created_at,
        )

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [],
                'timeout_triggered': True,
                'action': 'FAILED',
                'timeout_hours': 48,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['errors'] == 1  # Timeout counts as processed

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.FAILED
        assert step.completed_at is not None

        # Verify timeout audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_GATE_TIMEOUT,
            entity_id=step.execution_id,
        )
        assert audit.exists()

    def test_waiting_step_timeout_skip(self):
        """AC12: WAITING step + timeout + on_timeout=SKIP → SKIPPED."""
        created_at = timezone.now() - timedelta(hours=50)
        step = _create_waiting_step(
            [{'type': 'maintenance_window', 'timeout_hours': 48, 'on_timeout': 'SKIP'}],
            created_at=created_at,
        )

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [],
                'timeout_triggered': True,
                'action': 'SKIPPED',
                'timeout_hours': 48,
            }),
        ):
            evaluate_waiting_gates()

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.SKIPPED

    def test_parent_execution_completed_not_processed(self):
        """AC12: Parent execution COMPLETED → WAITING step NOT selected."""
        step = _create_waiting_step(
            [{'type': 'maintenance_window'}],
            execution_status='COMPLETED',
        )

        result = evaluate_waiting_gates()

        # Step should NOT be processed (filter: execution.status=RUNNING)
        assert result['waiting_steps'] == 0

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.WAITING  # Unchanged

    def test_evaluator_error_step_skipped_task_continues(self):
        """AC12: GateEvaluator error → step skipped, task continues."""
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])

        call_count = [0]

        def mock_evaluate(self_eval, step):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Unexpected error")
            return (True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            })

        with patch.object(GateEvaluator, 'evaluate', mock_evaluate):
            with patch('executions.tasks.retry_workflow_step') as mock_retry:
                mock_retry.apply_async = MagicMock()
                result = evaluate_waiting_gates()

        # One errored, one unblocked
        assert result['errors'] == 1
        assert result['unblocked'] == 1

    def test_multiple_waiting_steps_all_processed(self):
        """Multiple WAITING steps are all evaluated in one pass."""
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])
        _create_waiting_step([{'type': 'maintenance_window'}])

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(False, {
                'gates': [{'type': 'maintenance_window', 'satisfied': False, 'reason': 'Waiting'}],
                'timeout_triggered': False,
            }),
        ):
            result = evaluate_waiting_gates()

        assert result['waiting_steps'] == 3
        assert result['still_waiting'] == 3

    def test_action_execution_steps_none_edge_case(self):
        """Story 25.3 code review LOW-3: Edge case action.execution_steps = None."""
        from tests.factories import ActionFactory

        # Use ActionFactory with execution_steps explicitly set to None
        action = ActionFactory(execution_steps=None)
        execution = ExecutionFactory(action=action, status='RUNNING')
        step = _create_waiting_step([{'type': 'maintenance_window'}])
        step.execution = execution
        step.save()

        with patch.object(
            GateEvaluator,
            'evaluate',
            return_value=(True, {
                'gates': [{'type': 'maintenance_window', 'satisfied': True}],
                'timeout_triggered': False,
            }),
        ):
            with patch('executions.tasks.retry_workflow_step') as mock_retry:
                mock_retry.apply_async = MagicMock()
                evaluate_waiting_gates()

        # Step transitions to RUNNING even though execution_steps is None
        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.RUNNING

        # retry_workflow_step NOT called (no step_def found)
        assert mock_retry.apply_async.call_count == 0
