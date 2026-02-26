"""
ServiceNowService — ServiceNow ITSM integration service.

Story 27.9: ServiceNow is classified as a Service (consumed by the portal for
change management), not a Platform adapter (does not execute jobs).

Story 31.6: create_change() implemented — creates a change request via REST API.
"""
from __future__ import annotations

import httpx
import structlog
from django.conf import settings

from core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)


class ServiceNowService:
    """ServiceNow ITSM service client.

    ServiceNow is a consumed service for change management (opening, updating,
    closing change requests during execution flows). It does NOT execute jobs
    and therefore does NOT implement BaseAdapter.

    Configuration comes from Integration model (type='servicenow'):
    - base_url: ServiceNow instance URL
    - credential_ref: Vault reference for authentication
    - config: Additional configuration (instance, table, etc.)
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        **kwargs: object,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        logger.info("servicenow_service_initialized", base_url=self.base_url)

    def _get_verify_tls(self) -> bool:
        """SEC-13: Return TLS verification flag, forced True in production (DEBUG=False)."""
        verify_tls = getattr(settings, 'SERVICENOW_VERIFY_TLS', True)
        if not settings.DEBUG:
            verify_tls = True
        return verify_tls

    def create_change(
        self,
        change_model_code: str | None = None,
        change_type: str | None = None,
        short_description: str = "",
        description: str = "",
        **kwargs: object,
    ) -> str:
        """
        Create a ServiceNow change request via REST API (Story 31.6, AC#9).

        Args:
            change_model_code: sys_id of the ServiceNow change model
            change_type: Change type (normal, standard, emergency)
            short_description: Short description for the change
            description: Full description

        Returns:
            Change number (e.g. "CHG0001234")

        Raises:
            ServiceUnavailableError: If the API is unavailable or returns an error
        """
        url = f"{self.base_url}/api/now/table/change_request"
        payload: dict[str, str] = {
            "short_description": short_description or "IDP Portal — Changement automatique",
            "description": description,
            "type": change_type or "normal",
        }
        if change_model_code:
            payload["chg_model"] = change_model_code

        timeout = getattr(settings, 'SERVICENOW_TIMEOUT', 30)
        verify_tls = self._get_verify_tls()

        try:
            with httpx.Client(headers=self.auth_headers, timeout=timeout, verify=verify_tls) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                result = resp.json().get('result', {})
                change_number = result.get('number') or result.get('sys_id', '')
                logger.info(
                    "servicenow_create_change_success",
                    change_number=change_number,
                    base_url=self.base_url,
                )
                return str(change_number)
        except httpx.TimeoutException as exc:
            logger.error("servicenow_create_change_timeout", base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message="ServiceNow create_change timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_create_change_http_error",
                status=exc.response.status_code,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow create_change erreur {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("servicenow_create_change_request_error", base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
            ) from exc

    def update_change(self, change_id: str, **kwargs: object) -> None:
        """Update a ServiceNow change request (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.update_change() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )

    def get_change_status(self, change_id: str) -> None:
        """Query ServiceNow change request status (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.get_change_status() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )

    def close_change(self, change_id: str, **kwargs: object) -> None:
        """Close a ServiceNow change request (not yet implemented)."""
        raise NotImplementedError(
            "ServiceNowService.close_change() is not yet implemented. "
            "See integration-type-catalogue.md for specification."
        )
