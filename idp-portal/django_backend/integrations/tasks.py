"""
Story 51.1: Tâche Celery pour le health check des intégrations.

Lance le health check d'une intégration et met à jour les champs health_status,
health_checked_at, health_error_message.

Appelé depuis :
- Le signal post_save(Integration) — à chaque sauvegarde
- Le endpoint POST /api/v1/integrations/{id}/test-connection (Story 51.2)
- La tâche Celery Beat périodique (Story 51.3)
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog
from celery import shared_task  # type: ignore[import-untyped]
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from django.conf import settings

if TYPE_CHECKING:
    from integrations.health_check import HealthCheckResult

from platforms.registry import platform_registry  # Story 82.2: remplace les sets hardcodés

logger = structlog.get_logger(__name__)

# Types gérés par les services (ServiceRegistry)
# Story 82.2 AC3 (partiel): _ADAPTER_TYPES et _ADAPTER_TYPE_ALIASES supprimés.
# _SERVICE_TYPES conservé jusqu'à la création d'un ServiceRegistry (Story à venir).
_SERVICE_TYPES = {"servicenow", "jira", "splunk"}

# Vault est un service à instanciation spéciale (credentials directs)
_VAULT_TYPE = "vault"

_MAX_HEALTH_ERROR_LENGTH = 500


def _sanitize_health_error_message(msg: str | None) -> str | None:
    """Sanitize error message before persisting: strip stack traces, redact URLs, limit length."""
    if not msg or not msg.strip():
        return None
    lines = msg.splitlines()
    # Keep only non-traceback lines (strip "  File ", "Traceback", "  at ")
    kept = [
        line for line in lines
        if not line.strip().startswith("File ") and not line.strip().startswith("Traceback")
        and "  at " not in line[:20]
    ]
    text = " ".join(kept) if kept else msg
    # Redact URLs (http://, https://)
    text = re.sub(r"https?://[^\s]+", "[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _MAX_HEALTH_ERROR_LENGTH:
        text = text[: _MAX_HEALTH_ERROR_LENGTH] + "…"
    return text or None


def _resolve_and_check_adapter(integration) -> "HealthCheckResult":
    """Instancie l'adapter via AdapterRegistry et appelle health_check()."""
    from asgiref.sync import async_to_sync
    from adapters import get_platform_adapter
    from adapters.utils import build_auth_headers
    from integrations.health_check import IHealthCheckable, HealthCheckStatus, HealthCheckResult
    from django.utils import timezone

    # Story 82.2: normalisation via PlatformRegistry (remplace _ADAPTER_TYPE_ALIASES)
    platform_type = platform_registry.resolve_alias(integration.type)

    try:
        auth_headers = build_auth_headers(integration)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "health_check_auth_error",
            integration_id=integration.id,
            integration_type=integration.type,
            error=str(exc),
        )
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur résolution credentials : {exc}",
        )

    # Story 82.2: kwargs runtime extraits via PlatformRegistry (remplace les blocs if hardcodés)
    from adapters.runtime_config import build_platform_runtime_config
    platform_kwargs = build_platform_runtime_config(integration)

    try:
        adapter = get_platform_adapter(
            platform_type=platform_type,
            base_url=integration.base_url,
            auth_headers=auth_headers,
            **platform_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "health_check_adapter_init_error",
            integration_id=integration.id,
            platform_type=platform_type,
            error=str(exc),
        )
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur instanciation adapter : {exc}",
        )

    if not isinstance(adapter, IHealthCheckable):
        return HealthCheckResult(
            status=HealthCheckStatus.UNKNOWN,
            checked_at=timezone.now(),
            error_message="Adapter ne supporte pas IHealthCheckable",
        )

    return async_to_sync(adapter.health_check)()


def _resolve_and_check_service(integration) -> "HealthCheckResult":
    """Instancie le service et appelle health_check()."""
    from asgiref.sync import async_to_sync
    from services import get_service_client
    from adapters.utils import build_auth_headers
    from integrations.health_check import IHealthCheckable, HealthCheckStatus, HealthCheckResult
    from django.utils import timezone

    try:
        auth_headers = build_auth_headers(integration)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "health_check_auth_error",
            integration_id=integration.id,
            integration_type=integration.type,
            error=str(exc),
        )
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur résolution credentials : {exc}",
        )

    try:
        service = get_service_client(
            integration.type,
            base_url=integration.base_url,
            auth_headers=auth_headers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "health_check_service_init_error",
            integration_id=integration.id,
            service_type=integration.type,
            error=str(exc),
        )
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur instanciation service : {exc}",
        )

    if not isinstance(service, IHealthCheckable):
        return HealthCheckResult(
            status=HealthCheckStatus.UNKNOWN,
            checked_at=timezone.now(),
            error_message="Service ne supporte pas IHealthCheckable",
        )

    return async_to_sync(service.health_check)()


def _resolve_and_check_vault(integration) -> "HealthCheckResult":
    """Instancie VaultService ciblant l'intégration vault et appelle health_check()."""
    from asgiref.sync import async_to_sync
    from adapters.utils import resolve_credential
    from services.vault_service import VaultService
    from integrations.health_check import HealthCheckStatus, HealthCheckResult
    from django.utils import timezone

    credential_ref = getattr(integration, "credential_ref", None) or ""
    try:
        vault_token = resolve_credential(credential_ref, integration=integration) if credential_ref else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "health_check_vault_credential_error",
            integration_id=integration.id,
            error=str(exc),
        )
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur résolution credentials : {exc}",
        )

    try:
        vault_svc = VaultService(
            vault_addr=integration.base_url,
            vault_token=vault_token or None,
            instance_id=f"health_check_{integration.id}",
        )
    except Exception as exc:  # noqa: BLE001
        return HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=f"Erreur instanciation VaultService : {exc}",
        )

    return async_to_sync(vault_svc.health_check)()


_HC_LIMITS = settings.CELERY_TASK_TIME_LIMITS["run_integration_health_check"]


@shared_task(
    bind=True,
    max_retries=0,
    soft_time_limit=_HC_LIMITS["soft"],
    time_limit=_HC_LIMITS["hard"],
)
def run_integration_health_check(self, integration_id: int) -> None:
    """Lance le health check d'une intégration et met à jour les champs santé.

    Args:
        integration_id: PK de l'intégration à tester.

    Note:
        Cette tâche ne lève pas d'exception — toutes les erreurs sont capturées et
        enregistrées dans health_status=error, health_error_message=str(exc).
    """
    from integrations.models import Integration
    from integrations.health_check import HealthCheckStatus, HealthCheckResult
    from django.utils import timezone

    logger.info("health_check_task_start", integration_id=integration_id)

    try:
        integration = Integration.objects.get(id=integration_id)
    except Integration.DoesNotExist:
        logger.error("health_check_integration_not_found", integration_id=integration_id)
        return

    itype = integration.type
    # Story 82.2: normalisation via PlatformRegistry (remplace _ADAPTER_TYPE_ALIASES)
    normalized_type = platform_registry.resolve_alias(itype)

    try:
        if platform_registry.is_registered(normalized_type):
            result = _resolve_and_check_adapter(integration)
        elif itype == _VAULT_TYPE:
            result = _resolve_and_check_vault(integration)
        elif itype in _SERVICE_TYPES:
            result = _resolve_and_check_service(integration)
        else:
            # Type non supporté (inventory, inventory_db, etc.) → UNKNOWN
            logger.info(
                "health_check_unsupported_type",
                integration_id=integration_id,
                integration_type=itype,
            )
            result = HealthCheckResult(
                status=HealthCheckStatus.UNKNOWN,
                checked_at=timezone.now(),
                error_message=None,
            )
    except SoftTimeLimitExceeded:
        logger.error(
            "health_check_soft_timeout",
            integration_id=integration_id,
            integration_type=itype,
        )
        # Re-raise so Celery marks the task as FAILURE and time_limit works correctly
        raise
    except Exception as exc:  # noqa: BLE001 — resilience-boundary: tâche health check ne doit JAMAIS lever
        logger.error(
            "health_check_unexpected_error",
            integration_id=integration_id,
            integration_type=itype,
            error=str(exc),
            exc_info=True,
        )
        result = HealthCheckResult(
            status=HealthCheckStatus.ERROR,
            checked_at=timezone.now(),
            error_message=str(exc),
        )

    # Mise à jour des champs health check — update direct pour éviter les signaux imbriqués
    sanitized_error = _sanitize_health_error_message(result.error_message)
    Integration.objects.filter(id=integration_id).update(
        health_status=result.status.value,
        health_checked_at=result.checked_at,
        health_error_message=sanitized_error,
    )

    logger.info(
        "health_check_task_complete",
        integration_id=integration_id,
        integration_type=itype,
        health_status=result.status.value,
    )


_HC_ALL_LIMITS = settings.CELERY_TASK_TIME_LIMITS["health_check_all_integrations"]


@shared_task(
    soft_time_limit=_HC_ALL_LIMITS["soft"],
    time_limit=_HC_ALL_LIMITS["hard"],
)
def health_check_all_integrations() -> None:
    """Lance le health check périodique de toutes les intégrations.

    Tâche Celery Beat — schedule configuré dans idp_backend/celery.py.
    Dispatche run_integration_health_check.delay(id) pour chaque intégration.

    Note:
        Cette tâche ne lève pas d'exception — toutes les erreurs sont capturées.
    """
    from integrations.models import Integration

    try:
        logger.info("health_check_all_start")
        integration_ids = list(Integration.objects.all().only('id').values_list('id', flat=True))
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "health_check_all_query_error",
            error=str(exc),
            exc_info=True,
        )
        return

    dispatched_count = 0
    total = len(integration_ids)
    for integration_id in integration_ids:
        try:
            run_integration_health_check.delay(integration_id)
            dispatched_count += 1
        except SoftTimeLimitExceeded:
            logger.warning(
                "health_check_all_soft_timeout",
                dispatched=dispatched_count,
                total=total,
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "health_check_all_dispatch_error",
                integration_id=integration_id,
                error=str(exc),
            )

    logger.info(
        "health_check_all_dispatched",
        count=dispatched_count,
    )


_WARMUP_LIMITS = settings.CELERY_TASK_TIME_LIMITS["warmup_vault_secrets_cache"]


@shared_task(
    soft_time_limit=_WARMUP_LIMITS["soft"],
    time_limit=_WARMUP_LIMITS["hard"],
)
def warmup_vault_secrets_cache() -> dict[str, int]:
    """Pre-load Vault secrets for all integrations into the in-memory cache.

    Celery Beat task — runs periodically to keep the TTL cache warm so that
    execution requests hit the cache instead of calling Vault.

    Also callable at worker startup via ``warmup_vault_secrets_cache.delay()``.

    Returns:
        Dict with counts: {"total", "ok", "errors", "skipped"}.
    """
    import os

    enabled = os.getenv("VAULT_CACHE_WARMUP", "true").lower() in ("true", "1")
    if not enabled:
        logger.info("vault_cache_warmup_disabled")
        return {"total": 0, "ok": 0, "errors": 0, "skipped": 0}

    from services.vault_service import warmup_vault_cache

    try:
        return warmup_vault_cache()
    except SoftTimeLimitExceeded:
        logger.warning("warmup_vault_secrets_cache_soft_timeout")
        # Counters unknown — warmup_vault_cache() does not expose partial progress
        return {"total": -1, "ok": -1, "errors": -1, "skipped": -1}
