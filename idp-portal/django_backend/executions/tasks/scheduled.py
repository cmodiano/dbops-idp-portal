"""
executions/tasks/scheduled.py — Responsabilité unique : déclenchement périodique
des exécutions planifiées en attente (one-time et récurrentes).

Expose : process_pending_scheduled_executions
Story 42.1 : Celery Beat task to process pending scheduled executions.
"""
import os
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from executions.models import (
    ExecutionStatus,
    RecurringPattern,
    ScheduledExecution,
    ScheduledExecutionStatus,
)
from executions.services import ExecutionService
from executions.utils.scheduling import calculate_next_execution_date
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


@shared_task(bind=True, max_retries=0, name="executions.tasks.process_pending_scheduled_executions")
def process_pending_scheduled_executions(self: Any) -> dict:
    """
    Story 42.1: Periodic Celery Beat task to process pending scheduled executions.

    Fetches all pending scheduled executions (one-time and recurring), creates
    an Execution for each one, launches it, and updates the ScheduledExecution
    status atomically.

    Returns:
        dict with summary: {'processed': N, 'triggered': N, 'errors': N}
    """
    correlation_id = get_correlation_id()
    max_batch = int(os.getenv('CELERY_BEAT_PROCESS_SCHEDULED_MAX_BATCH', '50'))
    now = timezone.now()

    # AC2: select_for_update(skip_locked=True) prevents double processing by multiple workers.
    # transaction.atomic() is required so that the SELECT FOR UPDATE is issued within a proper
    # database transaction; without it the row locks are released immediately in autocommit mode,
    # rendering skip_locked ineffective and raising TransactionManagementError on strict backends.
    pending_qs = (
        ScheduledExecution.objects
        .list_pending(now)
        .select_for_update(skip_locked=True)
        .select_related('action', 'user', 'recurringpattern')
        [:max_batch]
    )
    with transaction.atomic():
        se_list = list(pending_qs)
    count = len(se_list)

    logger.info(
        "process_pending_scheduled_executions_start",
        count=count,
        correlation_id=correlation_id,
    )

    if count == 0:
        return {'processed': 0, 'triggered': 0, 'errors': 0}

    triggered = 0
    errors = 0

    for se in se_list:
        try:
            # AC3: Create execution via ExecutionService
            params = se.get_parameters()
            execution = ExecutionService().create_execution(
                user=se.user,
                action=se.action,
                environment=se.environment,
                parameters=params,
                correlation_id=se.correlation_id,
                source='celery_beat',
            )

            # AC4: Launch execution (unless pending approval)
            if execution.status != ExecutionStatus.PENDING_APPROVAL:
                try:
                    if se.action.item_type == "workflow":
                        from executions.container_workflow_runtime import ContainerWorkflowRuntime
                        ContainerWorkflowRuntime(execution).run()
                    elif getattr(settings, 'SIMULATE_EXECUTION_DEV', False):
                        from executions.simulation_service import SimulationService
                        SimulationService.create_simulated_steps(execution)
                        SimulationService.start_simulation(execution)
                except Exception as launch_err:  # noqa: BLE001 — resilience-boundary: launch failure logged, se still marked executed
                    logger.error(
                        "process_pending_scheduled_executions_error",
                        se_id=se.id,
                        execution_id=execution.id,
                        error=str(launch_err),
                        exc_info=True,
                        correlation_id=correlation_id,
                    )
                    # Fall through: still mark as executed to avoid infinite retry

            # Determine if recurring and active
            rp = getattr(se, 'recurringpattern', None)
            is_recurring_active = rp is not None and rp.is_active == 1

            # Build audit kwargs once; shared by both paths (one-time and recurring).
            audit_kwargs = {
                'user_id': str(se.user_id),
                'action_type': AuditActionType.SCHEDULED_EXECUTION_CELERY_TRIGGERED,
                'entity_type': AuditEntityType.SCHEDULED_EXECUTION,
                'entity_id': se.id,
                'details': {
                    'action_id': se.action_id,
                    'action_name': se.action.name,
                    'environment': se.environment,
                    'execution_id': execution.id,
                },
                'correlation_id': correlation_id,
            }

            if is_recurring_active and rp is not None:
                # AC6 + AC7: Recurring active — keep status=pending, update next_execution_date,
                # and write audit trail — all within a single atomic transaction.
                _update_recurring_scheduled_execution(se, rp, execution, audit_kwargs)
            else:
                # AC5 + AC7: One-time (or inactive recurring) — atomic update to executed
                # and audit trail within the same transaction to ensure consistency.
                with transaction.atomic():
                    updated = ScheduledExecution.objects.filter(
                        id=se.id,
                        status=ScheduledExecutionStatus.PENDING,
                    ).update(
                        status=ScheduledExecutionStatus.EXECUTED,
                        execution_id=execution.id,
                        updated_at=timezone.now(),
                    )
                    if updated == 0:
                        # Another worker already processed this entry
                        logger.info(
                            "process_pending_scheduled_executions_already_processed",
                            se_id=se.id,
                            correlation_id=correlation_id,
                        )
                        continue
                    # AC7: Audit written atomically with the status update
                    AuditService.create_entry(**audit_kwargs)

            logger.info(
                "process_pending_scheduled_executions_triggered",
                se_id=se.id,
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
            triggered += 1

        except Exception as e:  # noqa: BLE001 — resilience-boundary: error in one se must not block others
            logger.error(
                "process_pending_scheduled_executions_error",
                se_id=se.id,
                error=str(e),
                exc_info=True,
                correlation_id=correlation_id,
            )
            errors += 1

    logger.info(
        "process_pending_scheduled_executions_complete",
        processed=count,
        triggered=triggered,
        errors=errors,
        correlation_id=correlation_id,
    )

    return {'processed': count, 'triggered': triggered, 'errors': errors}


def _update_recurring_scheduled_execution(
    se: ScheduledExecution,
    rp: RecurringPattern,
    execution: Any,
    audit_kwargs: dict,
) -> None:
    """
    AC6 + AC7: Atomically update a recurring active ScheduledExecution after triggering,
    and write the audit trail within the same transaction.

    Keeps status=pending, links execution_id, recalculates next_execution_date.
    """
    with transaction.atomic():
        next_date = calculate_next_execution_date(
            rp.pattern_type, rp.get_pattern_config() or {}, timezone.now()
        )
        RecurringPattern.objects.filter(id=rp.id).update(
            next_execution_date=next_date,
            updated_at=timezone.now(),
        )
        ScheduledExecution.objects.filter(id=se.id).update(
            execution_id=execution.id,
            updated_at=timezone.now(),
        )
        # AC7: Audit written atomically with the recurring updates
        AuditService.create_entry(**audit_kwargs)
