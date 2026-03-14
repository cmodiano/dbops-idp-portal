"""
Service factory for consumed services (Vault, Splunk, ServiceNow, etc.).

Story 27.9: Services are systems consumed by the portal or adapters for
utility functions (secrets, logging, ITSM). They do NOT execute jobs.

Story 33.1: OCP — replaced if/elif chains with ServiceRegistry.
  New services are registered here; get_service_client() delegates to
  the registry without any if/elif.

Distinction:
- Platform adapters (adapters/): Execute jobs/workflows on remote platforms
  (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud).
  Use get_platform_adapter() from adapters/__init__.py.
- Services (services/): Consumed by the portal for utility functions
  (Vault secrets, Splunk logging, ServiceNow ITSM).
  Use get_service_client() from this module.
"""
from __future__ import annotations

from typing import Any

from services.definitions import ServiceDefinition, service_definition_registry
from services.registry import service_registry


# ---------------------------------------------------------------------------
# Factory functions — lazy imports to avoid circular dependencies
# ---------------------------------------------------------------------------

def _factory_vault(**config: Any) -> Any:
    from services.vault_service import VaultService
    return VaultService(**config)


def _factory_splunk(**config: Any) -> Any:
    from services.splunk_service import SplunkService
    return SplunkService(**config)


def _factory_servicenow(**config: Any) -> Any:
    from services.servicenow_service import ServiceNowService
    return ServiceNowService(**config)


def _factory_jira(**config: Any) -> Any:
    from services.jira_service import JiraService
    return JiraService(**config)


def _factory_notification(**config: Any) -> Any:
    from services.notification_service import NotificationService
    return NotificationService(**config)


# ---------------------------------------------------------------------------
# Registration — add new services here, never touch get_service_client()
# ---------------------------------------------------------------------------

service_registry.register("vault", _factory_vault)
service_registry.register("splunk", _factory_splunk)
service_registry.register("servicenow", _factory_servicenow)
service_registry.register("jira", _factory_jira)
service_registry.register("notification", _factory_notification)

# ---------------------------------------------------------------------------
# ServiceDefinition registry — source de vérité pour opérations, credential-free,
# et health check routing. Story 82.3.
# ---------------------------------------------------------------------------

service_definition_registry.register(ServiceDefinition(
    code="vault",
    display_name="HashiCorp Vault",
    requires_integration=True,
    operations=frozenset({"get_secret"}),
    supports_health_check=True,
))
service_definition_registry.register(ServiceDefinition(
    code="splunk",
    display_name="Splunk",
    requires_integration=True,
    operations=frozenset(),
    supports_health_check=True,
))
service_definition_registry.register(ServiceDefinition(
    code="servicenow",
    display_name="ServiceNow",
    requires_integration=True,
    operations=frozenset({
        "create_change", "update_change", "close_change",
        "get_change_status", "cancel_change",
    }),
    supports_health_check=True,
))
service_definition_registry.register(ServiceDefinition(
    code="jira",
    display_name="Jira",
    requires_integration=True,
    operations=frozenset({"create_issue", "update_issue", "get_issue"}),
    supports_health_check=True,
))
service_definition_registry.register(ServiceDefinition(
    code="notification",
    display_name="Notification",
    requires_integration=False,
    operations=frozenset({"send_email", "send_teams", "notify_execution_event"}),
    supports_health_check=False,
))


# ---------------------------------------------------------------------------
# Public API — signature and SERVICE_TYPES dict unchanged (backward-compatible)
# ---------------------------------------------------------------------------

# Story 82.3: SERVICE_TYPES dérivé depuis service_definition_registry (source de vérité).
# Conservé pour la compatibilité avec test_factories.py et autres consommateurs.
# Les consommateurs qui ont besoin des métadonnées complètes doivent utiliser
# service_definition_registry directement.
SERVICE_TYPES: dict[str, str] = {
    code: code for code in service_definition_registry.list_types()
}

# Guard: detect drift between SERVICE_TYPES and service_registry at import time.
# Story 82.3: le guard est maintenant basé sur service_definition_registry (source de vérité).
_registry_types = set(service_registry.list_types())
_definition_types = set(service_definition_registry.list_types())
assert _registry_types == _definition_types, (
    f"service_registry and service_definition_registry are out of sync. "
    f"service_registry-only: {_registry_types - _definition_types}, "
    f"service_definition_registry-only: {_definition_types - _registry_types}"
)
del _registry_types, _definition_types


# Re-exported for consumers who need to register custom services at runtime.
# Preferred over importing from services.registry directly.
__all__ = ["get_service_client", "SERVICE_TYPES", "service_registry", "service_definition_registry", "ServiceDefinition"]


def get_service_client(
    service_type: str,
    **config: Any,
) -> Any:
    """Factory to instantiate the correct service client for a given service type.

    Delegates to service_registry — no if/elif.

    Args:
        service_type: Service identifier ('vault', 'splunk', 'servicenow',
            'jira', or 'notification').
        **config: Service-specific configuration (base_url, auth_headers, etc.).

    Returns:
        Service client instance.

    Raises:
        ValueError: If service_type is not supported.
    """
    return service_registry.get(service_type, **config)
