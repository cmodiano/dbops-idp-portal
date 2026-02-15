"""
Service factory for consumed services (Vault, Splunk, ServiceNow, etc.).

Story 27.9: Services are systems consumed by the portal or adapters for
utility functions (secrets, logging, ITSM). They do NOT execute jobs.

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


# Registry of available service types
SERVICE_TYPES: dict[str, str] = {
    "vault": "services.vault_service.VaultService",
    "splunk": "services.splunk_service.SplunkService",
    "servicenow": "services.servicenow_service.ServiceNowService",
    "jira": "services.jira_service.JiraService",
}


def get_service_client(
    service_type: str,
    **config: Any,
) -> Any:
    """Factory to instantiate the correct service client for a given service type.

    Args:
        service_type: Service identifier ('vault', 'splunk', or 'servicenow').
        **config: Service-specific configuration (base_url, auth_headers, etc.).

    Returns:
        Service client instance.

    Raises:
        ValueError: If service_type is not supported.
    """
    if service_type == "vault":
        from services.vault_service import VaultService
        return VaultService(**config)

    if service_type == "splunk":
        from services.splunk_service import SplunkService
        return SplunkService(**config)

    if service_type == "servicenow":
        from services.servicenow_service import ServiceNowService
        return ServiceNowService(**config)

    if service_type == "jira":
        from services.jira_service import JiraService
        return JiraService(**config)

    available = list(SERVICE_TYPES.keys())
    raise ValueError(
        f"Unsupported service_type: '{service_type}'. Available: {available}"
    )
