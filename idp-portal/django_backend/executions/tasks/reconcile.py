"""
executions/tasks/reconcile.py — Réconciliateur simplifié : crash recovery pour exécutions stales.

Story 78.6 — Réconciliateur simplifié post-worker d'orchestration.

Responsabilités (ce que fait le réconciliateur) :
  1. Reclaim des leases expirés (RunnableStepService.reclaim_expired_leases) — crash recovery worker
  2. Re-drive des commandes pending (WorkflowCommandService.process_pending_commands) — commandes stuck
  3. Détection stale (RUNNING + cutoff) :
     - Step RUNNING avec platform_job_id réel → reattach poll (_reattach_poll)
     - Step RUNNING avec child execution ID → sync parent-child (_reconcile_schedule_step)
     - Step RUNNING sans platform_job_id → reset PENDING + enqueue (_reset_and_enqueue_step)
     - Pas de RUNNING steps + container workflow → enqueue next wave (_enqueue_recovery_steps)
     - Irrécupérable → mark FAILED (_mark_execution_failed)
  4. Parent-child cascade (enfants d'exécutions reconciliées → cascade FAILED)

Ce que le réconciliateur ne fait plus (délégué au worker d'orchestration 78.5) :
  - Exécution de handlers (ServiceCallHandler, HttpRequestHandler, EvaluationHandler)
  - Appel direct à _execute_workflow_steps() (l'ancienne boucle thread BFS)
  - Reconstruction complète du contexte d'exécution (_step_outputs) pour retry inline

Seuil stale : exécutions dont la dernière activité (updated_at si disponible, sinon created_at)
est antérieure à RECONCILE_STALE_THRESHOLD_MINUTES (défaut 10). Les container workflows mettent
à jour updated_at à chaque wave (heartbeat), évitant les faux positifs.

Déclenché par :
  1. AppConfig.ready() au démarrage Gunicorn/worker (recovery immédiat après crash)
  2. Celery Beat toutes les N minutes (filet de sécurité)

Story 76.4 — Deux types de platform_job_id :
  1. Action plateforme (AAP, Tower, etc.) : platform_job_id = vrai ID job → reattach poll
  2. Step schedule_execution : platform_job_id = child Execution.id → _reconcile_schedule_step
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from django.conf import settings
from django.db.models import Q
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


def _build_stale_filter(cutoff: Any) -> Q:
    """
    Story 76.3: Retourne le filtre Q pour détecter les exécutions stales.

    Logique : dernière activité (updated_at si disponible, sinon created_at) avant cutoff.
    """
    return Q(updated_at__lt=cutoff) | Q(updated_at__isnull=True, created_at__lt=cutoff)


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
        correlation_id = getattr(execution, "correlation_id", "") or ""
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
            correlation_id=correlation_id or None,
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


def _enqueue_recovery_steps(execution: Any, correlation_id: str = "") -> str:
    """Enqueue next wave of steps for a container workflow that crashed between steps.

    Story 78.6 — Replaces _resume_container_workflow(). Instead of calling
    _execute_workflow_steps() (the old thread-based BFS loop), computes the next
    wave and enqueues via RunnableStepService.enqueue(). The orchestration worker
    (78.5) handles actual execution.

    If all steps are terminal and no next wave exists, finalizes the execution
    via _finalize_execution_if_done().

    Returns 'reattached' on success.
    Raises on any error so the caller can fall back to _mark_execution_failed.
    """
    from executions.models import ExecutionStep, ExecutionStepStatus, ExecutionStatus  # noqa: PLC0415
    from executions.container_routing import get_next_step_ids  # noqa: PLC0415
    from executions.container_parallel import apply_join_policy  # noqa: PLC0415
    from executions.tasks.orchestration_worker import _enqueue_next_steps, _finalize_execution_if_done  # noqa: PLC0415
    from django.db.models import Max  # noqa: PLC0415

    all_steps = execution.action.execution_steps or []
    _step_config_by_id: dict[str, dict] = {
        s["step_id"]: s for s in all_steps if isinstance(s, dict) and s.get("step_id")
    }
    step_name_to_id = {
        s.get("name"): s.get("step_id")
        for s in all_steps
        if isinstance(s, dict) and s.get("name") and s.get("step_id")
    }

    terminal_steps = list(
        ExecutionStep.objects.filter(
            execution=execution,
            status__in=(ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED),
        ).order_by("step_order")
    )

    completed_steps = [s for s in terminal_steps if s.status == ExecutionStepStatus.COMPLETED]
    if not completed_steps:
        raise ValueError("No COMPLETED steps found — cannot resume container workflow")

    # --- Compute next wave (step IDs only, no _step_outputs rebuild for execution) ---
    _step_status_to_exec_status: dict[str, ExecutionStatus] = {
        ExecutionStepStatus.COMPLETED.value: ExecutionStatus.COMPLETED,
        ExecutionStepStatus.FAILED.value: ExecutionStatus.FAILED,
    }
    results: dict = {}
    for db_step in terminal_steps:
        step_id_key = db_step.config_step_id
        if not step_id_key and db_step.step_name:
            step_id_key = step_name_to_id.get(db_step.step_name)
        if step_id_key and step_id_key in _step_config_by_id:
            step_cfg = _step_config_by_id[step_id_key]
            step_status_val = getattr(db_step.status, "value", db_step.status) or db_step.status
            exec_status = _step_status_to_exec_status.get(
                step_status_val, ExecutionStatus.FAILED
            )
            next_ids = get_next_step_ids(step_cfg, exec_status, all_steps)
            results[step_id_key] = (exec_status, next_ids)

    terminal_step_ids = {
        db_step.config_step_id or step_name_to_id.get(db_step.step_name)
        for db_step in terminal_steps
    }
    terminal_step_ids = {sid for sid in terminal_step_ids if sid}

    candidate_steps = [
        _step_config_by_id[sid] for sid in results if sid in _step_config_by_id
    ]
    next_wave = [
        nid
        for nid in apply_join_policy(candidate_steps, results, _step_config_by_id)
        if nid not in terminal_step_ids
    ]

    logger.info(
        "reconcile_enqueue_recovery_steps",
        execution_id=execution.id,
        completed_count=len(completed_steps),
        next_wave=next_wave,
        correlation_id=correlation_id,
    )

    if not next_wave:
        # All steps already terminal — finalize via orchestration_worker helper
        _finalize_execution_if_done(execution, ExecutionStatus.COMPLETED)
        logger.info(
            "reconcile_container_workflow_completed",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )
        return "reattached"

    # Build a minimal runtime object for _enqueue_next_steps (needs _step_order_counter only)
    class _MinimalRuntime:
        _step_order_counter: int = 0

    runtime = _MinimalRuntime()
    max_order = ExecutionStep.objects.filter(execution=execution).aggregate(
        Max("step_order")
    )["step_order__max"]
    runtime._step_order_counter = max_order if max_order is not None else 0

    enqueued = _enqueue_next_steps(runtime, execution, next_wave, _step_config_by_id)

    logger.info(
        "reconcile_recovery_steps_enqueued",
        execution_id=execution.id,
        next_wave=next_wave,
        enqueued=enqueued,
        correlation_id=correlation_id,
    )
    return "reattached"


def _is_child_execution_id(execution: Any, platform_job_id: str) -> bool:
    """Return True if platform_job_id is the ID of a child Execution of this execution.

    Story 76.4 — Task 2.1:
    Detects the case where a schedule_execution step stored the child execution's ID
    as platform_job_id (ContainerWorkflowRuntime line ~654).

    Conditions:
      1. platform_job_id is a numeric string (can be cast to int).
      2. An Execution with id=int(platform_job_id) and parent_execution_id=execution.id exists.

    Edge case: a numeric platform_job_id that is NOT a child execution (e.g. Tower job IDs
    are integers) is NOT matched because condition 2 requires parent_execution_id to match.
    """
    from executions.models import Execution  # noqa: PLC0415

    try:
        candidate_id = int(platform_job_id)
    except (ValueError, TypeError):
        return False

    return Execution.objects.filter(
        id=candidate_id,
        parent_execution_id=execution.id,
    ).exists()


def _reset_and_enqueue_step(step: Any) -> bool:
    """Reset a RUNNING step to PENDING and enqueue it for the orchestration worker.

    Story 78.6 — Replaces _retry_non_platform_step(). Instead of executing the
    handler inline, resets the step status to PENDING and enqueues via
    RunnableStepService.enqueue(). The orchestration worker (78.5) handles execution.

    Returns True if the step was successfully enqueued, False otherwise.
    """
    from executions.models import ExecutionStepStatus  # noqa: PLC0415
    from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415

    try:
        step.status = ExecutionStepStatus.PENDING
        step.error_message = None
        step.save(update_fields=["status", "error_message"])

        RunnableStepService.enqueue(step)

        logger.info(
            "reconcile_step_reset_and_enqueued",
            execution_id=step.execution_id,
            step_id=step.id,
            step_name=step.step_name,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "reconcile_step_reset_enqueue_failed",
            execution_id=step.execution_id,
            step_id=step.id,
            error=str(exc),
            exc_info=True,
        )
        _mark_step_failed(step, f"Reset+enqueue failed: {exc!s}")
        return False


def _reconcile_schedule_step(execution: Any, step: Any) -> bool:
    """Handle reconciliation for a schedule_execution step whose platform_job_id is a child execution ID.

    Story 76.4 — Task 2.2:
    Instead of calling _reattach_poll (which would send a child execution ID to a platform
    adapter), this function checks the child execution status directly in the DB:

    - child terminal (COMPLETED/FAILED/CANCELLED):
        Update the parent step status to match the child outcome and return True.
    - child RUNNING and stale:
        Mark the child FAILED (cascade), then mark the parent step FAILED. Return False.
    - child not found (deleted or inconsistent):
        Mark the parent step FAILED with an explicit error. Return False.

    Returns True if the step was successfully resolved (child terminal), False otherwise.
    """
    from executions.models import Execution, ExecutionStatus, ExecutionStepStatus  # noqa: PLC0415

    child_id = int(step.platform_job_id)
    execution_id = execution.id

    try:
        child = Execution.objects.select_related("action").get(
            id=child_id, parent_execution_id=execution_id
        )
    except Execution.DoesNotExist:
        logger.error(
            "reconcile_schedule_step_child_not_found",
            execution_id=execution_id,
            step_id=step.id,
            child_id=child_id,
        )
        _mark_step_failed(
            step,
            f"schedule_execution step: child execution {child_id} not found — marked FAILED by reconciliation.",
        )
        return False

    terminal_statuses = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

    if child.status in terminal_statuses:
        # Child already finished — sync parent step status
        if child.status == ExecutionStatus.COMPLETED:
            if step.status not in (ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED):
                step.status = ExecutionStepStatus.COMPLETED
                step.completed_at = child.completed_at or timezone.now()
                # Story 77.1: Persist standard format {raw_output, extracted_output, status_context}.
                referenced_action = getattr(child, "action", None)
                raw_output = {
                    "child_execution_id": child.id,
                    "referenced_action_id": referenced_action.id if referenced_action else None,
                    "referenced_action_name": getattr(referenced_action, "name", None) if referenced_action else None,
                    "child_status": child.status,
                    "parameters_injected": False,  # unknown in reconcile context
                }
                # Get output_mapping from step config for extracted_output
                step_cfg = next(
                    (s for s in (execution.action.execution_steps or [])
                     if isinstance(s, dict) and s.get("step_id") == step.config_step_id),
                    {},
                )
                output_mapping = step_cfg.get("output_mapping", {}) or {}
                if not isinstance(output_mapping, dict):
                    output_mapping = {}
                from executions.output_extractor import OutputExtractor  # noqa: PLC0415

                extractor = OutputExtractor()
                extracted = extractor.extract(raw_output, output_mapping)
                step.set_output({
                    "raw_output": raw_output,
                    "extracted_output": extracted,
                    "status_context": {
                        "status": ExecutionStepStatus.COMPLETED,
                        "completed_at": step.completed_at.isoformat(),
                    },
                })
                step.save(update_fields=["status", "completed_at", "output"])
                # Touch execution.updated_at to avoid immediate re-stale (Story 76.3 heartbeat)
                Execution.objects.filter(id=execution_id).update(updated_at=timezone.now())
            logger.info(
                "reconcile_schedule_step_child_completed",
                execution_id=execution_id,
                step_id=step.id,
                child_id=child_id,
                child_status=child.status,
            )
            return True
        else:
            # Child FAILED or CANCELLED → mark parent step FAILED
            _mark_step_failed(
                step,
                f"schedule_execution step: child execution {child_id} is {child.status} — marked FAILED by reconciliation.",
            )
            logger.info(
                "reconcile_schedule_step_child_terminal_failed",
                execution_id=execution_id,
                step_id=step.id,
                child_id=child_id,
                child_status=child.status,
            )
            return False

    # Child is still RUNNING (and stale, since the parent is stale) → cascade FAILED
    logger.warning(
        "reconcile_schedule_step_child_still_running",
        execution_id=execution_id,
        step_id=step.id,
        child_id=child_id,
    )
    _mark_execution_failed(
        child,
        f"Child execution {child_id} still RUNNING while parent {execution_id} is stale — marked FAILED by cascade reconciliation.",
    )
    _mark_step_failed(
        step,
        f"schedule_execution step: child execution {child_id} was stale RUNNING — cascade FAILED by reconciliation.",
    )
    return False


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
                result = _enqueue_recovery_steps(
                    execution,
                    correlation_id=getattr(execution, "correlation_id", "") or "",
                )
                return result
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "reconcile_enqueue_recovery_failed",
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
    schedule_step_resolved = False

    for step in running_steps:
        if not step.platform_job_id:
            # Story 78.6: Reset to PENDING and enqueue for the orchestration worker
            if _reset_and_enqueue_step(step):
                reattached_any = True
            # On False: step already marked FAILED inside _reset_and_enqueue_step
            continue

        # Step has a platform_job_id — check if it's a child execution ID (schedule_execution step)
        # Story 76.4: platform_job_id may be a child Execution.id rather than a real platform job ID.
        if _is_child_execution_id(execution, step.platform_job_id):
            if _reconcile_schedule_step(execution, step):
                reattached_any = True
                schedule_step_resolved = True
            # If False: step was marked FAILED inside _reconcile_schedule_step
            continue

        # Step has a real platform_job_id — try to reattach polling
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

    # Story 78.6: After processing all steps, if a schedule_step was resolved (child
    # COMPLETED) and there are no RUNNING steps left, enqueue next wave via recovery.
    # Only trigger when a schedule_step was resolved — steps reset+enqueued by
    # _reset_and_enqueue_step are already PENDING and handled by the worker.
    if schedule_step_resolved and _is_container_workflow(execution):
        remaining_running = ExecutionStep.objects.filter(
            execution_id=execution_id,
            status=ExecutionStepStatus.RUNNING,
        ).exists()
        if not remaining_running:
            has_failed_step = ExecutionStep.objects.filter(
                execution_id=execution_id,
                status=ExecutionStepStatus.FAILED,
            ).exists()
            if has_failed_step:
                _mark_execution_failed(
                    execution,
                    "At least one step failed during reconciliation — marked FAILED.",
                )
                return "failed"
            # Schedule step resolved, no more RUNNING — enqueue next wave
            try:
                _enqueue_recovery_steps(
                    execution,
                    correlation_id=getattr(execution, "correlation_id", "") or "",
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "reconcile_schedule_step_enqueue_failed",
                    execution_id=execution_id,
                    error=str(exc),
                    exc_info=True,
                )
                _mark_execution_failed(
                    execution,
                    f"Failed to enqueue recovery after schedule_step resolution: {exc!s}",
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

    Scans for Execution records with status=RUNNING whose last activity is older than
    RECONCILE_STALE_THRESHOLD_MINUTES (default 10). Staleness is evaluated using:
    - updated_at if non-null (heartbeat set by container_workflow_runtime at each BFS wave /
      sequential step, and at the SUBMITTED→RUNNING transition). This allows long-running but
      healthy container workflows to stay alive as long as they are progressing.
    - created_at as fallback when updated_at is NULL (pre-76.3 executions or non-container
      workflows — rétrocompatibilité).

    Query: Q(updated_at__lt=cutoff) | Q(updated_at__isnull=True, created_at__lt=cutoff)

    For each stale execution:

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
    from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
    from executions.services.workflow_commands import WorkflowCommandService  # noqa: PLC0415

    # 1. Reclaim expired leases before stale detection (Story 78.2)
    RunnableStepService.reclaim_expired_leases()

    # 2. Re-drive pending commands (Story 78.6 — AC2)
    # Best-effort: log + continue if re-drive fails
    commands_redriven = 0
    try:
        commands_redriven = WorkflowCommandService.process_pending_commands()
        if commands_redriven:
            logger.info(
                "reconcile_commands_redriven",
                commands_redriven=commands_redriven,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "reconcile_commands_redrive_failed",
            error=str(exc),
            exc_info=True,
        )

    # 3. Stale detection
    cutoff = timezone.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    terminal_statuses = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }

    # Stale = dernière activité (updated_at si disponible, sinon created_at) avant le cutoff
    stale_filter = _build_stale_filter(cutoff)

    # --- 1. Root executions (no parent) ---
    stale_roots = list(
        Execution.objects.filter(
            status=ExecutionStatus.RUNNING,
            parent_execution__isnull=True,
        ).filter(stale_filter).select_related("action__integration")
    )

    # --- 2. Child executions (have a parent) ---
    # select_related includes parent_execution to avoid N+1 when checking parent status.
    stale_children = list(
        Execution.objects.filter(
            status=ExecutionStatus.RUNNING,
            parent_execution__isnull=False,
        ).filter(stale_filter).select_related("action__integration", "parent_execution")
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
            # Only add to processed_parent_ids when root is actually terminal after reconciliation.
            # Reattached roots remain RUNNING — their children must not be cascade-failed.
            if outcome == "failed":
                processed_parent_ids.add(execution.id)
            elif outcome not in ("reattached", "failed"):
                # skipped or other terminal-like outcome
                execution.refresh_from_db(fields=["status"])
                if execution.status in terminal_statuses:
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
                "commands_redriven": commands_redriven,
                "status": "partial_timeout",
            }
        except Exception as exc:  # noqa: BLE001 — never crash the whole reconciliation for one execution
            # Do not add to processed_parent_ids — execution state unknown, may still be RUNNING
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
                "commands_redriven": commands_redriven,
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
        commands_redriven=commands_redriven,
        stale_threshold_minutes=STALE_THRESHOLD_MINUTES,
    )

    return {
        "reattached": total_reattached,
        "failed": total_failed,
        "skipped": total_skipped,
        "errors": total_errors,
        "commands_redriven": commands_redriven,
    }
