"""Orchestration worker — Story 78.5: queue-based step-by-step execution.

Claims runnable steps, executes them via ContainerWorkflowRuntime, then
enqueues the next steps. Replaces the thread-based _run_workflow_loop.

Usage (Celery Beat):
    process_runnable_steps.apply_async()
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.db import transaction
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStepType,
)
from executions.domain.state_machine import assert_execution_transition
from executions.infra.work_queue import WorkQueue
from executions.observability import get_runnable_queue_depth

logger = structlog.get_logger(__name__)


def _build_runtime_for_step(execution: Execution, exec_step: ExecutionStep) -> tuple[Any, dict[Any, Any]]:
    """Build a minimal ContainerWorkflowRuntime with reconstructed _step_outputs."""
    from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
    from executions.tasks.gates import _build_step_outputs_from_completed  # noqa: PLC0415

    runtime = ContainerWorkflowRuntime(execution)

    # Reconstruct _step_outputs from completed steps in DB
    all_steps = execution.action.execution_steps or []
    step_name_to_id = {
        s.get('name'): s.get('step_id')
        for s in all_steps
        if isinstance(s, dict) and s.get('name') and s.get('step_id')
    }
    step_config_by_id = {
        s.get('step_id'): s
        for s in all_steps
        if isinstance(s, dict) and s.get('step_id')
    }

    completed_steps = ExecutionStep.objects.filter(
        execution=execution,
        status=ExecutionStepStatus.COMPLETED,
    ).order_by('step_order')

    _build_step_outputs_from_completed(
        completed_steps=completed_steps,
        step_config_by_id=step_config_by_id,
        step_name_to_id=step_name_to_id,
        step_outputs=runtime._step_outputs,
    )

    # Resume _step_order_counter from max existing step_order
    from django.db.models import Max  # noqa: PLC0415
    max_order = ExecutionStep.objects.filter(execution=execution).aggregate(
        Max('step_order')
    )['step_order__max']
    runtime._step_order_counter = max_order if max_order is not None else 0

    return runtime, step_config_by_id


def _enqueue_next_steps(
    runtime: Any,
    execution: Execution,
    next_step_ids: list[str],
    step_config_by_id: dict[Any, Any],
) -> int:
    """Create PENDING ExecutionSteps for next steps and enqueue them."""
    enqueued = 0
    for next_id in next_step_ids:
        step_config = step_config_by_id.get(next_id)
        if not step_config:
            logger.warning(
                "worker_next_step_config_not_found",
                execution_id=execution.id,
                step_id=next_id,
            )
            continue

        # Idempotency: check if an ExecutionStep for this config_step_id already exists
        # and is not in a terminal state (prevents duplicate creation on re-execution)
        existing = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id=next_id,
            status__in=[
                ExecutionStepStatus.PENDING,
                ExecutionStepStatus.RUNNING,
                ExecutionStepStatus.COMPLETED,
            ],
        ).exists()
        if existing:
            logger.info(
                "worker_next_step_already_exists",
                execution_id=execution.id,
                step_id=next_id,
            )
            continue

        step_type_str = step_config.get('step_type', 'platform')
        from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
        db_step_type = ContainerWorkflowRuntime._STEP_TYPE_TO_DB_TYPE.get(
            step_type_str, ExecutionStepType.PLATFORM
        )
        step_name = step_config.get('name') or f"Étape {step_config.get('order', 0)}"

        runtime._step_order_counter += 1
        exec_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=runtime._step_order_counter,
            step_name=step_name,
            config_step_id=next_id,
            step_type=db_step_type,
            status=ExecutionStepStatus.PENDING,
        )
        WorkQueue.enqueue(exec_step)
        enqueued += 1

    return enqueued


def _finalize_execution_if_done(execution: Execution, outcome: ExecutionStatus) -> None:
    """Finalize the execution if no more runnable steps and no pending steps.

    Uses transaction.atomic to ensure the check+update is race-free when
    multiple workers/commands finalize concurrently (e.g. fan-out last steps).
    """
    with transaction.atomic():
        # Check if there are any remaining PENDING or RUNNING steps
        has_active_steps = ExecutionStep.objects.filter(
            execution=execution,
            status__in=[ExecutionStepStatus.PENDING, ExecutionStepStatus.RUNNING],
        ).exists()

        # Check for WAITING steps (gate) — execution stays RUNNING
        has_waiting_steps = ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
        ).exists()

        if has_active_steps or has_waiting_steps:
            return

        # Determine final status from step outcomes
        has_failed = ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.FAILED,
        ).exists()

        final_status = ExecutionStatus.FAILED if has_failed else ExecutionStatus.COMPLETED

        # If the current step was cancelled, propagate
        if outcome == ExecutionStatus.CANCELLED:
            final_status = ExecutionStatus.CANCELLED

        # Validate transition legality before CAS (state_machine guards validity, CAS guards concurrency)
        assert_execution_transition(ExecutionStatus.RUNNING, final_status)

        # CAS: only update if still RUNNING
        update_fields: dict = {
            'status': final_status,
            'completed_at': timezone.now(),
        }
        if final_status == ExecutionStatus.FAILED:
            update_fields['error_message'] = "Workflow failed: a step failed"

        updated = Execution.objects.filter(
            id=execution.id,
        ).exclude(
            status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
        ).update(**update_fields)

    if updated > 0:
        logger.info(
            "worker_execution_finalized",
            execution_id=execution.id,
            final_status=final_status,
        )
        # Best-effort terminal broadcast
        try:
            execution.refresh_from_db()
            from executions.container_workflow_runtime import _broadcast_terminal  # noqa: PLC0415
            _broadcast_terminal(execution)
        except Exception:  # noqa: BLE001
            pass

        # Audit trail
        try:
            from core.services import AuditService  # noqa: PLC0415
            from core.models import AuditActionType, AuditEntityType  # noqa: PLC0415
            audit_action = {
                ExecutionStatus.COMPLETED: AuditActionType.EXECUTION_COMPLETED,
                ExecutionStatus.FAILED: AuditActionType.EXECUTION_FAILED,
                ExecutionStatus.CANCELLED: AuditActionType.EXECUTION_CANCELLED,
            }.get(final_status, AuditActionType.EXECUTION_FAILED)
            AuditService.create_entry(
                user_id=str(execution.user_id),
                action_type=audit_action,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution.id,
                details={"finalized_by": "orchestration_worker"},
                correlation_id=execution.correlation_id,
            )
        except Exception:  # noqa: BLE001
            pass


@shared_task(
    bind=True,
    name="executions.tasks.process_runnable_steps",
    max_retries=0,
    soft_time_limit=120,
    time_limit=180,
)
def process_runnable_steps(self: Any, batch_size: int = 5) -> dict:
    """Story 78.5: Claim and execute runnable steps from the queue.

    Designed to be called periodically via Celery Beat or on-demand.
    """
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"

    # Story 78.16: Emit queue depth metrics before claiming
    depth = get_runnable_queue_depth()
    logger.info(
        "process_runnable_steps_metrics",
        runnable_queue_depth=depth["pending"] + depth["running"],
        runnable_pending=depth["pending"],
        runnable_running=depth["running"],
        runnable_expired_leases=depth["expired_leases"],
    )

    claimed = WorkQueue.claim(batch_size=batch_size, worker_id=worker_id)
    if not claimed:
        return {"processed": 0, "worker_id": worker_id, "runnable_queue_depth": depth["pending"] + depth["running"]}

    processed = 0
    for runnable in claimed:
        try:
            exec_step = ExecutionStep.objects.select_related(
                'execution', 'execution__action', 'execution__user',
            ).get(id=runnable.execution_step_id)
        except ExecutionStep.DoesNotExist:
            logger.error(
                "worker_execution_step_not_found",
                runnable_id=runnable.id,
                execution_step_id=runnable.execution_step_id,
            )
            WorkQueue.release(runnable.execution_step_id)
            continue

        execution = exec_step.execution

        # Story 78.5 T2: Heartbeat — update execution.updated_at for staleness detection
        Execution.objects.filter(id=execution.id).update(updated_at=timezone.now())

        # Idempotency guard: skip already processed steps
        if exec_step.status in (ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED, ExecutionStepStatus.SKIPPED):
            logger.info(
                "worker_step_already_processed",
                execution_step_id=exec_step.id,
                status=exec_step.status,
            )
            WorkQueue.release(runnable.execution_step_id)
            continue

        # Skip if execution is no longer RUNNING
        execution.refresh_from_db(fields=['status'])
        if execution.status != ExecutionStatus.RUNNING:
            logger.info(
                "worker_execution_not_running",
                execution_id=execution.id,
                execution_status=execution.status,
                execution_step_id=exec_step.id,
            )
            WorkQueue.release(runnable.execution_step_id)
            continue

        # Build runtime and find step config
        try:
            runtime, step_config_by_id = _build_runtime_for_step(execution, exec_step)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "worker_runtime_build_failed",
                execution_id=execution.id,
                execution_step_id=exec_step.id,
                error=str(exc),
                exc_info=True,
            )
            exec_step.status = ExecutionStepStatus.FAILED
            exec_step.completed_at = timezone.now()
            exec_step.error_message = f"Runtime build failed: {exc}"
            exec_step.save(update_fields=['status', 'completed_at', 'error_message'])
            WorkQueue.release(runnable.execution_step_id)
            _finalize_execution_if_done(execution, ExecutionStatus.FAILED)
            continue

        step_config = step_config_by_id.get(exec_step.config_step_id or "")
        if not step_config:
            logger.error(
                "worker_step_config_not_found",
                execution_id=execution.id,
                config_step_id=exec_step.config_step_id,
            )
            exec_step.status = ExecutionStepStatus.FAILED
            exec_step.completed_at = timezone.now()
            exec_step.error_message = f"Step config not found: {exec_step.config_step_id}"
            exec_step.save(update_fields=['status', 'completed_at', 'error_message'])
            WorkQueue.release(runnable.execution_step_id)
            _finalize_execution_if_done(execution, ExecutionStatus.FAILED)
            continue

        # Execute the step
        try:
            outcome, next_step_ids = runtime.execute_single_step(exec_step, step_config)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "worker_step_execution_failed",
                execution_id=execution.id,
                execution_step_id=exec_step.id,
                error=str(exc),
                exc_info=True,
            )
            if exec_step.status not in (ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED):
                exec_step.status = ExecutionStepStatus.FAILED
                exec_step.completed_at = timezone.now()
                exec_step.error_message = str(exc)
                exec_step.save(update_fields=['status', 'completed_at', 'error_message'])
            outcome = ExecutionStatus.FAILED
            next_step_ids = []

        # Dequeue the processed step
        WorkQueue.release(runnable.execution_step_id)

        # Enqueue next steps (if not WAITING / no next)
        if next_step_ids:
            _enqueue_next_steps(runtime, execution, next_step_ids, step_config_by_id)
        else:
            # No next steps — check if execution is done
            _finalize_execution_if_done(execution, outcome)

        processed += 1

    return {
        "processed": processed,
        "worker_id": worker_id,
        "runnable_queue_depth": depth["pending"] + depth["running"],
        "runnable_expired_leases": depth["expired_leases"],
    }
