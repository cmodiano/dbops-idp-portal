"""Observability helpers for Epic 78 orchestration components.

Story 78.16: Expose key metrics as structured log fields.
These helpers are called by Celery tasks (not a separate polling task).
Logs are ingested in Splunk HEC (SPLUNK_INDEX=idp_portal_prod) and
queried via structured field searches.
"""
from __future__ import annotations

from django.utils import timezone


def get_runnable_queue_depth() -> dict:
    """Return pending/running/expired_leases counts for RUNNABLE_STEPS.

    Returns:
        dict with keys:
            - pending (int): RunnableStep rows with no claim at all (claimed_by=None, claimed_until=None)
            - running (int): RunnableStep rows with active lease (claimed_until > now)
            - expired_leases (int): rows with claimed_until set but already expired
        The three buckets are mutually exclusive.
    """
    from executions.models import RunnableStep  # noqa: PLC0415

    now = timezone.now()
    # claimed_until__isnull=True ensures mutual exclusivity with expired_leases bucket
    pending = RunnableStep.objects.filter(
        claimed_by__isnull=True,
        claimed_until__isnull=True,
    ).count()
    running = RunnableStep.objects.filter(
        claimed_until__isnull=False,
        claimed_until__gt=now,
    ).count()
    expired_leases = RunnableStep.objects.filter(
        claimed_until__isnull=False,
        claimed_until__lte=now,
    ).count()
    return {
        "pending": pending,
        "running": running,
        "expired_leases": expired_leases,
    }


def get_command_backlog() -> int:
    """Return count of PENDING WorkflowCommands.

    Returns:
        int: number of WorkflowCommand rows with status=PENDING
    """
    from executions.models import WorkflowCommand, WorkflowCommandStatus  # noqa: PLC0415

    return WorkflowCommand.objects.filter(
        status=WorkflowCommandStatus.PENDING,
    ).count()


def get_outbox_pending() -> int:
    """Return count of PENDING ExecutionOutbox entries.

    Returns:
        int: number of ExecutionOutbox rows with status=PENDING
    """
    from executions.models import ExecutionOutbox, OutboxEntryStatus  # noqa: PLC0415

    return ExecutionOutbox.objects.filter(
        status=OutboxEntryStatus.PENDING,
    ).count()
