"""
Adapter utilities — shared helpers for building adapter configurations.

Story 27.1: Centralizes auth header construction from Integration model.
"""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import structlog
from core.exceptions import BadRequestError

if TYPE_CHECKING:
    from integrations.models import Integration

logger = structlog.get_logger(__name__)


def build_auth_headers(integration: Integration) -> dict[str, str]:
    """Build HTTP auth headers from an Integration's auth_flow and credential_ref.

    For now, returns a Bearer token header using credential_ref as the token value.
    In production, credential_ref points to a Vault path and should be resolved
    via VaultService. This helper provides the fallback/direct token usage.

    Args:
        integration: Integration model instance.

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
        if auth_flow == "basic":
            # credential_ref expected as "username:password"
            encoded = base64.b64encode(credential_ref.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        if auth_flow == "pat":
            return {"Authorization": f"Bearer {credential_ref}"}

        # Default: token / basic_then_token — use Bearer
        return {"Authorization": f"Bearer {credential_ref}"}

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
