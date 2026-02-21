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
# Public API — signature and SERVICE_TYPES dict unchanged (backward-compatible)
# ---------------------------------------------------------------------------

# Kept in sync with the registry — test_service_types_registry() verifies len == 5
# WARNING: Adding a service to the registry MUST be accompanied by an entry here.
SERVICE_TYPES: dict[str, str] = {
    "vault": "services.vault_service.VaultService",
    "splunk": "services.splunk_service.SplunkService",
    "servicenow": "services.servicenow_service.ServiceNowService",
    "jira": "services.jira_service.JiraService",
    "notification": "services.notification_service.NotificationService",
}

# Guard: detect drift between SERVICE_TYPES and the registry at import time.
_registry_types = set(service_registry.list_types())
_declared_types = set(SERVICE_TYPES.keys())
assert _registry_types == _declared_types, (
    f"SERVICE_TYPES and service_registry are out of sync. "
    f"Registry-only: {_registry_types - _declared_types}, "
    f"SERVICE_TYPES-only: {_declared_types - _registry_types}"
)
del _registry_types, _declared_types


# Re-exported for consumers who need to register custom services at runtime.
# Preferred over importing from services.registry directly.
__all__ = ["get_service_client", "SERVICE_TYPES", "service_registry"]


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
