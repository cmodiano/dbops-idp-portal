"""
Ansible Tower / AWX adapter for remote execution management.

Story 27.2: TowerAdapter with trigger(), get_status(), get_job_logs(),
cancel_execution() — mirrors AAPAdapter structure for Tower/AWX API v2.

Tower/AWX API is identical to AAP API v2 (same endpoints under /api/v2/).
Separate adapter for clarity, evolvability, and future AAP 2.5+ divergence.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from adapters.base_adapter import BaseAdapter
from core.exceptions import ServiceUnavailableError

logger = structlog.get_logger(__name__)

# Tower/AWX job status → IDP portal execution status mapping (identical to AAP)
TOWER_STATUS_MAP: dict[str, str] = {
    "pending": "SUBMITTED",
    "waiting": "SUBMITTED",
    "running": "RUNNING",
    "successful": "COMPLETED",
    "failed": "FAILED",
    "error": "FAILED",
    "canceled": "CANCELLED",
}

# Timeout for Tower API calls (seconds)
TOWER_DEFAULT_TIMEOUT = 30.0
TOWER_LOGS_TIMEOUT = 60.0


class TowerAdapter(BaseAdapter):
    """Adapter for interacting with Ansible Tower / AWX API v2.

    Requires base_url and auth_headers to be provided at init.
    Typically instantiated via integration config (base_url, credential_ref → Vault).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = TOWER_DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Trigger (launch) — job template or workflow job template
    # ------------------------------------------------------------------

    async def trigger(
        self,
        template_id: str,
        resource_type: str = "job_template",
        extra_vars: dict | None = None,
        limit: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """Launch a job template or workflow job template on Tower/AWX.

        Args:
            template_id: Tower template ID to launch.
            resource_type: 'job_template' or 'workflow_job'.
            extra_vars: Optional extra variables dict.
            limit: Optional host/group limit string.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'platform_job_id', 'status', 'url'.

        Raises:
            ServiceUnavailableError: If Tower is unreachable or returns error.
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
            "tower_trigger_request",
            url=url,
            resource_type=resource_type,
            template_id=template_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # noqa: S501 — corporate CAs handled externally
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "tower_trigger_timeout",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_TIMEOUT",
                message="Tower did not respond in time",
                details={"url": url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "tower_trigger_http_error",
                url=url,
                status_code=exc.response.status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_HTTP_ERROR",
                message=f"Tower returned HTTP {exc.response.status_code}",
                details={"url": url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "tower_trigger_connection_error",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_CONNECTION_ERROR",
                message="Cannot connect to Tower",
                details={"url": url},
            ) from exc

        platform_job_id = str(data.get("id", ""))
        tower_status = data.get("status", "pending")

        logger.info(
            "tower_trigger_success",
            platform_job_id=platform_job_id,
            tower_status=tower_status,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        return {
            "platform_job_id": platform_job_id,
            "status": TOWER_STATUS_MAP.get(tower_status, "SUBMITTED"),
            "tower_status": tower_status,
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
    ) -> dict:
        """Get current status of a Tower/AWX job.

        Args:
            platform_job_id: Tower job ID.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status' (IDP mapping), 'tower_status', 'started', 'finished'.

        Raises:
            ServiceUnavailableError: If Tower is unreachable.
        """
        if resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/"
        else:
            url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/"

        logger.info(
            "tower_get_status_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # noqa: S501
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error("tower_get_status_timeout", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_TIMEOUT", message="Tower status check timed out", details={"platform_job_id": platform_job_id}) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("tower_get_status_http_error", platform_job_id=platform_job_id, status_code=exc.response.status_code, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_HTTP_ERROR", message=f"Tower returned HTTP {exc.response.status_code}", details={"platform_job_id": platform_job_id, "status_code": exc.response.status_code}) from exc
        except httpx.HTTPError as exc:
            logger.error("tower_get_status_connection_error", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_CONNECTION_ERROR", message="Cannot connect to Tower", details={"platform_job_id": platform_job_id}) from exc

        tower_status = data.get("status", "pending")

        logger.info(
            "tower_get_status_success",
            platform_job_id=platform_job_id,
            tower_status=tower_status,
            correlation_id=correlation_id,
        )

        return {
            "status": TOWER_STATUS_MAP.get(tower_status, "SUBMITTED"),
            "tower_status": tower_status,
            "started": data.get("started"),
            "finished": data.get("finished"),
            "elapsed": data.get("elapsed"),
        }

    # ------------------------------------------------------------------
    # Get job logs (stdout)
    # ------------------------------------------------------------------

    async def get_job_logs(
        self,
        platform_job_id: str,
        resource_type: str = "job_template",
        correlation_id: str | None = None,
    ) -> dict:
        """Retrieve stdout logs for a Tower/AWX job.

        Args:
            platform_job_id: Tower job ID.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Returns:
            Unified log dict with content, format, timestamp, complete, job_status.

        Raises:
            ServiceUnavailableError: If Tower is unreachable or returns an error.
        """
        if resource_type == "workflow_job":
            stdout_url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/stdout/"
            status_url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/"
        else:
            stdout_url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/stdout/"
            status_url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/"

        logger.info(
            "tower_get_job_logs_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=TOWER_LOGS_TIMEOUT,
                verify=False,  # noqa: S501
            ) as client:
                stdout_response = await client.get(
                    stdout_url,
                    params={"format": "txt"},
                )
                stdout_response.raise_for_status()
                content = stdout_response.text

                status_response = await client.get(status_url)
                status_response.raise_for_status()
                status_data = status_response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "tower_get_job_logs_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_LOGS_TIMEOUT",
                message="Tower log retrieval timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "tower_get_job_logs_not_found",
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
                "tower_get_job_logs_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_LOGS_UNAVAILABLE",
                message=f"Tower returned HTTP {status_code} for logs",
                details={"platform_job_id": platform_job_id, "status_code": status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "tower_get_job_logs_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TOWER_CONNECTION_ERROR",
                message="Cannot connect to Tower for log retrieval",
                details={"platform_job_id": platform_job_id},
            ) from exc

        tower_status = status_data.get("status", "unknown")
        terminal_statuses = {"successful", "failed", "error", "canceled"}
        is_complete = tower_status in terminal_statuses

        logger.info(
            "tower_get_job_logs_success",
            platform_job_id=platform_job_id,
            log_length=len(content),
            job_status=tower_status,
            complete=is_complete,
            correlation_id=correlation_id,
        )

        return {
            "content": content,
            "format": "text/plain",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "complete": is_complete,
            "job_status": tower_status,
        }

    # ------------------------------------------------------------------
    # Cancel execution
    # ------------------------------------------------------------------

    async def cancel_execution(
        self,
        platform_job_id: str,
        resource_type: str = "job_template",
        correlation_id: str | None = None,
    ) -> None:
        """Attempt to cancel a running job on Tower/AWX.

        Args:
            platform_job_id: The job ID on the Tower platform.
            resource_type: 'job_template' or 'workflow_job'.
            correlation_id: Tracing correlation ID.

        Raises:
            ServiceUnavailableError: If Tower is unreachable.
        """
        if resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/cancel/"
        else:
            url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/cancel/"

        logger.info(
            "tower_cancel_request",
            platform_job_id=platform_job_id,
            resource_type=resource_type,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # noqa: S501
            ) as client:
                response = await client.post(url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("tower_cancel_timeout", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_TIMEOUT", message="Tower cancel request timed out", details={"platform_job_id": platform_job_id}) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("tower_cancel_http_error", platform_job_id=platform_job_id, status_code=exc.response.status_code, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_HTTP_ERROR", message=f"Tower cancel returned HTTP {exc.response.status_code}", details={"platform_job_id": platform_job_id, "status_code": exc.response.status_code}) from exc
        except httpx.HTTPError as exc:
            logger.error("tower_cancel_connection_error", platform_job_id=platform_job_id, correlation_id=correlation_id, error=str(exc))
            raise ServiceUnavailableError(code="TOWER_CONNECTION_ERROR", message="Cannot connect to Tower for cancellation", details={"platform_job_id": platform_job_id}) from exc

        logger.info(
            "tower_cancel_success",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )
