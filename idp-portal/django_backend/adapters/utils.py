"""
Adapter utilities — shared helpers for building adapter configurations.

Story 27.1: Centralizes auth header construction from Integration model.
Story 27.6: Vault credential_ref resolution via VaultService.
"""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import structlog
from core.exceptions import BadRequestError

if TYPE_CHECKING:
    from integrations.models import Integration

logger = structlog.get_logger(__name__)


def resolve_credential(
    credential_ref: str,
    correlation_id: str | None = None,
    integration: "Integration | None" = None,
) -> str:
    """Resolve credential_ref — Vault path or direct token.

    Story 27.11: Supports multi-instance Vault via integration.secret_service_id.
    If the integration has a secret_service_id, a VaultService is created
    targeting that specific Vault instance. Otherwise, the default singleton is used.

    If *credential_ref* starts with ``vault:``, it is resolved via VaultService.
    Otherwise it is returned as-is (direct token for dev/test).
    """
    if not credential_ref.startswith("vault:"):
        return credential_ref

    from services.vault_service import VaultService, get_vault_service

    # Story 27.11: Determine which Vault instance to use
    if integration and getattr(integration, 'secret_service_id', None):
        from integrations.models import Integration as IntegrationModel

        sid = getattr(integration, 'secret_service_id', None)
        assert sid is not None  # we only enter when getattr returned truthy
        try:
            vault_integration = IntegrationModel.objects.get(id=int(sid))
        except IntegrationModel.DoesNotExist:
            logger.error(
                "resolve_credential_vault_not_found",
                secret_service_id=integration.secret_service_id,
                integration_id=getattr(integration, 'id', None),
            )
            raise BadRequestError(
                code="VAULT_INTEGRATION_NOT_FOUND",
                message=f"Vault integration id={integration.secret_service_id} not found",
                details={"secret_service_id": integration.secret_service_id},
            )

        vault_config = vault_integration.get_config() or {}
        vault_service = VaultService(
            vault_addr=vault_integration.base_url,
            vault_namespace=vault_config.get("namespace"),
            instance_id=str(vault_integration.id),
        )
        logger.debug(
            "resolve_credential_custom_vault",
            vault_integration_id=vault_integration.id,
            vault_addr=vault_integration.base_url,
        )
        return str(vault_service.get_secret(credential_ref, correlation_id))

    # Default: use singleton VaultService
    return str(get_vault_service().get_secret(credential_ref, correlation_id))


def build_auth_headers_from_credentials(
    credential_ref: str,
    auth_flow: str = "token",
) -> dict[str, str]:
    """Build HTTP auth headers from raw credential_ref and auth_flow (no Vault resolution).

    Used by Celery polling tasks where credentials are passed as task args.
    For request/Integration-based flows use build_auth_headers(integration) instead.

    Args:
        credential_ref: Already-resolved credential (e.g. token or "user:pass" for basic).
        auth_flow: "basic", "pat", or "token" (default).

    Returns:
        Dict of HTTP headers (e.g. {"Authorization": "Bearer <token>"}).
    """
    auth_flow = auth_flow or "token"
    if auth_flow == "basic":
        encoded = base64.b64encode(credential_ref.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    # pat and token (default): Bearer
    return {"Authorization": f"Bearer {credential_ref}"}


def build_auth_headers(
    integration: Integration,
    correlation_id: str | None = None,
) -> dict[str, str]:
    """Build HTTP auth headers from an Integration's auth_flow and credential_ref.

    If credential_ref is a Vault reference (``vault:…``), it is resolved via
    VaultService at call time. Otherwise it is used directly as the token.

    Args:
        integration: Integration model instance.
        correlation_id: Request correlation ID for Vault logging.

    Returns:
        Dict of HTTP headers (e.g. {"Authorization": "Bearer <token>"}).

    Raises:
        BadRequestError: If credential_ref is empty or auth_flow is invalid.
    """
    auth_flow = getattr(integration, "auth_flow", None) or "token"
    credential_ref = getattr(integration, "credential_ref", None) or ""

    integration_id = getattr(integration, "id", None)

    logger.debug(
        "build_auth_headers",
        integration_id=integration_id,
        auth_flow=auth_flow,
        has_credential=bool(credential_ref),
    )

    # CRITICAL-2 FIX: Validate credential_ref is not empty
    if not credential_ref:
        logger.error(
            "build_auth_headers_empty_credential",
            integration_id=integration_id,
            auth_flow=auth_flow,
        )
        raise BadRequestError(
            code="EMPTY_CREDENTIAL",
            message="Integration credential_ref is empty",
            details={"integration_id": integration_id, "auth_flow": auth_flow},
        )

    try:
        # Story 27.6/27.11: Resolve Vault references via VaultService (multi-instance)
        resolved = resolve_credential(credential_ref, correlation_id, integration)
        return build_auth_headers_from_credentials(resolved, auth_flow)
    except BadRequestError:
        raise
    except Exception as e:  # noqa: BLE001 — logged-and-wrapped: unexpected credential error wrapped in BadRequestError
        logger.error(
            "build_auth_headers_encoding_error",
            integration_id=integration_id,
            auth_flow=auth_flow,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise BadRequestError(
            code="AUTH_HEADER_BUILD_ERROR",
            message=f"Failed to build auth headers: {str(e)}",
            details={"integration_id": integration_id, "auth_flow": auth_flow},
        ) from e
