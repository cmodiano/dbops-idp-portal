"""
SplunkService — Splunk HEC (HTTP Event Collector) service for log ingestion.

Story 27.8: Send structured events to Splunk HEC for observability and audit.
Story 27.9: Reclassified as a Service (not a Platform adapter) — Splunk is
consumed by the portal for logging, not for executing jobs.
"""
from __future__ import annotations

import asyncio

import httpx
import structlog

from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

# Timeout for Splunk HEC API calls (seconds)
SPLUNK_DEFAULT_TIMEOUT = 30.0

# Retry config for transient errors (500, 503)
SPLUNK_MAX_RETRIES = 2
SPLUNK_RETRY_DELAY = 5.0
_TRANSIENT_STATUS_CODES = frozenset({500, 503})


class SplunkService(IHealthCheckable):
    """Service for sending events to Splunk HTTP Event Collector.

    Splunk is a consumed service (logging/observability), not a platform that
    executes jobs. It does NOT implement BaseAdapter.

    Requires base_url (HEC endpoint) and auth_headers with Splunk token.
    Typically instantiated via integration config (base_url, credential_ref -> Vault).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = SPLUNK_DEFAULT_TIMEOUT,
        default_sourcetype: str = "idp:execution",
        default_index: str = "prod-idp",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout
        self.default_sourcetype = default_sourcetype
        self.default_index = default_index

    # ------------------------------------------------------------------
    # Splunk HEC methods
    # ------------------------------------------------------------------

    async def send_event(
        self,
        event: dict,
        sourcetype: str | None = None,
        index: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Send a single event to Splunk HEC.

        Args:
            event: Event data dict to index in Splunk.
            sourcetype: Splunk sourcetype (default: idp:execution).
            index: Splunk index (default: prod-idp).
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status', 'code', 'text' from Splunk HEC response.

        Raises:
            ServiceUnavailableError: If Splunk HEC is unreachable or returns error.
        """
        url = f"{self.base_url}/services/collector/event"
        payload = self._build_hec_payload(event, sourcetype, index)

        logger.info(
            "splunk_event_sending",
            url=url,
            correlation_id=correlation_id,
            event_name=event.get("event", "unknown"),
        )

        result = await self._post_with_retry(url, payload, correlation_id=correlation_id)

        logger.info(
            "splunk_event_sent",
            correlation_id=correlation_id,
            event_name=event.get("event", "unknown"),
            hec_code=result.get("code"),
        )

        return result

    async def send_batch(
        self,
        events: list[dict],
        sourcetype: str | None = None,
        index: str | None = None,
        correlation_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Send a batch of events to Splunk HEC.

        Args:
            events: List of event data dicts to index.
            sourcetype: Splunk sourcetype override.
            index: Splunk index override.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status', 'count', 'code' from Splunk HEC response.

        Raises:
            ServiceUnavailableError: If Splunk HEC is unreachable or returns error.
        """
        if not events:
            return {"status": "success", "count": 0, "code": 0, "text": "No events"}

        url = f"{self.base_url}/services/collector/event"
        # Splunk HEC batch: newline-delimited JSON payloads
        lines = []
        for evt in events:
            payload = self._build_hec_payload(evt, sourcetype, index)
            lines.append(payload)

        # For batch, concatenate JSON objects (Splunk HEC accepts this)
        import json
        body = "\n".join(json.dumps(p) for p in lines)

        logger.info(
            "splunk_batch_sending",
            url=url,
            correlation_id=correlation_id,
            event_count=len(events),
        )

        result = await self._post_raw_with_retry(url, body, correlation_id=correlation_id)

        logger.info(
            "splunk_batch_sent",
            correlation_id=correlation_id,
            event_count=len(events),
            hec_code=result.get("code"),
        )

        return {**result, "count": len(events)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_hec_payload(
        self, event: dict, sourcetype: str | None, index: str | None
    ) -> dict:
        """Build Splunk HEC payload with indexed fields."""
        # Extract fields for Splunk indexing
        fields = {}
        for field_name in ("correlation_id", "user_id", "execution_id", "platform"):
            if field_name in event:
                fields[field_name] = event[field_name]

        payload: dict = {
            "event": event,
            "sourcetype": sourcetype or self.default_sourcetype,
            "index": index or self.default_index,
        }
        if fields:
            payload["fields"] = fields

        return payload

    async def _post_with_retry(
        self, url: str, payload: dict, *, correlation_id: str | None = None
    ) -> dict:
        """POST JSON payload to Splunk HEC with retry on transient errors."""
        import json
        return await self._post_raw_with_retry(
            url, json.dumps(payload), correlation_id=correlation_id
        )

    async def _post_raw_with_retry(
        self, url: str, body: str, *, correlation_id: str | None = None
    ) -> dict:
        """POST raw body to Splunk HEC with retry on transient errors."""
        last_exc: Exception | None = None
        headers = {**self.auth_headers, "Content-Type": "application/json"}

        for attempt in range(SPLUNK_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    verify=False,  # nosec B501  # noqa: S501 — corporate CAs handled externally
                ) as client:
                    response = await client.post(url, content=body, headers=headers)

                    if response.status_code in _TRANSIENT_STATUS_CODES and attempt < SPLUNK_MAX_RETRIES:
                        logger.warning(
                            "splunk_hec_transient_error",
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            correlation_id=correlation_id,
                        )
                        await asyncio.sleep(SPLUNK_RETRY_DELAY)
                        continue

                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < SPLUNK_MAX_RETRIES:
                    logger.warning(
                        "splunk_hec_timeout_retry",
                        attempt=attempt + 1,
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    await asyncio.sleep(SPLUNK_RETRY_DELAY)
                    continue

                logger.error(
                    "splunk_hec_timeout",
                    url=url,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                raise ServiceUnavailableError(
                    code="SPLUNK_TIMEOUT",
                    message="Splunk HEC did not respond in time",
                    details={"url": url},
                ) from exc

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "splunk_hec_error",
                    url=url,
                    status_code=exc.response.status_code,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                raise ServiceUnavailableError(
                    code="SPLUNK_HEC_ERROR",
                    message=f"Splunk HEC returned HTTP {exc.response.status_code}",
                    details={"url": url, "status_code": exc.response.status_code},
                ) from exc

            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < SPLUNK_MAX_RETRIES:
                    logger.warning(
                        "splunk_hec_connection_retry",
                        attempt=attempt + 1,
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    await asyncio.sleep(SPLUNK_RETRY_DELAY)
                    continue

                logger.error(
                    "splunk_hec_connection_error",
                    url=url,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                raise ServiceUnavailableError(
                    code="SPLUNK_CONNECTION_ERROR",
                    message="Cannot connect to Splunk HEC",
                    details={"url": url},
                ) from exc

        # Should not reach here, but safety net
        raise ServiceUnavailableError(
            code="SPLUNK_MAX_RETRIES",
            message="Splunk HEC max retries exceeded",
            details={"url": url},
        ) from last_exc

    # ------------------------------------------------------------------
    # Search — retrieve platform logs on demand
    # ------------------------------------------------------------------

    async def search_platform_logs(self, execution_id: int) -> str | None:
        """Search Splunk for platform logs of a given execution.

        Uses the Splunk REST search API (not HEC) to retrieve previously
        forwarded platform logs.  Best-effort: returns ``None`` on any error
        or timeout (30 s).

        Args:
            execution_id: The IDP execution ID (indexed field in Splunk events).

        Returns:
            The log content string, or ``None`` if not found / error.
        """
        import json  # noqa: PLC0415

        search_url = f"{self.base_url}/services/search/jobs"
        spl = f'search sourcetype="idp:platform_log" execution_id={execution_id}'
        headers = {**self.auth_headers, "Content-Type": "application/x-www-form-urlencoded"}

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=False,  # nosec B501  # noqa: S501
            ) as client:
                # 1. Create search job
                resp = await client.post(
                    search_url,
                    data={"search": spl, "output_mode": "json"},
                    headers=headers,
                )
                resp.raise_for_status()
                sid = resp.json().get("sid")
                if not sid:
                    logger.warning("splunk_search_no_sid", execution_id=execution_id)
                    return None

                # 2. Poll until done (max 30 s, 5 s per poll to avoid
                #    a single slow request consuming the entire deadline)
                job_url = f"{search_url}/{sid}"
                import time  # noqa: PLC0415
                poll_timeout = min(self.timeout, 5.0)
                deadline = time.monotonic() + 30.0
                while time.monotonic() < deadline:
                    status_resp = await client.get(
                        job_url,
                        params={"output_mode": "json"},
                        headers=self.auth_headers,
                        timeout=poll_timeout,
                    )
                    status_resp.raise_for_status()
                    dispatch_state = (
                        status_resp.json()
                        .get("entry", [{}])[0]
                        .get("content", {})
                        .get("dispatchState", "")
                    )
                    if dispatch_state == "DONE":
                        break
                    await asyncio.sleep(1)
                else:
                    logger.warning("splunk_search_timeout", execution_id=execution_id, sid=sid)
                    return None

                # 3. Fetch results
                results_resp = await client.get(
                    f"{job_url}/results",
                    params={"output_mode": "json"},
                    headers=self.auth_headers,
                )
                results_resp.raise_for_status()
                results = results_resp.json().get("results", [])
                if not results:
                    logger.info("splunk_search_no_results", execution_id=execution_id)
                    return None

                # Extract 'content' from the first matching event's _raw
                raw = results[0].get("_raw", "")
                try:
                    event_data = json.loads(raw) if isinstance(raw, str) else raw
                    return event_data.get("content")  # type: ignore[no-any-return]
                except (json.JSONDecodeError, AttributeError):
                    return raw or None

        except Exception:  # noqa: BLE001 — best-effort retrieval
            logger.exception("splunk_search_error", execution_id=execution_id)
            return None

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping Splunk via GET /services/server/info et valide l'authentification."""
        from datetime import datetime, timezone as tz
        url = f"{self.base_url}/services/server/info"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # nosec B501  # noqa: S501 — match send_event path, corporate CAs handled externally
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("splunk_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("splunk_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz.utc),
                error_message=str(exc),
            )


# Backward-compatible alias (Story 27.9 renamed SplunkAdapter → SplunkService)
SplunkAdapter = SplunkService
