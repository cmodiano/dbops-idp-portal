"""Gestion du retry avec backoff exponentiel via Celery — WorkflowRuntime."""
from __future__ import annotations

import structlog
from typing import TYPE_CHECKING, Callable

from django.utils import timezone

from executions.models import ExecutionStep, ExecutionStepStatus
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

if TYPE_CHECKING:
    from executions.models import Execution
    from executions.workflow_runtime import StepResult

logger = structlog.get_logger(__name__)


class RetryHandler:
    """
    Gestion du retry avec backoff exponentiel via Celery.

    Extrait de WorkflowRuntime (SRP) — responsable uniquement de la logique
    de retry et de planification des ré-essais via Celery.
    """

    # Story 16.4: Patterns indicating permanent (non-retryable) errors
    NON_RETRYABLE_PATTERNS = [
        'validation',
        'permission',
        'not found',
        'unauthorized',
        'forbidden',
        'bad request',
        '400', '401', '403', '404',
    ]

    def __init__(self, execution: "Execution", correlation_id: str) -> None:
        """
        Initialise le RetryHandler.

        Args:
            execution: L'instance Execution en cours d'exécution.
            correlation_id: L'identifiant de corrélation pour le logging.
        """
        self.execution = execution
        self.correlation_id = correlation_id

    def is_retryable_error(self, result: "StepResult") -> bool:
        """
        Détermine si une erreur est retryable (temporaire) ou permanente (AC3).

        Permanent errors: validation, permission, 4xx HTTP errors.
        Temporary errors: timeout, connection, 5xx, generic exceptions.

        Args:
            result: StepResult from step execution

        Returns:
            True if error is retryable (temporary), False if permanent
        """
        error_message = result.error_message
        if not error_message:
            return True

        # Check error_type first (more reliable than string matching)
        error_details = result.error_details or {}
        error_type = error_details.get('error_type', '')
        if error_type in ('validation', 'permission'):
            return False

        # Fallback to string pattern matching
        error_lower = error_message.lower()
        for pattern in self.NON_RETRYABLE_PATTERNS:
            if pattern in error_lower:
                return False
        return True

    def execute_with_retry(
        self,
        step: dict,
        execute_fn: Callable[[dict, int], "StepResult"],
        step_order_counter_fn: Callable[[], int],
    ) -> "StepResult":
        """
        Exécute une étape avec logique de retry si retry_enabled est true (Story 16.4, 20.3).

        Story 20.3: Uses Celery apply_async(countdown=...) for non-blocking retry
        instead of time.sleep(). First attempt is synchronous; subsequent retries
        are scheduled as Celery tasks.

        Implements:
        - AC1: Retry with exponential backoff (via Celery countdown)
        - AC2: Stop retrying on success
        - AC3: Stop retrying on permanent errors
        - AC4: Cancel-aware (checks execution status before each attempt)
        - AC5: Audit trail for each attempt

        Args:
            step: Step dict from workflow definition
            execute_fn: Callable(step, step_order) -> StepResult — exécute une étape
            step_order_counter_fn: Callable() -> int — incrémente le compteur et retourne la valeur

        Returns:
            StepResult with final outcome after first attempt
        """
        from executions.workflow_runtime import StepResult, StepOutcome  # noqa: PLC0415

        retry_enabled = step.get('retry_enabled', False)
        step_id = step.get('step_id', 'unknown')

        if not retry_enabled:
            step_order = step_order_counter_fn()
            return execute_fn(step, step_order)

        max_attempts = step.get('retry_max_attempts', 3)
        interval_seconds = step.get('retry_interval_seconds', 60)

        # AC4: Check if execution was cancelled before first attempt
        from executions.cancellation_cache import is_cancelled  # noqa: PLC0415
        if is_cancelled(self.execution.id):
            step_order = step_order_counter_fn()
            logger.info(
                "workflow_step_retry_cancelled",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                correlation_id=self.correlation_id,
            )
            ExecutionStep.objects.create(
                execution=self.execution,
                step_order=step_order,
                step_name=step.get('name', f"Step {step.get('order', 0)}"),
                step_type='platform',
                status=ExecutionStepStatus.FAILED,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                error_message="Execution cancelled during retry",
            )
            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message="Execution cancelled during retry",
            )

        # First attempt: synchronous (attempt=1)
        logger.info(
            "workflow_step_retry_attempt",
            execution_id=self.execution.id,
            step_id=step_id,
            attempt=1,
            max_attempts=max_attempts,
            correlation_id=self.correlation_id,
        )

        step_order = step_order_counter_fn()
        result = execute_fn(step, step_order)

        # AC2: Success — stop immediately
        if result.is_success:
            logger.info(
                "workflow_step_retry_success",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                max_attempts=max_attempts,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_SUCCESS,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'result': 'success',
                },
                correlation_id=self.correlation_id,
            )
            return result

        # AC3: Permanent error — stop immediately
        if result.is_error and not self.is_retryable_error(result):
            logger.warning(
                "workflow_step_non_retryable_error",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                error=result.error_message,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_ABORTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'reason': 'non_retryable_error',
                    'error': result.error_message,
                },
                correlation_id=self.correlation_id,
            )
            return result

        # Temporary failure — schedule Celery retry if more attempts available
        if max_attempts > 1:
            from executions.tasks import retry_workflow_step  # noqa: PLC0415

            delay_seconds = interval_seconds  # Delay before attempt 2

            logger.info(
                "workflow_step_retry_scheduling_celery",
                execution_id=self.execution.id,
                step_id=step_id,
                next_attempt=2,
                delay_seconds=delay_seconds,
                correlation_id=self.correlation_id,
            )

            # AC5: Audit trail for failed first attempt
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'result': 'error',
                    'error': result.error_message,
                    'next_wait_seconds': delay_seconds,
                    'retry_method': 'celery',
                },
                correlation_id=self.correlation_id,
            )

            # Schedule async retry via Celery
            retry_workflow_step.apply_async(
                args=[self.execution.id, step, 2],
                countdown=delay_seconds,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=f"Step failed, retry scheduled (attempt 2/{max_attempts} in {delay_seconds}s)",
                error_details={
                    'retry_scheduled': True,
                    'next_attempt': 2,
                    'max_attempts': max_attempts,
                    'delay_seconds': delay_seconds,
                },
            )

        # max_attempts = 1, no retry possible
        logger.error(
            "workflow_step_retry_exhausted",
            execution_id=self.execution.id,
            step_id=step_id,
            max_attempts=1,
            final_error=result.error_message,
            correlation_id=self.correlation_id,
        )
        AuditService.create_entry(
            user_id=str(self.execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=self.execution.id,
            details={
                'step_id': step_id,
                'max_attempts': 1,
                'final_error': result.error_message,
            },
            correlation_id=self.correlation_id,
        )
        return result
