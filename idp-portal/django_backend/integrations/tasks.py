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

from typing import TYPE_CHECKING

import structlog
from celery import shared_task  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from integrations.health_check import HealthCheckResult

logger = structlog.get_logger(__name__)

# Correspondance type Integration → type dans les registres
# Les aliases (azuredevops, terraform) sont normalisés vers les clés du registre.
_ADAPTER_TYPE_ALIASES: dict[str, str] = {
    "azuredevops": "azure_devops",
    "terraform": "terraform_cloud",
}

# Types gérés par les adapters (AdapterRegistry)
_ADAPTER_TYPES = {"aap", "tower", "azure_devops", "github_actions", "terraform_cloud"}

# Types gérés par les services (ServiceRegistry)
_SERVICE_TYPES = {"servicenow", "jira", "splunk"}

# Vault est un service à instanciation spéciale (credentials directs)
_VAULT_TYPE = "vault"


def _resolve_and_check_adapter(integration) -> "HealthCheckResult":
    """Instancie l'adapter via AdapterRegistry et appelle health_check()."""
    from asgiref.sync import async_to_sync
    from adapters import get_platform_adapter
    from adapters.utils import build_auth_headers
    from integrations.health_check import IHealthCheckable, HealthCheckStatus, HealthCheckResult
    from django.utils import timezone

    platform_type = _ADAPTER_TYPE_ALIASES.get(integration.type, integration.type)

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

    # github_actions requiert owner/repo depuis le config de l'intégration
    platform_kwargs: dict = {}
    if platform_type == "github_actions":
        config = integration.get_config() or {}
        platform_kwargs["owner"] = config.get("owner", "")
        platform_kwargs["repo"] = config.get("repo", "")

    # terraform_cloud requiert organization depuis le config de l'intégration
    if platform_type == "terraform_cloud":
        config = integration.get_config() or {}
        platform_kwargs["organization"] = config.get("organization", "")

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
        vault_token = ""

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


@shared_task(bind=True, max_retries=0)
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
    # Normaliser aliases
    normalized_type = _ADAPTER_TYPE_ALIASES.get(itype, itype)

    try:
        if normalized_type in _ADAPTER_TYPES:
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
    Integration.objects.filter(id=integration_id).update(
        health_status=result.status.value,
        health_checked_at=result.checked_at,
        health_error_message=result.error_message,
    )

    logger.info(
        "health_check_task_complete",
        integration_id=integration_id,
        integration_type=itype,
        health_status=result.status.value,
    )


@shared_task
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
    for integration_id in integration_ids:
        try:
            run_integration_health_check.delay(integration_id)
            dispatched_count += 1
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
