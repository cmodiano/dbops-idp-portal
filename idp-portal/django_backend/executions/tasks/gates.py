"""
executions/tasks/gates.py — Responsabilité unique : évaluation périodique des conditions
WAITING et transition des étapes de workflow vers RUNNING.

Expose : evaluate_waiting_gates
Helpers internes : _transition_step_to_running, _update_waiting_context,
                   _handle_gate_timeout
"""
import json
import os
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
)
from core.services import AuditService
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.utils import sanitize_audit_changes

logger = structlog.get_logger(__name__)


_GATES_LIMITS = settings.CELERY_TASK_TIME_LIMITS["evaluate_waiting_gates"]


@shared_task(
    bind=True,
    max_retries=0,
    name="executions.tasks.evaluate_waiting_gates",
    soft_time_limit=_GATES_LIMITS["soft"],
    time_limit=_GATES_LIMITS["hard"],
)
def evaluate_waiting_gates(self: Any) -> dict:
    """
    Story 25.3: Periodic Celery Beat task to evaluate WAITING gate conditions.

    Selects all ExecutionSteps in WAITING status with a RUNNING parent execution,
    evaluates their gate_conditions via GateEvaluator, and transitions them to
    RUNNING (if all conditions satisfied) or updates their waiting context.

    Story 25.3 code review fix MEDIUM-4: Batch processing to prevent timeout on large volumes.

    Returns:
        dict with summary of evaluation results
    """
    from executions.gate_evaluator import GateEvaluator

    # Story 72.1 (AC3): get_correlation_id() retourne None dans les workers Celery (pas de
    # contexte HTTP). On utilise un correlation_id de tâche pour les logs globaux de la tâche,
    # et step.execution.correlation_id pour chaque step dans la boucle.
    task_correlation_id = get_correlation_id()

    # Story 25.3 code review fix MEDIUM-4: Configurable batch size to prevent task timeout
    max_steps_per_batch = int(os.getenv('CELERY_BEAT_EVALUATE_GATES_MAX_STEPS', '100'))

    # AC2: Select WAITING steps with RUNNING parent execution
    # Order by created_at to prioritize oldest waiting steps first (FIFO fairness)
    # prefetch_related('execution__targets') is safe here thanks to max_steps_per_batch limiting
    waiting_steps = (
        ExecutionStep.objects.filter(
            status=ExecutionStepStatus.WAITING,
            execution__status=ExecutionStatus.RUNNING,
        )
        .select_related('execution__action')
        .prefetch_related('execution__targets')
        .order_by('created_at')[:max_steps_per_batch]
    )

    step_count = len(waiting_steps)  # Use len() instead of count() since we're using [:limit]

    logger.info(
        "evaluate_waiting_gates_start",
        waiting_step_count=step_count,
        correlation_id=task_correlation_id,
    )

    if step_count == 0:
        return {'waiting_steps': 0, 'unblocked': 0, 'still_waiting': 0, 'errors': 0}

    evaluator = GateEvaluator()
    unblocked = 0
    still_waiting = 0
    errors = 0

    processed = 0
    for step in waiting_steps:
        # Story 72.1 (AC3): Utiliser execution.correlation_id pour chaque step.
        # get_correlation_id() retourne None dans les workers Celery (pas de contexte HTTP).
        step_correlation_id = (step.execution.correlation_id or task_correlation_id or "")
        try:
            all_satisfied, gate_status = evaluator.evaluate(step)

            # AC8: Timeout handling
            if gate_status.get('timeout_triggered'):
                _handle_gate_timeout(step, gate_status, step_correlation_id)
                errors += 1  # Count as "processed" but not unblocked
                processed += 1
                continue

            if all_satisfied:
                # AC4: Transition WAITING → RUNNING
                _transition_step_to_running(step, gate_status, step_correlation_id)
                unblocked += 1
            else:
                # AC5: Update waiting context
                _update_waiting_context(step, gate_status, step_correlation_id)
                still_waiting += 1
            processed += 1

        except SoftTimeLimitExceeded:
            logger.warning(
                "evaluate_waiting_gates_soft_timeout",
                processed=processed,
                total=step_count,
                unblocked=unblocked,
                still_waiting=still_waiting,
                errors=errors,
                correlation_id=task_correlation_id,
            )
            return {
                'waiting_steps': step_count,
                'unblocked': unblocked,
                'still_waiting': still_waiting,
                'errors': errors,
                'status': 'partial_timeout',
                'processed': processed,
            }

        except Exception as e:  # noqa: BLE001 — resilience-boundary: gate evaluation must continue for other steps on error
            # AC9: Error handling — log and continue
            logger.error(
                "evaluate_waiting_gates_error",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=step_correlation_id,
                exc_info=True,
            )
            # Story 25.3 code review fix MEDIUM-1: persist error in step output for user visibility
            try:
                output = step.get_output() or {}
                output['evaluation_error'] = {
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'occurred_at': timezone.now().isoformat(),
                }
                # CAS guard: do not overwrite a step already transitioned by another worker.
                ExecutionStep.objects.filter(
                    id=step.id,
                    status=ExecutionStepStatus.WAITING,
                ).update(output=json.dumps(output))
            except Exception as save_error:  # noqa: BLE001 — best-effort-non-critical: error persist failure must not break gate loop
                logger.error(
                    "evaluate_waiting_gates_error_persist_failed",
                    step_id=step.id,
                    error=str(save_error),
                    correlation_id=step_correlation_id,
                    exc_info=True,
                )
            errors += 1

    logger.info(
        "evaluate_waiting_gates_complete",
        waiting_step_count=step_count,
        unblocked=unblocked,
        still_waiting=still_waiting,
        errors=errors,
        correlation_id=task_correlation_id,
    )

    return {
        'waiting_steps': step_count,
        'unblocked': unblocked,
        'still_waiting': still_waiting,
        'errors': errors,
    }


def _perform_step_transition(step: ExecutionStep, correlation_id: str) -> bool:
    """
    CAS update: transition step from WAITING to RUNNING.

    Story 71.6: Extracted from _transition_step_to_running (subtask 5.1).

    Returns:
        True if the transition was applied, False if another worker already processed it.
    """
    now = timezone.now()
    updated = ExecutionStep.objects.filter(
        id=step.id,
        status=ExecutionStepStatus.WAITING,
    ).update(
        status=ExecutionStepStatus.RUNNING,
        started_at=now,
    )
    if updated == 0:
        logger.warning(
            "evaluate_waiting_gates_step_already_running",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
        )
        return False

    step.refresh_from_db()
    _cleanup_step_resources(step, ExecutionStepStatus.WAITING, correlation_id)
    return True


def _emit_gate_satisfied_audit(step: ExecutionStep, correlation_id: str) -> None:
    """
    Emit audit trail entry for a gate step that has been satisfied.

    Story 71.6: Extracted from _transition_step_to_running (subtask 5.2).
    """
    waiting_duration = (timezone.now() - step.created_at).total_seconds()
    AuditService.create_entry(
        user_id=str(step.execution.user_id),
        action_type=AuditActionType.EXECUTION_STEP_GATE_SATISFIED,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=step.execution_id,
        details={
            'execution_id': str(step.execution_id),
            'action_name': step.execution.action.name if step.execution.action else None,
            'step_id': step.id,
            'step_order': step.step_order,
            'step_name': step.step_name,
            'waiting_duration_seconds': round(waiting_duration, 1),
        },
        correlation_id=correlation_id,
    )


def _transition_step_to_running(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Transition an ExecutionStep from WAITING to RUNNING and trigger execution.

    Story 25.3: Sets status=RUNNING, started_at, triggers the actual step execution.
    Story 71.6: Refactored into orchestrator calling sub-functions.
    Story 71.7 AC#5: CAS + audit wrapped in transaction.atomic(); resume after commit.
    """
    # Story 71.7 AC#5: Wrap CAS transition + audit in transaction for consistency
    with transaction.atomic():
        if not _perform_step_transition(step, correlation_id):
            return

        logger.info(
            "evaluate_waiting_gates_step_satisfied",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
        )

        _emit_gate_satisfied_audit(step, correlation_id)

    # Story 71.7 AC#5: Resume after transaction commit so Celery sees committed data
    action = step.execution.action
    from executions.utils.step_config import find_step_config  # noqa: PLC0415
    step_def = find_step_config(action.execution_steps or [], step)
    _resume_workflow_after_gate(step, action, step_def, correlation_id, old_style_step_def=step_def)


def _update_waiting_context(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Update the waiting context for a step whose conditions are NOT yet satisfied.

    Story 25.3: Updates ExecutionStep.output with the latest gate_status evaluation.
    """
    output = step.get_output() or {}
    gate_conditions = output.get('gate_conditions', [])

    # Skip emit for approval_granted gates: status never changes until user approves.
    # Avoids ~1 STEP_OUTPUT_UPDATED per minute while waiting (noisy, wasteful).
    is_approval_gate = any(
        isinstance(c, dict) and c.get('type') == 'approval_granted'
        for c in gate_conditions
    )

    output['gate_status'] = gate_status.get('gates', [])

    # Compute next_possible_at from gate details
    next_possible_at = None
    for gate in gate_status.get('gates', []):
        npa = gate.get('next_possible_at')
        if npa:
            if next_possible_at is None or npa > next_possible_at:
                next_possible_at = npa
    if next_possible_at:
        output['next_possible_at'] = next_possible_at

    # Compare BEFORE setting last_evaluated_at — otherwise the timestamp always differs
    # and output_changed would be True every time, defeating the skip-unnecessary-save optimization.
    def _comparable_output(o: dict) -> dict:
        return {k: o.get(k) for k in ('gate_status', 'next_possible_at', 'evaluation_error')}

    old_output = json.loads(step.output) if step.output else {}
    output_changed = (
        step.output is None
        or _comparable_output(old_output) != _comparable_output(output)
    )

    output['last_evaluated_at'] = timezone.now().isoformat()

    updated = 0
    if output_changed:
        # CAS write: only persist while still WAITING to avoid status regression.
        updated = ExecutionStep.objects.filter(
            id=step.id,
            status=ExecutionStepStatus.WAITING,
        ).update(output=json.dumps(output))
        if updated == 0:
            logger.debug(
                "evaluate_waiting_gates_step_context_skipped_not_waiting",
                step_id=step.id,
                execution_id=step.execution_id,
                correlation_id=correlation_id,
            )
            return
        step.output = json.dumps(output)

    # V113: Durable event so UI can refresh gate status on reconnect.
    # Skip for approval gates — no meaningful change until approval.
    if output_changed and updated == 1 and not is_approval_gate:
        try:
            from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
            WorkflowEventService.emit_step_output_updated(step.execution_id, step)
        except Exception as e:  # noqa: BLE001 — best-effort: emit must not fail evaluation
            logger.error(
                "evaluate_waiting_gates_emit_step_output_updated_failed",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )

    logger.info(
        "evaluate_waiting_gates_step_still_waiting",
        step_id=step.id,
        execution_id=step.execution_id,
        next_possible_at=next_possible_at,
        correlation_id=correlation_id,
    )


def _get_next_step_by_order(execution_steps: list, current_step_config: dict) -> dict | None:
    """Return the next step definition by order.

    Excludes parallel_group member steps so the result matches the runtime's
    non-member sequencing (ContainerWorkflowRuntime._execute_workflow_steps).
    Uses identity-based matching (step_id/name) as primary strategy, falling back
    to strict order comparison.
    """
    member_step_ids: set[str] = set()
    for s in execution_steps:
        if isinstance(s, dict) and s.get('step_type') == 'parallel_group':
            member_step_ids.update(s.get('parallel_steps') or [])
    non_member_steps = [
        s for s in execution_steps
        if isinstance(s, dict) and s.get('step_id') and s.get('step_id') not in member_step_ids
    ]
    sorted_steps = sorted(non_member_steps, key=lambda s: s.get('order', 0))
    current_order = current_step_config.get('order', 0)
    current_sid = current_step_config.get('step_id')
    current_name = current_step_config.get('name')

    # Try identity-based match first: find current step in sorted list, return next
    if current_sid or current_name:
        for i, s in enumerate(sorted_steps):
            if (current_sid and s.get('step_id') == current_sid) or (
                current_name and s.get('name') == current_name
            ):
                if i + 1 < len(sorted_steps):
                    return sorted_steps[i + 1]
                return None  # current step is last

    # Fallback: first step with strictly greater order
    for s in sorted_steps:
        if s.get('order', 0) > current_order:
            return s
    return None


def _cleanup_step_resources(step: ExecutionStep, old_status: ExecutionStepStatus, correlation_id: str) -> None:
    """
    Best-effort cleanup: remove step from runnable queue and emit durable status-changed event.

    Story 71.6: Extracted from _transition_step_to_running and _handle_gate_timeout
    to eliminate duplication (~30 LOC x2).
    Deferred to on_commit so delete/emit only run after successful transaction.
    """
    from django.db import transaction  # noqa: PLC0415

    def _do_cleanup() -> None:
        try:
            from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
            RunnableStepService.delete(step.id)
        except Exception as e:
            logger.error(
                "evaluate_waiting_gates_runnable_step_delete_failed",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
        try:
            from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
            WorkflowEventService.emit_step_status_changed(
                step.execution_id, step, old_status=old_status,
            )
        except Exception as e:
            logger.error(
                "evaluate_waiting_gates_emit_step_status_changed_failed",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )

    transaction.on_commit(_do_cleanup)


def _complete_execution_on_last_step(step: ExecutionStep, correlation_id: str) -> None:
    """
    Complete the parent execution when the gate is the last step (CAS update).

    Story 71.6: Extracted from _transition_step_to_running and _handle_gate_timeout
    to eliminate duplication (~30 LOC x2).
    """
    try:
        execution = step.execution
        if execution.status == ExecutionStatus.RUNNING:
            updated = Execution.objects.filter(
                id=execution.id,
                status=ExecutionStatus.RUNNING,
            ).update(
                status=ExecutionStatus.COMPLETED,
                completed_at=timezone.now(),
            )
            if updated:
                changes = sanitize_audit_changes({'status': {'old': ExecutionStatus.RUNNING, 'new': ExecutionStatus.COMPLETED}})
                AuditService.create_entry(
                    user_id=str(execution.user_id),
                    action_type=AuditActionType.EXECUTION_COMPLETED,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=execution.id,
                    details={
                        'action_id': execution.action_id,
                        'action_name': execution.action.name if execution.action else None,
                        'changes': changes,
                    },
                    correlation_id=correlation_id,
                )
                logger.info(
                    "gate_execution_completed_last_step",
                    step_id=step.id,
                    execution_id=step.execution_id,
                    correlation_id=correlation_id,
                )
    except Exception as exc:  # noqa: BLE001 — resilience-boundary: gate completion update failure logged
        logger.error(
            "gate_execution_complete_error",
            execution_id=step.execution_id,
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


def _resume_workflow_after_gate(
    step: ExecutionStep,
    action: Any,
    step_def: dict | None,
    correlation_id: str,
    old_style_step_def: dict | None = None,
) -> None:
    """
    Resume the workflow after a gate step is satisfied or timed out (SKIPPED).

    Handles ADR-007 container workflows (resume_container_workflow_from_gate or
    complete execution) and old-style workflows (retry_workflow_step).

    Story 71.6: Extracted from _transition_step_to_running and _handle_gate_timeout
    to eliminate duplication (~20 LOC x2).

    Args:
        step: The gate ExecutionStep
        action: The parent Action (with execution_steps)
        step_def: The step config dict from find_step_config (may be None)
        correlation_id: Correlation ID for logging
        old_style_step_def: Step def to pass to retry_workflow_step for old-style workflows.
                           If None, old-style path is a no-op.
    """
    execution_steps = action.execution_steps or []

    if step_def is None:
        logger.error(
            "gate_resume_step_def_not_found",
            step_id=step.id,
            step_name=step.step_name,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
        )
        return

    is_adr007_step = bool(step_def.get('step_type'))
    on_success_step_ids = step_def.get('on_success_step_ids') or []

    # Fallback: linear order when gate has no explicit on_success_step_ids
    if is_adr007_step and not on_success_step_ids:
        next_s = _get_next_step_by_order(execution_steps, step_def)
        next_id = next_s.get('step_id') if next_s else None
        if next_id:
            on_success_step_ids = [next_id]

    if is_adr007_step and on_success_step_ids:
        resume_container_workflow_from_gate.apply_async(
            args=[step.execution_id, on_success_step_ids],
            queue="default",
        )
        logger.info(
            "gate_resume_container_workflow",
            step_id=step.id,
            execution_id=step.execution_id,
            on_success_step_ids=on_success_step_ids,
            correlation_id=correlation_id,
        )
    elif is_adr007_step and not on_success_step_ids:
        # Gate is last step — complete execution
        _complete_execution_on_last_step(step, correlation_id)
    elif old_style_step_def:
        # Old-style workflow
        import executions.tasks as _tasks
        _tasks.retry_workflow_step.apply_async(
            args=[step.execution_id, old_style_step_def, 1],
        )
        logger.info(
            "gate_resume_old_style_workflow",
            step_id=step.id,
            execution_id=step.execution_id,
            step_def_id=old_style_step_def.get('step_id') or old_style_step_def.get('name'),
            correlation_id=correlation_id,
        )


def _perform_timeout_step_update(
    step: ExecutionStep,
    next_step_status: ExecutionStepStatus,
    error_msg: str,
    timeout_action: str,
    correlation_id: str,
) -> bool:
    """
    CAS update: transition step from WAITING to SKIPPED/FAILED on timeout.

    Story 71.6: Extracted from _handle_gate_timeout (subtask 4.2).

    Returns:
        True if the update was applied, False if another worker already processed it.
    """
    completed_at = timezone.now()
    updated = ExecutionStep.objects.filter(
        id=step.id,
        status=ExecutionStepStatus.WAITING,
    ).update(
        status=next_step_status,
        error_message=error_msg,
        completed_at=completed_at,
    )
    if updated == 0:
        logger.warning(
            "evaluate_waiting_gates_step_timeout_already_processed",
            step_id=step.id,
            execution_id=step.execution_id,
            timeout_action=timeout_action,
            correlation_id=correlation_id,
        )
        return False

    # Keep local instance in sync for downstream events/audit payloads.
    step.status = next_step_status
    step.error_message = error_msg
    step.completed_at = completed_at

    _cleanup_step_resources(step, ExecutionStepStatus.WAITING, correlation_id)
    return True


def _mark_execution_failed(execution: Execution, step: ExecutionStep, correlation_id: str) -> None:
    """
    Mark a parent execution as FAILED (resilience boundary — best-effort).

    Story 71.6: Extracted from _handle_gate_timeout (subtask 4.4).
    """
    try:
        updated = Execution.objects.filter(
            id=execution.id,
        ).exclude(
            status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
        ).update(
            status=ExecutionStatus.FAILED,
            completed_at=timezone.now(),
        )
        if updated:
            logger.info(
                "gate_timeout_execution_failed",
                execution_id=execution.id,
                step_id=step.id,
                correlation_id=correlation_id,
            )
    except Exception as exc:  # noqa: BLE001 — resilience-boundary: timeout execution update failure logged, task continues
        logger.error(
            "gate_timeout_execution_update_error",
            execution_id=step.execution_id,
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


def _handle_timeout_continuation(
    step: ExecutionStep,
    timeout_action: str,
    correlation_id: str,
) -> None:
    """
    Continue workflow after gate timeout: SKIPPED → resume next step, FAILED → mark execution failed.

    Story 71.6: Extracted from _handle_gate_timeout (subtask 4.3).
    """
    if timeout_action == 'SKIPPED':
        action = step.execution.action
        execution_steps = action.execution_steps or []
        from executions.utils.step_config import find_step_config  # noqa: PLC0415
        step_def = find_step_config(execution_steps, step)
        old_style_next = (
            _get_next_step_by_order(execution_steps, step_def) if step_def else None
        )
        _resume_workflow_after_gate(step, action, step_def, correlation_id, old_style_step_def=old_style_next)
    else:
        _mark_execution_failed(step.execution, step, correlation_id)


def _handle_gate_timeout(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Handle a gate timeout condition — transition step to FAILED or SKIPPED.

    Story 25.3: Based on on_timeout value, transitions the step and creates audit trail.
    Story 30.7 (CELERY-4/CELERY-5): Continue the workflow after timeout.
    Story 71.6: Refactored into orchestrator calling sub-functions.
    """
    timeout_action = gate_status.get('action', 'FAILED')
    timeout_hours = gate_status.get('timeout_hours')
    error_msg = f"Gate timeout exceeded after {timeout_hours}h"

    next_step_status = (
        ExecutionStepStatus.SKIPPED if timeout_action == 'SKIPPED'
        else ExecutionStepStatus.FAILED
    )

    # Story 71.7 AC#6: Wrap CAS timeout update + audit in transaction for consistency
    with transaction.atomic():
        if not _perform_timeout_step_update(step, next_step_status, error_msg, timeout_action, correlation_id):
            return

        logger.info(
            "evaluate_waiting_gates_step_timeout",
            step_id=step.id,
            execution_id=step.execution_id,
            timeout_hours=timeout_hours,
            timeout_action=timeout_action,
            error_message=error_msg,
            correlation_id=correlation_id,
        )

        # Audit trail: gate timeout
        waiting_duration = (timezone.now() - step.created_at).total_seconds()
        AuditService.create_entry(
            user_id=str(step.execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_GATE_TIMEOUT,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=step.execution_id,
            details={
                'execution_id': str(step.execution_id),
                'action_name': step.execution.action.name if step.execution.action else None,
                'step_id': step.id,
                'step_order': step.step_order,
                'step_name': step.step_name,
                'timeout_hours': timeout_hours,
                'on_timeout': timeout_action,
                'error_message': error_msg,
                'waiting_duration_seconds': round(waiting_duration, 1),
            },
            correlation_id=correlation_id,
        )

    # Story 71.7 AC#6: Continuation after transaction commit so Celery sees committed data
    _handle_timeout_continuation(step, timeout_action, correlation_id)


_RESUME_LIMITS = settings.CELERY_TASK_TIME_LIMITS["resume_container_workflow_from_gate"]


@shared_task(
    bind=True,
    max_retries=0,
    name="executions.tasks.resume_container_workflow_from_gate",
    soft_time_limit=_RESUME_LIMITS["soft"],
    time_limit=_RESUME_LIMITS["hard"],
)
def resume_container_workflow_from_gate(
    self: Any, execution_id: int, on_success_step_ids: str | list[str]
) -> dict:
    """
    Story 57.7: Reprend le container workflow après satisfaction d'un gate step.
    Story 67.4: Accepte on_success_step_ids (list) pour fan-out parallèle.

    Appelé par _transition_step_to_running() quand le gate step est satisfait
    et que l'exécution est un container workflow ADR-007.

    Args:
        execution_id: ID de l'Execution à reprendre
        on_success_step_ids: step_id ou liste de step_ids à partir desquels reprendre
    """
    from executions.models import Execution, ExecutionStatus
    from executions.cancellation_cache import is_cancelled
    from executions.container_workflow_runtime import ContainerWorkflowRuntime

    correlation_id = get_correlation_id()
    step_ids = (
        on_success_step_ids if isinstance(on_success_step_ids, list) else [on_success_step_ids]
    )
    first_step_id = step_ids[0] if step_ids else ""

    logger.info(
        "resume_container_workflow_gate_start",
        execution_id=execution_id,
        on_success_step_ids=step_ids,
        correlation_id=correlation_id,
    )

    try:
        if is_cancelled(execution_id):
            logger.info(
                "resume_container_workflow_gate_cancelled",
                execution_id=execution_id,
                correlation_id=correlation_id,
            )
            return {'outcome': 'cancelled'}

        with transaction.atomic():
            # Story 57.7: Use select_related('action') without select_for_update to
            # keep the query shape compatible with existing unit tests that patch
            # Execution.objects.select_related().get(...).
            execution = Execution.objects.select_related('action').get(id=execution_id)

            # Vérifier que l'exécution est toujours en RUNNING
            if execution.status != ExecutionStatus.RUNNING:
                logger.warning(
                    "resume_container_workflow_gate_not_running",
                    execution_id=execution_id,
                    status=execution.status,
                    correlation_id=correlation_id,
                )
                return {'outcome': 'not_running', 'status': str(execution.status)}

            # Idempotency: si un step cible existe déjà (RUNNING ou COMPLETED), ne pas re-exécuter
            target_steps_exist = ExecutionStep.objects.filter(
                execution=execution,
                config_step_id__in=step_ids,
                status__in=[ExecutionStepStatus.RUNNING, ExecutionStepStatus.COMPLETED],
            ).exists()
            if target_steps_exist:
                logger.info(
                    "resume_container_workflow_gate_already_resumed",
                    execution_id=execution_id,
                    on_success_step_ids=step_ids,
                    correlation_id=correlation_id,
                )
                return {'outcome': 'already_resumed', 'step_ids': step_ids}

            # Trouver les steps restants à partir de on_success_step_ids (Story 67.4: union)
            all_steps = execution.action.execution_steps or []
            remaining_steps = []
            found_ids: set[str] = set()
            for step_id in step_ids:
                if not step_id or not isinstance(step_id, str):
                    continue
                for s in all_steps:
                    if isinstance(s, dict) and s.get('step_id') == step_id:
                        found_ids.add(step_id)
                        break
            # Inclure tous les steps à partir du premier trouvé (ordre préservé)
            collect = False
            for s in all_steps:
                if isinstance(s, dict):
                    sid = s.get('step_id')
                    if sid in found_ids:
                        collect = True
                    if collect:
                        remaining_steps.append(s)

            if not found_ids:
                logger.error(
                    "resume_container_workflow_gate_step_not_found",
                    execution_id=execution_id,
                    on_success_step_ids=step_ids,
                    correlation_id=correlation_id,
                )
                return {'outcome': 'step_not_found', 'step_id': first_step_id}

            # Reconstruire le contexte _step_outputs depuis les ExecutionStep COMPLETED existants
            completed_steps = ExecutionStep.objects.filter(
                execution=execution,
                status=ExecutionStepStatus.COMPLETED,
            ).order_by('step_order')

            # _step_outputs is keyed by step_id (config's step_id UUID).
            # Use config_step_id directly when available; fall back to name→id mapping for old records.
            step_name_to_id = {
                s.get('name'): s.get('step_id')
                for s in all_steps
                if isinstance(s, dict) and s.get('name') and s.get('step_id')
            }

            # Reprendre le workflow depuis le step cible
            runtime = ContainerWorkflowRuntime(execution)
            # Restaurer le contexte des outputs de steps déjà exécutés (keyed par step_id)
            for db_step in completed_steps:
                step_output = db_step.get_output() or {}
                # Primary: use config_step_id (robust UUID-based matching)
                step_id_key = db_step.config_step_id
                # Fallback for old records: map step_name → step_id via config
                if not step_id_key and db_step.step_name:
                    step_id_key = step_name_to_id.get(db_step.step_name)
                if step_id_key:
                    runtime._step_outputs[step_id_key] = step_output
            runtime.workflow_steps = remaining_steps
            # Story 67.4: Vague initiale explicite pour reprendre exactement aux step_ids cibles.
            # IMPORTANT: toujours défini (pas seulement fan-out 2+ step_ids) sinon
            # _execute_workflow_steps recalcule les entry points du sous-graphe remaining_steps
            # et peut ré-exécuter le gate step lui-même (boucle infinie d'approbation).
            runtime._initial_wave = [s for s in step_ids if isinstance(s, str) and s]
            # Resume: _step_order_counter must continue from max existing step_order
            # to avoid UK_EXEC_STEPS_EXEC_ORDER violation (step_order already used by gate)
            from django.db.models import Max
            max_order = ExecutionStep.objects.filter(execution=execution).aggregate(
                Max('step_order')
            )['step_order__max']
            runtime._step_order_counter = max_order if max_order is not None else 0
            # All locking, idempotency checks, and runtime preparation done above.
            # Exit transaction here to release select_for_update lock before downstream work.
        # Execute workflow steps AFTER releasing the DB lock (child executions, tasks, etc.)
        runtime._execute_workflow_steps()

        logger.info(
            "resume_container_workflow_gate_complete",
            execution_id=execution_id,
            on_success_step_ids=step_ids,
            remaining_steps_count=len(remaining_steps),
            correlation_id=correlation_id,
        )
        return {'outcome': 'completed', 'resumed_from': step_ids}

    except SoftTimeLimitExceeded:
        logger.error(
            "resume_workflow_soft_timeout",
            execution_id=execution_id,
            on_success_step_ids=step_ids,
            correlation_id=correlation_id,
        )
        # Do NOT modify execution status — the workflow loop handles inconsistent states
        raise

    except Execution.DoesNotExist:
        logger.error(
            "resume_container_workflow_gate_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
        return {'outcome': 'error', 'error': 'Execution not found'}
    except Exception as exc:  # noqa: BLE001 — resilience-boundary: gate resume failure logged
        logger.error(
            "resume_container_workflow_gate_error",
            execution_id=execution_id,
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )
        return {'outcome': 'error', 'error': str(exc)}
