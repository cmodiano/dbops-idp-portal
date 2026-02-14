"""
Celery tasks for workflow execution.
Story 20.3: Asynchronous retry with Celery apply_async(countdown=...).
Story 25.3: Periodic evaluation of WAITING gate conditions.
Story 27.1: AAP job monitoring polling task.
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
                gate_status.get('action', 'FAILED')
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
    Also triggers workflow continuation (on_error_step_id or next step).
    """
    timeout_action = gate_status.get('action', 'FAILED')
    timeout_hours = gate_status.get('timeout_hours')

    if timeout_action == 'SKIPPED':
        step.status = ExecutionStepStatus.SKIPPED
    else:
        step.status = ExecutionStepStatus.FAILED
        step.error_message = f'Gate timeout after {timeout_hours}h'

    step.completed_at = timezone.now()
    step.save()

    logger.info(
        "evaluate_waiting_gates_step_timeout",
        step_id=step.id,
        execution_id=step.execution_id,
        timeout_hours=timeout_hours,
        timeout_action=timeout_action,
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
            'waiting_duration_seconds': round(waiting_duration, 1),
        },
        correlation_id=correlation_id,
    )

    # Story 25.3 code review fix MEDIUM-3: Continue workflow after timeout
    # If FAILED → follow on_error_step_id logic (if defined)
    # If SKIPPED → continue to next step
    # This requires triggering the workflow runtime to process the next step.
    # For now, log a TODO to notify WorkflowRuntime to poll for completed steps.
    # Full implementation would require a task queue or workflow engine notification.
    logger.info(
        "evaluate_waiting_gates_step_timeout_workflow_continuation_needed",
        step_id=step.id,
        execution_id=step.execution_id,
        timeout_action=timeout_action,
        correlation_id=correlation_id,
        # TODO Story 25.3b: Implement workflow continuation after gate timeout
        # Option 1: Trigger retry_workflow_step with next step
        # Option 2: WorkflowRuntime polling task to detect completed steps
        # Option 3: Event-driven workflow engine (future architecture)
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
) -> dict:
    """
    Story 27.1 (AC4): Poll AAP for job status and logs, then broadcast
    updates via Django Channels to the execution's WebSocket group.

    This task is designed to be self-scheduling: after each poll, if the
    job is still running, it schedules itself again with a countdown.

    Args:
        execution_id: IDP Portal execution ID.
        platform_job_id: AAP job ID to monitor.
        resource_type: 'job_template' or 'workflow_job'.
        base_url: AAP base URL (from integration).
        credential_ref: Credential reference for auth.
        auth_flow: Auth flow type (token, basic, pat).
        poll_interval: Seconds between polls (default 5).

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
        correlation_id=correlation_id,
    )

    # CRITICAL-3 FIX: Initialize loop=None to prevent leak if exception before loop creation
    loop = None
    try:
        # Build adapter
        from adapters.aap_adapter import AAPAdapter
        from adapters.utils import build_auth_headers as _build_headers_from_integration

        # Build auth headers directly (we receive raw values, not an Integration object)
        import base64 as _b64
        if auth_flow == "basic":
            _encoded = _b64.b64encode(credential_ref.encode()).decode()
            auth_headers = {"Authorization": f"Basic {_encoded}"}
        else:
            auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = AAPAdapter(base_url=base_url, auth_headers=auth_headers)

        # Run async adapter calls in sync Celery task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)  # Set as current loop for this thread

        status_data = loop.run_until_complete(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = loop.run_until_complete(
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
            correlation_id=correlation_id,
        )
        # Re-schedule despite error (transient failure)
        poll_aap_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e)}
    finally:
        # CRITICAL-3 FIX: Ensure loop is closed even if exception before loop creation
        if loop is not None:
            loop.close()

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

    # Re-schedule next poll
    poll_aap_job_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "resource_type": resource_type,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
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
) -> dict:
    """
    Story 27.2 (AC4): Poll Tower/AWX for job status and logs, then broadcast
    updates via Django Channels to the execution's WebSocket group.

    Mirrors poll_aap_job_status but uses TowerAdapter.

    Args:
        execution_id: IDP Portal execution ID.
        platform_job_id: Tower job ID to monitor.
        resource_type: 'job_template' or 'workflow_job'.
        base_url: Tower base URL (from integration).
        credential_ref: Credential reference for auth.
        auth_flow: Auth flow type (token, basic, pat).
        poll_interval: Seconds between polls (default 5).

    Returns:
        dict with final status information.
    """
    import asyncio

    correlation_id = get_correlation_id()

    logger.info(
        "poll_tower_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        resource_type=resource_type,
        correlation_id=correlation_id,
    )

    loop = None
    try:
        from adapters.tower_adapter import TowerAdapter

        import base64 as _b64
        if auth_flow == "basic":
            _encoded = _b64.b64encode(credential_ref.encode()).decode()
            auth_headers = {"Authorization": f"Basic {_encoded}"}
        else:
            auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = TowerAdapter(base_url=base_url, auth_headers=auth_headers)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        status_data = loop.run_until_complete(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = loop.run_until_complete(
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
            correlation_id=correlation_id,
        )
        poll_tower_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e)}
    finally:
        if loop is not None:
            loop.close()

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
