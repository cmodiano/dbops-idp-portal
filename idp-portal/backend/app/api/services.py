"""FastAPI dependency injection: services (Story 4.2bis, Task 3.1; Story 4.5, Task 2)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.repositories import integration_repository
from app.services.vault_service import VaultService
from app.services.servicenow_service import ServiceNowService


class VaultServiceDisabled:
    """Mock Vault service for dev mode when Vault is disabled."""

    async def get_secret(self, path: str, correlation_id: str | None = None) -> dict[str, Any]:
        """Raise error indicating Vault is disabled."""
        raise ServiceUnavailableError(
            code="VAULT_DISABLED",
            message="Vault is disabled (VAULT_ADDR not configured). Configure VAULT_ADDR to enable secret retrieval.",
        )


def get_vault_service() -> VaultService | VaultServiceDisabled:
    """Factory function for VaultService dependency injection.

    Returns VaultService if VAULT_ADDR is configured, otherwise returns
    VaultServiceDisabled for dev mode.

    Returns:
        VaultService instance or VaultServiceDisabled if Vault not configured
    """
    vault_addr = getattr(settings, "vault_addr", "")
    if not vault_addr:
        return VaultServiceDisabled()

    return VaultService()


async def get_servicenow_service(
    vault_service: VaultService | VaultServiceDisabled | None = None,
) -> ServiceNowService | None:
    """Factory for ServiceNowService (Story 4.5, Task 2 / 6.2).

    Enables ServiceNow when configured via:
    1. SERVICENOW_BASE_URL (env), or
    2. INTEGRATIONS table (type=servicenow with base_url).

    Returns None if ServiceNow not configured or Vault disabled.
    """
    if vault_service is None:
        vault_service = get_vault_service()

    if isinstance(vault_service, VaultServiceDisabled):
        return None

    servicenow_base_url = getattr(settings, "servicenow_base_url", "")
    if servicenow_base_url:
        return ServiceNowService(vault_service)

    # Task 6.2: fallback to INTEGRATIONS table (base_url/credentials from DB)
    integration = await integration_repository.get_by_type("servicenow")
    if integration and integration.base_url:
        return ServiceNowService(vault_service)

    return None
