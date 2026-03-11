"""
executions/tasks/reconcile.py — Crash recovery: reconcile stale RUNNING executions.

After a backend crash and restart, executions that were in RUNNING status are left
orphaned: their Celery polling tasks are gone and the workflow orchestration thread
is dead. This task detects those executions and either:

  - Reattaches a poll_platform_job_status task if the step has a platform_job_id
    (the platform job was already triggered and is still running on the remote platform).
  - Marks the execution FAILED if no platform_job_id exists (trigger never completed
    or the execution was between steps).

Triggered at two points:
  1. AppConfig.ready() on Gunicorn/worker startup (immediate recovery after crash).
  2. Celery Beat every N minutes (safety net for mid-flight task losses).

Stale threshold: executions whose updated_at is older than RECONCILE_STALE_THRESHOLD_MINUTES
(default 10) are considered orphaned. This prevents false positives on slow but healthy runs.
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from django.conf import settings
from django.utils import timezone

logger = structlog.get_logger(__name__)

_LIMITS = settings.CELERY_TASK_TIME_LIMITS["reconcile_stale_executions"]


def _parse_stale_threshold_minutes() -> int:
    """Parse RECONCILE_STALE_THRESHOLD_MINUTES defensively; default 10 on invalid value."""
    raw = os.getenv("RECONCILE_STALE_THRESHOLD_MINUTES", "10")
    try:
        val = int(raw)
        return val if val > 0 else 10
    except (ValueError, TypeError):
        return 10


STALE_THRESHOLD_MINUTES = _parse_stale_threshold_minutes()


def _build_adapter_kwargs(integration: Any) -> dict:
    """Extract platform-specific adapter kwargs from integration config.

    Mirrors the logic in trigger.py and workflow_step_executor.py.
    """
    adapter_kwargs: dict = {}
    config = integration.get_config() if hasattr(integration, "get_config") else None
    if config:
        for key in ("owner", "repo", "organization", "namespace"):
            if key in config:
                adapter_kwargs[key] = config[key]
        if "ssl_verify" in config:
            adapter_kwargs["ssl_verify"] = config["ssl_verify"]
        if config.get("ca_bundle_path"):
            adapter_kwargs["ca_bundle_path"] = config["ca_bundle_path"]
    return adapter_kwargs


def _reattach_poll(
    execution_id: int,
    step: Any,
    integration: Any,
) -> bool:
    """Schedule a new poll_platform_job_status task for a stale RUNNING step.

    Returns True if successfully scheduled, False otherwise.
    """
    from executions.tasks.polling import poll_platform_job_status, get_platform_queue  # noqa: PLC0415

    platform_type = integration.type
    platform_job_id = step.platform_job_id

    adapter_kwargs = _build_adapter_kwargs(integration)

    try:
        poll_platform_job_status.apply_async(
            args=[execution_id, platform_job_id, platform_type],
            kwargs={
                "base_url": integration.base_url,
                "credential_ref": getattr(integration, "credential_ref", "") or "",
                "auth_flow": getattr(integration, "auth_flow", "token") or "token",
                "poll_interval": 5,
                "retry_count": 0,
                "adapter_kwargs": adapter_kwargs if adapter_kwargs else None,
            },
            queue=get_platform_queue(platform_type),
        )
        logger.info(
            "reconcile_poll_reattached",
            execution_id=execution_id,
            step_id=step.id,
            platform_job_id=platform_job_id,
            platform_type=platform_type,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort: log and continue to next step
        logger.error(
            "reconcile_poll_reattach_failed",
            execution_id=execution_id,
            step_id=step.id,
            platform_job_id=platform_job_id,
            error=str(exc),
            exc_info=True,
        )
        return False


def _mark_step_failed(step: Any, reason: str) -> None:
    """Mark a single ExecutionStep as FAILED."""
    from executions.models import ExecutionStepStatus  # noqa: PLC0415

    if step.status not in (ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED):
        step.status = ExecutionStepStatus.FAILED
        step.completed_at = timezone.now()
        step.error_message = reason
        step.save(update_fields=["status", "completed_at", "error_message"])


def _mark_execution_failed(execution: Any, reason: str) -> None:
    """Mark an Execution as FAILED with an audit entry."""
    from executions.models import ExecutionStatus  # noqa: PLC0415
    from core.services import AuditService  # noqa: PLC0415
    from core.models import AuditActionType, AuditEntityType  # noqa: PLC0415
    from core.utils import sanitize_audit_changes  # noqa: PLC0415

    terminal_statuses = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }
    if execution.status in terminal_statuses:
        return

    old_status = execution.status
    execution.status = ExecutionStatus.FAILED
    execution.completed_at = timezone.now()
    execution.error_message = reason
    execution.save(update_fields=["status", "completed_at", "error_message"])

    try:
        changes = sanitize_audit_changes({'status': {'old': old_status, 'new': ExecutionStatus.FAILED}})
        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_FAILED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                "reason": reason,
                "reconciled_at": timezone.now().isoformat(),
                "changes": changes,
            },
        )
    except Exception as exc:  # noqa: BLE001 — best-effort audit
        logger.warning(
            "reconcile_audit_failed",
            execution_id=execution.id,
            error=str(exc),
        )


def _reconcile_execution(execution: Any) -> str:
    """
    Reconcile a single stale RUNNING execution.

    Returns one of: 'reattached', 'failed', 'skipped'.
    """
    from executions.models import ExecutionStep, ExecutionStepStatus  # noqa: PLC0415

    execution_id = execution.id

    # Find RUNNING steps for this execution.
    # The integration is accessed via the already-prefetched execution.action.integration
    # passed in from the main query — no extra select_related needed here.
    running_steps = list(
        ExecutionStep.objects.filter(
            execution_id=execution_id,
            status=ExecutionStepStatus.RUNNING,
        )
    )

    if not running_steps:
        # Execution is RUNNING but no step is RUNNING — crashed between steps
        logger.warning(
            "reconcile_execution_no_running_step",
            execution_id=execution_id,
        )
        _mark_execution_failed(
            execution,
            "Execution found RUNNING at startup with no active step — marked FAILED by reconciliation.",
        )
        return "failed"

    reattached_any = False

    for step in running_steps:
        if not step.platform_job_id:
            # Step is RUNNING but trigger never completed — no platform job to reattach
            logger.warning(
                "reconcile_step_no_platform_job_id",
                execution_id=execution_id,
                step_id=step.id,
                step_name=step.step_name,
            )
            _mark_step_failed(
                step,
                "Step found RUNNING at startup with no platform_job_id — marked FAILED by reconciliation.",
            )
            continue

        # Step has a platform_job_id — try to reattach polling
        try:
            integration = execution.action.integration
        except Exception:  # noqa: BLE001 — action or integration may be deleted
            integration = None

        if integration is None:
            logger.error(
                "reconcile_step_no_integration",
                execution_id=execution_id,
                step_id=step.id,
                platform_job_id=step.platform_job_id,
            )
            _mark_step_failed(
                step,
                "Cannot reattach polling: action has no integration configured.",
            )
            continue

        if _reattach_poll(execution_id, step, integration):
            reattached_any = True
        else:
            _mark_step_failed(
                step,
                "Failed to reattach polling task at startup — marked FAILED by reconciliation.",
            )

    if not reattached_any:
        # All steps either had no platform_job_id or failed to reattach
        _mark_execution_failed(
            execution,
            "All RUNNING steps failed to reattach polling at startup — marked FAILED by reconciliation.",
        )
        return "failed"

    return "reattached"


@shared_task(
    name="executions.tasks.reconcile_stale_executions",
    soft_time_limit=_LIMITS["soft"],
    time_limit=_LIMITS["hard"],
)
def reconcile_stale_executions() -> dict:
    """
    Detect and recover stale RUNNING executions after a crash.

    Scans for Execution records with status=RUNNING whose created_at is older than
    RECONCILE_STALE_THRESHOLD_MINUTES (default 10). For each:

    - If a RUNNING step has a platform_job_id: reattach poll_platform_job_status.
    - If a RUNNING step has no platform_job_id: mark step + execution FAILED.
    - If no RUNNING step exists: mark execution FAILED.

    Child executions (parent_execution_id set) are skipped — the parent workflow
    reconciliation handles cascade.

    Returns:
        dict with 'reattached', 'failed', 'skipped', 'errors' counts.
    """
    from executions.models import Execution, ExecutionStatus  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    # Use created_at as the staleness signal — Execution has no updated_at field.
    # An execution created more than STALE_THRESHOLD_MINUTES ago that is still RUNNING
    # is considered orphaned. This is conservative: short-lived executions that finish
    # quickly are never in RUNNING long enough to be caught.
    stale_executions = list(
        Execution.objects.filter(
            status=ExecutionStatus.RUNNING,
            created_at__lt=cutoff,
            parent_execution__isnull=True,  # skip child executions
        ).select_related("action__integration")
    )

    total_reattached = 0
    total_failed = 0
    total_skipped = 0
    total_errors = 0

    logger.info(
        "reconcile_stale_executions_start",
        stale_count=len(stale_executions),
        stale_threshold_minutes=STALE_THRESHOLD_MINUTES,
        cutoff=cutoff.isoformat(),
    )

    for execution in stale_executions:
        try:
            outcome = _reconcile_execution(execution)
            if outcome == "reattached":
                total_reattached += 1
            elif outcome == "failed":
                total_failed += 1
            else:
                total_skipped += 1
        except SoftTimeLimitExceeded:
            logger.warning(
                "reconcile_stale_executions_soft_timeout",
                reattached=total_reattached,
                failed=total_failed,
                skipped=total_skipped,
                errors=total_errors,
            )
            return {
                "reattached": total_reattached,
                "failed": total_failed,
                "skipped": total_skipped,
                "errors": total_errors,
                "status": "partial_timeout",
            }
        except Exception as exc:  # noqa: BLE001 — never crash the whole reconciliation for one execution
            logger.error(
                "reconcile_execution_error",
                execution_id=execution.id,
                error=str(exc),
                exc_info=True,
            )
            total_errors += 1

    logger.info(
        "reconcile_stale_executions_complete",
        reattached=total_reattached,
        failed=total_failed,
        skipped=total_skipped,
        errors=total_errors,
        stale_threshold_minutes=STALE_THRESHOLD_MINUTES,
    )

    return {
        "reattached": total_reattached,
        "failed": total_failed,
        "skipped": total_skipped,
        "errors": total_errors,
    }
