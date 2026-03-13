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

Stale threshold: executions whose last activity (updated_at if set, else created_at) is older than
RECONCILE_STALE_THRESHOLD_MINUTES (default 10) are considered orphaned. Container workflows update
updated_at at each BFS wave / sequential step (heartbeat), so long-running but healthy workflows
are never incorrectly marked stale. Executions without updated_at (pre-76.3) fall back to created_at.
Note: gate steps (Story 57.7) do not emit heartbeats while waiting; a gate held longer than the
stale threshold may be incorrectly reconciled (pre-existing limitation).

Story 76.5 — Retry pour étapes non-platform (service_call, http_request, evaluation) :
======================================================================================

Steps RUNNING sans ``platform_job_id`` : ces steps s'exécutent de façon synchrone dans le runtime
(ServiceCallHandler, HttpRequestHandler, EvaluationHandler). En cas de crash pendant l'exécution,
un retry est possible car il n'y a pas de job asynchrone à réattacher.

**Stratégie retry vs FAILED :**
- **Retry automatique** pour : service_call, http_request, evaluation (tous éligibles).
- **Pas de retry** (comportement FAILED conservé) pour : platform, schedule_execution.
- **Idempotence service_call** : retry par défaut pour toutes les opérations. Le risque de doublon
  sur ``create_change`` ServiceNow est documenté ; une exclusion future est possible si nécessaire.

**Flux retry :** helper ``_retry_non_platform_step(execution, step)`` — reconstruit le contexte
(_step_outputs depuis COMPLETED, resolved_params via StepTemplateResolver), appelle le handler,
met à jour le step et déclenche ``_resume_container_workflow`` si succès.

Story 76.4 — Deux types de platform_job_id :
===============================================

1. **Action simple** (non-workflow) :
   L'action est une action plateforme (AAP, Tower, Azure DevOps, GitHub, Terraform, etc.).
   ``trigger_platform_job`` stocke ``platform_job_id = adapter_result.get("platform_job_id")``
   (ex. ``"job-123"`` pour AAP, ``"42"`` pour Tower, ``"run-abc"`` pour Terraform).
   Le polling interroge la plateforme via ``adapter.get_status(platform_job_id)``.
   → **Reattach fonctionne** : l'adapter reçoit un vrai ID de job plateforme.

2. **Step schedule_execution (container workflow)** :
   Le parent exécute un workflow ; une étape référence une action (workflow ou action simple).
   ``ContainerWorkflowRuntime._create_and_run_child_execution`` crée une exécution enfant et
   stocke ``parent_step.platform_job_id = str(child_execution.id)`` (ligne ~654).
   Il n'y a pas de job AAP/TC à interroger — ``platform_job_id`` est un ID d'exécution IDP.
   → **Reattach naïf échoue** : l'adapter recevrait un entier numérique qui n'est pas un job
   plateforme valide, causant un échec ou un comportement indéfini.

Stratégie implémentée (Option A — Story 76.4) :
  - ``_is_child_execution_id(execution, platform_job_id)`` : détecte si ``platform_job_id``
    correspond à un ``Execution.id`` enfant de l'exécution courante.
  - ``_reconcile_schedule_step(execution, step)`` : au lieu de ``_reattach_poll``, vérifie le
    statut du child directement en DB :
      * child terminal (COMPLETED/FAILED/CANCELLED) → met à jour le parent step et continue.
      * child RUNNING et stale → marque child FAILED (cascade), puis marque parent step FAILED.
  - Intégration dans ``_reconcile_execution`` : avant d'appeler ``_reattach_poll``, si
    ``_is_child_execution_id`` est vrai → appelle ``_reconcile_schedule_step`` à la place.
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
        step_id_key = db_step.config_step_id
        if not step_id_key and db_step.step_name:
            step_id_key = step_name_to_id.get(db_step.step_name)
        if step_id_key and step_id_key in _step_config_by_id:
            step_cfg = _step_config_by_id[step_id_key]
            next_ids = get_next_step_ids(step_cfg, ExecutionStatus.COMPLETED, all_steps)
            results[step_id_key] = (ExecutionStatus.COMPLETED, next_ids)

    completed_step_ids = {
        db_step.config_step_id or step_name_to_id.get(db_step.step_name)
        for db_step in completed_steps
    }
    completed_step_ids = {sid for sid in completed_step_ids if sid}

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


# Story 76.5 — Types éligibles au retry (steps synchrones sans platform_job_id)
_RETRYABLE_STEP_TYPES = frozenset({
    "service_call",
    "http_request",
    "evaluation",
})


def _retry_non_platform_step(execution: Any, step: Any) -> bool:
    """Retry a RUNNING step without platform_job_id (service_call, http_request, evaluation).

    Story 76.5 — Reconstructs context from COMPLETED steps, calls the appropriate handler,
    updates the step on success, and triggers _resume_container_workflow.

    Returns True if retry succeeded (step COMPLETED, workflow resumed), False otherwise.
    """
    from executions.models import Execution, ExecutionStep, ExecutionStepStatus  # noqa: PLC0415
    from executions.output_extractor import OutputExtractor  # noqa: PLC0415
    from executions.template_resolver import StepTemplateResolver  # noqa: PLC0415

    raw_type = getattr(step, "step_type", None) or ""
    step_type = (getattr(raw_type, "value", raw_type) or "").lower() if raw_type else ""
    if step_type not in _RETRYABLE_STEP_TYPES:
        return False

    execution_id = execution.id
    step_id = step.config_step_id or step.step_name
    correlation_id = getattr(execution, "correlation_id", "") or ""

    logger.info(
        "reconcile_non_platform_retry_start",
        execution_id=execution_id,
        step_id=step.id,
        step_type=step_type,
        config_step_id=step_id,
        correlation_id=correlation_id,
    )

    all_steps = execution.action.execution_steps or []
    _step_config_by_id = {
        s.get("step_id"): s for s in all_steps if isinstance(s, dict) and s.get("step_id")
    }
    step_name_to_id = {
        s.get("name"): s.get("step_id")
        for s in all_steps
        if isinstance(s, dict) and s.get("name") and s.get("step_id")
    }

    step_cfg = _step_config_by_id.get(step_id) if step_id else None
    if not step_cfg:
        step_cfg = next(
            (s for s in all_steps if isinstance(s, dict) and s.get("step_id") == step_id),
            None,
        )
    if not step_cfg:
        logger.error(
            "reconcile_non_platform_retry_no_config",
            execution_id=execution_id,
            step_id=step_id,
            config_step_id=step.config_step_id,
        )
        _mark_step_failed(
            step,
            "Retry failed: step config not found in action.execution_steps.",
        )
        return False

    # Rebuild _step_outputs from COMPLETED steps
    completed_steps = list(
        ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.COMPLETED,
        ).order_by("step_order")
    )
    _step_outputs: dict = {}
    extractor = OutputExtractor()
    for db_step in completed_steps:
        raw_output = db_step.get_output() or {}
        cfg_id = db_step.config_step_id
        if not cfg_id and db_step.step_name:
            cfg_id = step_name_to_id.get(db_step.step_name)
        if cfg_id:
            cfg = _step_config_by_id.get(cfg_id, {})
            output_mapping = cfg.get("output_mapping", {})
            if isinstance(output_mapping, dict) and output_mapping:
                extracted = extractor.extract(raw_output, output_mapping)
            else:
                extracted = raw_output
            _step_outputs[cfg_id] = extracted

    # Resolve input_mapping
    input_mapping = step_cfg.get("input_mapping", {})
    resolved_params: dict = {}
    if input_mapping and isinstance(input_mapping, dict):
        resolver = StepTemplateResolver(
            _step_outputs,
            execution_context={
                "action_name": getattr(execution.action, "name", ""),
                "environment": execution.environment,
                "execution_id": execution_id,
            },
        )
        resolved_params = resolver.resolve(input_mapping)

    # Dispatch handler
    handler_map = {
        "service_call": ("executions.step_handlers.service_call_handler", "ServiceCallHandler"),
        "http_request": ("executions.step_handlers.http_request_handler", "HttpRequestHandler"),
        "evaluation": ("executions.step_handlers.evaluation_handler", "EvaluationHandler"),
    }
    module_path, class_name = handler_map.get(step_type, (None, None))
    if not module_path or not class_name:
        _mark_step_failed(step, f"Retry failed: unknown step_type {step_type!r}.")
        return False

    from importlib import import_module  # noqa: PLC0415

    mod = import_module(module_path)
    handler_cls = getattr(mod, class_name)
    handler = handler_cls()

    try:
        result = handler.execute(
            step_config=step_cfg,
            resolved_params=resolved_params,
            execution=execution,
            step=step_cfg,
            correlation_id=correlation_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "reconcile_non_platform_retry_failed",
            execution_id=execution_id,
            step_id=step.id,
            step_type=step_type,
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )
        _mark_step_failed(
            step,
            f"Retry failed: {exc!s}",
        )
        return False

    # Success — update step and extract output
    raw_output = result.get("raw_output", result) if isinstance(result, dict) else {}
    if not isinstance(raw_output, dict):
        raw_output = {"result": raw_output}
    # Determine status: EvaluationHandler returns status; others default to COMPLETED
    from executions.models import ExecutionStatus as ExecStatus  # noqa: PLC0415

    result_status = ExecStatus.COMPLETED
    if isinstance(result, dict):
        hs = result.get("status")
        if isinstance(hs, ExecStatus) and hs == ExecStatus.FAILED:
            result_status = ExecStatus.FAILED

    if result_status == ExecStatus.FAILED:
        _mark_step_failed(step, "Retry completed but handler returned FAILED status.")
        return False

    step.status = ExecutionStepStatus.COMPLETED
    step.completed_at = timezone.now()
    step.error_message = None
    step.set_output(raw_output)
    step.save(update_fields=["status", "completed_at", "error_message", "output"])

    Execution.objects.filter(id=execution_id).update(updated_at=timezone.now())

    logger.info(
        "reconcile_non_platform_retry_success",
        execution_id=execution_id,
        step_id=step.id,
        step_type=step_type,
        correlation_id=correlation_id,
    )

    # Workflow continuation is handled by the caller's block (reattached_any + remaining_running)
    return True


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
                # AC2 Task 2.2: set output so _resume_container_workflow can rebuild _step_outputs
                referenced_action = getattr(child, "action", None)
                step.set_output({
                    "child_execution_id": child.id,
                    "referenced_action_id": referenced_action.id if referenced_action else None,
                    "referenced_action_name": getattr(referenced_action, "name", None) if referenced_action else None,
                    "child_status": child.status,
                    "parameters_injected": False,  # unknown in reconcile context
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
            # Story 76.5: Retry for non-platform steps (service_call, http_request, evaluation)
            raw_st = getattr(step, "step_type", None) or ""
            step_type_str = (getattr(raw_st, "value", raw_st) or "").lower() if raw_st else ""
            if step_type_str in _RETRYABLE_STEP_TYPES:
                if _retry_non_platform_step(execution, step):
                    reattached_any = True
                # On False: step already marked FAILED inside _retry_non_platform_step
            else:
                # platform, schedule_execution, or unknown — keep FAILED behavior
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

        # Step has a platform_job_id — check if it's a child execution ID (schedule_execution step)
        # Story 76.4: platform_job_id may be a child Execution.id rather than a real platform job ID.
        if _is_child_execution_id(execution, step.platform_job_id):
            if _reconcile_schedule_step(execution, step):
                reattached_any = True
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

    # AC2 Task 2.2: if schedule step(s) were resolved (child COMPLETED), there may be no
    # RUNNING steps left — trigger workflow continuation immediately instead of waiting
    # for the next reconcile run.
    # Story 76.5 fix: do NOT resume if any step FAILED (mixed retry success + retry fail).
    if reattached_any and _is_container_workflow(execution):
        remaining_running = ExecutionStep.objects.filter(
            execution_id=execution_id,
            status=ExecutionStepStatus.RUNNING,
        ).exists()
        has_failed_step = ExecutionStep.objects.filter(
            execution_id=execution_id,
            status=ExecutionStepStatus.FAILED,
        ).exists()
        if not remaining_running and not has_failed_step:
            try:
                result = _resume_container_workflow(
                    execution,
                    correlation_id=getattr(execution, "correlation_id", "") or "",
                )
                return result
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "reconcile_schedule_step_resume_failed",
                    execution_id=execution_id,
                    error=str(exc),
                    exc_info=True,
                )
                # Fall through — we still return "reattached" since we resolved the step
        elif has_failed_step:
            _mark_execution_failed(
                execution,
                "At least one RUNNING step failed retry — marked FAILED by reconciliation.",
            )
            return "failed"

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
