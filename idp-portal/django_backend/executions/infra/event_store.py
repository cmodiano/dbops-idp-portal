"""
Façade for durable workflow event persistence.

Wraps `WorkflowEventService` behind a simplified API so callers do not need
to know about entity_type routing, sequence allocation, or best-effort vs
critical semantics — that stays encapsulated in the underlying service.

Usage:
    from executions.infra.event_store import EventStore

    EventStore.append_event(execution_id, event_type, payload)
    events = EventStore.get_events(execution_id, since_sequence=5)
"""

from __future__ import annotations

import structlog
from typing import Any

from django.db.models import QuerySet

from executions.models import WorkflowEvent
from executions.services.workflow_events import WorkflowEventService

logger = structlog.get_logger(__name__)


class EventStore:
    """Simplified façade over WorkflowEventService."""

    @staticmethod
    def append_event(
        execution_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> WorkflowEvent | None:
        """Persist a workflow event with atomic sequence allocation.

        If *entity_type* / *entity_id* are not supplied, they default to
        execution-level (entity_type=EXECUTION, entity_id=execution_id).
        Pass *step_id* as a shortcut for step-level events.
        """
        from executions.models import WorkflowEventEntityType

        if entity_type is None:
            if step_id is not None:
                entity_type = WorkflowEventEntityType.EXECUTION_STEP
                entity_id = step_id
            else:
                entity_type = WorkflowEventEntityType.EXECUTION
                entity_id = execution_id

        if entity_id is None:
            if entity_type == WorkflowEventEntityType.EXECUTION:
                entity_id = execution_id
            else:
                raise ValueError(
                    f"entity_id is required when entity_type={entity_type!r}"
                )

        event = WorkflowEventService.emit(
            execution_id=execution_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )

        if event is not None:
            logger.info(
                "event_store.append",
                execution_id=execution_id,
                event_type=event_type,
                sequence=event.sequence_num,
            )

        return event

    @staticmethod
    def get_events(
        execution_id: int,
        since_sequence: int = 0,
    ) -> QuerySet:
        """Return events for *execution_id* ordered by sequence, optionally
        filtered to those after *since_sequence*."""
        return (
            WorkflowEvent.objects
            .filter(execution_id=execution_id, sequence_num__gt=since_sequence)
            .order_by("sequence_num")
        )
