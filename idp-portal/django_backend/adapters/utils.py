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


def _resolve_credential(credential_ref: str, correlation_id: str | None = None) -> str:
    """Resolve credential_ref — Vault path or direct token.

    If *credential_ref* starts with ``vault:``, it is resolved via VaultService.
    Otherwise it is returned as-is (direct token for dev/test).
    """
    if credential_ref.startswith("vault:"):
        from core.vault_service import get_vault_service

        return str(get_vault_service().get_secret(credential_ref, correlation_id))
    return credential_ref


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
        # Story 27.6: Resolve Vault references via VaultService
        resolved = _resolve_credential(credential_ref, correlation_id)

        if auth_flow == "basic":
            # resolved expected as "username:password"
            encoded = base64.b64encode(resolved.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        if auth_flow == "pat":
            return {"Authorization": f"Bearer {resolved}"}

        # Default: token / basic_then_token — use Bearer
        return {"Authorization": f"Bearer {resolved}"}

    except BadRequestError:
        raise
    except Exception as e:
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
