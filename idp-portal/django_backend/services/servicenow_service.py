"""
ServiceNowService — ServiceNow ITSM integration service.

Story 27.9: ServiceNow is classified as a Service (consumed by the portal for
change management), not a Platform adapter (does not execute jobs).

Story 31.6: create_change() implemented — creates a change request via REST API.
Story 57.9: close_change() and cancel_change() implemented (ADR-007 Phase 3).
"""
from __future__ import annotations

import json
import httpx
import structlog
from django.conf import settings

from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)


class ServiceNowService(IHealthCheckable):
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
        timeout: float = 30.0,
        **kwargs: object,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout
        logger.info("servicenow_service_initialized", base_url=self.base_url)

    def _get_verify_tls(self) -> bool:
        """SEC-13: Return TLS verification flag, forced True in production (DEBUG=False)."""
        verify_tls = getattr(settings, 'SERVICENOW_VERIFY_TLS', True)
        if not settings.DEBUG:
            if not verify_tls:
                logger.warning(
                    "servicenow_tls_override_ignored",
                    reason="TLS verification forced True in production (DEBUG=False)",
                    configured_value=verify_tls,
                )
                verify_tls = True
        return verify_tls

    def create_change(
        self,
        change_model_code: str | None = None,
        change_type: str | None = None,
        short_description: str = "",
        description: str = "",
        **kwargs: object,
    ) -> dict:
        """
        Create a ServiceNow change request via REST API (Story 31.6, AC#9).

        Args:
            change_model_code: sys_id of the ServiceNow change model
            change_type: Change type (normal, standard, emergency)
            short_description: Short description for the change
            description: Full description

        Returns:
            dict with keys 'number' (str) and 'sys_id' (str)

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
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v

        timeout = getattr(settings, 'SERVICENOW_TIMEOUT', 30)
        verify_tls = self._get_verify_tls()

        try:
            with httpx.Client(headers=self.auth_headers, timeout=timeout, verify=verify_tls) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                try:
                    json_body = resp.json()
                except (json.JSONDecodeError, ValueError):
                    json_body = {}
                result = json_body.get('result', {}) if isinstance(json_body, dict) else {}
                change_number = result.get('number') or result.get('sys_id', '')
                sys_id = result.get('sys_id', '')
                if not change_number and not sys_id:
                    logger.error(
                        "servicenow_create_change_no_identifiers",
                        status_code=resp.status_code,
                        body_redacted="<non-json or empty result>",
                        base_url=self.base_url,
                    )
                    raise ServiceUnavailableError(
                        code="SERVICENOW_INVALID_RESPONSE",
                        message="ServiceNow create_change returned 2xx but no number or sys_id in result",
                    )
                logger.info(
                    "servicenow_create_change_success",
                    change_number=change_number,
                    base_url=self.base_url,
                )
                return {"number": str(change_number), "sys_id": str(sys_id)}
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

    def close_change(
        self,
        change_id: str,
        close_code: str = "successful",
        close_notes: str = "",
        **kwargs: object,
    ) -> dict:
        """
        Close a ServiceNow change request (Story 57.9, ADR-007 Phase 3).

        Args:
            change_id: sys_id or change number of the change request
            close_code: Close code (default: "successful")
            close_notes: Closure notes
            **kwargs: Additional fields to include in the PATCH payload

        Returns:
            dict with keys 'closed' (True) and 'sys_id' (str)

        Raises:
            ServiceUnavailableError: If the API is unavailable or returns an error
        """
        url = f"{self.base_url}/api/now/table/change_request/{change_id}"
        payload: dict[str, str] = {
            "state": "3",
            "close_code": close_code,
            "close_notes": close_notes,
        }
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v

        timeout = getattr(settings, 'SERVICENOW_TIMEOUT', 30)
        verify_tls = self._get_verify_tls()

        try:
            with httpx.Client(headers=self.auth_headers, timeout=timeout, verify=verify_tls) as client:
                resp = client.patch(url, json=payload)
                resp.raise_for_status()
                try:
                    json_body = resp.json()
                except (json.JSONDecodeError, ValueError):
                    json_body = {}
                result = json_body.get('result', {}) if isinstance(json_body, dict) else {}
                sys_id = result.get('sys_id', '')
                logger.info(
                    "servicenow_close_change_success",
                    change_id=change_id,
                    sys_id=sys_id,
                    base_url=self.base_url,
                )
                return {"closed": True, "sys_id": str(sys_id)}
        except httpx.TimeoutException as exc:
            logger.error("servicenow_close_change_timeout", change_id=change_id, base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message="ServiceNow close_change timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_close_change_http_error",
                change_id=change_id,
                status=exc.response.status_code,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow close_change erreur {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("servicenow_close_change_request_error", change_id=change_id, base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
            ) from exc

    def cancel_change(
        self,
        change_id: str,
        reason: str = "",
        **kwargs: object,
    ) -> dict:
        """
        Cancel a ServiceNow change request (Story 57.9, ADR-007 Phase 3).

        Args:
            change_id: sys_id or change number of the change request
            reason: Cancellation reason
            **kwargs: Additional fields to include in the PATCH payload

        Returns:
            dict with keys 'cancelled' (True) and 'sys_id' (str)

        Raises:
            ServiceUnavailableError: If the API is unavailable or returns an error
        """
        url = f"{self.base_url}/api/now/table/change_request/{change_id}"
        payload: dict[str, str] = {
            "state": "4",
            "cancel_reason": reason,
        }
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v

        timeout = getattr(settings, 'SERVICENOW_TIMEOUT', 30)
        verify_tls = self._get_verify_tls()

        try:
            with httpx.Client(headers=self.auth_headers, timeout=timeout, verify=verify_tls) as client:
                resp = client.patch(url, json=payload)
                resp.raise_for_status()
                try:
                    json_body = resp.json()
                except (json.JSONDecodeError, ValueError):
                    json_body = {}
                result = json_body.get('result', {}) if isinstance(json_body, dict) else {}
                sys_id = result.get('sys_id', '')
                logger.info(
                    "servicenow_cancel_change_success",
                    change_id=change_id,
                    sys_id=sys_id,
                    base_url=self.base_url,
                )
                return {"cancelled": True, "sys_id": str(sys_id)}
        except httpx.TimeoutException as exc:
            logger.error("servicenow_cancel_change_timeout", change_id=change_id, base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message="ServiceNow cancel_change timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_cancel_change_http_error",
                change_id=change_id,
                status=exc.response.status_code,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow cancel_change erreur {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            logger.error("servicenow_cancel_change_request_error", change_id=change_id, base_url=self.base_url, error=str(exc))
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping ServiceNow via GET table API (sysparm_limit=1) et valide l'authentification."""
        from datetime import datetime, timezone as tz
        url = f"{self.base_url}/api/now/table/sys_properties?sysparm_limit=1"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._get_verify_tls(),
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("servicenow_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("servicenow_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz.utc),
                error_message=str(exc),
            )
