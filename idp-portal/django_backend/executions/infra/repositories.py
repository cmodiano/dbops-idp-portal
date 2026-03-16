"""Repository d'accès aux données d'exécution.

Façade infrastructure encapsulant les patterns ORM utilisés
par la couche app (orchestration_worker, etc.).

Story 85.2.
"""
from __future__ import annotations

from django.db.models import Max, QuerySet
from django.utils import timezone

from executions.models import Execution, ExecutionStep, ExecutionStepStatus


class ExecutionRepository:
    """Accès aux données des entités Execution et ExecutionStep."""

    @staticmethod
    def get_step_with_relations(step_id: int) -> ExecutionStep:
        """Charge un ExecutionStep avec execution, action et user.

        Lève ExecutionStep.DoesNotExist si absent.
        """
        return (
            ExecutionStep.objects
            .select_related('execution', 'execution__action', 'execution__user')
            .get(id=step_id)
        )

    @staticmethod
    def get_completed_steps(execution_id: int) -> QuerySet:
        """Retourne les ExecutionStep COMPLETED pour une execution, ordonnés par step_order."""
        return (
            ExecutionStep.objects
            .filter(execution_id=execution_id, status=ExecutionStepStatus.COMPLETED)
            .order_by('step_order')
        )

    @staticmethod
    def get_max_step_order(execution_id: int) -> int | None:
        """Retourne le step_order maximal parmi les ExecutionStep, ou None si aucun."""
        result = (
            ExecutionStep.objects
            .filter(execution_id=execution_id)
            .aggregate(Max('step_order'))
        )
        return result['step_order__max']  # type: ignore[no-any-return]

    @staticmethod
    def step_exists_active(execution_id: int, config_step_id: str) -> bool:
        """True si un step avec ce config_step_id est en état actif (PENDING/RUNNING/COMPLETED)."""
        return ExecutionStep.objects.filter(
            execution_id=execution_id,
            config_step_id=config_step_id,
            status__in=[
                ExecutionStepStatus.PENDING,
                ExecutionStepStatus.RUNNING,
                ExecutionStepStatus.COMPLETED,
            ],
        ).exists()

    @staticmethod
    def touch_heartbeat(execution_id: int) -> None:
        """Met à jour Execution.updated_at — heartbeat pour détection de stagnation."""
        Execution.objects.filter(id=execution_id).update(updated_at=timezone.now())
