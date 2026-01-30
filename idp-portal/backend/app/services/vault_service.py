"""Vault service for dynamic secret retrieval (Story 4.2bis, Task 2).

Provides connection to HashiCorp Vault and retrieval of secrets on-demand.
Secrets are never persisted - only retrieved in-memory for platform adapter calls.
"""

from __future__ import annotations

import asyncio
from typing import Any

import hvac
import hvac.exceptions
import structlog

from app.core.config import settings
from app.core.exceptions import VaultError

logger = structlog.get_logger()


class VaultService:
    """Service for connecting to HashiCorp Vault and retrieving secrets dynamically.

    Supports Token and AppRole authentication methods.
    Secrets are retrieved on-demand and never persisted.
    """

    def __init__(self) -> None:
        """Initialize Vault client with authentication.

        Uses Token authentication if VAULT_TOKEN is set, otherwise AppRole if
        VAULT_ROLE_ID and VAULT_SECRET_ID are set.

        Raises:
            VaultError: If connection fails or authentication fails
        """
        vault_addr = getattr(settings, "vault_addr", "")
        if not vault_addr:
            raise VaultError(
                code="VAULT_CONNECTION_FAILED",
                message="VAULT_ADDR not configured",
            )

        try:
            # Initialize client with timeout (MEDIUM-3 fix)
            self.client = hvac.Client(url=vault_addr, timeout=30)

            # Authenticate: Token OR AppRole (not both)
            vault_token = getattr(settings, "vault_token", "")
            vault_role_id = getattr(settings, "vault_role_id", "")
            vault_secret_id = getattr(settings, "vault_secret_id", "")

            if vault_token:
                # Token authentication
                self.client.token = vault_token
            elif vault_role_id and vault_secret_id:
                # AppRole authentication
                response = self.client.auth.approle.login(
                    role_id=vault_role_id,
                    secret_id=vault_secret_id,
                )
                # Validate AppRole response structure (MEDIUM-1 fix)
                if response and "auth" in response and "client_token" in response["auth"]:
                    self.client.token = response["auth"]["client_token"]
                else:
                    raise VaultError(
                        code="VAULT_AUTH_FAILED",
                        message="AppRole login succeeded but no client_token in response",
                    )
            else:
                raise VaultError(
                    code="VAULT_AUTH_FAILED",
                    message="No authentication method configured (VAULT_TOKEN or VAULT_ROLE_ID+VAULT_SECRET_ID required)",
                )

        except Exception as e:
            logger.error("vault_connection_failed", error=str(e))
            raise VaultError(
                code="VAULT_CONNECTION_FAILED",
                message=f"Failed to connect to Vault: {str(e)}",
            ) from e

    async def get_secret(self, path: str, correlation_id: str | None = None) -> dict[str, Any]:
        """Retrieve secret from Vault at given path.

        Tries KV v2 first, falls back to KV v1 if path doesn't exist in v2.

        Args:
            path: Vault secret path (e.g., "secret/data/idp/aap-prod")
            correlation_id: Optional request correlation ID for tracing (Story 4.3, AC4)

        Returns:
            Dictionary containing secret data fields

        Raises:
            VaultError: If secret not found, Vault unavailable, or auth failed
        """
        # Bind correlation_id to structlog context if provided
        if correlation_id:
            structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        def _read_secret() -> dict[str, Any]:
            """Synchronous secret reading function."""
            try:
                # Try KV v2 first
                try:
                    response = self.client.secrets.kv.v2.read_secret_version(path=path, version=None)
                    if response and "data" in response and "data" in response["data"]:
                        result = response["data"]["data"]
                        logger.debug("vault_secret_retrieved", path=path, kv_version="v2")
                        return result
                    # If KV v2 response structure is unexpected, fallback to v1
                    raise hvac.exceptions.InvalidPath("Unexpected KV v2 response structure")
                except hvac.exceptions.InvalidPath:
                    # Fallback to KV v1
                    try:
                        response = self.client.secrets.kv.v1.read_secret(path=path)
                        if response and "data" in response:
                            result = response["data"]
                            logger.debug("vault_secret_retrieved", path=path, kv_version="v1")
                            return result
                        result = response if isinstance(response, dict) else {}
                        logger.debug("vault_secret_retrieved", path=path, kv_version="v1")
                        return result
                    except hvac.exceptions.InvalidPath:
                        raise VaultError(
                            code="SECRET_NOT_FOUND",
                            message=f"Secret not found at path: {path}",
                        )

            except hvac.exceptions.VaultDown as e:
                logger.error("vault_unavailable", path=path, error=str(e))
                raise VaultError(
                    code="VAULT_UNAVAILABLE",
                    message=f"Vault is unavailable: {str(e)}",
                ) from e

            except hvac.exceptions.Forbidden as e:
                logger.error("vault_auth_failed", path=path, error=str(e))
                raise VaultError(
                    code="VAULT_AUTH_FAILED",
                    message=f"Vault authentication failed (token expired?): {str(e)}",
                ) from e

            except VaultError:
                # Re-raise VaultError as-is (from nested try blocks)
                raise

            except hvac.exceptions.InvalidPath as e:
                logger.warning("vault_secret_not_found", path=path, error=str(e))
                raise VaultError(
                    code="SECRET_NOT_FOUND",
                    message=f"Secret not found at path: {path}",
                ) from e

            except Exception as e:
                logger.error("vault_error", path=path, error=str(e))
                raise VaultError(
                    code="VAULT_UNAVAILABLE",
                    message=f"Unexpected Vault error: {str(e)}",
                ) from e

        # Run synchronous hvac calls in thread pool
        return await asyncio.to_thread(_read_secret)
