"""
Tests for executions.infra.event_store — Story 78.9 AC2.

Verifies the EventStore façade correctly delegates to WorkflowEventService
and provides monotonic sequencing and ordered retrieval.
"""

import pytest
from django.db import transaction

from executions.infra.event_store import EventStore
from executions.models import (
    WorkflowEvent,
    WorkflowEventEntityType,
    WorkflowEventType,
)
from tests.factories import ExecutionFactory


@pytest.mark.django_db(transaction=True)
class TestAppendEvent:
    """AC2: append_event creates an event with monotonic sequence."""

    def test_creates_event_with_sequence(self):
        execution = ExecutionFactory()
        event = EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
            payload={"old_status": "SUBMITTED", "new_status": "RUNNING"},
        )
        assert event is not None
        assert event.execution_id == execution.id
        assert event.event_type == WorkflowEventType.EXECUTION_STATUS_CHANGED
        assert event.sequence_num == 1

    def test_monotonic_sequence(self):
        execution = ExecutionFactory()
        e1 = EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
            payload={"old_status": "SUBMITTED", "new_status": "RUNNING"},
        )
        e2 = EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_COMPLETED,
            payload={"old_status": "RUNNING", "new_status": "COMPLETED"},
        )
        assert e1.sequence_num == 1
        assert e2.sequence_num == 2

    def test_step_event_with_step_id(self):
        execution = ExecutionFactory()
        event = EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.STEP_STARTED,
            payload={"step_name": "deploy"},
            step_id=42,
        )
        assert event.entity_type == WorkflowEventEntityType.EXECUTION_STEP
        assert event.entity_id == 42

    def test_defaults_to_execution_entity(self):
        execution = ExecutionFactory()
        event = EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
        )
        assert event.entity_type == WorkflowEventEntityType.EXECUTION
        assert event.entity_id == execution.id

    def test_rollback_cancels_event(self):
        execution = ExecutionFactory()
        try:
            with transaction.atomic():
                EventStore.append_event(
                    execution_id=execution.id,
                    event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
                    payload={"test": "rollback"},
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        assert not WorkflowEvent.objects.filter(execution_id=execution.id).exists()


@pytest.mark.django_db(transaction=True)
class TestGetEvents:
    """AC2: get_events returns events ordered by sequence."""

    def test_returns_ordered_by_sequence(self):
        execution = ExecutionFactory()
        EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
            payload={"seq": "first"},
        )
        EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_COMPLETED,
            payload={"seq": "second"},
        )

        events = list(EventStore.get_events(execution_id=execution.id))
        assert len(events) == 2
        assert events[0].sequence_num < events[1].sequence_num

    def test_since_sequence_filters(self):
        execution = ExecutionFactory()
        EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_STATUS_CHANGED,
        )
        EventStore.append_event(
            execution_id=execution.id,
            event_type=WorkflowEventType.EXECUTION_COMPLETED,
        )

        events = list(EventStore.get_events(execution_id=execution.id, since_sequence=1))
        assert len(events) == 1
        assert events[0].sequence_num == 2

    def test_empty_when_no_events(self):
        execution = ExecutionFactory()
        events = list(EventStore.get_events(execution_id=execution.id))
        assert events == []
