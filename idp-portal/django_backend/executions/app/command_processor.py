"""Processeur de commandes workflow — Story 85.3 : Relocalisation vers app/command_processor.py.

Origine : executions/services/workflow_commands.py (Stories 78.4 / 78.5).
Ce module est désormais le module actif ; services/workflow_commands.py est un shim de
rétrocompatibilité qui ré-exporte depuis ici.

Story 78.4 — Command Store pour orchestration asynchrone.
Story 78.5 — Handlers approve/reject/cancel/timeout/resume branchés.

L'API écrit une commande durable et retourne rapidement,
un processor séparé traite les commandes en FIFO.

Usage:
    from executions.app.command_processor import WorkflowCommandService
    WorkflowCommandService.write_command(execution_id, "approve", payload, "user@example.com")
"""
from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone

from catalog.workflow_definition_repository import get_steps as get_workflow_steps
from executions.domain.commands import CommandType, VALID_COMMAND_TYPES
from executions.domain.workflow_graph import find_step_config, get_linear_next_step_ids
from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
    WorkflowCommand,
    WorkflowCommandStatus,
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
        multi-worker (même pattern que WorkQueue.claim).

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

        Story 78.5: Route vers _handle_approve, _handle_reject, _handle_cancel,
        _handle_timeout, _handle_resume.
        """
        logger.info(
            "workflow_command_dispatched",
            command_id=cmd.id,
            command_type=cmd.command_type,
            execution_id=cmd.execution_id,
        )

        handler = {
            CommandType.APPROVE.value: cls._handle_approve,
            CommandType.REJECT.value: cls._handle_reject,
            CommandType.CANCEL.value: cls._handle_cancel,
            CommandType.TIMEOUT_SIGNAL.value: cls._handle_timeout,
            CommandType.RESUME_SIGNAL.value: cls._handle_resume,
        }.get(cmd.command_type)

        if handler is None:
            raise ValueError(f"No handler for command_type: {cmd.command_type}")

        handler(cmd)

    @classmethod
    def _handle_approve(cls, cmd: WorkflowCommand) -> None:
        """Handle approve command: step WAITING→COMPLETED, emit event, enqueue next steps."""
        payload = cmd.payload or {}
        step_id = payload.get("step_id")
        user_id = cmd.created_by or "system"

        if not step_id:
            raise ValueError("approve command requires payload.step_id")

        step = ExecutionStep.objects.select_related('execution', 'execution__action').get(
            id=step_id, execution_id=cmd.execution_id,
        )

        if step.status != ExecutionStepStatus.WAITING:
            logger.info(
                "command_approve_step_not_waiting",
                step_id=step_id,
                status=step.status,
                execution_id=cmd.execution_id,
            )
            return  # Idempotent: already processed

        # Update step status (state_machine validates WAITING→COMPLETED)
        from executions.domain.state_machine import assert_step_transition  # noqa: PLC0415
        assert_step_transition(step.status, ExecutionStepStatus.COMPLETED)
        step.status = ExecutionStepStatus.COMPLETED
        step.completed_at = timezone.now()
        step.approval_comment = payload.get("comment", "")

        # Update gate_status in output
        # Story 84.2: Marquer TOUTES les conditions à résolution manuelle (sans break).
        from executions.gates.registry import gate_registry  # noqa: PLC0415
        output = step.get_output() or {}
        gate_status = output.get("gate_status", [])
        for gs in gate_status:
            if isinstance(gs, dict) and gate_registry.is_manual_condition_type(gs.get("type", "")):
                gs["satisfied"] = True
                gs["reason"] = f"Approuvé par utilisateur {user_id}"
        output["gate_status"] = gate_status
        step.set_output(output)
        step.save()

        # Story 78.7: Write outbox entry for side-effects (replaces on_commit callback)
        from executions.services.outbox import OutboxService, APPROVAL_GRANTED  # noqa: PLC0415
        OutboxService.write_entry(
            execution_id=cmd.execution_id,
            event_type=APPROVAL_GRANTED,
            payload={
                "execution_step_id": step.id,
                "approved_by": user_id,
                "execution_id": cmd.execution_id,
            },
            idempotency_key=OutboxService.build_idempotency_key(
                cmd.execution_id, APPROVAL_GRANTED, f"step_{step.id}",
            ),
        )

        # Determine and enqueue next steps
        execution = step.execution
        all_steps = get_workflow_steps(execution.action)
        step_config = find_step_config(all_steps, step.config_step_id)

        if step_config:
            on_success = step_config.get("on_success_step_ids") or []
            if not on_success:
                # Linear fallback: next step by order
                on_success = get_linear_next_step_ids(step_config, all_steps)

            if on_success:
                cls._enqueue_resume_steps(execution, on_success, all_steps)
            else:
                # No next steps — finalize if needed (deferred to on_commit)
                transaction.on_commit(
                    lambda: cls._finalize_if_done(execution)
                )
        else:
            transaction.on_commit(
                lambda: cls._finalize_if_done(execution)
            )

        logger.info(
            "command_approve_handled",
            step_id=step_id,
            execution_id=cmd.execution_id,
            user_id=user_id,
        )

    @classmethod
    def _handle_reject(cls, cmd: WorkflowCommand) -> None:
        """Handle reject command: step WAITING→FAILED, emit event, route to error path."""
        payload = cmd.payload or {}
        step_id = payload.get("step_id")
        user_id = cmd.created_by or "system"

        if not step_id:
            raise ValueError("reject command requires payload.step_id")

        step = ExecutionStep.objects.select_related('execution', 'execution__action').get(
            id=step_id, execution_id=cmd.execution_id,
        )

        if step.status != ExecutionStepStatus.WAITING:
            logger.info(
                "command_reject_step_not_waiting",
                step_id=step_id,
                status=step.status,
                execution_id=cmd.execution_id,
            )
            return  # Idempotent

        from executions.domain.state_machine import assert_step_transition  # noqa: PLC0415
        assert_step_transition(step.status, ExecutionStepStatus.FAILED)
        step.status = ExecutionStepStatus.FAILED
        step.completed_at = timezone.now()
        step.approval_comment = payload.get("comment", "")
        step.save()

        # Story 78.7: Write outbox entry for side-effects (replaces on_commit callback)
        from executions.services.outbox import OutboxService, APPROVAL_REJECTED  # noqa: PLC0415
        OutboxService.write_entry(
            execution_id=cmd.execution_id,
            event_type=APPROVAL_REJECTED,
            payload={
                "execution_step_id": step.id,
                "rejected_by": user_id,
                "execution_id": cmd.execution_id,
                "reason": payload.get("comment", ""),
            },
            idempotency_key=OutboxService.build_idempotency_key(
                cmd.execution_id, APPROVAL_REJECTED, f"step_{step.id}",
            ),
        )

        # Route to error path or fail execution
        execution = step.execution
        all_steps = get_workflow_steps(execution.action)
        step_config = find_step_config(all_steps, step.config_step_id)

        on_error = (step_config.get("on_error_step_ids") or []) if step_config else []

        if on_error:
            cls._enqueue_resume_steps(execution, on_error, all_steps)
        else:
            # No error path — fail the execution
            if execution.status == ExecutionStatus.RUNNING:
                Execution.objects.filter(
                    id=execution.id, status=ExecutionStatus.RUNNING,
                ).update(
                    status=ExecutionStatus.FAILED,
                    completed_at=timezone.now(),
                    error_message="Step approval rejected",
                )

        logger.info(
            "command_reject_handled",
            step_id=step_id,
            execution_id=cmd.execution_id,
            user_id=user_id,
        )

    @classmethod
    def _handle_cancel(cls, cmd: WorkflowCommand) -> None:
        """Handle cancel command: execution→CANCELLED, cascade cancel children."""
        execution = Execution.objects.get(id=cmd.execution_id)

        if execution.status not in (ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING):
            logger.info(
                "command_cancel_not_cancellable",
                execution_id=cmd.execution_id,
                status=execution.status,
            )
            return  # Idempotent

        # Validate transition legality before CAS
        from executions.domain.state_machine import assert_execution_transition  # noqa: PLC0415
        assert_execution_transition(execution.status, ExecutionStatus.CANCELLED)

        # CAS update to CANCELLED
        updated = Execution.objects.filter(
            id=execution.id,
            status__in=[ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING],
        ).update(
            status=ExecutionStatus.CANCELLED,
            completed_at=timezone.now(),
        )

        if updated == 0:
            return

        # Cascade cancel child executions
        Execution.objects.filter(
            parent_execution_id=execution.id,
            status__in=[ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING],
        ).update(
            status=ExecutionStatus.CANCELLED,
            completed_at=timezone.now(),
        )

        # Cancel pending steps
        ExecutionStep.objects.filter(
            execution_id=execution.id,
            status__in=[ExecutionStepStatus.PENDING, ExecutionStepStatus.RUNNING, ExecutionStepStatus.WAITING],
        ).update(
            status=ExecutionStepStatus.FAILED,
            completed_at=timezone.now(),
            error_message="Execution cancelled",
        )

        # Dequeue all runnable steps for this execution
        from executions.infra.work_queue import WorkQueue  # noqa: PLC0415
        WorkQueue.delete_for_execution(execution.id)

        # Mark in cancellation cache
        from executions.cancellation_cache import mark_cancelled  # noqa: PLC0415
        mark_cancelled(execution.id)

        # Audit trail (was in ExecutionCancelView before 78.5)
        try:
            from core.services import AuditService  # noqa: PLC0415
            from core.models import AuditActionType, AuditEntityType  # noqa: PLC0415
            AuditService.create_entry(
                user_id=cmd.created_by or "system",
                action_type=AuditActionType.EXECUTION_CANCELLED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution.id,
                details={"cancelled_by": cmd.created_by, "via": "workflow_command"},
                correlation_id=getattr(execution, 'correlation_id', None),
            )
        except Exception:  # noqa: BLE001
            logger.warning("command_cancel_audit_failed", execution_id=execution.id)

        logger.info(
            "command_cancel_handled",
            execution_id=cmd.execution_id,
            cancelled_by=cmd.created_by,
        )

    @classmethod
    def _handle_timeout(cls, cmd: WorkflowCommand) -> None:
        """Handle timeout_signal: step WAITING→FAILED, route to error path."""
        payload = cmd.payload or {}
        step_id = payload.get("step_id")

        if not step_id:
            raise ValueError("timeout_signal command requires payload.step_id")

        step = ExecutionStep.objects.select_related('execution', 'execution__action').get(
            id=step_id, execution_id=cmd.execution_id,
        )

        if step.status != ExecutionStepStatus.WAITING:
            return  # Idempotent

        from executions.domain.state_machine import assert_step_transition  # noqa: PLC0415
        assert_step_transition(step.status, ExecutionStepStatus.FAILED)
        step.status = ExecutionStepStatus.FAILED
        step.completed_at = timezone.now()
        step.error_message = "Step timed out"
        step.save()

        # Dequeue
        from executions.infra.work_queue import WorkQueue  # noqa: PLC0415
        WorkQueue.release(step.id)

        # Route to error path
        execution = step.execution
        all_steps = get_workflow_steps(execution.action)
        step_config = find_step_config(all_steps, step.config_step_id)
        on_error = (step_config.get("on_error_step_ids") or []) if step_config else []

        if on_error:
            cls._enqueue_resume_steps(execution, on_error, all_steps)
        else:
            if execution.status == ExecutionStatus.RUNNING:
                Execution.objects.filter(
                    id=execution.id, status=ExecutionStatus.RUNNING,
                ).update(
                    status=ExecutionStatus.FAILED,
                    completed_at=timezone.now(),
                    error_message="Step timed out",
                )

        logger.info(
            "command_timeout_handled",
            step_id=step_id,
            execution_id=cmd.execution_id,
        )

    @classmethod
    def _handle_resume(cls, cmd: WorkflowCommand) -> None:
        """Handle resume_signal: enqueue specified step_ids as new runnable steps."""
        payload = cmd.payload or {}
        step_ids = payload.get("step_ids", [])

        if not step_ids:
            raise ValueError("resume_signal command requires payload.step_ids")

        execution = Execution.objects.select_related('action').get(id=cmd.execution_id)

        if execution.status != ExecutionStatus.RUNNING:
            logger.info(
                "command_resume_execution_not_running",
                execution_id=cmd.execution_id,
                status=execution.status,
            )
            return

        all_steps = get_workflow_steps(execution.action)
        cls._enqueue_resume_steps(execution, step_ids, all_steps)

        logger.info(
            "command_resume_handled",
            step_ids=step_ids,
            execution_id=cmd.execution_id,
        )

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _enqueue_resume_steps(
        cls, execution: Execution, step_ids: list[str], all_steps: list,
    ) -> None:
        """Create PENDING ExecutionSteps for the given step_ids and enqueue them."""
        from executions.infra.work_queue import WorkQueue  # noqa: PLC0415
        from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
        from django.db.models import Max  # noqa: PLC0415

        max_order = ExecutionStep.objects.filter(
            execution=execution,
        ).aggregate(Max('step_order'))['step_order__max'] or 0

        step_config_by_id = {
            s.get('step_id'): s
            for s in all_steps
            if isinstance(s, dict) and s.get('step_id')
        }

        for sid in step_ids:
            if not isinstance(sid, str) or not sid:
                continue

            # Idempotency: skip if step already exists and is active
            existing = ExecutionStep.objects.filter(
                execution=execution,
                config_step_id=sid,
                status__in=[
                    ExecutionStepStatus.PENDING,
                    ExecutionStepStatus.RUNNING,
                    ExecutionStepStatus.COMPLETED,
                ],
            ).exists()
            if existing:
                continue

            step_config = step_config_by_id.get(sid)
            if not step_config:
                continue

            step_type_str = step_config.get('step_type', 'platform')
            from executions.models import ExecutionStepType  # noqa: PLC0415
            db_step_type = ContainerWorkflowRuntime._STEP_TYPE_TO_DB_TYPE.get(
                step_type_str, ExecutionStepType.PLATFORM,
            )
            step_name = step_config.get('name') or f"Étape {step_config.get('order', 0)}"

            max_order += 1
            exec_step = ExecutionStep.objects.create(
                execution=execution,
                step_order=max_order,
                step_name=step_name,
                config_step_id=sid,
                step_type=db_step_type,
                status=ExecutionStepStatus.PENDING,
            )
            WorkQueue.enqueue(exec_step)

    @staticmethod
    def _finalize_if_done(execution: Execution) -> None:
        """Finalize execution if no more active steps remain."""
        from executions.app.orchestrator import _finalize_execution_if_done  # noqa: PLC0415
        with transaction.atomic():
            execution.refresh_from_db()
            _finalize_execution_if_done(execution, ExecutionStatus.COMPLETED)
