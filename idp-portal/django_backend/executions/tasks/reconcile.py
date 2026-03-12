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

Stale threshold: executions whose created_at is older than RECONCILE_STALE_THRESHOLD_MINUTES
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


def _is_container_workflow(execution: Any) -> bool:
    """Return True if the execution's action defines a container workflow.

    A container workflow has ``execution_steps`` as a non-empty list of dicts
    that each contain a ``step_id`` key.
    """
    try:
        steps = execution.action.execution_steps
        if not steps or not isinstance(steps, list):
            return False
        return any(isinstance(s, dict) and s.get("step_id") for s in steps)
    except AttributeError:
        return False


def _resume_container_workflow(execution: Any, correlation_id: str = "") -> str:
    """Resume a container workflow execution that crashed between steps.

    Reconstructs ``_step_outputs`` from COMPLETED steps in the DB, computes
    the next wave of steps to execute, and either marks the execution
    COMPLETED (if the workflow is fully done) or calls
    ``_execute_workflow_steps()`` to continue from where it left off.

    Returns 'reattached' on success.
    Raises on any error so the caller can fall back to ``_mark_execution_failed``.
    """
    from executions.models import ExecutionStep, ExecutionStepStatus, ExecutionStatus  # noqa: PLC0415
    from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
    from executions.output_extractor import OutputExtractor  # noqa: PLC0415
    from executions.container_routing import get_next_step_ids  # noqa: PLC0415
    from executions.container_parallel import apply_join_policy  # noqa: PLC0415
    from django.db.models import Max  # noqa: PLC0415

    all_steps = execution.action.execution_steps or []
    _step_config_by_id = {
        s.get("step_id"): s for s in all_steps if isinstance(s, dict) and s.get("step_id")
    }
    step_name_to_id = {
        s.get("name"): s.get("step_id")
        for s in all_steps
        if isinstance(s, dict) and s.get("name") and s.get("step_id")
    }

    completed_steps = list(
        ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.COMPLETED,
        ).order_by("step_order")
    )

    if not completed_steps:
        raise ValueError("No COMPLETED steps found — cannot resume container workflow")

    # --- Rebuild _step_outputs from COMPLETED DB steps ---
    runtime = ContainerWorkflowRuntime(execution=execution)
    _extractor = OutputExtractor()
    for db_step in completed_steps:
        raw_output = db_step.get_output() or {}
        step_id_key = db_step.config_step_id
        if not step_id_key and db_step.step_name:
            step_id_key = step_name_to_id.get(db_step.step_name)
        if step_id_key:
            step_cfg = _step_config_by_id.get(step_id_key, {})
            output_mapping = step_cfg.get("output_mapping", {})
            if isinstance(output_mapping, dict) and output_mapping:
                extracted = _extractor.extract(raw_output, output_mapping)
            else:
                extracted = raw_output
            runtime._step_outputs[step_id_key] = extracted

    # --- Compute next wave ---
    results: dict = {}
    for db_step in completed_steps:
        step_id = db_step.config_step_id
        if step_id and step_id in _step_config_by_id:
            step_cfg = _step_config_by_id[step_id]
            next_ids = get_next_step_ids(step_cfg, ExecutionStatus.COMPLETED, all_steps)
            results[step_id] = (ExecutionStatus.COMPLETED, next_ids)

    completed_step_ids = {s.config_step_id for s in completed_steps if s.config_step_id}

    candidate_steps = [
        _step_config_by_id[sid] for sid in results if sid in _step_config_by_id
    ]
    next_wave = [
        nid
        for nid in apply_join_policy(candidate_steps, results, runtime._step_lookup_by_id)
        if nid not in completed_step_ids
    ]

    logger.info(
        "reconcile_container_workflow_resume",
        execution_id=execution.id,
        completed_count=len(completed_steps),
        next_wave=next_wave,
        correlation_id=correlation_id,
    )

    if not next_wave:
        # All steps already COMPLETED — mark execution COMPLETED
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = timezone.now()
        execution.save(update_fields=["status", "completed_at"])
        logger.info(
            "reconcile_container_workflow_completed",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )
        return "reattached"

    # Resume from next wave
    max_order = ExecutionStep.objects.filter(execution=execution).aggregate(
        Max("step_order")
    )["step_order__max"]
    runtime._step_order_counter = max_order if max_order is not None else 0
    runtime._initial_wave = next_wave
    runtime._execute_workflow_steps()

    logger.info(
        "reconcile_container_workflow_reattached",
        execution_id=execution.id,
        next_wave=next_wave,
        correlation_id=correlation_id,
    )
    return "reattached"


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
        # Execution is RUNNING but no step is RUNNING — crashed between steps.
        # For container workflows with COMPLETED steps, attempt automatic resume.
        logger.warning(
            "reconcile_execution_no_running_step",
            execution_id=execution_id,
        )
        if _is_container_workflow(execution):
            try:
                result = _resume_container_workflow(
                    execution,
                    correlation_id=getattr(execution, "correlation_id", "") or "",
                )
                return result
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "reconcile_container_workflow_resume_failed",
                    execution_id=execution_id,
                    error=str(exc),
                    exc_info=True,
                )
                # Fall through to _mark_execution_failed below

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
    - If no RUNNING step exists and execution is a container workflow with COMPLETED steps:
      attempt automatic resume from the last completed step; fall back to FAILED on error.
    - If no RUNNING step exists and not a resumable container workflow: mark execution FAILED.

    Processing order:
    1. Root executions (parent_execution_id is null) are processed first.
    2. Child executions (parent_execution_id is not null) are processed second:
       - If the parent was reconciled in this run (present in processed_parent_ids):
         mark child FAILED directly by cascade.
       - If the parent is already in a terminal state (FAILED/COMPLETED/CANCELLED) in DB:
         mark child FAILED directly by cascade.
       - Otherwise: apply normal reconciliation (reattach or resume).

    Returns:
        dict with 'reattached', 'failed', 'skipped', 'errors' counts.
    """
    from executions.models import Execution, ExecutionStatus  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    terminal_statuses = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }

    # --- 1. Root executions (no parent) ---
    stale_roots = list(
        Execution.objects.filter(
            status=ExecutionStatus.RUNNING,
            created_at__lt=cutoff,
            parent_execution__isnull=True,
        ).select_related("action__integration")
    )

    # --- 2. Child executions (have a parent) ---
    # select_related includes parent_execution to avoid N+1 when checking parent status.
    stale_children = list(
        Execution.objects.filter(
            status=ExecutionStatus.RUNNING,
            created_at__lt=cutoff,
            parent_execution__isnull=False,
        ).select_related("action__integration", "parent_execution")
    )

    total_reattached = 0
    total_failed = 0
    total_skipped = 0
    total_errors = 0

    logger.info(
        "reconcile_stale_executions_start",
        stale_roots=len(stale_roots),
        stale_children=len(stale_children),
        stale_threshold_minutes=STALE_THRESHOLD_MINUTES,
        cutoff=cutoff.isoformat(),
    )

    # IDs of root executions reconciled (terminal) in this run — used to cascade FAILED
    # to children whose parent was just reconciled.
    processed_parent_ids: set[int] = set()

    # --- Process root executions ---
    for execution in stale_roots:
        try:
            outcome = _reconcile_execution(execution)
            processed_parent_ids.add(execution.id)
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
            processed_parent_ids.add(execution.id)
            logger.error(
                "reconcile_execution_error",
                execution_id=execution.id,
                error=str(exc),
                exc_info=True,
            )
            total_errors += 1

    # --- Process child executions ---
    # NOTE: This loop handles 2-level hierarchies only (root → child).
    # For deeper hierarchies (root → parent → grandchild), a grandchild's parent
    # may have been marked FAILED during this same loop iteration, but the
    # grandchild's prefetched parent_execution object still holds the pre-update
    # RUNNING status. Such grandchildren fall through to _reconcile_execution
    # rather than cascade-FAILED. This is an accepted limitation: the next
    # reconciliation run will cascade them correctly.
    for execution in stale_children:
        try:
            parent_id = execution.parent_execution_id
            parent = execution.parent_execution  # prefetched via select_related

            if parent_id in processed_parent_ids:
                # Parent was reconciled (and made terminal) in this run → cascade FAILED
                _mark_execution_failed(
                    execution,
                    "Parent execution reconciled as terminal — child marked FAILED by cascade.",
                )
                total_failed += 1
            elif parent is not None and parent.status in terminal_statuses:
                # Parent is already in a terminal state in DB → cascade FAILED
                _mark_execution_failed(
                    execution,
                    "Parent execution already in terminal state — child marked FAILED by cascade.",
                )
                total_failed += 1
            else:
                # Parent is healthy or unknown → apply normal reconciliation
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
