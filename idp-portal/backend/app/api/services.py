"""FastAPI dependency injection: services (Story 4.2bis, Task 3.1)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.services.vault_service import VaultService


class VaultServiceDisabled:
    """Mock Vault service for dev mode when Vault is disabled."""

    async def get_secret(self, path: str) -> dict[str, Any]:
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
