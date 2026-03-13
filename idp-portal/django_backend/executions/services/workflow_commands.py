"""Service pour la persistance et le traitement des commandes workflow.

Story 78.4 — Command Store pour orchestration asynchrone.
L'API écrit une commande durable et retourne rapidement,
un processor séparé traite les commandes en FIFO.

Usage:
    from executions.services.workflow_commands import WorkflowCommandService
    WorkflowCommandService.write_command(execution_id, "approve", payload, "user@example.com")
"""
from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone

from executions.models import (
    Execution,
    WorkflowCommand,
    WorkflowCommandStatus,
    VALID_COMMAND_TYPES,
)

logger = structlog.get_logger(__name__)


class WorkflowCommandService:
    """Service pour la persistance et le traitement des commandes workflow."""

    @classmethod
    def write_command(cls, execution_id: int, command_type: str, payload: dict | None = None, created_by: str | None = None) -> WorkflowCommand:
        """Persiste une commande et retourne immédiatement.

        Args:
            execution_id: ID de l'exécution cible.
            command_type: Type de commande (approve, reject, cancel, timeout_signal, resume_signal).
            payload: Données JSON optionnelles.
            created_by: Identifiant utilisateur.

        Returns:
            WorkflowCommand créée avec status='pending'.

        Raises:
            ValueError: Si command_type invalide.
            Execution.DoesNotExist: Si l'exécution n'existe pas.
        """
        if command_type not in VALID_COMMAND_TYPES:
            raise ValueError(f"Invalid command_type: {command_type}. Must be one of {VALID_COMMAND_TYPES}")

        with transaction.atomic():
            # Valider que l'exécution existe (exists() plus efficace que get())
            if not Execution.objects.filter(pk=execution_id).exists():
                raise Execution.DoesNotExist(
                    "Execution matching query does not exist."
                )

            command = WorkflowCommand.objects.create(
                execution_id=execution_id,
                command_type=command_type,
                payload=payload or {},
                created_by=created_by,
            )

        logger.info(
            "workflow_command_created",
            command_id=command.id,
            execution_id=execution_id,
            command_type=command_type,
            created_by=created_by,
        )

        return command

    @classmethod
    def process_pending_commands(cls, batch_size: int = 50) -> int:
        """Traite les commandes pending en FIFO. Retourne le nombre traité.

        Utilise SELECT ... FOR UPDATE SKIP LOCKED pour la concurrence
        multi-worker (même pattern que RunnableStepService.claim_batch).

        Args:
            batch_size: Nombre max de commandes à traiter par batch.

        Returns:
            Nombre de commandes traitées.
        """
        processed = 0

        with transaction.atomic():
            commands = list(
                WorkflowCommand.objects
                .filter(status=WorkflowCommandStatus.PENDING)
                .order_by("created_at")
                .select_for_update(skip_locked=True)[:batch_size]
            )

            for cmd in commands:
                try:
                    with transaction.atomic():
                        cls._dispatch_command(cmd)
                        cmd.status = WorkflowCommandStatus.PROCESSED
                        cmd.processed_at = timezone.now()
                        cmd.save(update_fields=["status", "processed_at"])
                        processed += 1
                except Exception as e:
                    cmd.status = WorkflowCommandStatus.FAILED
                    cmd.error_message = str(e)[:4000]
                    cmd.processed_at = timezone.now()
                    cmd.save(update_fields=["status", "error_message", "processed_at"])
                    logger.error(
                        "workflow_command_failed",
                        command_id=cmd.id,
                        command_type=cmd.command_type,
                        error=str(e),
                    )

        return processed

    @classmethod
    def _dispatch_command(cls, cmd: WorkflowCommand) -> None:
        """Dispatch vers le handler approprié.

        Story 78.4: infrastructure seulement — les handlers seront
        branchés dans 78.5/78.6.
        """
        logger.info(
            "workflow_command_dispatched",
            command_id=cmd.id,
            command_type=cmd.command_type,
            execution_id=cmd.execution_id,
        )
