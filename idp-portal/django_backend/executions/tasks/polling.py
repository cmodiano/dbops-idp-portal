"""
executions/tasks/polling.py — Responsabilité unique : surveillance asynchrone des jobs
sur les plateformes externes.

Story 34.5 (SOLID-BE-3): OCP — une seule tâche générique `poll_platform_job_status`
délègue à l'AdapterRegistry (Story 33.1). Les 5 tâches nommées sont des shims
backward-compatibles (≤ 15 lignes chacun). Ajouter une plateforme ne nécessite
aucune modification de ce fichier.

Expose : poll_platform_job_status (générique), poll_aap_job_status, poll_tower_job_status,
         poll_azure_devops_run_status, poll_github_actions_run_status,
         poll_terraform_cloud_run_status, MAX_POLLING_RETRIES
"""
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from django.utils import timezone

from executions.models import (
    Execution, ExecutionStatus,
    ExecutionStep, ExecutionStepStatus,
)
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)


def get_platform_queue(platform_type: str) -> str:
    """Story 47.4: Resolve Celery queue for platform_type from AdapterRegistry.

    Replaces hardcoded PLATFORM_QUEUE_MAP. Returns 'default' for unknown types.
    Adding a new platform only requires registering it in adapters/__init__.py.
    """
    from adapters.registry import adapter_registry  # noqa: PLC0415
    return adapter_registry.get_queue(platform_type)

# Story 30.7 (RACE-1): Maximum polling retries before marking execution as FAILED.
# 20 retries × 5s default interval ≈ 100s minimum; sufficient for transient failures.
MAX_POLLING_RETRIES = 20


def _mark_execution_polling_exhausted(
    execution_id: int,
    platform_job_id: str,
    retry_count: int,
    error: str,
    correlation_id: str | None = None,
) -> None:
    """
    Story 30.7 (RACE-1): Mark execution as FAILED when polling retries are exhausted.
    Creates an audit entry with EXECUTION_POLLING_EXHAUSTED action type.
    """
    logger.error(
        "polling_exhausted",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        error=error,
        correlation_id=correlation_id,
    )

    try:
        execution = Execution.objects.get(id=execution_id)
        terminal_statuses = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

        if execution.status not in terminal_statuses:
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = timezone.now()
            execution.save()

        # Update the platform step with error
        platform_step = ExecutionStep.objects.filter(
            execution_id=execution_id,
            platform_job_id=platform_job_id,
        ).first()
        if platform_step and platform_step.status not in {
            ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED
        }:
            platform_step.status = ExecutionStepStatus.FAILED
            platform_step.error_message = f"Polling exhausted after {retry_count} retries: {error}"
            platform_step.completed_at = timezone.now()
            platform_step.save()

        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_POLLING_EXHAUSTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                'platform_job_id': platform_job_id,
                'retry_count': retry_count,
                'max_retries': MAX_POLLING_RETRIES,
                'last_error': error,
            },
            correlation_id=correlation_id,
        )
    except Execution.DoesNotExist:
        logger.warning(
            "polling_exhausted_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:  # noqa: BLE001 — resilience-boundary: polling exhausted update error logged, task completes
        logger.error(
            "polling_exhausted_update_error",
            execution_id=execution_id,
            error=str(exc),
            correlation_id=correlation_id,
            exc_info=True,
        )


def _broadcast_execution_update(
    execution_id: int,
    status_data: dict,
    logs_data: dict,
    is_terminal: bool,
    correlation_id: str | None = None,
) -> None:
    """Broadcast status and log updates to the execution's WebSocket group."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        group_name = f"execution_{execution_id}"

        # Send status update
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "status_update",
                "data": {
                    "execution_id": execution_id,
                    "status": status_data.get("status"),
                    "aap_status": status_data.get("aap_status"),
                    "started": status_data.get("started"),
                    "finished": status_data.get("finished"),
                },
            },
        )

        # Send log update
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "log_update",
                "data": {
                    "execution_id": execution_id,
                    "content": logs_data.get("content", ""),
                    "complete": logs_data.get("complete", False),
                    "timestamp": logs_data.get("timestamp"),
                },
            },
        )

        # Send terminal event
        if is_terminal:
            event_type = "execution_complete" if status_data.get("status") == "COMPLETED" else "execution_failed"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": event_type,
                    "data": {
                        "execution_id": execution_id,
                        "status": status_data.get("status"),
                        "aap_status": status_data.get("aap_status"),
                        "finished": status_data.get("finished"),
                    },
                },
            )
    except ImportError:
        logger.debug("poll_broadcast_skipped_no_channels", execution_id=execution_id)
    except Exception as e:  # noqa: BLE001 — best-effort-non-critical: channels broadcast is non-critical, polling must not be interrupted
        logger.warning(
            "poll_broadcast_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )


def _update_execution_from_poll(
    execution_id: int,
    platform_job_id: str,
    idp_status: str,
    logs_content: str,
    correlation_id: str | None = None,
    output_fields: dict | None = None,
) -> None:
    """Update execution and step records based on polling results."""
    try:
        execution = Execution.objects.get(id=execution_id)

        # Update execution status if it changed
        current_status = execution.status
        terminal_statuses = {ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}

        if current_status not in terminal_statuses and idp_status != current_status:
            from executions.services import ExecutionService
            svc = ExecutionService()
            try:
                svc.update_status(execution_id, idp_status, str(execution.user_id))
            except ValueError as ve:
                logger.warning(
                    "poll_status_transition_invalid",
                    execution_id=execution_id,
                    current=current_status,
                    target=idp_status,
                    error=str(ve),
                    correlation_id=correlation_id,
                )

        # Update platform step logs and output fields
        platform_step = (
            ExecutionStep.objects.filter(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
            ).first()
        )
        if platform_step:
            output = platform_step.get_output() or {}
            if logs_content:
                output["platform_logs"] = logs_content
            # Stocker les champs AAP standard si fournis
            if output_fields:
                output.update(output_fields)
            if logs_content or output_fields:
                platform_step.set_output(output)
                platform_step.save()

    except Execution.DoesNotExist:
        logger.warning(
            "poll_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as e:  # noqa: BLE001 — resilience-boundary: poll update error logged, Celery task completes gracefully
        logger.error(
            "poll_update_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )


def _forward_platform_logs_to_splunk(
    execution_id: int,
    platform_job_id: str,
    platform_type: str,
    logs_content: str,
    correlation_id: str | None = None,
) -> None:
    """Forward platform logs to Splunk HEC at terminal state (best-effort).

    Silently skipped when no active Splunk integration is configured.
    """
    if not logs_content:
        return

    try:
        from services.splunk_utils import get_splunk_service  # noqa: PLC0415
        from asgiref.sync import async_to_sync  # noqa: PLC0415

        splunk_client = get_splunk_service(correlation_id=correlation_id)
        if splunk_client is None:
            logger.debug(
                "splunk_integration_not_configured",
                execution_id=execution_id,
                correlation_id=correlation_id,
            )
            return

        async_to_sync(splunk_client.send_event)(
            event={
                "event": "platform_log",
                "execution_id": execution_id,
                "platform_job_id": platform_job_id,
                "platform_type": platform_type,
                "content": logs_content,
                "correlation_id": correlation_id,
            },
            sourcetype="idp:platform_log",
            correlation_id=correlation_id,
        )
        logger.info(
            "platform_logs_forwarded_to_splunk",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort: Splunk forwarding must never interrupt polling
        logger.warning(
            "platform_logs_splunk_forward_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Story 34.5 (SOLID-BE-3): Tâche Celery générique — OCP poller
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_platform_job_status")
def poll_platform_job_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    platform_type: str,
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "token",
    poll_interval: int = 5,
    retry_count: int = 0,
    adapter_kwargs: dict | None = None,
    poll_kwargs: dict | None = None,
) -> dict:
    """
    Story 34.5 (SOLID-BE-3): Tâche de polling générique OCP.

    Construit l'adapter via AdapterRegistry (get_platform_adapter), interroge
    get_status() + get_job_logs(), et détecte la terminaison via
    logs_data["complete"] — contrat BaseAdapter garanti pour tous les adapters.

    Aucun if/elif sur platform_type : l'ajout d'une nouvelle plateforme ne
    nécessite aucune modification de ce fichier (OCP).

    Args:
        execution_id: ID de l'exécution IDP Portal.
        platform_job_id: ID du job sur la plateforme externe.
        platform_type: Identifiant plateforme ('aap', 'tower', 'azure_devops',
            'github_actions', 'terraform_cloud', ...).
        base_url: URL de base de la plateforme.
        credential_ref: Référence de credential pour l'auth.
        auth_flow: Type de flux d'authentification (token, basic, pat).
        poll_interval: Secondes entre deux polls (défaut 5).
        retry_count: Compteur d'erreurs consécutives (Story 30.7 RACE-1).
        adapter_kwargs: Kwargs spécifiques à l'adapter (ssl_verify, owner, etc.).
        poll_kwargs: Kwargs transmis à get_status() et get_job_logs()
            (resource_type, pipeline_id, etc.).

    Returns:
        dict avec outcome: 'complete' | 'polling' | 'error' | 'exhausted'.
    """
    from asgiref.sync import async_to_sync  # noqa: PLC0415
    import executions.tasks as _tasks  # noqa: PLC0415

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_platform_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type=platform_type,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters import get_platform_adapter  # noqa: PLC0415
        from adapters.utils import build_auth_headers_from_credentials  # noqa: PLC0415

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = get_platform_adapter(
            platform_type=platform_type,
            base_url=base_url,
            auth_headers=auth_headers,
            **(adapter_kwargs or {}),
        )

        status_data = async_to_sync(adapter.get_status)(
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
            **(poll_kwargs or {}),
        )
        logs_data = async_to_sync(adapter.get_job_logs)(
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
            **(poll_kwargs or {}),
        )
    except Exception as e:  # noqa: BLE001 — resilience-boundary: adapter error logged, polling returns error outcome
        logger.error(
            "poll_platform_job_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            platform_type=platform_type,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
            exc_info=True,
        )
        # Story 30.7 (RACE-1): Check max retries before re-scheduling
        if retry_count >= MAX_POLLING_RETRIES:
            _tasks._mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_platform_job_status.apply_async(
            args=[execution_id, platform_job_id, platform_type],
            kwargs={
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
                "adapter_kwargs": adapter_kwargs,
                "poll_kwargs": poll_kwargs,
            },
            countdown=poll_interval,
            queue=get_platform_queue(platform_type),
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    # AC2: détection terminale unifiée via contrat BaseAdapter.get_job_logs()
    is_terminal = logs_data.get("complete", False)

    # Broadcast updates via Django Channels
    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    # Construire les champs de plateforme à stocker dans l'output du step
    platform_status = status_data.get("aap_status") or status_data.get("status")
    artifacts_raw = status_data.get("artifacts")
    artifacts = artifacts_raw if artifacts_raw is not None else {}
    failed_tasks = status_data.get("failed_tasks") or []
    changed_hosts = status_data.get("changed_hosts") or []
    outputs = status_data.get("outputs") or {}
    job_conclusion = status_data.get("job_conclusion")

    error_summary = None
    if failed_tasks and isinstance(failed_tasks, list) and len(failed_tasks) > 0:
        first = failed_tasks[0]
        if isinstance(first, dict):
            task_name = first.get("task") or first.get("name") or ""
            host_name = first.get("host") or ""
            if task_name:
                error_summary = f"{task_name} sur {host_name}" if host_name else task_name

    output_fields: dict = {
        "platform_job_id": platform_job_id,
        "job_status": platform_status,
        "artifacts": artifacts,
    }
    if error_summary:
        output_fields["error_summary"] = error_summary
    if failed_tasks:
        output_fields["failed_tasks"] = failed_tasks
    if changed_hosts:
        output_fields["changed_hosts"] = changed_hosts
    if outputs:
        output_fields["outputs"] = outputs
    if job_conclusion is not None:
        output_fields["job_conclusion"] = job_conclusion

    # Update execution step status in DB
    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
        output_fields=output_fields,
    )

    if is_terminal:
        logger.info(
            "poll_platform_job_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            platform_type=platform_type,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        _tasks._forward_platform_logs_to_splunk(
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            platform_type=platform_type,
            logs_content=logs_data.get("content", ""),
            correlation_id=correlation_id,
        )
        return {"outcome": "complete", "status": idp_status}

    # Re-schedule next poll (reset retry_count on success)
    poll_platform_job_status.apply_async(
        args=[execution_id, platform_job_id, platform_type],
        kwargs={
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
            "adapter_kwargs": adapter_kwargs,
            "poll_kwargs": poll_kwargs,
        },
        countdown=poll_interval,
        queue=get_platform_queue(platform_type),
    )

    logger.info(
        "poll_platform_job_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type=platform_type,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {"outcome": "polling", "status": idp_status}


# ---------------------------------------------------------------------------
# Backward-compat shims (Story 34.5 AC3) — ≤ 15 lignes chacun
# Les noms Celery sont inchangés ; chaque shim traduit ses paramètres
# spécifiques et délègue directement à poll_platform_job_status (synchrone).
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_aap_job_status")
def poll_aap_job_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    resource_type: str = "job_template",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "token",
    poll_interval: int = 5,
    retry_count: int = 0,
    ssl_verify: bool = True,
    ca_bundle_path: str | None = None,
) -> Any:
    """Story 34.5: Shim backward-compat — délègue à poll_platform_job_status."""
    return poll_platform_job_status(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type="aap",
        base_url=base_url,
        credential_ref=credential_ref,
        auth_flow=auth_flow,
        poll_interval=poll_interval,
        retry_count=retry_count,
        adapter_kwargs={"ssl_verify": ssl_verify, "ca_bundle_path": ca_bundle_path},
        poll_kwargs={"resource_type": resource_type},
    )


@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_tower_job_status")
def poll_tower_job_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    resource_type: str = "job_template",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "token",
    poll_interval: int = 5,
    retry_count: int = 0,
) -> Any:
    """Story 34.5: Shim backward-compat — délègue à poll_platform_job_status."""
    return poll_platform_job_status(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type="tower",
        base_url=base_url,
        credential_ref=credential_ref,
        auth_flow=auth_flow,
        poll_interval=poll_interval,
        retry_count=retry_count,
        adapter_kwargs={},
        poll_kwargs={"resource_type": resource_type},
    )


@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_azure_devops_run_status")
def poll_azure_devops_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    pipeline_id: str = "",
    base_url: str = "",
    credential_ref: str = "",
    auth_flow: str = "basic",
    poll_interval: int = 5,
    retry_count: int = 0,
) -> Any:
    """Story 34.5: Shim backward-compat — délègue à poll_platform_job_status."""
    return poll_platform_job_status(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type="azure_devops",
        base_url=base_url,
        credential_ref=credential_ref,
        auth_flow=auth_flow,
        poll_interval=poll_interval,
        retry_count=retry_count,
        adapter_kwargs={},
        poll_kwargs={"pipeline_id": pipeline_id},
    )


@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_github_actions_run_status")
def poll_github_actions_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    owner: str = "",
    repo: str = "",
    base_url: str = "",
    credential_ref: str = "",
    poll_interval: int = 60,
    retry_count: int = 0,
) -> Any:
    """Story 34.5: Shim backward-compat — délègue à poll_platform_job_status."""
    return poll_platform_job_status(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type="github_actions",
        base_url=base_url,
        credential_ref=credential_ref,
        auth_flow="token",
        poll_interval=poll_interval,
        retry_count=retry_count,
        adapter_kwargs={"owner": owner, "repo": repo},
        poll_kwargs={},
    )


@shared_task(bind=True, max_retries=0, name="executions.tasks.poll_terraform_cloud_run_status")
def poll_terraform_cloud_run_status(
    self: Any,
    execution_id: int,
    platform_job_id: str,
    organization: str = "",
    base_url: str = "",
    credential_ref: str = "",
    poll_interval: int = 60,
    retry_count: int = 0,
) -> Any:
    """Story 34.5: Shim backward-compat — délègue à poll_platform_job_status."""
    return poll_platform_job_status(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        platform_type="terraform_cloud",
        base_url=base_url,
        credential_ref=credential_ref,
        auth_flow="token",
        poll_interval=poll_interval,
        retry_count=retry_count,
        adapter_kwargs={"organization": organization},
        poll_kwargs={},
    )
