"""
executions/tasks/cleanup.py — Purge old platform logs and workflow events.

Logs are forwarded to Splunk at terminal state; after a retention period they can
be safely removed from the database to save Oracle CLOB storage.

Workflow events are ephemeral UI-sync records purged after a short retention
period (default 7 days) since they are only needed for WebSocket catch-up.
"""
from __future__ import annotations

import os
from datetime import timedelta

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

logger = structlog.get_logger(__name__)


def _parse_log_retention_days() -> int:
    """Parse PLATFORM_LOG_RETENTION_DAYS defensively; default 7 on invalid value."""
    raw = os.getenv("PLATFORM_LOG_RETENTION_DAYS", "7")
    try:
        val = int(raw)
        return val if val > 0 else 7
    except (ValueError, TypeError):
        return 7


LOG_RETENTION_DAYS = _parse_log_retention_days()
PURGE_BATCH_SIZE = 100


@shared_task(name="executions.tasks.purge_old_platform_logs")
def purge_old_platform_logs() -> dict:
    """Purge platform_logs from ExecutionStep output for old terminal executions.

    Runs daily via Celery Beat.  Only touches steps whose execution reached a
    terminal state more than ``LOG_RETENTION_DAYS`` days ago and whose output
    still contains ``platform_logs``.

    Returns:
        dict with ``purged`` count and ``errors`` count.
    """
    from executions.models import ExecutionStep, ExecutionStatus  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=LOG_RETENTION_DAYS)
    terminal_statuses = [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    ]

    # Filter steps belonging to old terminal executions, with non-null output,
    # that have NOT already been purged (output does not contain 'logs_purged'),
    # and that actually have platform_logs to purge (avoids retrying steps that
    # lack platform_logs indefinitely).
    # Note: output is a TextField (Oracle CLOB), not a JSONField, so we use
    # __contains with a raw string match instead of JSON path lookups.
    qs = (
        ExecutionStep.objects
        .filter(
            execution__status__in=terminal_statuses,
            execution__completed_at__lt=cutoff,
        )
        .exclude(output__isnull=True)
        .exclude(output__contains='"logs_purged"')
        .filter(output__contains='"platform_logs"')
        .only("id", "output")
    )

    total_purged = 0
    total_errors = 0

    # Process in batches to avoid long transactions
    while True:
        batch_ids = list(qs.values_list("id", flat=True)[:PURGE_BATCH_SIZE])
        if not batch_ids:
            break

        steps = ExecutionStep.objects.filter(id__in=batch_ids).only("id", "output")
        for step in steps:
            output = None
            try:
                output = step.get_output()
                if not output or "platform_logs" not in output:
                    continue

                del output["platform_logs"]
                output["logs_purged"] = True
                output["logs_purged_at"] = timezone.now().isoformat()
                step.set_output(output)
                step.save(update_fields=["output"])
                total_purged += 1
            except Exception:  # noqa: BLE001 — best-effort: never crash the task
                logger.exception(
                    "purge_platform_logs_step_error",
                    step_id=step.id,
                )
                total_errors += 1
                # Mark step with logs_purged so it won't be retried indefinitely
                if output is not None:
                    try:
                        output["logs_purged"] = True
                        step.set_output(output)
                        step.save(update_fields=["output"])
                    except Exception:  # noqa: BLE001 — best-effort
                        pass

    logger.info(
        "purge_old_platform_logs_complete",
        purged=total_purged,
        errors=total_errors,
        retention_days=LOG_RETENTION_DAYS,
    )

    return {"purged": total_purged, "errors": total_errors}


def _parse_workflow_event_retention_days() -> int:
    """Parse WORKFLOW_EVENT_RETENTION_DAYS defensively; default 7 on invalid value."""
    raw = os.getenv("WORKFLOW_EVENT_RETENTION_DAYS", "7")
    try:
        val = int(raw)
        return val if val > 0 else 7
    except (ValueError, TypeError):
        return 7


WORKFLOW_EVENT_RETENTION_DAYS = _parse_workflow_event_retention_days()
WORKFLOW_EVENT_PURGE_BATCH_SIZE = 1000


@shared_task(name="executions.tasks.purge_old_workflow_events")
def purge_old_workflow_events() -> dict:
    """Purge workflow events older than the retention period.

    Workflow events are ephemeral records used for WebSocket catch-up on
    page reload.  Once past retention they serve no purpose and waste
    Oracle storage.

    Deletes in batches to avoid long-running transactions and excessive
    undo/redo generation.

    Returns:
        dict with ``deleted`` count.
    """
    from executions.models import WorkflowEvent  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=WORKFLOW_EVENT_RETENTION_DAYS)
    total_deleted = 0

    while True:
        # Fetch IDs in a batch to delete — avoids unbounded DELETE with WHERE
        batch_ids = list(
            WorkflowEvent.objects
            .filter(created_at__lt=cutoff)
            .values_list("id", flat=True)[:WORKFLOW_EVENT_PURGE_BATCH_SIZE]
        )
        if not batch_ids:
            break

        deleted, _ = WorkflowEvent.objects.filter(id__in=batch_ids).delete()
        total_deleted += deleted

    logger.info(
        "purge_old_workflow_events_complete",
        deleted=total_deleted,
        retention_days=WORKFLOW_EVENT_RETENTION_DAYS,
    )

    return {"deleted": total_deleted}
