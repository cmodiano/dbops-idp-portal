"""Outbox dispatcher — Celery task for reliable side-effect delivery.

Story 78.7: Periodically claims PENDING outbox entries via SELECT FOR UPDATE
SKIP LOCKED, dispatches each side-effect, and marks DISPATCHED or FAILED.

Usage (Celery Beat):
    process_outbox_entries.delay()
"""
from __future__ import annotations

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from executions.models import ExecutionOutbox, OutboxEntryStatus
from executions.observability import get_outbox_pending
from executions.services.outbox import (
    APPROVAL_GRANTED,
    APPROVAL_REJECTED,
    STEP_BROADCAST,
    EXECUTION_NOTIFICATION,
    APPROVAL_NOTIFICATION,
)

logger = structlog.get_logger(__name__)


@shared_task(name="executions.tasks.process_outbox_entries")
def process_outbox_entries(batch_size: int = 50) -> dict:
    """Claim and dispatch PENDING outbox entries.

    Pattern identical to WorkflowCommandService.process_pending_commands():
    SELECT FOR UPDATE SKIP LOCKED, FIFO by created_at, per-entry savepoint.

    Returns:
        Dict with dispatched/failed counts.
    """
    # Story 78.16: Emit outbox pending metric before dispatching
    outbox_pending_before = get_outbox_pending()
    logger.info(
        "process_outbox_entries_metrics",
        outbox_pending=outbox_pending_before,
    )

    dispatched = 0
    failed = 0

    with transaction.atomic():
        # Oracle does not support LIMIT/OFFSET with SELECT FOR UPDATE.
        # Step 1: fetch candidate IDs with LIMIT (no lock).
        candidate_ids = list(
            ExecutionOutbox.objects
            .filter(
                status=OutboxEntryStatus.PENDING,
                attempt_no__lt=F("max_attempts"),
            )
            .order_by("created_at")
            .values_list('id', flat=True)[:batch_size]
        )
        # Step 2: lock specific rows by PK (no LIMIT needed).
        entries = list(
            ExecutionOutbox.objects
            .filter(id__in=candidate_ids)
            .select_for_update(skip_locked=True)
        ) if candidate_ids else []

        for entry in entries:
            try:
                with transaction.atomic():
                    _dispatch_entry(entry)
                    entry.status = OutboxEntryStatus.DISPATCHED
                    entry.dispatched_at = timezone.now()
                    entry.save(update_fields=["status", "dispatched_at"])
                    dispatched += 1
            except Exception as e:
                entry.attempt_no += 1
                entry.last_error = str(e)[:4000]
                if entry.attempt_no >= entry.max_attempts:
                    entry.status = OutboxEntryStatus.FAILED
                entry.save(update_fields=["attempt_no", "last_error", "status"])
                failed += 1
                logger.error(
                    "outbox_dispatch_failed",
                    entry_id=entry.id,
                    event_type=entry.event_type,
                    attempt_no=entry.attempt_no,
                    error=str(e),
                )

    logger.info(
        "outbox_dispatch_complete",
        dispatched=dispatched,
        failed=failed,
        outbox_pending_before=outbox_pending_before,
    )
    return {"dispatched": dispatched, "failed": failed}


def _dispatch_entry(entry: ExecutionOutbox) -> None:
    """Route dispatch based on event_type."""
    payload = entry.payload or {}

    if entry.event_type == APPROVAL_GRANTED:
        _dispatch_approval_granted(entry, payload)
    elif entry.event_type == APPROVAL_REJECTED:
        _dispatch_approval_rejected(entry, payload)
    elif entry.event_type == STEP_BROADCAST:
        _dispatch_step_broadcast(entry, payload)
    elif entry.event_type in (EXECUTION_NOTIFICATION, APPROVAL_NOTIFICATION):
        _dispatch_notification(entry, payload)
    else:
        raise ValueError(f"Unknown outbox event_type: {entry.event_type}")


def _dispatch_approval_granted(entry: ExecutionOutbox, payload: dict) -> None:
    from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
    from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
    from executions.models import ExecutionStep  # noqa: PLC0415

    step_id = payload["execution_step_id"]
    step = ExecutionStep.objects.get(id=step_id)
    approved_by = payload.get("approved_by", "system")

    WorkflowEventService.emit_approval_granted(entry.execution_id, step, approved_by=approved_by)
    RunnableStepService.delete(step_id)


def _dispatch_approval_rejected(entry: ExecutionOutbox, payload: dict) -> None:
    from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
    from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
    from executions.models import ExecutionStep  # noqa: PLC0415

    step_id = payload["execution_step_id"]
    step = ExecutionStep.objects.get(id=step_id)
    rejected_by = payload.get("rejected_by", "system")

    WorkflowEventService.emit_approval_rejected(entry.execution_id, step, rejected_by=rejected_by)
    RunnableStepService.delete(step_id)


def _dispatch_step_broadcast(entry: ExecutionOutbox, payload: dict) -> None:
    from executions.utils.websocket_broadcast import broadcast_step_update  # noqa: PLC0415
    from executions.models import ExecutionStep  # noqa: PLC0415

    step_id = payload["execution_step_id"]
    step = ExecutionStep.objects.get(id=step_id)
    broadcast_step_update(entry.execution_id, step)


def _dispatch_notification(entry: ExecutionOutbox, payload: dict) -> None:
    """Dispatch notification for both EXECUTION_NOTIFICATION and APPROVAL_NOTIFICATION."""
    from services.notification_service import NotificationService  # noqa: PLC0415
    from executions.models import Execution  # noqa: PLC0415

    execution = Execution.objects.select_related("action").get(id=entry.execution_id)
    event = payload.get("event", "on_approval_required" if entry.event_type == APPROVAL_NOTIFICATION else "on_success")
    page_me = payload.get("page_me", False)
    NotificationService().notify_execution_event(execution, execution.action, event, page_me=page_me)
