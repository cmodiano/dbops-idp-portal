"""
Tests unitaires pour process_pending_scheduled_executions — Story 42.1 AC10

Tests:
- T5.2: Aucune scheduled_execution pending → résultat vide
- T5.3: One-time pending → status=executed, execution_id lié
- T5.4: Récurrente active → status=pending conservé, next_execution_date recalculé
- T5.5: Récurrente inactive (is_active=0) → traitée comme one-time → status=executed
- T5.6: Erreur BadRequestError → log + continue, error comptabilisé
- T5.7: Erreur lancement (ContainerWorkflowRuntime) → log + continue, se marquée exécutée
- T5.8: Audit entry créée pour chaque déclenchement réussi
- T5.9: Batch size respecté (slice [:max_batch])
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone

from core.models import AuditActionType
from executions.models import ScheduledExecutionStatus
from executions.tasks.scheduled import process_pending_scheduled_executions
from tests.factories import (
    ScheduledExecutionFactory,
    RecurringPatternFactory,
)


def _make_execution_mock(status='SUBMITTED'):
    """Create a mock Execution with the given status."""
    execution = MagicMock()
    execution.id = 999
    execution.status = status
    return execution


@pytest.mark.django_db
class TestProcessPendingScheduledExecutions:
    """Tests unitaires pour la tâche Celery Beat process_pending_scheduled_executions."""

    def test_no_pending_returns_empty_result(self):
        """T5.2: Aucune scheduled_execution pending → résultat vide."""
        result = process_pending_scheduled_executions()

        assert result == {'processed': 0, 'triggered': 0, 'errors': 0}

    def test_one_time_pending_triggered_and_marked_executed(self):
        """T5.3: One-time pending → Execution créée, status=executed, execution_id lié."""
        se = ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        execution_mock = _make_execution_mock()

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry') as mock_audit:
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock

            result = process_pending_scheduled_executions()

        assert result['processed'] == 1
        assert result['triggered'] == 1
        assert result['errors'] == 0

        se.refresh_from_db()
        assert se.status == ScheduledExecutionStatus.EXECUTED
        assert se.execution_id == execution_mock.id
        assert mock_audit.called

    def test_recurring_active_keeps_status_pending_and_recalculates_next_date(self):
        """T5.4: Récurrente active → status=pending conservé, next_execution_date recalculé."""
        se = ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        past_next = timezone.now() - timedelta(hours=1)
        rp = RecurringPatternFactory(
            scheduled_execution=se,
            next_execution_date=past_next,
            is_active=1,
        )
        execution_mock = _make_execution_mock()

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry'), \
             patch('executions.tasks.scheduled.calculate_next_execution_date') as mock_calc:
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock
            future_date = timezone.now() + timedelta(days=1)
            mock_calc.return_value = future_date

            result = process_pending_scheduled_executions()

        assert result['processed'] == 1
        assert result['triggered'] == 1
        assert result['errors'] == 0

        # status should remain pending (recurring)
        se.refresh_from_db()
        assert se.status == ScheduledExecutionStatus.PENDING
        assert se.execution_id == execution_mock.id

        # next_execution_date should be updated
        rp.refresh_from_db()
        assert rp.next_execution_date == future_date

    def test_recurring_inactive_treated_as_one_time_and_marked_executed(self):
        """T5.5: Récurrente inactive (is_active=0) → traitée comme one-time → status=executed."""
        se = ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        RecurringPatternFactory(
            scheduled_execution=se,
            next_execution_date=timezone.now() - timedelta(hours=1),
            is_active=0,  # inactive
        )
        execution_mock = _make_execution_mock()

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry'):
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock

            result = process_pending_scheduled_executions()

        assert result['triggered'] == 1
        assert result['errors'] == 0

        se.refresh_from_db()
        assert se.status == ScheduledExecutionStatus.EXECUTED
        assert se.execution_id == execution_mock.id

    def test_bad_request_error_on_create_execution_is_logged_and_counted(self):
        """T5.6: Erreur BadRequestError sur create_execution → loguée, comptée en errors, traitement continue."""
        from core.exceptions import BadRequestError

        se = ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.logger') as mock_logger:
            mock_instance = MockService.return_value
            mock_instance.create_execution.side_effect = BadRequestError("Integration INVALID")

            result = process_pending_scheduled_executions()

        assert result['processed'] == 1
        assert result['triggered'] == 0
        assert result['errors'] == 1
        # Verify error was logged
        assert mock_logger.error.called

        # ScheduledExecution should NOT be marked executed (error occurred before update)
        se.refresh_from_db()
        assert se.status == ScheduledExecutionStatus.PENDING

    def test_launch_error_is_logged_se_still_marked_executed(self):
        """T5.7: Erreur lancement (ContainerWorkflowRuntime) → loguée, se marquée exécutée quand même."""
        se = ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        # Use item_type=workflow to trigger ContainerWorkflowRuntime path
        se.action.item_type = 'workflow'
        se.action.save()

        execution_mock = _make_execution_mock(status='SUBMITTED')

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry'), \
             patch('executions.container_workflow_runtime.ContainerWorkflowRuntime') as MockRuntime, \
             patch('executions.tasks.scheduled.logger') as mock_logger:
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock
            # Runtime raises an error during launch
            MockRuntime.return_value.run.side_effect = RuntimeError("Container failed to start")

            result = process_pending_scheduled_executions()

        # Task should still count as triggered (se marked executed despite launch error)
        assert result['triggered'] == 1
        assert result['errors'] == 0

        # ScheduledExecution should still be marked executed (launch error does not block update)
        se.refresh_from_db()
        assert se.status == ScheduledExecutionStatus.EXECUTED
        assert se.execution_id == execution_mock.id

        # Launch error should be logged
        assert mock_logger.error.called

    def test_audit_entry_created_for_each_successful_trigger(self):
        """T5.8: Audit entry créée pour chaque déclenchement réussi."""
        ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=3),
            status='pending',
        )
        execution_mock = _make_execution_mock()

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry') as mock_audit:
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock

            result = process_pending_scheduled_executions()

        assert result['triggered'] == 2
        # Audit should be called once per successful trigger
        assert mock_audit.call_count == 2

        # Verify audit call uses the correct action type
        for audit_call in mock_audit.call_args_list:
            kwargs = audit_call.kwargs if audit_call.kwargs else audit_call[1]
            assert kwargs.get('action_type') == AuditActionType.SCHEDULED_EXECUTION_CELERY_TRIGGERED

    def test_batch_size_respected(self):
        """T5.9: Batch size respecté (slice [:max_batch])."""
        # Create 5 pending scheduled executions
        for _ in range(5):
            ScheduledExecutionFactory(
                scheduled_at=timezone.now() - timedelta(minutes=5),
                status='pending',
            )

        execution_mock = _make_execution_mock()

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry'), \
             patch.dict('os.environ', {'CELERY_BEAT_PROCESS_SCHEDULED_MAX_BATCH': '3'}):
            mock_instance = MockService.return_value
            mock_instance.create_execution.return_value = execution_mock

            result = process_pending_scheduled_executions()

        # Only 3 should be processed due to batch size limit
        assert result['processed'] == 3
        assert result['triggered'] == 3

    def test_error_in_one_se_does_not_block_others(self):
        """AC8 résilience: erreur sur une scheduled_execution ne bloque pas les autres."""
        from core.exceptions import BadRequestError

        ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=10),
            status='pending',
        )
        ScheduledExecutionFactory(
            scheduled_at=timezone.now() - timedelta(minutes=5),
            status='pending',
        )
        execution_mock = _make_execution_mock()

        call_count = 0

        def side_effect_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise BadRequestError("First one fails")
            return execution_mock

        with patch('executions.tasks.scheduled.ExecutionService') as MockService, \
             patch('executions.tasks.scheduled.AuditService.create_entry'):
            mock_instance = MockService.return_value
            mock_instance.create_execution.side_effect = side_effect_create

            result = process_pending_scheduled_executions()

        assert result['processed'] == 2
        assert result['triggered'] == 1
        assert result['errors'] == 1
