"""
Tests Story 78.7 — Table EXECUTION_OUTBOX pour effets externes fiables

AC1 : Table EXECUTION_OUTBOX créée avec les bonnes colonnes, contraintes et index
AC2 : OutboxService.write_entry() écriture transactionnelle et idempotente
AC3 : process_outbox_entries dispatche PENDING→DISPATCHED, FIFO, retry, max_attempts
AC4 : Idempotence end-to-end (double écriture → un seul dispatch)
"""
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from executions.models import (
    ExecutionOutbox,
    OutboxEntryStatus,
    WorkflowCommand,
    ExecutionStepStatus,
)
from executions.services.outbox import (
    OutboxService,
    APPROVAL_GRANTED,
    APPROVAL_REJECTED,
    STEP_BROADCAST,
    EXECUTION_NOTIFICATION,
    APPROVAL_NOTIFICATION,
)
from executions.tasks.outbox_dispatcher import process_outbox_entries, _dispatch_entry
from tests.factories import ExecutionFactory, ExecutionStepFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_outbox_entry(execution=None, **kwargs):
    """Helper pour créer un ExecutionOutbox en base.

    Note: created_at a auto_now_add=True — Django ignore le kwarg au create().
    Ce helper applique created_at via .update() après création si fourni.
    """
    if execution is None:
        execution = ExecutionFactory()
    created_at = kwargs.pop("created_at", None)
    defaults = {
        "execution": execution,
        "event_type": kwargs.pop("event_type", APPROVAL_GRANTED),
        "payload": kwargs.pop("payload", {"execution_step_id": 1}),
        "status": kwargs.pop("status", OutboxEntryStatus.PENDING),
        "idempotency_key": kwargs.pop("idempotency_key", f"test:{execution.id}:key"),
    }
    defaults.update(kwargs)
    entry = ExecutionOutbox.objects.create(**defaults)
    if created_at is not None:
        ExecutionOutbox.objects.filter(pk=entry.pk).update(created_at=created_at)
        entry.refresh_from_db()
    return entry


# ===========================================================================
# AC1 — Modèle et contraintes
# ===========================================================================

@pytest.mark.django_db
class TestAC1ModelSchema:
    """AC1 : Le modèle ExecutionOutbox a les bonnes colonnes et défauts."""

    def test_table_name(self):
        assert ExecutionOutbox._meta.db_table == "EXECUTION_OUTBOX"

    def test_ordering(self):
        assert ExecutionOutbox._meta.ordering == ["created_at"]

    def test_create_entry_all_fields(self):
        execution = ExecutionFactory()
        entry = ExecutionOutbox.objects.create(
            execution=execution,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 42},
            idempotency_key="test:42:approval_granted:step_42",
        )
        entry.refresh_from_db()
        assert entry.id is not None
        assert entry.execution_id == execution.id
        assert entry.event_type == APPROVAL_GRANTED
        assert entry.payload == {"step_id": 42}
        assert entry.status == OutboxEntryStatus.PENDING
        assert entry.idempotency_key == "test:42:approval_granted:step_42"
        assert entry.created_at is not None
        assert entry.dispatched_at is None
        assert entry.attempt_no == 0
        assert entry.max_attempts == 3
        assert entry.last_error is None

    def test_status_default_pending(self):
        execution = ExecutionFactory()
        entry = ExecutionOutbox.objects.create(
            execution=execution,
            event_type=APPROVAL_GRANTED,
            payload={},
            idempotency_key="test:default-status",
        )
        entry.refresh_from_db()
        assert entry.status == OutboxEntryStatus.PENDING

    def test_unique_idempotency_key(self):
        execution = ExecutionFactory()
        ExecutionOutbox.objects.create(
            execution=execution,
            event_type=APPROVAL_GRANTED,
            payload={},
            idempotency_key="test:unique:key",
        )
        with pytest.raises(IntegrityError):
            ExecutionOutbox.objects.create(
                execution=execution,
                event_type=APPROVAL_REJECTED,
                payload={},
                idempotency_key="test:unique:key",
            )

    def test_str_representation(self):
        execution = ExecutionFactory()
        entry = ExecutionOutbox.objects.create(
            execution=execution,
            event_type=STEP_BROADCAST,
            payload={},
            idempotency_key="test:str:repr",
        )
        assert STEP_BROADCAST in str(entry)
        assert OutboxEntryStatus.PENDING in str(entry)

    def test_index_exists(self):
        index_names = [idx.name for idx in ExecutionOutbox._meta.indexes]
        assert "idx_outbox_status_created" in index_names


# ===========================================================================
# AC2 — Écriture transactionnelle et idempotente
# ===========================================================================

@pytest.mark.django_db
class TestAC2WriteEntry:
    """AC2 : OutboxService.write_entry() écrit dans l'outbox de manière idempotente."""

    def test_write_entry_creates_entry(self):
        execution = ExecutionFactory()
        entry, created = OutboxService.write_entry(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 10},
            idempotency_key="test:write:create",
        )
        assert created is True
        assert entry.execution_id == execution.id
        assert entry.event_type == APPROVAL_GRANTED
        assert entry.payload == {"step_id": 10}
        assert entry.status == OutboxEntryStatus.PENDING

    def test_write_entry_idempotent_duplicate(self):
        execution = ExecutionFactory()
        key = "test:write:idempotent"

        entry1, created1 = OutboxService.write_entry(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 10},
            idempotency_key=key,
        )
        entry2, created2 = OutboxService.write_entry(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 10},
            idempotency_key=key,
        )

        assert created1 is True
        assert created2 is False
        assert entry1.id == entry2.id
        assert ExecutionOutbox.objects.filter(idempotency_key=key).count() == 1

    def test_build_idempotency_key(self):
        key = OutboxService.build_idempotency_key(42, APPROVAL_GRANTED, "step_15")
        assert key == "42:approval_granted:step_15"

    def test_handle_approve_writes_outbox(self):
        """_handle_approve écrit dans l'outbox dans la même transaction (AC2)."""
        from executions.services.workflow_commands import WorkflowCommandService

        execution = ExecutionFactory(status="RUNNING")
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_type="approval",
        )

        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="approve",
            payload={"step_id": step.id},
            created_by="test-user",
        )

        with patch("executions.app.command_processor.find_step_config", return_value=None):
            with transaction.atomic():
                WorkflowCommandService._handle_approve(cmd)

        # Verify outbox entry was created
        entries = ExecutionOutbox.objects.filter(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
        )
        assert entries.count() == 1
        entry = entries.first()
        assert entry.payload["execution_step_id"] == step.id
        assert entry.payload["approved_by"] == "test-user"
        expected_key = f"{execution.id}:{APPROVAL_GRANTED}:step_{step.id}"
        assert entry.idempotency_key == expected_key

    def test_handle_reject_writes_outbox(self):
        """_handle_reject écrit dans l'outbox dans la même transaction (AC2)."""
        from executions.services.workflow_commands import WorkflowCommandService

        execution = ExecutionFactory(status="RUNNING")
        step = ExecutionStepFactory(
            execution=execution,
            status=ExecutionStepStatus.WAITING,
            step_type="approval",
        )

        cmd = WorkflowCommand.objects.create(
            execution=execution,
            command_type="reject",
            payload={"step_id": step.id, "comment": "Not approved"},
            created_by="test-user",
        )

        with patch("executions.app.command_processor.find_step_config", return_value=None):
            with transaction.atomic():
                WorkflowCommandService._handle_reject(cmd)

        entries = ExecutionOutbox.objects.filter(
            execution_id=execution.id,
            event_type=APPROVAL_REJECTED,
        )
        assert entries.count() == 1
        entry = entries.first()
        assert entry.payload["execution_step_id"] == step.id
        assert entry.payload["rejected_by"] == "test-user"
        assert entry.payload["reason"] == "Not approved"
        expected_key = f"{execution.id}:{APPROVAL_REJECTED}:step_{step.id}"
        assert entry.idempotency_key == expected_key


# ===========================================================================
# AC3 — Dispatcher
# ===========================================================================

@pytest.mark.django_db
class TestAC3Dispatcher:
    """AC3 : process_outbox_entries dispatche PENDING→DISPATCHED avec retry."""

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_dispatch_pending_to_dispatched(self, mock_dispatch):
        execution = ExecutionFactory()
        entry = _make_outbox_entry(execution=execution, idempotency_key="test:dispatch:1")

        result = process_outbox_entries(batch_size=10)

        assert result["dispatched"] == 1
        assert result["failed"] == 0
        entry.refresh_from_db()
        assert entry.status == OutboxEntryStatus.DISPATCHED
        assert entry.dispatched_at is not None
        mock_dispatch.assert_called_once()

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_dispatch_fifo_order(self, mock_dispatch):
        """Entries are processed in FIFO order by created_at."""
        execution = ExecutionFactory()
        now = timezone.now()

        entry_old = _make_outbox_entry(
            execution=execution,
            idempotency_key="test:fifo:old",
            created_at=now - timezone.timedelta(seconds=10),
        )
        entry_new = _make_outbox_entry(
            execution=execution,
            idempotency_key="test:fifo:new",
            created_at=now,
        )

        process_outbox_entries(batch_size=10)

        # Both should be dispatched
        entry_old.refresh_from_db()
        entry_new.refresh_from_db()
        assert entry_old.status == OutboxEntryStatus.DISPATCHED
        assert entry_new.status == OutboxEntryStatus.DISPATCHED

        # Verify call order: old before new
        call_args = [call.args[0].id for call in mock_dispatch.call_args_list]
        assert call_args == [entry_old.id, entry_new.id]

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry", side_effect=RuntimeError("dispatch error"))
    def test_dispatch_failure_increments_attempt(self, mock_dispatch):
        execution = ExecutionFactory()
        entry = _make_outbox_entry(execution=execution, idempotency_key="test:fail:1")

        result = process_outbox_entries(batch_size=10)

        assert result["failed"] == 1
        entry.refresh_from_db()
        assert entry.attempt_no == 1
        assert entry.last_error == "dispatch error"
        # Not yet at max_attempts (3), so still PENDING
        assert entry.status == OutboxEntryStatus.PENDING

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry", side_effect=RuntimeError("fatal"))
    def test_dispatch_max_attempts_marks_failed(self, mock_dispatch):
        execution = ExecutionFactory()
        entry = _make_outbox_entry(
            execution=execution,
            idempotency_key="test:maxfail:1",
            attempt_no=2,  # Already at 2, max is 3
        )

        process_outbox_entries(batch_size=10)

        entry.refresh_from_db()
        assert entry.attempt_no == 3
        assert entry.status == OutboxEntryStatus.FAILED
        assert entry.last_error == "fatal"

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_dispatched_entries_are_skipped(self, mock_dispatch):
        """Entries already DISPATCHED are not re-dispatched."""
        execution = ExecutionFactory()
        _make_outbox_entry(
            execution=execution,
            idempotency_key="test:skip:dispatched",
            status=OutboxEntryStatus.DISPATCHED,
        )

        result = process_outbox_entries(batch_size=10)

        assert result["dispatched"] == 0
        mock_dispatch.assert_not_called()

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_failed_entries_are_skipped(self, mock_dispatch):
        """Entries already FAILED are not retried."""
        execution = ExecutionFactory()
        _make_outbox_entry(
            execution=execution,
            idempotency_key="test:skip:failed",
            status=OutboxEntryStatus.FAILED,
        )

        result = process_outbox_entries(batch_size=10)

        assert result["dispatched"] == 0
        mock_dispatch.assert_not_called()

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_batch_size_limit(self, mock_dispatch):
        """Only batch_size entries are processed per call."""
        execution = ExecutionFactory()
        for i in range(5):
            _make_outbox_entry(
                execution=execution,
                idempotency_key=f"test:batch:{i}",
            )

        result = process_outbox_entries(batch_size=3)

        assert result["dispatched"] == 3
        assert mock_dispatch.call_count == 3
        # 2 remaining still PENDING
        remaining = ExecutionOutbox.objects.filter(status=OutboxEntryStatus.PENDING).count()
        assert remaining == 2

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_entries_at_max_attempts_are_not_claimed(self, mock_dispatch):
        """Entries where attempt_no >= max_attempts are not claimed."""
        execution = ExecutionFactory()
        _make_outbox_entry(
            execution=execution,
            idempotency_key="test:maxed:1",
            attempt_no=3,
            max_attempts=3,
        )

        result = process_outbox_entries(batch_size=10)

        assert result["dispatched"] == 0
        mock_dispatch.assert_not_called()


# ===========================================================================
# AC3 — Dispatch routing (integration-level with mocks)
# ===========================================================================

@pytest.mark.django_db
class TestAC3DispatchRouting:
    """Verify _dispatch_entry routes to correct service based on event_type."""

    @patch("executions.services.runnable_steps.RunnableStepService.delete")
    @patch("executions.services.workflow_events.WorkflowEventService.emit_approval_granted")
    def test_dispatch_approval_granted(self, mock_emit, mock_delete):
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)

        entry = _make_outbox_entry(
            execution=execution,
            event_type=APPROVAL_GRANTED,
            payload={"execution_step_id": step.id, "approved_by": "user1", "execution_id": execution.id},
            idempotency_key="test:route:approve",
        )

        _dispatch_entry(entry)

        mock_emit.assert_called_once()
        mock_delete.assert_called_once_with(step.id)

    @patch("executions.services.runnable_steps.RunnableStepService.delete")
    @patch("executions.services.workflow_events.WorkflowEventService.emit_approval_rejected")
    def test_dispatch_approval_rejected(self, mock_emit, mock_delete):
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)

        entry = _make_outbox_entry(
            execution=execution,
            event_type=APPROVAL_REJECTED,
            payload={"execution_step_id": step.id, "rejected_by": "user1", "execution_id": execution.id},
            idempotency_key="test:route:reject",
        )

        _dispatch_entry(entry)

        mock_emit.assert_called_once()
        mock_delete.assert_called_once_with(step.id)

    @patch("executions.utils.websocket_broadcast.broadcast_step_update")
    def test_dispatch_step_broadcast(self, mock_broadcast):
        execution = ExecutionFactory()
        step = ExecutionStepFactory(execution=execution)

        entry = _make_outbox_entry(
            execution=execution,
            event_type=STEP_BROADCAST,
            payload={"execution_step_id": step.id},
            idempotency_key="test:route:broadcast",
        )

        _dispatch_entry(entry)

        mock_broadcast.assert_called_once_with(execution.id, step)

    @patch("services.notification_service.NotificationService.notify_execution_event")
    def test_dispatch_execution_notification(self, mock_notify):
        execution = ExecutionFactory()

        entry = _make_outbox_entry(
            execution=execution,
            event_type=EXECUTION_NOTIFICATION,
            payload={"event": "on_success", "page_me": True},
            idempotency_key="test:route:exec_notif",
        )

        _dispatch_entry(entry)

        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args
        assert call_kwargs[1]["page_me"] is True

    @patch("services.notification_service.NotificationService.notify_execution_event")
    def test_dispatch_approval_notification(self, mock_notify):
        execution = ExecutionFactory()

        entry = _make_outbox_entry(
            execution=execution,
            event_type=APPROVAL_NOTIFICATION,
            payload={"event": "on_approval_required"},
            idempotency_key="test:route:approval_notif",
        )

        _dispatch_entry(entry)

        mock_notify.assert_called_once()

    def test_dispatch_unknown_event_type_raises(self):
        execution = ExecutionFactory()
        entry = _make_outbox_entry(
            execution=execution,
            event_type="unknown_type",
            idempotency_key="test:route:unknown",
        )

        with pytest.raises(ValueError, match="Unknown outbox event_type"):
            _dispatch_entry(entry)


# ===========================================================================
# AC4 — Idempotence end-to-end
# ===========================================================================

@pytest.mark.django_db
class TestAC4IdempotenceE2E:
    """AC4 : Double écriture même clé → une seule entrée → un seul dispatch."""

    @patch("executions.tasks.outbox_dispatcher._dispatch_entry")
    def test_double_write_single_dispatch(self, mock_dispatch):
        execution = ExecutionFactory()
        key = "test:e2e:idempotent"

        # Double write with same key
        entry1, created1 = OutboxService.write_entry(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 1},
            idempotency_key=key,
        )
        entry2, created2 = OutboxService.write_entry(
            execution_id=execution.id,
            event_type=APPROVAL_GRANTED,
            payload={"step_id": 1},
            idempotency_key=key,
        )

        assert created1 is True
        assert created2 is False

        # Only one entry in DB
        assert ExecutionOutbox.objects.filter(idempotency_key=key).count() == 1

        # Dispatch processes only 1 entry
        result = process_outbox_entries(batch_size=10)
        assert result["dispatched"] == 1
        assert mock_dispatch.call_count == 1


# ===========================================================================
# Outbox entry status TextChoices
# ===========================================================================

@pytest.mark.django_db
class TestOutboxEntryStatus:
    """Verify OutboxEntryStatus enum values."""

    def test_status_values(self):
        assert OutboxEntryStatus.PENDING == "pending"
        assert OutboxEntryStatus.DISPATCHED == "dispatched"
        assert OutboxEntryStatus.FAILED == "failed"

    def test_event_type_constants(self):
        assert APPROVAL_GRANTED == "approval_granted"
        assert APPROVAL_REJECTED == "approval_rejected"
        assert STEP_BROADCAST == "step_broadcast"
        assert EXECUTION_NOTIFICATION == "execution_notification"
        assert APPROVAL_NOTIFICATION == "approval_notification"
