"""
executions/tasks/gates.py — Responsabilité unique : évaluation périodique des conditions
WAITING et transition des étapes de workflow vers RUNNING.

Expose : evaluate_waiting_gates
Helpers internes : _transition_step_to_running, _update_waiting_context,
                   _handle_gate_timeout
"""
import os
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

from executions.models import (
    ExecutionStatus,
    ExecutionStep, ExecutionStepStatus,
)
from core.services import AuditService
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)


@shared_task(bind=True, max_retries=0, name="executions.tasks.evaluate_waiting_gates")
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

    correlation_id = get_correlation_id()

    # Story 25.3 code review fix MEDIUM-4: Configurable batch size to prevent task timeout
    max_steps_per_batch = int(os.getenv('CELERY_BEAT_EVALUATE_GATES_MAX_STEPS', '100'))

    # AC2: Select WAITING steps with RUNNING parent execution
    # Note: prefetch_related('execution__targets') removed to prevent memory leak
    # when many steps × many targets. Targets are loaded per-step in GateEvaluator.
    # Order by created_at to prioritize oldest waiting steps first (FIFO fairness)
    waiting_steps = (
        ExecutionStep.objects.filter(
            status=ExecutionStepStatus.WAITING,
            execution__status=ExecutionStatus.RUNNING,
        )
        .select_related('execution__action')
        .order_by('created_at')[:max_steps_per_batch]
    )

    step_count = len(waiting_steps)  # Use len() instead of count() since we're using [:limit]

    logger.info(
        "evaluate_waiting_gates_start",
        waiting_step_count=step_count,
        correlation_id=correlation_id,
    )

    if step_count == 0:
        return {'waiting_steps': 0, 'unblocked': 0, 'still_waiting': 0, 'errors': 0}

    evaluator = GateEvaluator()
    unblocked = 0
    still_waiting = 0
    errors = 0

    for step in waiting_steps:
        try:
            all_satisfied, gate_status = evaluator.evaluate(step)

            # AC8: Timeout handling
            if gate_status.get('timeout_triggered'):
                _handle_gate_timeout(step, gate_status, correlation_id or "")
                errors += 1  # Count as "processed" but not unblocked
                continue

            if all_satisfied:
                # AC4: Transition WAITING → RUNNING
                _transition_step_to_running(step, gate_status, correlation_id or "")
                unblocked += 1
            else:
                # AC5: Update waiting context
                _update_waiting_context(step, gate_status, correlation_id or "")
                still_waiting += 1

        except Exception as e:  # noqa: BLE001 — resilience-boundary: gate evaluation must continue for other steps on error
            # AC9: Error handling — log and continue
            logger.error(
                "evaluate_waiting_gates_error",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
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
                step.set_output(output)
                step.save()
            except Exception as save_error:  # noqa: BLE001 — best-effort-non-critical: error persist failure must not break gate loop
                logger.error(
                    "evaluate_waiting_gates_error_persist_failed",
                    step_id=step.id,
                    error=str(save_error),
                    correlation_id=correlation_id,
                    exc_info=True,
                )
            errors += 1

    logger.info(
        "evaluate_waiting_gates_complete",
        waiting_step_count=step_count,
        unblocked=unblocked,
        still_waiting=still_waiting,
        errors=errors,
        correlation_id=correlation_id,
    )

    return {
        'waiting_steps': step_count,
        'unblocked': unblocked,
        'still_waiting': still_waiting,
        'errors': errors,
    }


def _transition_step_to_running(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Transition an ExecutionStep from WAITING to RUNNING and trigger execution.

    Story 25.3: Sets status=RUNNING, started_at, triggers the actual step execution via
    retry_workflow_step, and creates an audit trail entry.

    Uses atomic update with WHERE clause to prevent race conditions between
    multiple Celery Beat workers.
    """
    # Atomic transition with race condition protection
    now = timezone.now()
    updated = ExecutionStep.objects.filter(
        id=step.id,
        status=ExecutionStepStatus.WAITING,  # Only update if still WAITING
    ).update(
        status=ExecutionStepStatus.RUNNING,
        started_at=now,
    )

    if updated == 0:
        # Another worker already transitioned this step
        logger.warning(
            "evaluate_waiting_gates_step_already_running",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
        )
        return

    # V113: Remove from runnable queue now that step is RUNNING (best-effort)
    try:
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        RunnableStepService.delete(step.id)
    except Exception:
        logger.error(
            "evaluate_waiting_gates_runnable_step_delete_failed",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
            exc_info=True,
        )

    # Refresh step to get updated fields
    step.refresh_from_db()

    # V113: Durable event for UI catch-up (best-effort)
    try:
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        WorkflowEventService.emit_step_status_changed(
            step.execution_id, step, old_status=ExecutionStepStatus.WAITING,
        )
    except Exception:
        logger.error(
            "evaluate_waiting_gates_emit_step_status_changed_failed",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
            exc_info=True,
        )

    logger.info(
        "evaluate_waiting_gates_step_satisfied",
        step_id=step.id,
        execution_id=step.execution_id,
        correlation_id=correlation_id,
    )

    # Audit trail: gate conditions satisfied
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

    # Story 25.3: Trigger actual step execution
    # Find the step definition from the action's workflow to pass to retry_workflow_step
    action = step.execution.action
    execution_steps = action.execution_steps or []

    # Match by step_order from output's gate_conditions context or by name
    step_def = None
    for s in execution_steps:
        if isinstance(s, dict) and s.get('name') == step.step_name:
            step_def = s
            break

    if step_def:
        # Story 57.7: Détecter si c'est un step ADR-007 container workflow
        # Les steps ADR-007 ont un step_type ; les old-style steps n'en ont pas
        is_adr007_step = bool(step_def.get('step_type'))
        on_success_step_id = step_def.get('on_success_step_id')

        # Access through package namespace for testability (retry_workflow_step)
        import executions.tasks as _tasks

        if is_adr007_step and on_success_step_id:
            # Container workflow ADR-007 : reprendre depuis le prochain step
            resume_container_workflow_from_gate.apply_async(
                args=[step.execution_id, on_success_step_id],
            )
            logger.info(
                "evaluate_waiting_gates_step_container_workflow_resumed",
                step_id=step.id,
                execution_id=step.execution_id,
                on_success_step_id=on_success_step_id,
                correlation_id=correlation_id,
            )
        elif is_adr007_step and not on_success_step_id:
            # Gate est le dernier step du workflow — compléter l'exécution
            try:
                execution = step.execution
                if execution.status == ExecutionStatus.RUNNING:
                    execution.status = ExecutionStatus.COMPLETED
                    execution.completed_at = timezone.now()
                    execution.save()
                    logger.info(
                        "evaluate_waiting_gates_step_container_workflow_completed",
                        step_id=step.id,
                        execution_id=step.execution_id,
                        correlation_id=correlation_id,
                    )
            except Exception as exc:  # noqa: BLE001 — resilience-boundary: gate completion update failure logged
                logger.error(
                    "evaluate_waiting_gates_step_container_workflow_complete_error",
                    execution_id=step.execution_id,
                    error=str(exc),
                    correlation_id=correlation_id,
                    exc_info=True,
                )
        else:
            # Old-style workflow : comportement existant
            _tasks.retry_workflow_step.apply_async(
                args=[step.execution_id, step_def, 1],
            )
            logger.info(
                "evaluate_waiting_gates_step_execution_triggered",
                step_id=step.id,
                execution_id=step.execution_id,
                step_def_id=step_def.get('step_id'),
                correlation_id=correlation_id,
            )
    else:
        # Story 25.3 code review fix LOW-1: ERROR instead of WARNING (step in zombie state)
        logger.error(
            "evaluate_waiting_gates_step_def_not_found",
            step_id=step.id,
            step_name=step.step_name,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
        )


def _update_waiting_context(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Update the waiting context for a step whose conditions are NOT yet satisfied.

    Story 25.3: Updates ExecutionStep.output with the latest gate_status evaluation.
    """
    output = step.get_output() or {}
    output['gate_status'] = gate_status.get('gates', [])
    output['last_evaluated_at'] = timezone.now().isoformat()

    # Compute next_possible_at from gate details
    next_possible_at = None
    for gate in gate_status.get('gates', []):
        npa = gate.get('next_possible_at')
        if npa:
            if next_possible_at is None or npa > next_possible_at:
                next_possible_at = npa
    if next_possible_at:
        output['next_possible_at'] = next_possible_at

    step.set_output(output)
    step.save()

    # V113: Durable event so UI can refresh gate status on reconnect
    from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
    WorkflowEventService.emit_step_output_updated(step.execution_id, step)

    logger.info(
        "evaluate_waiting_gates_step_still_waiting",
        step_id=step.id,
        execution_id=step.execution_id,
        next_possible_at=next_possible_at,
        correlation_id=correlation_id,
    )


def _handle_gate_timeout(step: ExecutionStep, gate_status: dict, correlation_id: str) -> None:
    """
    Handle a gate timeout condition — transition step to FAILED or SKIPPED.

    Story 25.3: Based on on_timeout value, transitions the step and creates audit trail.
    Story 30.7 (CELERY-4/CELERY-5): Actually continue the workflow after timeout
    instead of leaving it blocked. SKIPPED steps get an explicit error_message.
    """
    timeout_action = gate_status.get('action', 'FAILED')
    timeout_hours = gate_status.get('timeout_hours')

    # Story 30.7 (CELERY-5): Always set error_message, even for SKIPPED steps
    error_msg = f"Gate timeout exceeded after {timeout_hours}h"

    if timeout_action == 'SKIPPED':
        step.status = ExecutionStepStatus.SKIPPED
        step.error_message = error_msg
    else:
        step.status = ExecutionStepStatus.FAILED
        step.error_message = error_msg

    step.completed_at = timezone.now()
    step.save()

    # V113: Remove from runnable queue and emit durable event (best-effort)
    try:
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        RunnableStepService.delete(step.id)
    except Exception:
        logger.error(
            "evaluate_waiting_gates_timeout_runnable_step_delete_failed",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
            exc_info=True,
        )
    try:
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        WorkflowEventService.emit_step_status_changed(
            step.execution_id, step, old_status=ExecutionStepStatus.WAITING,
        )
    except Exception:
        logger.error(
            "evaluate_waiting_gates_timeout_emit_step_status_changed_failed",
            step_id=step.id,
            execution_id=step.execution_id,
            correlation_id=correlation_id,
            exc_info=True,
        )

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

    # Story 30.7 (CELERY-4): Continue workflow after gate timeout.
    # If FAILED → mark execution as FAILED.
    # If SKIPPED → trigger next step execution.
    if timeout_action == 'SKIPPED':
        # Find the next step definition and trigger it
        action = step.execution.action
        execution_steps = action.execution_steps or []
        next_step_def = None
        found_current = False
        for s in execution_steps:
            if isinstance(s, dict) and s.get('name') == step.step_name:
                found_current = True
                continue
            if found_current and isinstance(s, dict):
                next_step_def = s
                break

        if next_step_def and next_step_def.get('name'):
            # Story 30.7 Code Review: Validate next_step_def has required fields
            # Access through package namespace for testability:
            # allows @patch("executions.tasks.retry_workflow_step.apply_async") to intercept
            import executions.tasks as _tasks
            _tasks.retry_workflow_step.apply_async(
                args=[step.execution_id, next_step_def, 1],
            )
            logger.info(
                "evaluate_waiting_gates_step_timeout_next_step_triggered",
                step_id=step.id,
                execution_id=step.execution_id,
                next_step_name=next_step_def.get('name'),
                correlation_id=correlation_id,
            )
        else:
            logger.info(
                "evaluate_waiting_gates_step_timeout_no_next_step",
                step_id=step.id,
                execution_id=step.execution_id,
                correlation_id=correlation_id,
            )
    else:
        # FAILED → mark execution as FAILED
        try:
            execution = step.execution
            if execution.status not in {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}:
                execution.status = ExecutionStatus.FAILED
                execution.completed_at = timezone.now()
                execution.save()
                logger.info(
                    "evaluate_waiting_gates_step_timeout_execution_failed",
                    execution_id=execution.id,
                    step_id=step.id,
                    correlation_id=correlation_id,
                )
        except Exception as exc:  # noqa: BLE001 — resilience-boundary: timeout execution update failure logged, task continues
            logger.error(
                "evaluate_waiting_gates_step_timeout_execution_update_error",
                execution_id=step.execution_id,
                error=str(exc),
                correlation_id=correlation_id,
                exc_info=True,
            )


@shared_task(bind=True, max_retries=0, name="executions.tasks.resume_container_workflow_from_gate")
def resume_container_workflow_from_gate(self: Any, execution_id: int, on_success_step_id: str) -> dict:
    """
    Story 57.7: Reprend le container workflow après satisfaction d'un gate step.

    Appelé par _transition_step_to_running() quand le gate step est satisfait
    et que l'exécution est un container workflow ADR-007.

    Args:
        execution_id: ID de l'Execution à reprendre
        on_success_step_id: step_id à partir duquel reprendre le workflow
    """
    from executions.models import Execution, ExecutionStatus
    from executions.cancellation_cache import is_cancelled
    from executions.container_workflow_runtime import ContainerWorkflowRuntime

    correlation_id = get_correlation_id()

    logger.info(
        "resume_container_workflow_gate_start",
        execution_id=execution_id,
        on_success_step_id=on_success_step_id,
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

        # Trouver les steps restants à partir de on_success_step_id
        all_steps = execution.action.execution_steps or []
        remaining_steps = []
        found = False
        for s in all_steps:
            if isinstance(s, dict):
                if found:
                    remaining_steps.append(s)
                elif s.get('step_id') == on_success_step_id:
                    found = True
                    remaining_steps.append(s)

        if not found:
            logger.error(
                "resume_container_workflow_gate_step_not_found",
                execution_id=execution_id,
                on_success_step_id=on_success_step_id,
                correlation_id=correlation_id,
            )
            return {'outcome': 'step_not_found', 'step_id': on_success_step_id}

        # Reconstruire le contexte _step_outputs depuis les ExecutionStep COMPLETED existants
        from executions.models import ExecutionStep, ExecutionStepStatus
        completed_steps = ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.COMPLETED,
        ).order_by('step_order')

        # _step_outputs est keyed par step_id (step.get('step_id')), pas par step_name.
        # ExecutionStep.step_name stocke step.get('name') (nom humain), pas le step_id.
        # On construit le mapping name → step_id depuis la définition du workflow.
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
            step_id_key = step_name_to_id.get(db_step.step_name) if db_step.step_name else None
            if step_id_key:
                runtime._step_outputs[step_id_key] = step_output
        runtime.workflow_steps = remaining_steps
        runtime._execute_workflow_steps()

        logger.info(
            "resume_container_workflow_gate_complete",
            execution_id=execution_id,
            on_success_step_id=on_success_step_id,
            remaining_steps_count=len(remaining_steps),
            correlation_id=correlation_id,
        )
        return {'outcome': 'completed', 'resumed_from': on_success_step_id}

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
