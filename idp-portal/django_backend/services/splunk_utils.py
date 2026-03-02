"""
services/splunk_utils.py — Helper to obtain a configured SplunkService instance.

Centralises the Integration lookup + auth header rewriting so that both
the polling task and the views can retrieve a ready-to-use Splunk client
without duplicating logic.
"""
from __future__ import annotations

import structlog

from services.splunk_service import SplunkService

logger = structlog.get_logger(__name__)


def get_splunk_service(correlation_id: str | None = None) -> SplunkService | None:
    """Get a configured SplunkService from the active Splunk integration, or None."""
    try:
        from integrations.models import Integration  # noqa: PLC0415
        from adapters.utils import build_auth_headers  # noqa: PLC0415
        from services import get_service_client  # noqa: PLC0415

        integration = Integration.objects.filter(type="splunk", status="valid").first()
        if integration is None:
            logger.debug("splunk_integration_not_configured", correlation_id=correlation_id)
            return None

        auth_headers = build_auth_headers(integration, correlation_id=correlation_id)
        # Splunk HEC expects "Authorization: Splunk {token}", not "Bearer {token}"
        auth_value = auth_headers.get("Authorization", "")
        if auth_value.startswith("Bearer "):
            auth_headers["Authorization"] = "Splunk " + auth_value[len("Bearer "):]

        client: SplunkService = get_service_client(
            "splunk",
            base_url=integration.base_url,
            auth_headers=auth_headers,
        )
        return client
    except Exception:  # noqa: BLE001 — best-effort: caller handles None
        logger.exception("get_splunk_service_error", correlation_id=correlation_id)
        return None
