"""Service for WORKFLOW_EVENTS — durable event sourcing for real-time UI sync.

V113: Each status change in an execution or step produces a persistent event row.
The WebSocket consumer uses sequence_num for catch-up on reconnect, solving
the fire-and-forget problem where approval notifications are lost on page reload.

Usage:
    from executions.services.workflow_events import WorkflowEventService
    WorkflowEventService.emit_step_status_changed(execution, step, old_status)
"""
from __future__ import annotations

import structlog
from typing import Any

from django.db import models

from executions.models import (
    WorkflowEvent,
    WorkflowEventType,
    WorkflowEventEntityType,
)

if __name__ != "__main__":
    from executions.models import Execution, ExecutionStep

logger = structlog.get_logger(__name__)


class WorkflowEventService:
    """Emit and query durable workflow events for UI sync."""

    @staticmethod
    def _next_sequence_num(execution_id: int) -> int:
        """Get next monotonically increasing sequence number for an execution."""
        max_seq = (
            WorkflowEvent.objects
            .filter(execution_id=execution_id)
            .aggregate(max_seq=models.Max('sequence_num'))
            ['max_seq']
        )
        return (max_seq or 0) + 1

    @classmethod
    def emit(
        cls,
        execution_id: int,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent | None:
        """Create a workflow event. Best-effort: never raises."""
        try:
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
        except Exception:  # noqa: BLE001
            logger.warning(
                "workflow_event_emit_failed",
                execution_id=execution_id,
                event_type=event_type,
                entity_id=entity_id,
                exc_info=True,
            )
            return None

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
        """Emit when execution status transitions."""
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
        """Emit when a step status transitions."""
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
        """Emit when step output is updated (e.g. gate context refresh, logs)."""
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
    def emit_approval_requested(
        cls,
        execution_id: int,
        step: "ExecutionStep",
    ) -> WorkflowEvent | None:
        """Emit when a gate step requires approval."""
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
        """Emit when a gate step approval is granted."""
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
        """Emit when a gate step approval is rejected."""
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
        """Return the latest sequence number for an execution (0 if none)."""
        max_seq = (
            WorkflowEvent.objects
            .filter(execution_id=execution_id)
            .aggregate(max_seq=models.Max('sequence_num'))
            ['max_seq']
        )
        return max_seq or 0
