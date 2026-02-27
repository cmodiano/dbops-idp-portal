"""
executions/tasks/cleanup.py — Purge old platform logs from ExecutionStep output.

Logs are forwarded to Splunk at terminal state; after a retention period they can
be safely removed from the database to save Oracle CLOB storage.
"""
from __future__ import annotations

import os
from datetime import timedelta

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

logger = structlog.get_logger(__name__)

LOG_RETENTION_DAYS = int(os.getenv("PLATFORM_LOG_RETENTION_DAYS", "7"))
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
    # that have NOT already been purged (output does not contain 'logs_purged').
    qs = (
        ExecutionStep.objects
        .filter(
            execution__status__in=terminal_statuses,
            execution__completed_at__lt=cutoff,
        )
        .exclude(output__isnull=True)
        .exclude(output__contains='"logs_purged"')
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

    logger.info(
        "purge_old_platform_logs_complete",
        purged=total_purged,
        errors=total_errors,
        retention_days=LOG_RETENTION_DAYS,
    )

    return {"purged": total_purged, "errors": total_errors}
