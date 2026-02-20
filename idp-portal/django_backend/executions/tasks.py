"""
Celery tasks for workflow execution.
Story 20.3: Asynchronous retry with Celery apply_async(countdown=...).
Story 25.3: Periodic evaluation of WAITING gate conditions.
Story 27.1: AAP job monitoring polling task.
Story 27.4: GitHub Actions monitoring polling task (catch-up fallback).
"""
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

from executions.models import (
    Execution, ExecutionStatus,
    ExecutionStep, ExecutionStepStatus,
)
from executions.workflow_runtime import StepOutcome
from core.services import AuditService
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)

# Story 30.7 (RACE-1): Maximum polling retries before marking execution as FAILED.
# 20 retries × 5s default interval ≈ 100s minimum; sufficient for transient failures.
MAX_POLLING_RETRIES = 20


@shared_task(bind=True, max_retries=0)
def retry_workflow_step(self: Any, execution_id: int, step: dict, attempt: int) -> dict:
    """
    Retry a workflow step asynchronously after a calculated delay.

    Scheduled by WorkflowRuntime._execute_step_with_retry() when a step fails
    and retry is enabled. The countdown parameter on apply_async handles the delay.

    Args:
        execution_id: ID of the execution
        step: Step definition dict from workflow JSON
        attempt: Current attempt number (2, 3, ...)

    Returns:
        dict with outcome information
    """
    step_id = step.get('step_id', 'unknown')

    logger.info(
        "celery_retry_workflow_step_start",
        execution_id=execution_id,
        step_id=step_id,
        attempt=attempt,
        task_id=self.request.id,
    )

    try:
        # Check cancellation before executing
        from executions.cancellation_cache import is_cancelled
        if is_cancelled(execution_id):
            logger.info(
                "celery_retry_workflow_step_cancelled",
                execution_id=execution_id,
                step_id=step_id,
                attempt=attempt,
            )
            return {
                'outcome': StepOutcome.ERROR.value,
                'error_message': 'Execution cancelled during retry',
            }

        # Load execution and create runtime
        execution = Execution.objects.get(id=execution_id)
        from executions.workflow_runtime import WorkflowRuntime
        runtime = WorkflowRuntime(execution)

        # Execute the step
        result = runtime._execute_step(step)

        # Success — done
        if result.is_success:
            logger.info(
                "celery_retry_workflow_step_success",
                execution_id=execution_id,
                step_id=step_id,
                attempt=attempt,
            )
            AuditService.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_SUCCESS,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details={
                    'step_id': step_id,
                    'attempt': attempt,
                    'max_attempts': step.get('retry_max_attempts', 3),
                    'result': 'success',
                },
            )
            return {
                'outcome': result.outcome.value,
                'output': result.output,
            }

        # Permanent error — stop
        if result.is_error and not runtime._is_retryable_error(result):
            logger.warning(
                "celery_retry_workflow_step_permanent_error",
                execution_id=execution_id,
                step_id=step_id,
                attempt=attempt,
                error=result.error_message,
            )
            AuditService.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_ABORTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details={
                    'step_id': step_id,
                    'attempt': attempt,
                    'reason': 'non_retryable_error',
                    'error': result.error_message,
                },
            )
            return {
                'outcome': result.outcome.value,
                'error_message': result.error_message,
            }

        # Max attempts reached — exhausted
        max_attempts = step.get('retry_max_attempts', 3)
        if attempt >= max_attempts:
            logger.error(
                "celery_retry_workflow_step_exhausted",
                execution_id=execution_id,
                step_id=step_id,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            AuditService.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details={
                    'step_id': step_id,
                    'max_attempts': max_attempts,
                    'final_error': result.error_message,
                },
            )
            return {
                'outcome': result.outcome.value,
                'error_message': result.error_message,
            }

        # Schedule next retry with exponential backoff
        interval_seconds = step.get('retry_interval_seconds', 60)
        backoff_multiplier = step.get('retry_backoff_multiplier', 2.0)
        delay_seconds = interval_seconds * (backoff_multiplier ** (attempt - 1))

        logger.info(
            "celery_retry_workflow_step_rescheduling",
            execution_id=execution_id,
            step_id=step_id,
            attempt=attempt,
            next_attempt=attempt + 1,
            delay_seconds=delay_seconds,
        )

        # Audit trail for this attempt
        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                'step_id': step_id,
                'attempt': attempt,
                'max_attempts': max_attempts,
                'result': 'error',
                'error': result.error_message,
                'next_retry_delay_seconds': delay_seconds,
                'retry_method': 'celery',
            },
        )

        # Schedule next attempt via Celery countdown
        retry_workflow_step.apply_async(
            args=[execution_id, step, attempt + 1],
            countdown=delay_seconds,
        )

        return {
            'outcome': 'retry_scheduled',
            'next_attempt': attempt + 1,
            'delay_seconds': delay_seconds,
        }

    except Execution.DoesNotExist:
        logger.error(
            "celery_retry_workflow_step_execution_not_found",
            execution_id=execution_id,
        )
        return {
            'outcome': StepOutcome.ERROR.value,
            'error_message': f'Execution {execution_id} not found',
        }
    except Exception as e:
        # Story 22.11: Justified broad catch - Celery retry task must handle all failure modes
        logger.exception(
            "celery_retry_workflow_step_error",
            execution_id=execution_id,
            step_id=step_id,
            attempt=attempt,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=get_correlation_id(),
        )
        return {
            'outcome': StepOutcome.ERROR.value,
            'error_message': f'Celery task error: {str(e)}',
        }


@shared_task(bind=True, max_retries=0)
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
    import os

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

        except Exception as e:
            # AC9: Error handling — log and continue
            logger.error(
                "evaluate_waiting_gates_error",
                step_id=step.id,
                execution_id=step.execution_id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
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
            except Exception as save_error:
                logger.error(
                    "evaluate_waiting_gates_error_persist_failed",
                    step_id=step.id,
                    error=str(save_error),
                    correlation_id=correlation_id,
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

    # Refresh step to get updated fields
    step.refresh_from_db()

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
        retry_workflow_step.apply_async(
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
            retry_workflow_step.apply_async(
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
        except Exception as exc:
            logger.error(
                "evaluate_waiting_gates_step_timeout_execution_update_error",
                execution_id=step.execution_id,
                error=str(exc),
                correlation_id=correlation_id,
            )


def _mark_execution_polling_exhausted(
    execution_id: int,
    platform_job_id: str,
    retry_count: int,
    error: str,
    correlation_id: str | None = None,
) -> None:
    """
    Story 30.7 (RACE-1): Mark execution as FAILED when polling retries are exhausted.
    Creates an audit entry with EXECUTION_POLLING_EXHAUSTED action type.
    """
    logger.error(
        "polling_exhausted",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        error=error,
        correlation_id=correlation_id,
    )

    try:
        execution = Execution.objects.get(id=execution_id)
        terminal_statuses = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

        if execution.status not in terminal_statuses:
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = timezone.now()
            execution.save()

        # Update the platform step with error
        platform_step = ExecutionStep.objects.filter(
            execution_id=execution_id,
            platform_job_id=platform_job_id,
        ).first()
        if platform_step and platform_step.status not in {
            ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED
        }:
            platform_step.status = ExecutionStepStatus.FAILED
            platform_step.error_message = f"Polling exhausted after {retry_count} retries: {error}"
            platform_step.completed_at = timezone.now()
            platform_step.save()

        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_POLLING_EXHAUSTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                'platform_job_id': platform_job_id,
                'retry_count': retry_count,
                'max_retries': MAX_POLLING_RETRIES,
                'last_error': error,
            },
            correlation_id=correlation_id,
        )
    except Execution.DoesNotExist:
        logger.warning(
            "polling_exhausted_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.error(
            "polling_exhausted_update_error",
            execution_id=execution_id,
            error=str(exc),
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Story 27.1: AAP job monitoring polling task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def poll_aap_job_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    resource_type: str = "job_template",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "token",
    poll_interval: int = 5,
    retry_count: int = 0,
    ssl_verify: bool = True,
    ca_bundle_path: str | None = None,
) -> dict:
    """
    Story 27.1 (AC4): Poll AAP for job status and logs, then broadcast
    updates via Django Channels to the execution's WebSocket group.

    Story 30.7 (RACE-1): Added retry_count / MAX_POLLING_RETRIES to prevent
    infinite re-scheduling on persistent adapter errors.

    Args:
        execution_id: IDP Portal execution ID.
        platform_job_id: AAP job ID to monitor.
        resource_type: 'job_template' or 'workflow_job'.
        base_url: AAP base URL (from integration).
        credential_ref: Credential reference for auth.
        auth_flow: Auth flow type (token, basic, pat).
        poll_interval: Seconds between polls (default 5).
        retry_count: Current error retry count (Story 30.7).

    Returns:
        dict with final status information.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_aap_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        resource_type=resource_type,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        # Build adapter
        from adapters.aap_adapter import AAPAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = AAPAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            ssl_verify=ssl_verify,
            ca_bundle_path=ca_bundle_path,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_aap_job_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        # Story 30.7 (RACE-1): Check max retries before re-scheduling
        if retry_count >= MAX_POLLING_RETRIES:
            _mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_aap_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
                "ssl_verify": ssl_verify,
                "ca_bundle_path": ca_bundle_path,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    aap_status = status_data.get("aap_status", "unknown")
    is_terminal = aap_status in {"successful", "failed", "error", "canceled"}

    # Broadcast updates via Django Channels
    _broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
    )

    # Update execution step status in DB
    _update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_aap_job_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=aap_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {"outcome": "complete", "status": idp_status, "aap_status": aap_status}

    # Re-schedule next poll (reset retry_count on success)
    poll_aap_job_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "resource_type": resource_type,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
            "ssl_verify": ssl_verify,
            "ca_bundle_path": ca_bundle_path,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_aap_job_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        aap_status=aap_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {"outcome": "polling", "status": idp_status, "aap_status": aap_status}


# ---------------------------------------------------------------------------
# Story 27.2: Tower/AWX job monitoring polling task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def poll_tower_job_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    resource_type: str = "job_template",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "token",
    poll_interval: int = 5,
    retry_count: int = 0,
) -> dict:
    """
    Story 27.2 (AC4): Poll Tower/AWX for job status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_tower_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        resource_type=resource_type,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.tower_adapter import TowerAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = TowerAdapter(base_url=base_url, auth_headers=auth_headers)

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_tower_job_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_tower_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    tower_status = status_data.get("tower_status", "unknown")
    is_terminal = tower_status in {"successful", "failed", "error", "canceled"}

    _broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
    )

    _update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_tower_job_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=tower_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {"outcome": "complete", "status": idp_status, "tower_status": tower_status}

    poll_tower_job_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "resource_type": resource_type,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_tower_job_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        tower_status=tower_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {"outcome": "polling", "status": idp_status, "tower_status": tower_status}


# ---------------------------------------------------------------------------
# Story 27.3: Azure DevOps pipeline run monitoring polling task
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def poll_azure_devops_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    pipeline_id: str = "",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "basic",
    poll_interval: int = 5,
    retry_count: int = 0,
) -> dict:
    """
    Story 27.3 (AC4): Poll Azure DevOps for pipeline run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_azure_devops_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        pipeline_id=pipeline_id,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.azure_devops_adapter import AzureDevOpsAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = AzureDevOpsAdapter(base_url=base_url, auth_headers=auth_headers)

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                pipeline_id=pipeline_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                pipeline_id=pipeline_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_azure_devops_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_azure_devops_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "pipeline_id": pipeline_id,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    azure_state = status_data.get("azure_devops_state", "inProgress")
    azure_result = status_data.get("azure_devops_result")
    is_terminal = azure_state == "completed" and azure_result in {
        "succeeded", "failed", "canceled"
    }

    _broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
    )

    _update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_azure_devops_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_state=azure_state,
            final_result=azure_result,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "azure_devops_state": azure_state,
            "azure_devops_result": azure_result,
        }

    poll_azure_devops_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "pipeline_id": pipeline_id,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_azure_devops_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        azure_devops_state=azure_state,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "azure_devops_state": azure_state,
        "azure_devops_result": azure_result,
    }


def _broadcast_execution_update(
    execution_id: int,
    status_data: dict,
    logs_data: dict,
    is_terminal: bool,
) -> None:
    """Broadcast status and log updates to the execution's WebSocket group."""
    try:
        from channels.layers import get_channel_layer  # type: ignore[import-untyped]
        from asgiref.sync import async_to_sync  # type: ignore[import-untyped]

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        group_name = f"execution_{execution_id}"

        # Send status update
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "status_update",
                "data": {
                    "execution_id": execution_id,
                    "status": status_data.get("status"),
                    "aap_status": status_data.get("aap_status"),
                    "started": status_data.get("started"),
                    "finished": status_data.get("finished"),
                },
            },
        )

        # Send log update
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "log_update",
                "data": {
                    "execution_id": execution_id,
                    "content": logs_data.get("content", ""),
                    "complete": logs_data.get("complete", False),
                    "timestamp": logs_data.get("timestamp"),
                },
            },
        )

        # Send terminal event
        if is_terminal:
            event_type = "execution_complete" if status_data.get("status") == "COMPLETED" else "execution_failed"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": event_type,
                    "data": {
                        "execution_id": execution_id,
                        "status": status_data.get("status"),
                        "aap_status": status_data.get("aap_status"),
                        "finished": status_data.get("finished"),
                    },
                },
            )
    except ImportError:
        logger.debug("poll_aap_broadcast_skipped_no_channels")
    except Exception as e:
        logger.warning(
            "poll_aap_broadcast_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
        )


def _update_execution_from_poll(
    execution_id: int,
    platform_job_id: str,
    idp_status: str,
    logs_content: str,
    correlation_id: str | None = None,
) -> None:
    """Update execution and step records based on polling results."""
    try:
        execution = Execution.objects.get(id=execution_id)

        # Update execution status if it changed
        current_status = execution.status
        terminal_statuses = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

        if current_status not in terminal_statuses and idp_status != current_status:
            from executions.services import ExecutionService
            svc = ExecutionService()
            try:
                svc.update_status(execution_id, idp_status, str(execution.user_id))
            except ValueError as ve:
                logger.warning(
                    "poll_aap_status_transition_invalid",
                    execution_id=execution_id,
                    current=current_status,
                    target=idp_status,
                    error=str(ve),
                    correlation_id=correlation_id,
                )

        # Update platform step logs
        platform_step = (
            ExecutionStep.objects.filter(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
            ).first()
        )
        if platform_step and logs_content:
            output = platform_step.get_output() or {}
            output["aap_logs"] = logs_content
            platform_step.set_output(output)
            platform_step.save()

    except Execution.DoesNotExist:
        logger.warning(
            "poll_aap_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.error(
            "poll_aap_update_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Story 27.4: GitHub Actions polling task (catch-up fallback for webhooks)
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=0)
def poll_github_actions_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    owner: str = "",
    repo: str = "",
    base_url: str = "",
    credential_ref: str = "",
    poll_interval: int = 60,
    retry_count: int = 0,
) -> dict:
    """
    Story 27.4 (AC4): Poll GitHub Actions for workflow run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_github_actions_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        owner=owner,
        repo=repo,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.github_actions_adapter import GitHubActionsAdapter

        auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = GitHubActionsAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            owner=owner,
            repo=repo,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_github_actions_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_github_actions_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "owner": owner,
                "repo": repo,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    gh_status = status_data.get("github_actions_status", "queued")
    gh_conclusion = status_data.get("github_actions_conclusion")
    is_terminal = gh_status == "completed" and gh_conclusion in {
        "success", "failure", "cancelled", "timed_out", "skipped"
    }

    _broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
    )

    _update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_github_actions_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=gh_status,
            final_conclusion=gh_conclusion,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "github_actions_status": gh_status,
            "github_actions_conclusion": gh_conclusion,
        }

    poll_github_actions_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "owner": owner,
            "repo": repo,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_github_actions_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        github_actions_status=gh_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "github_actions_status": gh_status,
        "github_actions_conclusion": gh_conclusion,
    }


# ---------------------------------------------------------------------------
# Story 27.5: Terraform Cloud polling task (catch-up fallback for webhooks)
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=0)
def poll_terraform_cloud_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    organization: str = "",
    base_url: str = "",
    credential_ref: str = "",
    poll_interval: int = 60,
    retry_count: int = 0,
) -> dict:
    """
    Story 27.5 (AC4): Poll Terraform Cloud for run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_terraform_cloud_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        organization=organization,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.terraform_cloud_adapter import (
            TerraformCloudAdapter,
            TERRAFORM_CLOUD_TERMINAL_STATUSES,
        )

        auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = TerraformCloudAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            organization=organization,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_terraform_cloud_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_terraform_cloud_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "organization": organization,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    tc_status = status_data.get("terraform_cloud_status", "pending")
    is_terminal = tc_status in TERRAFORM_CLOUD_TERMINAL_STATUSES

    _broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
    )

    _update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_terraform_cloud_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            terraform_cloud_status=tc_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "terraform_cloud_status": tc_status,
        }

    poll_terraform_cloud_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "organization": organization,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_terraform_cloud_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        terraform_cloud_status=tc_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "terraform_cloud_status": tc_status,
    }
