"""
ServiceNowService — ServiceNow ITSM integration service.

Story 27.9: ServiceNow is classified as a Service (consumed by the portal for
change management), not a Platform adapter (does not execute jobs).

Story 31.6: create_change() implemented — creates a change request via REST API.
Story 57.9: close_change() and cancel_change() implemented (ADR-007 Phase 3).
Story 86.2: update_change() and get_change_status() implemented (Table API PATCH/GET).
"""
from __future__ import annotations

import json
import httpx
import structlog
from django.conf import settings

from core.exceptions import ServiceUnavailableError
from core.middleware import get_correlation_id
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

    .. note::
        **Mixed sync/async pattern (by design).**
        Business methods (create_change, close_change, cancel_change) are synchronous
        because they are called from synchronous Celery tasks. The health_check()
        method is async to satisfy the ``IHealthCheckable`` interface used by the
        async health dashboard endpoint. This is intentional and expected.
    """

    _STATE_LABELS: dict[str, str] = {
        "-5": "pending",
        "1": "open",
        "2": "work_in_progress",
        "3": "closed",     # close_change envoie state="3"
        "4": "cancelled",  # cancel_change envoie state="4"
    }

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = 30.0,
        **kwargs: object,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = getattr(settings, 'SERVICENOW_TIMEOUT', timeout)
        self.__sync_client: httpx.Client | None = None  # PERF-BE-01: lazy init
        logger.info("servicenow_service_initialized", base_url=self.base_url)

    @property
    def _sync_client(self) -> httpx.Client:
        """PERF-BE-01: Shared HTTP client — created once per instance, reused across sync calls.

        Lazy initialization ensures the client is created during the first method call,
        which allows test patches of httpx.Client to be active at creation time.
        The async health_check() uses a separate httpx.AsyncClient (unchanged).
        """
        if self.__sync_client is None:
            self.__sync_client = httpx.Client(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._get_verify_tls(),
            )
        return self.__sync_client

    def close(self) -> None:
        """Close the shared sync HTTP client and release connection pool resources.

        Call this when the ServiceNowService instance is no longer needed.
        Idempotent: safe to call multiple times or when no client was created.
        The async health_check() AsyncClient is not affected (created per call).
        """
        if self.__sync_client is not None:
            self.__sync_client.close()
            self.__sync_client = None

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

        correlation_id = get_correlation_id()

        try:
            client = self._sync_client
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
                    details={"base_url": self.base_url},
                )
            logger.info(
                "servicenow_create_change_success",
                change_number=change_number,
                base_url=self.base_url,
                correlation_id=correlation_id,
            )
            return {"number": str(change_number), "sys_id": str(sys_id)}
        except httpx.TimeoutException as exc:
            logger.error(
                "servicenow_create_change_timeout",
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message="ServiceNow create_change timeout",
                details={"base_url": self.base_url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_create_change_http_error",
                status=exc.response.status_code,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow create_change erreur {exc.response.status_code}",
                details={"base_url": self.base_url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "servicenow_create_change_request_error",
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
                details={"base_url": self.base_url},
            ) from exc

    def update_change(self, change_id: str, **kwargs: object) -> dict:
        """Update a ServiceNow change request via PATCH (Story 86.2, AC#1, #2).

        Réutilise ``_patch_change_request()`` (DRY — même pattern que close_change/cancel_change).

        Args:
            change_id: sys_id or change number of the change request.
            **kwargs: Fields to update (e.g. work_notes, state). None values are ignored.

        Returns:
            dict with keys ``updated`` (True) and ``sys_id`` (str).

        Raises:
            ServiceUnavailableError: If the API is unavailable or returns an error.
        """
        payload: dict[str, str] = {}
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v
        return self._patch_change_request(
            change_id, payload, "update_change", "updated", True
        )

    def get_change_status(self, change_id: str) -> dict:
        """Query ServiceNow change request status via GET (Story 86.2, AC#3, #4, #5).

        Performs a GET on ``/api/now/table/change_request/{change_id}`` with
        ``sysparm_fields=number,sys_id,state,priority,sys_updated_on``.

        Maps numeric ServiceNow state codes to readable labels via ``_STATE_LABELS``.
        Unknown codes are returned as-is (no error).

        Args:
            change_id: sys_id or change number of the change request.

        Returns:
            dict with keys ``change_id`` (str), ``number`` (str), ``state`` (str),
            ``priority`` (int).

        Raises:
            ServiceUnavailableError: If the API is unavailable or returns an error.
        """
        url = f"{self.base_url}/api/now/table/change_request/{change_id}"
        params = {"sysparm_fields": "number,sys_id,state,priority,sys_updated_on"}
        correlation_id = get_correlation_id()
        try:
            client = self._sync_client
            resp = client.get(url, params=params)
            resp.raise_for_status()
            try:
                json_body = resp.json()
            except (json.JSONDecodeError, ValueError):
                json_body = {}
            result = json_body.get('result', {}) if isinstance(json_body, dict) else {}
            sys_id = result.get('sys_id', '')
            if not sys_id:
                raise ServiceUnavailableError(
                    code="SERVICENOW_INVALID_RESPONSE",
                    message="ServiceNow get_change_status returned 2xx but no sys_id in result",
                    details={"change_id": change_id, "base_url": self.base_url},
                )
            raw_state = str(result.get('state', ''))
            mapped_state = self._STATE_LABELS.get(raw_state, raw_state)
            priority_raw = result.get('priority')
            try:
                priority = int(str(priority_raw)) if priority_raw not in (None, '') else 0
            except (TypeError, ValueError):
                priority = 0
            logger.info(
                "servicenow_get_change_status_success",
                change_id=change_id,
                state=mapped_state,
                base_url=self.base_url,
                correlation_id=correlation_id,
            )
            return {
                "change_id": change_id,
                "number": str(result.get('number', '')),
                "state": mapped_state,
                "priority": priority,
            }
        except httpx.TimeoutException as exc:
            logger.error(
                "servicenow_get_change_status_timeout",
                change_id=change_id,
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message="ServiceNow get_change_status timeout",
                details={"change_id": change_id, "base_url": self.base_url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_get_change_status_http_error",
                change_id=change_id,
                status=exc.response.status_code,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow get_change_status erreur {exc.response.status_code}",
                details={"change_id": change_id, "base_url": self.base_url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "servicenow_get_change_status_request_error",
                change_id=change_id,
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
                details={"change_id": change_id, "base_url": self.base_url},
            ) from exc

    def _patch_change_request(
        self,
        change_id: str,
        payload: dict[str, str],
        operation: str,
        success_key: str,
        success_value: bool,
    ) -> dict:
        """
        Helper for PATCH change_request operations (close_change, cancel_change, update_change).
        Story 57.9 — DRY extraction to reduce duplication. Story 86.2 — reused by update_change.
        """
        url = f"{self.base_url}/api/now/table/change_request/{change_id}"
        correlation_id = get_correlation_id()
        details: dict[str, str | int] = {"change_id": change_id, "base_url": self.base_url}

        try:
            client = self._sync_client
            resp = client.patch(url, json=payload)
            resp.raise_for_status()
            try:
                json_body = resp.json()
            except (json.JSONDecodeError, ValueError):
                json_body = {}
            result = json_body.get('result', {}) if isinstance(json_body, dict) else {}
            sys_id = result.get('sys_id', '')
            if not sys_id:
                logger.error(
                    "servicenow_patch_no_sys_id",
                    operation=operation,
                    change_id=change_id,
                    status_code=resp.status_code,
                    base_url=self.base_url,
                    correlation_id=correlation_id,
                )
                raise ServiceUnavailableError(
                    code="SERVICENOW_INVALID_RESPONSE",
                    message=f"ServiceNow {operation} returned 2xx but no sys_id in result",
                    details=details,
                )
            logger.info(
                "servicenow_patch_success",
                operation=operation,
                change_id=change_id,
                sys_id=sys_id,
                base_url=self.base_url,
                correlation_id=correlation_id,
            )
            return {success_key: success_value, "sys_id": str(sys_id)}
        except httpx.TimeoutException as exc:
            logger.error(
                "servicenow_patch_timeout",
                operation=operation,
                change_id=change_id,
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_TIMEOUT",
                message=f"ServiceNow {operation} timeout",
                details=details,
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "servicenow_patch_http_error",
                operation=operation,
                change_id=change_id,
                status=exc.response.status_code,
                error=str(exc),
                correlation_id=correlation_id,
            )
            details["status_code"] = exc.response.status_code
            raise ServiceUnavailableError(
                code="SERVICENOW_HTTP_ERROR",
                message=f"ServiceNow {operation} erreur {exc.response.status_code}",
                details=details,
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "servicenow_patch_request_error",
                operation=operation,
                change_id=change_id,
                base_url=self.base_url,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise ServiceUnavailableError(
                code="SERVICENOW_UNAVAILABLE",
                message=f"ServiceNow indisponible: {exc}",
                details=details,
            ) from exc

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
        payload: dict[str, str] = {
            "state": "3",
            "close_code": close_code,
            "close_notes": close_notes,
        }
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v
        return self._patch_change_request(
            change_id, payload, "close_change", "closed", True
        )

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
        payload: dict[str, str] = {
            "state": "4",
            "cancel_reason": reason,
        }
        for k, v in kwargs.items():
            if v is None:
                continue
            payload[k] = str(v) if not isinstance(v, str) else v
        return self._patch_change_request(
            change_id, payload, "cancel_change", "cancelled", True
        )

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
