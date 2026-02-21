"""
executions/tasks/polling.py — Responsabilité unique : surveillance asynchrone des jobs
sur 5 plateformes externes (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud).

Pattern commun : asyncio.run() pour appels adapters async. Adapters importés en lazy
dans chaque tâche pour éviter les imports circulaires.

Expose : poll_aap_job_status, poll_tower_job_status, poll_azure_devops_run_status,
         poll_github_actions_run_status, poll_terraform_cloud_run_status,
         MAX_POLLING_RETRIES
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
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType

logger = structlog.get_logger(__name__)

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
    except Exception as exc:
        logger.error(
            "polling_exhausted_update_error",
            execution_id=execution_id,
            error=str(exc),
            correlation_id=correlation_id,
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
        from channels.layers import get_channel_layer  # type: ignore[import-untyped]
        from asgiref.sync import async_to_sync  # type: ignore[import-untyped]

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
    except Exception as e:
        logger.warning(
            "poll_broadcast_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )


def _update_execution_from_poll(
    execution_id: int,
    platform_job_id: str,
    idp_status: str,
    logs_content: str,
    correlation_id: str | None = None,
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
                    "poll_aap_status_transition_invalid",
                    execution_id=execution_id,
                    current=current_status,
                    target=idp_status,
                    error=str(ve),
                    correlation_id=correlation_id,
                )

        # Update platform step logs
        platform_step = (
            ExecutionStep.objects.filter(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
            ).first()
        )
        if platform_step and logs_content:
            output = platform_step.get_output() or {}
            output["aap_logs"] = logs_content
            platform_step.set_output(output)
            platform_step.save()

    except Execution.DoesNotExist:
        logger.warning(
            "poll_aap_execution_not_found",
            execution_id=execution_id,
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.error(
            "poll_aap_update_error",
            execution_id=execution_id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Story 27.1: AAP job monitoring polling task
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
) -> dict:
    """
    Story 27.1 (AC4): Poll AAP for job status and logs, then broadcast
    updates via Django Channels to the execution's WebSocket group.

    Story 30.7 (RACE-1): Added retry_count / MAX_POLLING_RETRIES to prevent
    infinite re-scheduling on persistent adapter errors.

    Args:
        execution_id: IDP Portal execution ID.
        platform_job_id: AAP job ID to monitor.
        resource_type: 'job_template' or 'workflow_job'.
        base_url: AAP base URL (from integration).
        credential_ref: Credential reference for auth.
        auth_flow: Auth flow type (token, basic, pat).
        poll_interval: Seconds between polls (default 5).
        retry_count: Current error retry count (Story 30.7).

    Returns:
        dict with final status information.
    """
    import asyncio
    # Access through package namespace for testability:
    # allows @patch("executions.tasks.get_correlation_id") etc. to intercept
    import executions.tasks as _tasks

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_aap_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        resource_type=resource_type,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        # Build adapter
        from adapters.aap_adapter import AAPAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = AAPAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            ssl_verify=ssl_verify,
            ca_bundle_path=ca_bundle_path,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_aap_job_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
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
        poll_aap_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
                "ssl_verify": ssl_verify,
                "ca_bundle_path": ca_bundle_path,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    aap_status = status_data.get("aap_status", "unknown")
    is_terminal = aap_status in {"successful", "failed", "error", "canceled"}

    # Broadcast updates via Django Channels
    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    # Update execution step status in DB
    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_aap_job_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=aap_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {"outcome": "complete", "status": idp_status, "aap_status": aap_status}

    # Re-schedule next poll (reset retry_count on success)
    poll_aap_job_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "resource_type": resource_type,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
            "ssl_verify": ssl_verify,
            "ca_bundle_path": ca_bundle_path,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_aap_job_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        aap_status=aap_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {"outcome": "polling", "status": idp_status, "aap_status": aap_status}


# ---------------------------------------------------------------------------
# Story 27.2: Tower/AWX job monitoring polling task
# ---------------------------------------------------------------------------

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
) -> dict:
    """
    Story 27.2 (AC4): Poll Tower/AWX for job status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio
    # Access through package namespace for testability
    import executions.tasks as _tasks

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_tower_job_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        resource_type=resource_type,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.tower_adapter import TowerAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = TowerAdapter(base_url=base_url, auth_headers=auth_headers)

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                resource_type=resource_type,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_tower_job_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _tasks._mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_tower_job_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "resource_type": resource_type,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    tower_status = status_data.get("tower_status", "unknown")
    is_terminal = tower_status in {"successful", "failed", "error", "canceled"}

    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_tower_job_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=tower_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {"outcome": "complete", "status": idp_status, "tower_status": tower_status}

    poll_tower_job_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "resource_type": resource_type,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_tower_job_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        tower_status=tower_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {"outcome": "polling", "status": idp_status, "tower_status": tower_status}


# ---------------------------------------------------------------------------
# Story 27.3: Azure DevOps pipeline run monitoring polling task
# ---------------------------------------------------------------------------

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
) -> dict:
    """
    Story 27.3 (AC4): Poll Azure DevOps for pipeline run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio
    # Access through package namespace for testability
    import executions.tasks as _tasks

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_azure_devops_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        pipeline_id=pipeline_id,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.azure_devops_adapter import AzureDevOpsAdapter
        from adapters.utils import build_auth_headers_from_credentials

        auth_headers = build_auth_headers_from_credentials(credential_ref, auth_flow)
        adapter = AzureDevOpsAdapter(base_url=base_url, auth_headers=auth_headers)

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                pipeline_id=pipeline_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                pipeline_id=pipeline_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_azure_devops_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _tasks._mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_azure_devops_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "pipeline_id": pipeline_id,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "auth_flow": auth_flow,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    azure_state = status_data.get("azure_devops_state", "inProgress")
    azure_result = status_data.get("azure_devops_result")
    is_terminal = azure_state == "completed" and azure_result in {
        "succeeded", "failed", "canceled"
    }

    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_azure_devops_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_state=azure_state,
            final_result=azure_result,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "azure_devops_state": azure_state,
            "azure_devops_result": azure_result,
        }

    poll_azure_devops_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "pipeline_id": pipeline_id,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "auth_flow": auth_flow,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_azure_devops_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        azure_devops_state=azure_state,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "azure_devops_state": azure_state,
        "azure_devops_result": azure_result,
    }


# ---------------------------------------------------------------------------
# Story 27.4: GitHub Actions polling task (catch-up fallback for webhooks)
# ---------------------------------------------------------------------------

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
) -> dict:
    """
    Story 27.4 (AC4): Poll GitHub Actions for workflow run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio
    # Access through package namespace for testability
    import executions.tasks as _tasks

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_github_actions_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        owner=owner,
        repo=repo,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.github_actions_adapter import GitHubActionsAdapter

        auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = GitHubActionsAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            owner=owner,
            repo=repo,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_github_actions_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _tasks._mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_github_actions_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "owner": owner,
                "repo": repo,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    gh_status = status_data.get("github_actions_status", "queued")
    gh_conclusion = status_data.get("github_actions_conclusion")
    is_terminal = gh_status == "completed" and gh_conclusion in {
        "success", "failure", "cancelled", "timed_out", "skipped"
    }

    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_github_actions_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            final_status=gh_status,
            final_conclusion=gh_conclusion,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "github_actions_status": gh_status,
            "github_actions_conclusion": gh_conclusion,
        }

    poll_github_actions_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "owner": owner,
            "repo": repo,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_github_actions_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        github_actions_status=gh_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "github_actions_status": gh_status,
        "github_actions_conclusion": gh_conclusion,
    }


# ---------------------------------------------------------------------------
# Story 27.5: Terraform Cloud polling task (catch-up fallback for webhooks)
# ---------------------------------------------------------------------------

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
) -> dict:
    """
    Story 27.5 (AC4): Poll Terraform Cloud for run status and logs.
    Story 30.7 (RACE-1): retry_count / MAX_POLLING_RETRIES.
    """
    import asyncio
    # Access through package namespace for testability
    import executions.tasks as _tasks

    correlation_id = _tasks.get_correlation_id()

    logger.info(
        "poll_terraform_cloud_run_status_start",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        organization=organization,
        retry_count=retry_count,
        max_retries=MAX_POLLING_RETRIES,
        correlation_id=correlation_id,
    )

    try:
        from adapters.terraform_cloud_adapter import (
            TerraformCloudAdapter,
            TERRAFORM_CLOUD_TERMINAL_STATUSES,
        )

        auth_headers = {"Authorization": f"Bearer {credential_ref}"}

        adapter = TerraformCloudAdapter(
            base_url=base_url,
            auth_headers=auth_headers,
            organization=organization,
        )

        # Story 30.7 (CELERY-3): Use asyncio.run() instead of manual event loop
        status_data = asyncio.run(
            adapter.get_status(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )

        logs_data = asyncio.run(
            adapter.get_job_logs(
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
            )
        )
    except Exception as e:
        logger.error(
            "poll_terraform_cloud_run_status_adapter_error",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            error=str(e),
            error_type=type(e).__name__,
            retry_count=retry_count,
            max_retries=MAX_POLLING_RETRIES,
            correlation_id=correlation_id,
        )
        if retry_count >= MAX_POLLING_RETRIES:
            _tasks._mark_execution_polling_exhausted(
                execution_id=execution_id,
                platform_job_id=platform_job_id,
                retry_count=retry_count,
                error=str(e),
                correlation_id=correlation_id,
            )
            return {"outcome": "exhausted", "error": str(e), "retry_count": retry_count}
        poll_terraform_cloud_run_status.apply_async(
            args=[execution_id, platform_job_id],
            kwargs={
                "organization": organization,
                "base_url": base_url,
                "credential_ref": credential_ref,
                "poll_interval": poll_interval,
                "retry_count": retry_count + 1,
            },
            countdown=poll_interval,
        )
        return {"outcome": "error", "error": str(e), "retry_count": retry_count}

    idp_status = status_data.get("status", "SUBMITTED")
    tc_status = status_data.get("terraform_cloud_status", "pending")
    is_terminal = tc_status in TERRAFORM_CLOUD_TERMINAL_STATUSES

    _tasks._broadcast_execution_update(
        execution_id=execution_id,
        status_data=status_data,
        logs_data=logs_data,
        is_terminal=is_terminal,
        correlation_id=correlation_id,
    )

    _tasks._update_execution_from_poll(
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        idp_status=idp_status,
        logs_content=logs_data.get("content", ""),
        correlation_id=correlation_id,
    )

    if is_terminal:
        logger.info(
            "poll_terraform_cloud_run_status_complete",
            execution_id=execution_id,
            platform_job_id=platform_job_id,
            terraform_cloud_status=tc_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )
        return {
            "outcome": "complete",
            "status": idp_status,
            "terraform_cloud_status": tc_status,
        }

    poll_terraform_cloud_run_status.apply_async(
        args=[execution_id, platform_job_id],
        kwargs={
            "organization": organization,
            "base_url": base_url,
            "credential_ref": credential_ref,
            "poll_interval": poll_interval,
            "retry_count": 0,
        },
        countdown=poll_interval,
    )

    logger.info(
        "poll_terraform_cloud_run_status_rescheduled",
        execution_id=execution_id,
        platform_job_id=platform_job_id,
        terraform_cloud_status=tc_status,
        next_poll_in=poll_interval,
        correlation_id=correlation_id,
    )

    return {
        "outcome": "polling",
        "status": idp_status,
        "terraform_cloud_status": tc_status,
    }
