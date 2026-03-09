"""
executions/tasks/retry.py — Responsabilité unique : exécution asynchrone d'un step
de workflow avec backoff exponentiel via Celery.

Expose : retry_workflow_step
"""
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]

from executions.models import Execution
from executions.workflow_runtime import StepOutcome
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)

# story 66-16 review: module-level constant (was incorrectly defined inside the function)
_MAX_RETRY_DELAY_SECONDS = 86400  # 24h max, prevents overflow on high attempt counts


@shared_task(bind=True, max_retries=0, name="executions.tasks.retry_workflow_step")
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
        execution = Execution.objects.select_related('action').get(id=execution_id)
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
                    'execution_id': str(execution_id),
                    'action_name': execution.action.name if execution.action else None,
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
                    'execution_id': str(execution_id),
                    'action_name': execution.action.name if execution.action else None,
                    'step_id': step_id,
                    'attempt': attempt,
                    'max_attempts': step.get('retry_max_attempts', 3),
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
                    'execution_id': str(execution_id),
                    'action_name': execution.action.name if execution.action else None,
                    'step_id': step_id,
                    'max_attempts': max_attempts,
                    'final_error': result.error_message,
                },
            )
            return {
                'outcome': result.outcome.value,
                'error_message': result.error_message,
            }

        # Schedule next retry with exponential backoff — capped at 24h (story 66-16 finding MEDIUM)
        interval_seconds = step.get('retry_interval_seconds', 60)
        backoff_multiplier = step.get('retry_backoff_multiplier', 2.0)
        delay_seconds = min(
            interval_seconds * (backoff_multiplier ** (attempt - 1)),
            _MAX_RETRY_DELAY_SECONDS,
        )

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
                'execution_id': str(execution_id),
                'action_name': execution.action.name if execution.action else None,
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
    except Exception as e:  # noqa: BLE001 — resilience-boundary: Celery retry task must handle all failure modes gracefully
        # Story 22.11: Justified broad catch - Celery retry task must handle all failure modes
        # Access through package namespace for testability:
        # allows @patch("executions.tasks.logger") and @patch("executions.tasks.get_correlation_id")
        import executions.tasks as _tasks
        _tasks.logger.exception(
            "celery_retry_workflow_step_error",
            execution_id=execution_id,
            step_id=step_id,
            attempt=attempt,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=_tasks.get_correlation_id(),
        )
        return {
            'outcome': StepOutcome.ERROR.value,
            'error_message': f'Celery task error: {str(e)}',
        }
