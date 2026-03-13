"""
Tests Story 78.4 — Table WORKFLOW_COMMANDS et persistance des commandes

AC1 : Table WORKFLOW_COMMANDS avec colonnes id, execution_id, command_type, payload, status, created_at, processed_at, created_by
AC2 : Modèle Django WorkflowCommand correspondant avec migration 0018
AC3 : write_command() persiste commande avec status='pending' et retourne immédiatement
AC4 : process_pending_commands() traite FIFO, status processed/failed
AC5 : Tests couvrant création, FIFO, idempotence, gestion erreur, validation
"""
from unittest.mock import patch

import pytest
from django.utils import timezone

from executions.models import (
    WorkflowCommand,
    WorkflowCommandStatus,
    VALID_COMMAND_TYPES,
    Execution,
)
from executions.services.workflow_commands import WorkflowCommandService
from tests.factories import ExecutionFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_command(execution=None, **kwargs):
    """Helper pour créer un WorkflowCommand en base.

    Note: created_at a auto_now_add=True — Django ignore le kwarg au create().
    Ce helper applique created_at via .update() après création si fourni.
    """
    if execution is None:
        execution = ExecutionFactory()
    created_at = kwargs.pop("created_at", None)
    defaults = {
        "execution": execution,
        "command_type": kwargs.pop("command_type", "approve"),
        "payload": kwargs.pop("payload", {}),
        "status": kwargs.pop("status", WorkflowCommandStatus.PENDING),
        "created_by": kwargs.pop("created_by", "test-user"),
    }
    defaults.update(kwargs)
    cmd = WorkflowCommand.objects.create(**defaults)
    if created_at is not None:
        WorkflowCommand.objects.filter(pk=cmd.pk).update(created_at=created_at)
        cmd.refresh_from_db()
    return cmd


# ===========================================================================
# AC1/AC2 — Modèle et schéma
# ===========================================================================

@pytest.mark.django_db
class TestAC1AC2ModelSchema:
    """AC1/AC2 : Le modèle WorkflowCommand a les bonnes colonnes et défauts."""

    def test_table_name(self):
        assert WorkflowCommand._meta.db_table == "WORKFLOW_COMMANDS"

    def test_ordering(self):
        assert WorkflowCommand._meta.ordering == ["created_at"]

    def test_status_default(self):
        execution = ExecutionFactory()
        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="approve",
        )
        cmd.refresh_from_db()
        assert cmd.status == WorkflowCommandStatus.PENDING

    def test_nullable_fields(self):
        execution = ExecutionFactory()
        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="cancel",
        )
        cmd.refresh_from_db()
        assert cmd.payload is None or cmd.payload == {}  # JSONField default behavior
        assert cmd.processed_at is None
        assert cmd.created_by is None
        assert cmd.error_message is None

    def test_round_trip_all_fields(self):
        """Écriture et relecture de tous les champs."""
        execution = ExecutionFactory()
        now = timezone.now()
        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="reject",
            payload={"step_id": 42, "comment": "Non conforme"},
            status=WorkflowCommandStatus.PROCESSED,
            processed_at=now,
            created_by="admin@example.com",
            error_message=None,
        )
        cmd.refresh_from_db()
        assert cmd.execution_id == execution.id
        assert cmd.command_type == "reject"
        assert cmd.payload == {"step_id": 42, "comment": "Non conforme"}
        assert cmd.status == WorkflowCommandStatus.PROCESSED
        assert cmd.processed_at is not None
        assert cmd.created_by == "admin@example.com"
        assert cmd.created_at is not None

    def test_fk_execution(self):
        """FK vers Execution fonctionne."""
        field = WorkflowCommand._meta.get_field("execution")
        assert field.related_model is Execution
        assert field.remote_field.on_delete.__name__ == "CASCADE"

    def test_index_exists(self):
        """Index sur (status, created_at) est défini."""
        index_names = [idx.name for idx in WorkflowCommand._meta.indexes]
        assert "idx_wf_cmd_status_created" in index_names

    def test_str_representation(self):
        execution = ExecutionFactory()
        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="approve",
        )
        result = str(cmd)
        assert "approve" in result
        assert "pending" in result

    def test_valid_command_types_constant(self):
        """VALID_COMMAND_TYPES contient les 5 types attendus."""
        expected = {"approve", "reject", "cancel", "timeout_signal", "resume_signal"}
        assert set(VALID_COMMAND_TYPES) == expected


# ===========================================================================
# AC3 — write_command()
# ===========================================================================

@pytest.mark.django_db
class TestAC3WriteCommand:
    """AC3 : write_command() persiste avec status='pending'."""

    def test_write_command_creates_pending(self):
        execution = ExecutionFactory()
        cmd = WorkflowCommandService.write_command(
            execution_id=execution.id,
            command_type="approve",
            payload={"step_id": 1},
            created_by="user@example.com",
        )
        assert cmd.id is not None
        assert cmd.status == WorkflowCommandStatus.PENDING
        assert cmd.command_type == "approve"
        assert cmd.payload == {"step_id": 1}
        assert cmd.created_by == "user@example.com"
        assert cmd.execution_id == execution.id
        assert cmd.processed_at is None

    def test_write_command_persisted_in_db(self):
        execution = ExecutionFactory()
        cmd = WorkflowCommandService.write_command(
            execution_id=execution.id,
            command_type="cancel",
        )
        db_cmd = WorkflowCommand.objects.get(pk=cmd.id)
        assert db_cmd.command_type == "cancel"
        assert db_cmd.status == WorkflowCommandStatus.PENDING

    def test_write_command_invalid_type_raises(self):
        execution = ExecutionFactory()
        with pytest.raises(ValueError, match="Invalid command_type"):
            WorkflowCommandService.write_command(
                execution_id=execution.id,
                command_type="invalid_type",
            )

    def test_write_command_nonexistent_execution_raises(self):
        with pytest.raises(Execution.DoesNotExist):
            WorkflowCommandService.write_command(
                execution_id=999999,
                command_type="approve",
            )

    def test_write_command_default_payload(self):
        """Payload par défaut est un dict vide."""
        execution = ExecutionFactory()
        cmd = WorkflowCommandService.write_command(
            execution_id=execution.id,
            command_type="reject",
        )
        assert cmd.payload == {}

    def test_write_command_all_types(self):
        """Chaque type de commande valide peut être créé."""
        execution = ExecutionFactory()
        for cmd_type in VALID_COMMAND_TYPES:
            cmd = WorkflowCommandService.write_command(
                execution_id=execution.id,
                command_type=cmd_type,
            )
            assert cmd.command_type == cmd_type
            assert cmd.status == WorkflowCommandStatus.PENDING


# ===========================================================================
# AC4 — process_pending_commands()
# ===========================================================================

@pytest.mark.django_db
class TestAC4ProcessPendingCommands:
    """AC4 : Traitement FIFO, status processed/failed."""

    def test_process_single_command(self):
        execution = ExecutionFactory()
        cmd = _make_command(execution=execution)

        # Story 78.5: _dispatch_command now has real handlers that need valid payload.
        # Mock dispatch to test infrastructure only (78.4 scope).
        with patch.object(WorkflowCommandService, '_dispatch_command', classmethod(lambda cls, c: None)):
            count = WorkflowCommandService.process_pending_commands()

        assert count == 1
        cmd.refresh_from_db()
        assert cmd.status == WorkflowCommandStatus.PROCESSED
        assert cmd.processed_at is not None

    def test_fifo_order(self):
        """Les commandes sont traitées dans l'ordre chronologique."""
        execution = ExecutionFactory()
        now = timezone.now()

        # Créer 3 commandes avec des timestamps décroissants pour vérifier l'ordre FIFO
        cmd3 = _make_command(execution=execution, command_type="cancel",
                             created_at=now)
        cmd1 = _make_command(execution=execution, command_type="approve",
                             created_at=now - timezone.timedelta(minutes=10))
        cmd2 = _make_command(execution=execution, command_type="reject",
                             created_at=now - timezone.timedelta(minutes=5))

        processed_order = []

        @classmethod
        def tracking_dispatch(cls, cmd):
            processed_order.append(cmd.id)

        with patch.object(WorkflowCommandService, '_dispatch_command', tracking_dispatch):
            count = WorkflowCommandService.process_pending_commands()

        assert count == 3
        # Ordre FIFO : cmd1 (le plus ancien) → cmd2 → cmd3
        assert processed_order == [cmd1.id, cmd2.id, cmd3.id]

    def test_idempotence_already_processed(self):
        """Commande déjà processed → skip (pas de double traitement)."""
        execution = ExecutionFactory()
        cmd = _make_command(
            execution=execution,
            status=WorkflowCommandStatus.PROCESSED,
            processed_at=timezone.now(),
        )

        count = WorkflowCommandService.process_pending_commands()
        assert count == 0
        cmd.refresh_from_db()
        assert cmd.status == WorkflowCommandStatus.PROCESSED

    def test_idempotence_already_failed(self):
        """Commande déjà failed → skip."""
        execution = ExecutionFactory()
        cmd = _make_command(
            execution=execution,
            status=WorkflowCommandStatus.FAILED,
            error_message="previous error",
        )

        count = WorkflowCommandService.process_pending_commands()
        assert count == 0
        cmd.refresh_from_db()
        assert cmd.status == WorkflowCommandStatus.FAILED

    def test_error_handling_failed_status(self):
        """Commande qui échoue → status failed, erreur stockée."""
        execution = ExecutionFactory()
        cmd = _make_command(execution=execution)

        with patch.object(
            WorkflowCommandService,
            '_dispatch_command',
            side_effect=RuntimeError("Handler crashed"),
        ):
            count = WorkflowCommandService.process_pending_commands()

        assert count == 0
        cmd.refresh_from_db()
        assert cmd.status == WorkflowCommandStatus.FAILED
        assert "Handler crashed" in cmd.error_message
        assert cmd.processed_at is not None

    def test_error_does_not_block_next_commands(self):
        """Une commande qui échoue ne bloque pas les suivantes."""
        execution = ExecutionFactory()
        now = timezone.now()

        cmd1 = _make_command(execution=execution, command_type="approve",
                             created_at=now - timezone.timedelta(minutes=5))
        cmd2 = _make_command(execution=execution, command_type="reject",
                             created_at=now)

        call_count = [0]

        @classmethod
        def failing_first_dispatch(cls, cmd):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First command fails")
            # Second command succeeds (default stub behavior)

        with patch.object(WorkflowCommandService, '_dispatch_command', failing_first_dispatch):
            count = WorkflowCommandService.process_pending_commands()

        # 1 processed (cmd2), cmd1 failed
        assert count == 1
        cmd1.refresh_from_db()
        cmd2.refresh_from_db()
        assert cmd1.status == WorkflowCommandStatus.FAILED
        assert cmd2.status == WorkflowCommandStatus.PROCESSED

    def test_batch_size_respected(self):
        """batch_size limite le nombre de commandes traitées, en FIFO."""
        execution = ExecutionFactory()
        now = timezone.now()
        cmds = []
        for i in range(5):
            cmds.append(_make_command(
                execution=execution,
                created_at=now - timezone.timedelta(minutes=5 - i),
            ))

        # Story 78.5: Mock dispatch since commands lack valid handler payloads
        with patch.object(WorkflowCommandService, '_dispatch_command', classmethod(lambda cls, c: None)):
            count = WorkflowCommandService.process_pending_commands(batch_size=2)
        assert count == 2
        # Les 2 plus anciennes traitées (FIFO)
        for cmd in cmds[:2]:
            cmd.refresh_from_db()
            assert cmd.status == WorkflowCommandStatus.PROCESSED
        # Les 3 restantes toujours pending
        for cmd in cmds[2:]:
            cmd.refresh_from_db()
            assert cmd.status == WorkflowCommandStatus.PENDING

    def test_no_pending_returns_zero(self):
        """Pas de commandes pending → retourne 0."""
        count = WorkflowCommandService.process_pending_commands()
        assert count == 0
