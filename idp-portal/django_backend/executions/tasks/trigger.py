"""
executions/tasks/trigger.py — Tâche Celery pour le trigger asynchrone des jobs plateforme.

Story 47.2 : Remplace l'appel synchrone async_to_sync(adapter.trigger)() dans execute().
Le trigger est dispatché en arrière-plan ; la requête HTTP POST /executions retourne
immédiatement (<2s) sans bloquer sur la latence plateforme (30–60s).

Expose : trigger_platform_job
"""
from typing import Any

import structlog
from celery import shared_task  # type: ignore[import-untyped]

logger = structlog.get_logger("executions.tasks")


@shared_task(bind=True, max_retries=0, name="executions.tasks.trigger_platform_job")
def trigger_platform_job(
    self: Any,
    execution_step_id: int,
    execution_id: int,
    integration_id: int,
    trigger_kwargs: dict,
) -> dict:
    """Tâche Celery async — Story 47.2 : déclenche le job sur la plateforme externe.

    Remplace l'appel synchrone async_to_sync(adapter.trigger)() dans execute().
    Après le trigger réussi, schedule le premier poll via poll_platform_job_status.

    Args:
        execution_step_id: ID de l'ExecutionStep (pour stocker platform_job_id).
        execution_id: ID de l'Execution (pour le poll).
        integration_id: ID de l'Integration (credentials + config adapter).
        trigger_kwargs: Dict des kwargs plateforme-spécifiques
            (correlation_id, template_id, resource_type, extra_vars...).

    Returns:
        {'outcome': 'dispatched', 'platform_job_id': str} en cas de succès.
        {'outcome': 'error', 'error': str} en cas d'échec.
    """
    from asgiref.sync import async_to_sync  # noqa: PLC0415
    import executions.tasks as _tasks  # noqa: PLC0415
    from adapters import get_platform_adapter  # noqa: PLC0415
    from adapters.utils import build_auth_headers  # noqa: PLC0415
    from integrations.models import Integration  # noqa: PLC0415
    from executions.models import ExecutionStep  # noqa: PLC0415
    from executions.tasks.polling import (  # noqa: PLC0415
        poll_platform_job_status, get_platform_queue,
    )
    from executions.models import ExecutionStepStatus  # noqa: PLC0415
    from django.utils import timezone as tz  # noqa: PLC0415

    # Préférer le correlation_id passé depuis le contexte HTTP (execute()) car
    # _tasks.get_correlation_id() retourne None dans le worker Celery (pas de middleware HTTP).
    correlation_id = trigger_kwargs.get("correlation_id") or _tasks.get_correlation_id()

    logger.info(
        "trigger_platform_job_start",
        execution_step_id=execution_step_id,
        execution_id=execution_id,
        integration_id=integration_id,
        correlation_id=correlation_id,
    )

    # Chargement des objets DB
    try:
        integration = Integration.objects.get(id=integration_id)
        execution_step = ExecutionStep.objects.get(id=execution_step_id)
    except (Integration.DoesNotExist, ExecutionStep.DoesNotExist) as exc:
        logger.error(
            "trigger_platform_job_not_found",
            execution_step_id=execution_step_id,
            integration_id=integration_id,
            error=str(exc),
            correlation_id=correlation_id,
        )
        return {"outcome": "error", "error": str(exc)}

    try:
        # S'assurer que correlation_id est présent dans trigger_kwargs (déjà injecté par execute(),
        # mais on le normalise ici pour les appels directs sans correlation_id)
        trigger_kwargs = {**trigger_kwargs, "correlation_id": correlation_id}

        # Construire les headers d'auth (gère Vault, OAuth2, token, basic, etc.)
        auth_headers = build_auth_headers(integration, correlation_id)

        # Extraire platform_kwargs depuis la config de l'integration
        # Même logique que workflow_step_executor.py lignes 404–412
        platform_type = integration.type
        platform_kwargs: dict[str, Any] = {}
        config = integration.get_config() if hasattr(integration, "get_config") else {}
        if config:
            for key in ("owner", "repo", "organization", "namespace"):
                if key in config:
                    platform_kwargs[key] = config[key]
            if "ssl_verify" in config:
                platform_kwargs["ssl_verify"] = config["ssl_verify"]
            if config.get("ca_bundle_path"):
                platform_kwargs["ca_bundle_path"] = config["ca_bundle_path"]

        # Créer l'adapter et appeler trigger()
        adapter = get_platform_adapter(
            platform_type=platform_type,
            base_url=integration.base_url,
            auth_headers=auth_headers,
            **platform_kwargs,
        )
        adapter_result = async_to_sync(adapter.trigger)(**trigger_kwargs)

        # Stocker platform_job_id pour corrélation webhook
        platform_job_id = adapter_result.get("platform_job_id")
        if platform_job_id:
            execution_step.platform_job_id = str(platform_job_id)
            execution_step.save()

        logger.info(
            "trigger_platform_job_success",
            execution_step_id=execution_step_id,
            execution_id=execution_id,
            platform_type=platform_type,
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

        # Scheduler le premier poll
        if platform_job_id:
            poll_platform_job_status.apply_async(
                args=[execution_id, platform_job_id, platform_type],
                kwargs={
                    "base_url": integration.base_url,
                    "credential_ref": getattr(integration, "credential_ref", ""),
                    "auth_flow": getattr(integration, "auth_flow", "token"),
                    "poll_interval": 5,
                    "retry_count": 0,
                },
                queue=get_platform_queue(platform_type),
            )

        return {"outcome": "dispatched", "platform_job_id": platform_job_id}

    except Exception as exc:  # noqa: BLE001 — broad-catch-fail-fast: all adapter errors mark execution INTEGRATION_ERROR with audit trail
        logger.critical(
            "trigger_platform_job_failed",
            execution_step_id=execution_step_id,
            execution_id=execution_id,
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id,
            exc_info=True,
        )
        # Marquer l'étape FAILED (déjà en place depuis fix H2 Story 47.2)
        execution_step.status = ExecutionStepStatus.FAILED
        execution_step.completed_at = tz.now()
        execution_step.error_message = f"{type(exc).__name__}: {str(exc)}"
        execution_step.save()

        # Story 47.3 : fail-fast complet — step FAILED + execution INTEGRATION_ERROR + audit
        from executions.models import Execution, ExecutionStatus  # noqa: PLC0415
        from core.services import AuditService  # noqa: PLC0415
        from core.models import AuditActionType, AuditEntityType  # noqa: PLC0415
        try:
            execution = Execution.objects.get(id=execution_id)
            if execution.status not in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.REJECTED,
            ):
                execution.status = ExecutionStatus.INTEGRATION_ERROR
                execution.save(update_fields=["status"])
            AuditService.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_INTEGRATION_ERROR,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details={
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "step_id": execution_step_id,
                    "adapter": "trigger_platform_job",
                },
                correlation_id=correlation_id,
            )
        except Exception as inner_exc:  # noqa: BLE001 — best-effort audit, ne doit pas masquer l'erreur principale
            logger.error(
                "trigger_platform_job_audit_failed",
                execution_id=execution_id,
                error=str(inner_exc),
                correlation_id=correlation_id,
            )

        return {"outcome": "error", "error": str(exc)}
