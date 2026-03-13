"""Service for WORKFLOW_EVENTS — durable event sourcing for real-time UI sync.

V113: Each status change in an execution or step produces a persistent event row.
The WebSocket consumer uses sequence_num for catch-up on reconnect, solving
the fire-and-forget problem where approval notifications are lost on page reload.

V122: Sequence numbers are now allocated atomically via WORKFLOW_EVENT_COUNTER
(row-level lock via SELECT FOR UPDATE), eliminating race conditions under
concurrent emitters (parallel workflow steps completing simultaneously).

Usage:
    from executions.services.workflow_events import WorkflowEventService
    WorkflowEventService.emit_step_status_changed(execution, step, old_status)
"""
from __future__ import annotations

import structlog
from typing import Any

from django.db import IntegrityError, transaction

from executions.models import (
    WorkflowEvent,
    WorkflowEventCounter,
    WorkflowEventType,
    WorkflowEventEntityType,
)

if __name__ != "__main__":
    from executions.models import Execution, ExecutionStep

logger = structlog.get_logger(__name__)

# Event types that are best-effort (telemetry).
# Failures are logged but swallowed — workflow must not fail due to these.
BEST_EFFORT_EVENT_TYPES = frozenset({
    WorkflowEventType.STEP_OUTPUT_UPDATED,
    WorkflowEventType.TARGET_ADDED,
})

# Event types that are critical to workflow correctness.
# Failures MUST propagate — the caller or transaction must handle them.
# NOTE: The emit() logic uses `event_type not in BEST_EFFORT_EVENT_TYPES` (implicit-critical
# default), so any unknown event type is treated as critical by default (fail-safe).
# This constant is used for documentation, tests, and explicit membership checks.
CRITICAL_EVENT_TYPES = frozenset({
    WorkflowEventType.EXECUTION_STATUS_CHANGED,
    WorkflowEventType.EXECUTION_COMPLETED,
    WorkflowEventType.EXECUTION_FAILED,
    WorkflowEventType.STEP_STATUS_CHANGED,
    WorkflowEventType.STEP_STARTED,
    WorkflowEventType.STEP_COMPLETED,
    WorkflowEventType.STEP_FAILED,
    WorkflowEventType.APPROVAL_REQUESTED,
    WorkflowEventType.APPROVAL_GRANTED,
    WorkflowEventType.APPROVAL_REJECTED,
})


class WorkflowEventService:
    """Emit and query durable workflow events for UI sync."""

    @staticmethod
    def _next_sequence_num(execution_id: int) -> int:
        """Allocate the next monotonically increasing sequence number atomically.

        Uses a row-level lock (SELECT FOR UPDATE) on WORKFLOW_EVENT_COUNTER to
        guarantee uniqueness under concurrent emitters. Must be called within
        an active transaction (transaction.atomic()).

        Implementation note: select_for_update() cannot lock a non-existent row.
        On first emit for an execution, two concurrent threads could both see no
        row and race to INSERT. We handle this explicitly: catch IntegrityError
        and re-fetch with the lock so only one thread increments at a time.
        """
        try:
            counter = (
                WorkflowEventCounter.objects
                .select_for_update()
                .get(execution_id=execution_id)
            )
        except WorkflowEventCounter.DoesNotExist:
            try:
                counter = WorkflowEventCounter.objects.create(
                    execution_id=execution_id,
                    last_sequence_num=0,
                )
            except IntegrityError:
                # Another concurrent emitter created the row between our GET and CREATE.
                # Re-fetch with the row-level lock to ensure atomic increment.
                counter = (
                    WorkflowEventCounter.objects
                    .select_for_update()
                    .get(execution_id=execution_id)
                )
        counter.last_sequence_num += 1
        counter.save(update_fields=['last_sequence_num'])
        return counter.last_sequence_num

    @classmethod
    def emit(
        cls,
        execution_id: int,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent | None:
        """Create a workflow event.

        Critical events (fail/retry) raise on failure.
        Best-effort events (telemetry) log a warning and return None on failure.
        """
        is_critical = event_type not in BEST_EFFORT_EVENT_TYPES

        if is_critical:
            return cls._emit_inner(execution_id, event_type, entity_type, entity_id, payload)

        # Best-effort: swallow any exception
        try:
            return cls._emit_inner(execution_id, event_type, entity_type, entity_id, payload)
        except Exception:  # noqa: BLE001
            logger.warning(
                "workflow_event_emit_failed",
                execution_id=execution_id,
                event_type=event_type,
                entity_id=entity_id,
                exc_info=True,
            )
            return None

    @classmethod
    def _emit_inner(
        cls,
        execution_id: int,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Core emit logic — always runs inside a transaction for atomic sequence allocation."""
        with transaction.atomic():
            seq = cls._next_sequence_num(execution_id)
            event = WorkflowEvent(
                execution_id=execution_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                sequence_num=seq,
            )
            if payload:
                event.set_payload(payload)
            event.save()
        return event

    # ---------------------------------------------------------------
    # Convenience emitters for common transitions
    # ---------------------------------------------------------------

    @classmethod
    def emit_execution_status_changed(
        cls,
        execution: "Execution",
        old_status: str,
        new_status: str,
    ) -> WorkflowEvent | None:
        """Emit when execution status transitions. Critical."""
        event_type = WorkflowEventType.EXECUTION_STATUS_CHANGED
        if new_status == "COMPLETED":
            event_type = WorkflowEventType.EXECUTION_COMPLETED
        elif new_status == "FAILED":
            event_type = WorkflowEventType.EXECUTION_FAILED

        return cls.emit(
            execution_id=execution.id,
            event_type=event_type,
            entity_type=WorkflowEventEntityType.EXECUTION,
            entity_id=execution.id,
            payload={
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    @classmethod
    def emit_step_status_changed(
        cls,
        execution_id: int,
        step: "ExecutionStep",
        old_status: str,
    ) -> WorkflowEvent | None:
        """Emit when a step status transitions. Critical."""
        new_status = step.status
        event_type = WorkflowEventType.STEP_STATUS_CHANGED
        if new_status == "RUNNING":
            event_type = WorkflowEventType.STEP_STARTED
        elif new_status == "COMPLETED":
            event_type = WorkflowEventType.STEP_COMPLETED
        elif new_status == "FAILED":
            event_type = WorkflowEventType.STEP_FAILED

        return cls.emit(
            execution_id=execution_id,
            event_type=event_type,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
            payload={
                "step_order": step.step_order,
                "step_name": step.step_name,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    @classmethod
    def emit_step_output_updated(
        cls,
        execution_id: int,
        step: "ExecutionStep",
    ) -> WorkflowEvent | None:
        """Emit when step output is updated (e.g. gate context refresh, logs). Best-effort."""
        return cls.emit(
            execution_id=execution_id,
            event_type=WorkflowEventType.STEP_OUTPUT_UPDATED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
            payload={
                "step_order": step.step_order,
                "step_name": step.step_name,
                "status": step.status,
            },
        )

    @classmethod
    def emit_target_added(
        cls,
        execution_id: int,
        target_id: int,
        target_name: str | None = None,
    ) -> WorkflowEvent | None:
        """Emit when a target is added to an execution. Best-effort."""
        return cls.emit(
            execution_id=execution_id,
            event_type=WorkflowEventType.TARGET_ADDED,
            entity_type=WorkflowEventEntityType.EXECUTION_TARGET,
            entity_id=target_id,
            payload={"target_name": target_name} if target_name else None,
        )

    @classmethod
    def emit_approval_requested(
        cls,
        execution_id: int,
        step: "ExecutionStep",
    ) -> WorkflowEvent | None:
        """Emit when a gate step requires approval. Critical."""
        return cls.emit(
            execution_id=execution_id,
            event_type=WorkflowEventType.APPROVAL_REQUESTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
            payload={
                "step_order": step.step_order,
                "step_name": step.step_name,
                "status": step.status,
            },
        )

    @classmethod
    def emit_approval_granted(
        cls,
        execution_id: int,
        step: "ExecutionStep",
        approved_by: str | None = None,
    ) -> WorkflowEvent | None:
        """Emit when a gate step approval is granted. Critical."""
        return cls.emit(
            execution_id=execution_id,
            event_type=WorkflowEventType.APPROVAL_GRANTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
            payload={
                "step_order": step.step_order,
                "step_name": step.step_name,
                "approved_by": approved_by,
            },
        )

    @classmethod
    def emit_approval_rejected(
        cls,
        execution_id: int,
        step: "ExecutionStep",
        rejected_by: str | None = None,
    ) -> WorkflowEvent | None:
        """Emit when a gate step approval is rejected. Critical."""
        return cls.emit(
            execution_id=execution_id,
            event_type=WorkflowEventType.APPROVAL_REJECTED,
            entity_type=WorkflowEventEntityType.EXECUTION_STEP,
            entity_id=step.id,
            payload={
                "step_order": step.step_order,
                "step_name": step.step_name,
                "rejected_by": rejected_by,
            },
        )

    # ---------------------------------------------------------------
    # Query helpers for catch-up
    # ---------------------------------------------------------------

    @staticmethod
    def get_events_since(
        execution_id: int,
        since_sequence: int,
        limit: int = 100,
    ) -> list[dict]:
        """Return events after a given sequence number (for client catch-up)."""
        events = (
            WorkflowEvent.objects
            .filter(execution_id=execution_id, sequence_num__gt=since_sequence)
            .order_by('sequence_num')[:limit]
        )
        result = []
        for ev in events:
            result.append({
                "sequence_num": ev.sequence_num,
                "event_type": ev.event_type,
                "entity_type": ev.entity_type,
                "entity_id": ev.entity_id,
                "payload": ev.get_payload(),
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            })
        return result

    @staticmethod
    def get_latest_sequence(execution_id: int) -> int:
        """Return the latest sequence number for an execution (0 if none).

        Reads from WORKFLOW_EVENT_COUNTER (source of truth for sequence allocation)
        rather than MAX(sequence_num) from WORKFLOW_EVENTS, to stay consistent with
        the atomic counter even in edge cases where an event insert failed.
        """
        try:
            counter = WorkflowEventCounter.objects.get(execution_id=execution_id)
            return counter.last_sequence_num
        except WorkflowEventCounter.DoesNotExist:
            return 0
