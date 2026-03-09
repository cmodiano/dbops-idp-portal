"""
Adapter utilities — shared helpers for building adapter configurations.

Story 27.1: Centralizes auth header construction from Integration model.
Story 27.6: Vault credential_ref resolution via VaultService.
"""
from __future__ import annotations

import base64
import time
from typing import TYPE_CHECKING, cast

import requests
import structlog
from django.core.cache import cache

from core.exceptions import BadRequestError

if TYPE_CHECKING:
    from integrations.models import Integration

logger = structlog.get_logger(__name__)

# OAuth2 token cache: keyed by (integration_id, scope) to avoid blocking request threads.
# Stores {"access_token": str, "expires_at": float}. TTL uses expires_in from response
# or 300s conservative default. Cache key prefix.
_OAUTH2_CACHE_PREFIX = "oauth2_token"
_OAUTH2_CACHE_TTL = 3600  # Max cache duration (1h) — actual TTL from expires_in
_OAUTH2_TOKEN_REQUEST_TIMEOUT = 5


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

    from services.vault_service import get_vault_service, get_vault_service_for_integration

    # Story 27.11: Determine which Vault instance to use
    if integration and getattr(integration, 'secret_service_id', None):
        from integrations.models import Integration as IntegrationModel

        sid = cast(str, integration.secret_service_id)  # ADP-LOW-01: cast() pour type narrowing, évite assert en production
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
        vault_service = get_vault_service_for_integration(
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
        auth_flow: "basic", "api_key", "pat", or "token" (default).

    Returns:
        Dict of HTTP headers (e.g. {"Authorization": "Bearer <token>"}).
    """
    auth_flow = auth_flow or "token"
    if auth_flow == "basic":
        encoded = base64.b64encode(credential_ref.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    if auth_flow == "api_key":
        # Story 31.12: api_key without config access — use X-API-Key as header name
        # For custom header_name, use build_auth_headers(integration) instead
        return {"X-API-Key": credential_ref}
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

    # Story 31.12: api_key — use header_name from config
    if auth_flow == "api_key":
        config = getattr(integration, 'get_config', lambda: {})() or {}
        header_name = config.get('header_name') or 'X-API-Key'
        resolved = resolve_credential(credential_ref, correlation_id, integration)
        logger.debug("build_auth_headers_api_key", integration_id=integration_id, header_name=header_name)
        return {header_name: resolved}

    # Story 31.12: oauth2_client_credentials — POST to token_url for access token
    # Token cache keyed by (integration_id, scope) to avoid blocking request threads.
    if auth_flow == "oauth2_client_credentials":
        token_url = getattr(integration, 'token_url', None)
        if not token_url:
            raise BadRequestError(
                code="MISSING_TOKEN_URL",
                message="token_url is required for oauth2_client_credentials flow",
                details={"integration_id": integration_id},
            )
        config = getattr(integration, 'get_config', lambda: {})() or {}
        scope = config.get('scope')
        scope_key = (scope or '') or ''
        cache_key = f"{_OAUTH2_CACHE_PREFIX}:{integration_id}:{scope_key}"

        # Check cache first — return cached token if not expired
        cached = cache.get(cache_key)
        if cached and isinstance(cached, dict):
            access_token = cached.get("access_token")
            expires_at = cached.get("expires_at", 0)
            if access_token and expires_at > time.time():
                logger.debug("build_auth_headers_oauth2_cache_hit", integration_id=integration_id)
                return {"Authorization": f"Bearer {access_token}"}

        resolved = resolve_credential(credential_ref, correlation_id, integration)
        # credential_ref format: "client_id:client_secret" (same convention as basic auth)
        if ':' in resolved:
            client_id, client_secret = resolved.split(':', 1)
        else:
            client_id, client_secret = resolved, ''
        data: dict = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
        if scope:
            data["scope"] = scope
        try:
            resp = requests.post(token_url, data=data, timeout=_OAUTH2_TOKEN_REQUEST_TIMEOUT)
            resp.raise_for_status()
            body = resp.json()
            access_token = body.get("access_token")
            if not access_token:
                raise BadRequestError(
                    code="OAUTH2_NO_ACCESS_TOKEN",
                    message="OAuth2 token endpoint did not return access_token",
                    details={"integration_id": integration_id, "token_url": token_url},
                )
            # Store in cache with expiry (expires_in or conservative 300s, minus 30s skew)
            expires_in = body.get("expires_in")
            if isinstance(expires_in, (int, float)) and expires_in > 0:
                ttl_seconds = int(expires_in) - 30
            else:
                ttl_seconds = 300 - 30  # 270s conservative default
            ttl_seconds = max(60, min(ttl_seconds, _OAUTH2_CACHE_TTL))
            expires_at = time.time() + ttl_seconds
            cache.set(cache_key, {"access_token": access_token, "expires_at": expires_at}, timeout=ttl_seconds)
            logger.debug("build_auth_headers_oauth2_success", integration_id=integration_id)
            return {"Authorization": f"Bearer {access_token}"}
        except requests.RequestException as exc:
            logger.error("build_auth_headers_oauth2_error", integration_id=integration_id, error=str(exc))
            raise BadRequestError(
                code="OAUTH2_TOKEN_REQUEST_FAILED",
                message=f"Failed to acquire OAuth2 token: {str(exc)}",
                details={"integration_id": integration_id, "token_url": token_url},
            ) from exc

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
