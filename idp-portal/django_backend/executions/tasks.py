"""
Celery tasks for workflow execution.
Story 20.3: Asynchronous retry with Celery apply_async(countdown=...).
"""

import structlog
from celery import shared_task
from django.db import transaction

from executions.models import Execution, ExecutionStatus
from executions.workflow_runtime import StepResult, StepOutcome
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)


@shared_task(bind=True, max_retries=0)
def retry_workflow_step(self, execution_id: int, step: dict, attempt: int):
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
        logger.exception(
            "celery_retry_workflow_step_error",
            execution_id=execution_id,
            step_id=step_id,
            attempt=attempt,
            error=str(e),
        )
        return {
            'outcome': StepOutcome.ERROR.value,
            'error_message': f'Celery task error: {str(e)}',
        }
