"""
AAP (Ansible Automation Platform) adapter for remote execution management.

Story 27.1: Extended with get_job_logs(), trigger(), get_status() for full
AAP integration including log retrieval and job monitoring.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from django.conf import settings

from adapters.base_adapter import BaseAdapter
from adapters.status_mappers import AAP_STATUS_MAP, AAP_TOWER_TERMINAL_STATUSES  # noqa: F401 — re-exported for backward compat
from core.exceptions import AdapterTimeoutError, ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

# Timeout for AAP API calls (seconds)
AAP_DEFAULT_TIMEOUT = 30.0
AAP_LOGS_TIMEOUT = 60.0  # Longer timeout for potentially large log retrieval


class AAPAdapter(BaseAdapter, IHealthCheckable):
    """Adapter for interacting with Ansible Automation Platform API v2.

    Requires base_url and auth_headers to be provided at init.
    Typically instantiated via integration config (base_url, credential_ref → Vault).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float | None = None,
        ssl_verify: bool = True,
        ca_bundle_path: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        default_timeout = getattr(settings, 'AAP_SOCKET_TIMEOUT', AAP_DEFAULT_TIMEOUT)
        self.timeout = timeout if timeout is not None else default_timeout
        # verify: use CA bundle path if set, otherwise ssl_verify boolean
        self._verify = (ca_bundle_path or "").strip() or ssl_verify
        if self._verify is False:
            logger.warning(
                "aap_adapter_ssl_verify_disabled",
                base_url=self.base_url,
                message="SSL verification is disabled for this AAP integration; connection is not verified.",
            )

    # ------------------------------------------------------------------
    # Trigger (launch) — job template or workflow job template
    # ------------------------------------------------------------------

    async def trigger(  # type: ignore[override]
        self,
        template_id: str,
        resource_type: str = "job_template",
        extra_vars: dict | None = None,
        limit: str | None = None,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Launch a job template or workflow job template on AAP.

        Args:
            template_id: AAP template ID to launch.
            resource_type: 'job_template' or 'workflow_job'.
            extra_vars: Optional extra variables dict.
            limit: Optional host/group limit string.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'platform_job_id', 'status', 'url'.

        Raises:
            AdapterTimeoutError: If AAP does not respond within the configured timeout.
            ServiceUnavailableError: If AAP returns an HTTP error or connection fails.
        """
        if resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_job_templates/{template_id}/launch/"
        else:
            url = f"{self.base_url}/api/v2/job_templates/{template_id}/launch/"

        payload: dict = {}
        if extra_vars:
            payload["extra_vars"] = extra_vars
        if limit:
            payload["limit"] = limit

        logger.info(
            "aap_trigger_request",
            url=url,
            resource_type=resource_type,
            template_id=template_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._verify,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "aap_trigger_timeout",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise AdapterTimeoutError(
                adapter_type="aap",
                message="AAP did not respond in time",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "aap_trigger_http_error",
                url=url,
                status_code=exc.response.status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AAP_HTTP_ERROR",
                message=f"AAP returned HTTP {exc.response.status_code}",
                details={"url": url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "aap_trigger_connection_error",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AAP_CONNECTION_ERROR",
                message="Cannot connect to AAP",
                details={"url": url},
            ) from exc

        platform_job_id = str(data.get("id", ""))
        aap_status = data.get("status", "pending")

        logger.info(
            "aap_trigger_success",
            platform_job_id=platform_job_id,
            aap_status=aap_status,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        return {
            "platform_job_id": platform_job_id,
            "status": AAP_STATUS_MAP.get(aap_status, "SUBMITTED"),
            "aap_status": aap_status,
            "url": data.get("url", ""),
        }

    # ------------------------------------------------------------------
    # Get status
    # ------------------------------------------------------------------

    async def get_status(
        self,
        platform_job_id: str,
        resource_type: str = "job_template",
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Get current status of an AAP job.

        Args:
            platform_job_id: AAP job ID.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status' (IDP mapping), 'aap_status', 'started', 'finished',
            'elapsed', 'artifacts', 'failed_tasks', 'changed_hosts'.

        Raises:
            AdapterTimeoutError: If AAP does not respond within the configured timeout.
            ServiceUnavailableError: If AAP returns an HTTP error or connection fails.
        """
        if resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/"
        else:
            url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/"

        logger.info(
            "aap_get_status_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        failed_tasks: list = []
        changed_hosts: list = []
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._verify,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                # Récupérer job_host_summaries pour failed_tasks/changed_hosts (job_template uniquement)
                if resource_type != "workflow_job":
                    try:
                        summaries_url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/job_host_summaries/?page_size=200"
                        summaries_response = await client.get(summaries_url)
                        summaries_response.raise_for_status()
                        summaries_data = summaries_response.json()
                        for host_summary in summaries_data.get("results", []):
                            host_name = host_summary.get("host_name", "")
                            if host_name and host_summary.get("failed", 0) > 0:
                                failed_tasks.append({"task": host_name, "host": host_name})
                            if host_name and host_summary.get("changed", 0) > 0:
                                changed_hosts.append(host_name)
                    except Exception:  # noqa: BLE001 — résilience: job_host_summaries non critique
                        logger.warning(
                            "aap_get_status_host_summaries_failed",
                            platform_job_id=platform_job_id,
                            correlation_id=correlation_id,
                        )
        except httpx.TimeoutException as exc:
            logger.error("aap_get_status_timeout", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise AdapterTimeoutError(adapter_type="aap", message="AAP status check timed out", platform_job_id=platform_job_id) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("aap_get_status_http_error", platform_job_id=platform_job_id, status_code=exc.response.status_code, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="AAP_HTTP_ERROR", message=f"AAP returned HTTP {exc.response.status_code}", details={"platform_job_id": platform_job_id, "status_code": exc.response.status_code}) from exc
        except httpx.HTTPError as exc:
            logger.error("aap_get_status_connection_error", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="AAP_CONNECTION_ERROR", message="Cannot connect to AAP", details={"platform_job_id": platform_job_id}) from exc

        aap_status = data.get("status", "pending")
        artifacts = data.get("artifacts") or {}

        logger.info(
            "aap_get_status_success",
            platform_job_id=platform_job_id,
            aap_status=aap_status,
            num_artifacts=len(artifacts),
            correlation_id=correlation_id,
        )

        return {
            "status": AAP_STATUS_MAP.get(aap_status, "SUBMITTED"),
            "aap_status": aap_status,
            "started": data.get("started"),
            "finished": data.get("finished"),
            "elapsed": data.get("elapsed"),
            "artifacts": artifacts,
            "failed_tasks": failed_tasks,
            "changed_hosts": changed_hosts,
        }

    # ------------------------------------------------------------------
    # Get job logs (stdout) — Story 27.1 Task 2
    # ------------------------------------------------------------------

    async def get_job_logs(
        self,
        platform_job_id: str,
        resource_type: str = "job_template",
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Retrieve stdout logs for an AAP job.

        Args:
            platform_job_id: AAP job ID.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Returns:
            Unified log dict:
            {
                "content": str,           # Raw log text
                "format": "text/plain",
                "timestamp": str,          # ISO timestamp of retrieval
                "complete": bool,          # True if job is in terminal state
                "job_status": str,         # AAP status at retrieval time
            }

        Raises:
            ServiceUnavailableError: If AAP is unreachable or returns an error.
        """
        if resource_type == "workflow_job":
            stdout_url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/stdout/"
            status_url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/"
        else:
            stdout_url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/stdout/"
            status_url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/"

        logger.info(
            "aap_get_job_logs_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=AAP_LOGS_TIMEOUT,
                verify=self._verify,
            ) as client:
                # Fetch stdout as plain text
                stdout_response = await client.get(
                    stdout_url,
                    params={"format": "txt"},
                )
                stdout_response.raise_for_status()
                content = stdout_response.text

                # Fetch current job status
                status_response = await client.get(status_url)
                status_response.raise_for_status()
                status_data = status_response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "aap_get_job_logs_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AAP_LOGS_TIMEOUT",
                message="AAP log retrieval timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                # MEDIUM-1 FIX: Return job_status="not_found" to allow caller to distinguish
                # between "job exists but logs empty" vs "job not found yet (retry later)"
                logger.warning(
                    "aap_get_job_logs_not_found",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                return {
                    "content": "",
                    "format": "text/plain",
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "complete": False,
                    "job_status": "not_found",
                }
            logger.error(
                "aap_get_job_logs_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AAP_LOGS_UNAVAILABLE",
                message=f"AAP returned HTTP {status_code} for logs",
                details={"platform_job_id": platform_job_id, "status_code": status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "aap_get_job_logs_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AAP_CONNECTION_ERROR",
                message="Cannot connect to AAP for log retrieval",
                details={"platform_job_id": platform_job_id},
            ) from exc

        aap_status = status_data.get("status", "unknown")
        is_complete = aap_status in AAP_TOWER_TERMINAL_STATUSES

        logger.info(
            "aap_get_job_logs_success",
            platform_job_id=platform_job_id,
            log_length=len(content),
            job_status=aap_status,
            complete=is_complete,
            correlation_id=correlation_id,
        )

        return {
            "content": content,
            "format": "text/plain",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "complete": is_complete,
            "job_status": aap_status,
        }

    # ------------------------------------------------------------------
    # List templates — Story 31.5
    # ------------------------------------------------------------------

    async def list_templates(
        self,
        resource_type: str = "job_template",
        search: str | None = None,
        page_size: int = 200,
    ) -> list[dict]:
        """List job templates or workflow job templates from AAP API v2.

        Args:
            resource_type: 'job_template' or 'workflow_job'.
            search: Optional search string (name filter).
            page_size: Max results per page (default 200, AAP max 200).

        Returns:
            List of dicts with keys: id, name, description.

        Raises:
            ValueError: If resource_type is invalid.
            ServiceUnavailableError: If AAP API is unreachable or returns error.
        """
        if resource_type not in ("job_template", "workflow_job"):
            raise ValueError(f"resource_type invalide: {resource_type!r}")

        endpoint_map = {
            "job_template": "job_templates",
            "workflow_job": "workflow_job_templates",
        }
        endpoint = endpoint_map[resource_type]
        url = f"{self.base_url}/api/v2/{endpoint}/"

        params: dict[str, str | int] = {"page_size": page_size}
        if search:
            params["search"] = search

        logger.info(
            "aap_list_templates_request",
            url=url,
            resource_type=resource_type,
            search=search,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._verify,
            ) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "description": item.get("description", ""),
                    }
                    for item in data.get("results", [])
                ]
        except httpx.TimeoutException as exc:
            logger.warning("aap_list_templates_timeout", url=url, error=str(exc))
            raise AdapterTimeoutError(
                adapter_type="aap",
                message="AAP API timeout",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "aap_list_templates_http_error",
                url=url,
                status=exc.response.status_code,
            )
            raise ServiceUnavailableError(
                code="AAP_HTTP_ERROR",
                message=f"AAP API erreur {exc.response.status_code}",
                details={"url": url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("aap_list_templates_request_error", url=url, error=str(exc))
            raise ServiceUnavailableError(
                code="AAP_CONNECTION_ERROR",
                message="AAP API indisponible",
                details={"url": url},
            ) from exc

    # ------------------------------------------------------------------
    # Cancel execution
    # ------------------------------------------------------------------

    async def cancel_execution(
        self,
        platform_job_id: str,
        resource_type: str = "job_template",
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> None:
        """Attempt to cancel a running job on AAP.

        Args:
            platform_job_id: The job ID on the AAP platform.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Raises:
            ServiceUnavailableError: If AAP is unreachable.
        """
        if resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/cancel/"
        else:
            url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/cancel/"

        logger.info(
            "aap_cancel_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._verify,
            ) as client:
                response = await client.post(url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("aap_cancel_timeout", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="AAP_TIMEOUT", message="AAP cancel request timed out", details={"platform_job_id": platform_job_id}) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("aap_cancel_http_error", platform_job_id=platform_job_id, status_code=exc.response.status_code, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="AAP_HTTP_ERROR", message=f"AAP cancel returned HTTP {exc.response.status_code}", details={"platform_job_id": platform_job_id, "status_code": exc.response.status_code}) from exc
        except httpx.HTTPError as exc:
            logger.error("aap_cancel_connection_error", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="AAP_CONNECTION_ERROR", message="Cannot connect to AAP for cancellation", details={"platform_job_id": platform_job_id}) from exc

        logger.info(
            "aap_cancel_success",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping AAP via GET /api/v2/ping/ et valide l'authentification.

        Returns:
            HealthCheckResult avec status ok/error, timestamp, message d'erreur.
        """
        url = f"{self.base_url}/api/v2/ping/"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self._verify,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("aap_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("aap_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz=timezone.utc),
                error_message=str(exc),
            )
