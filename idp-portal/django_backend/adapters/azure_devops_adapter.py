"""
Azure DevOps Pipelines adapter for remote execution management.

Story 27.3: AzureDevOpsAdapter with trigger(), get_status(), get_job_logs(),
cancel_execution() for Azure DevOps Pipelines API v7.1+.

Azure DevOps uses a different API structure than AAP/Tower:
- POST /pipelines/{pipelineId}/runs to launch
- GET /pipelines/{pipelineId}/runs/{runId} for status (state + result)
- GET /pipelines/{pipelineId}/runs/{runId}/logs for log listing
- GET /pipelines/{pipelineId}/runs/{runId}/logs/{logId} for individual logs
- Auth: PAT via Basic auth (base64(:PAT))
"""
from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone

import httpx
import structlog

from adapters.base_adapter import BaseAdapter
from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

# Azure DevOps state+result → IDP portal execution status mapping
# Azure DevOps separates "state" (inProgress, completed, canceling)
# and "result" (succeeded, failed, canceled) — both must be checked.
AZURE_DEVOPS_STATUS_MAP: dict[str, str] = {
    "inProgress": "RUNNING",
    "canceling": "RUNNING",
    "completed:succeeded": "COMPLETED",
    "completed:failed": "FAILED",
    "completed:canceled": "CANCELLED",
}

# Terminal result values (when state == "completed")
AZURE_DEVOPS_TERMINAL_RESULTS = {"succeeded", "failed", "canceled"}

# Timeout for Azure DevOps API calls (seconds)
AZURE_DEVOPS_DEFAULT_TIMEOUT = 30.0
AZURE_DEVOPS_LOGS_TIMEOUT = 60.0

# API version query parameter
API_VERSION = "7.1"


def _map_azure_devops_status(state: str, result: str | None) -> str:
    """Map Azure DevOps state+result to IDP Portal status.

    Args:
        state: Azure DevOps run state (inProgress, completed, canceling).
        result: Azure DevOps run result (succeeded, failed, canceled) or None.

    Returns:
        IDP Portal status string (never None).
    """
    # LOW-2 FIX: Explicit None handling for mypy strict mode
    if state == "completed" and result:
        mapped = AZURE_DEVOPS_STATUS_MAP.get(f"completed:{result}")
        return mapped if mapped is not None else "FAILED"
    mapped = AZURE_DEVOPS_STATUS_MAP.get(state)
    return mapped if mapped is not None else "SUBMITTED"


class AzureDevOpsAdapter(BaseAdapter, IHealthCheckable):
    """Adapter for interacting with Azure DevOps Pipelines API v7.1+.

    Requires base_url, pipeline_id, and auth_headers to be provided at init.
    base_url format: https://dev.azure.com/{organization}/{project}

    Inherits from BaseAdapter to implement Strategy Pattern (Stories 27.1-27.3).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        timeout: float = AZURE_DEVOPS_DEFAULT_TIMEOUT,
        verify_ssl: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_headers = auth_headers
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    # ------------------------------------------------------------------
    # Trigger (launch) — pipeline run
    # ------------------------------------------------------------------

    async def trigger(  # type: ignore[override]
        self,
        pipeline_id: str,
        template_parameters: dict | None = None,
        variables: dict | None = None,
        branch: str | None = None,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Launch a pipeline run on Azure DevOps.

        Args:
            pipeline_id: Azure DevOps pipeline ID (must be numeric).
            template_parameters: Optional template parameters dict.
            variables: Optional runtime variables dict
                       (format: {"var": {"value": "val"}}).
            branch: Optional branch ref (e.g. "refs/heads/main").
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'platform_job_id', 'status', 'url'.

        Raises:
            ValueError: If pipeline_id is not numeric.
            ServiceUnavailableError: If Azure DevOps is unreachable or returns error.
        """
        # MEDIUM-5 FIX: Validate pipeline_id format (must be numeric)
        if not pipeline_id.isdigit():
            raise ValueError(
                f"Azure DevOps pipeline_id must be numeric, got: {pipeline_id}"
            )

        url = (
            f"{self.base_url}/_apis/pipelines/{pipeline_id}/runs"
            f"?api-version={API_VERSION}"
        )

        payload: dict = {}
        if template_parameters:
            payload["templateParameters"] = template_parameters
        if variables:
            payload["variables"] = variables
        if branch:
            payload["resources"] = {
                "repositories": {
                    "self": {"refName": branch}
                }
            }

        logger.info(
            "azure_devops_trigger_request",
            url=url,
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "azure_devops_trigger_timeout",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_TIMEOUT",
                message="Azure DevOps did not respond in time",
                details={"url": url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "azure_devops_trigger_http_error",
                url=url,
                status_code=exc.response.status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_HTTP_ERROR",
                message=f"Azure DevOps returned HTTP {exc.response.status_code}",
                details={"url": url, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "azure_devops_trigger_connection_error",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_CONNECTION_ERROR",
                message="Cannot connect to Azure DevOps",
                details={"url": url},
            ) from exc

        run_id = str(data.get("id", ""))
        state = data.get("state", "inProgress")
        result = data.get("result")
        idp_status = _map_azure_devops_status(state, result)

        # Extract pipeline_id from response for later use
        pipeline_info = data.get("pipeline", {})
        response_pipeline_id = str(pipeline_info.get("id", pipeline_id))

        logger.info(
            "azure_devops_trigger_success",
            platform_job_id=run_id,
            pipeline_id=response_pipeline_id,
            state=state,
            result=result,
            correlation_id=correlation_id,
        )

        return {
            "platform_job_id": run_id,
            "status": idp_status,
            "azure_devops_state": state,
            "azure_devops_result": result,
            "pipeline_id": response_pipeline_id,
            "url": data.get("url", ""),
        }

    # ------------------------------------------------------------------
    # Get status
    # ------------------------------------------------------------------

    async def get_status(  # type: ignore[override]
        self,
        platform_job_id: str,
        pipeline_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Get current status of an Azure DevOps pipeline run.

        Args:
            platform_job_id: Azure DevOps run ID.
            pipeline_id: Azure DevOps pipeline ID.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status' (IDP mapping), 'azure_devops_state',
            'azure_devops_result', 'createdDate', 'finishedDate'.

        Raises:
            ServiceUnavailableError: If Azure DevOps is unreachable.
        """
        url = (
            f"{self.base_url}/_apis/pipelines/{pipeline_id}"
            f"/runs/{platform_job_id}?api-version={API_VERSION}"
        )

        logger.info(
            "azure_devops_get_status_request",
            platform_job_id=platform_job_id,
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # nosec B501  # noqa: S501
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "azure_devops_get_status_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_TIMEOUT",
                message="Azure DevOps status check timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "azure_devops_get_status_not_found",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                return {
                    "status": "SUBMITTED",
                    "azure_devops_state": "not_found",
                    "azure_devops_result": None,
                    "createdDate": None,
                    "finishedDate": None,
                }
            logger.error(
                "azure_devops_get_status_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_HTTP_ERROR",
                message=f"Azure DevOps returned HTTP {status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "azure_devops_get_status_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_CONNECTION_ERROR",
                message="Cannot connect to Azure DevOps",
                details={"platform_job_id": platform_job_id},
            ) from exc

        state = data.get("state", "inProgress")
        result = data.get("result")
        idp_status = _map_azure_devops_status(state, result)

        logger.info(
            "azure_devops_get_status_success",
            platform_job_id=platform_job_id,
            state=state,
            result=result,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )

        return {
            "status": idp_status,
            "azure_devops_state": state,
            "azure_devops_result": result,
            "createdDate": data.get("createdDate"),
            "finishedDate": data.get("finishedDate"),
        }

    # ------------------------------------------------------------------
    # Get job logs — Story 27.3 Task 2.4
    # ------------------------------------------------------------------

    async def get_job_logs(  # type: ignore[override]
        self,
        platform_job_id: str,
        pipeline_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Retrieve logs for an Azure DevOps pipeline run.

        Azure DevOps logs are retrieved in two steps:
        1. GET /logs to list available log entries (each has a logId)
        2. GET /logs/{logId} for each entry to get plain text content

        Args:
            platform_job_id: Azure DevOps run ID.
            pipeline_id: Azure DevOps pipeline ID.
            correlation_id: Tracing correlation ID.

        Returns:
            Unified log dict:
            {
                "content": str,           # Combined log text
                "format": "text/plain",
                "timestamp": str,          # ISO timestamp of retrieval
                "complete": bool,          # True if run is in terminal state
                "job_status": str,         # Azure DevOps state at retrieval
            }

        Raises:
            ServiceUnavailableError: If Azure DevOps is unreachable.
        """
        logs_list_url = (
            f"{self.base_url}/_apis/pipelines/{pipeline_id}"
            f"/runs/{platform_job_id}/logs?api-version={API_VERSION}"
        )
        status_url = (
            f"{self.base_url}/_apis/pipelines/{pipeline_id}"
            f"/runs/{platform_job_id}?api-version={API_VERSION}"
        )

        logger.info(
            "azure_devops_get_job_logs_request",
            platform_job_id=platform_job_id,
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=AZURE_DEVOPS_LOGS_TIMEOUT,
                verify=False,  # nosec B501  # noqa: S501
            ) as client:
                # Step 1: Get log listing
                logs_response = await client.get(logs_list_url)
                logs_response.raise_for_status()
                logs_data = logs_response.json()

                # Step 2: Fetch individual log contents with rate limiting + retry
                # MEDIUM-1 FIX: Use StringIO for efficient concatenation
                # MEDIUM-2 FIX: Semaphore rate limiting (max 10 parallel requests)
                # MEDIUM-3 FIX: Retry and warning on individual log failures
                log_entries = logs_data.get("logs", [])
                buffer = io.StringIO()
                semaphore = asyncio.Semaphore(10)

                async def fetch_log(entry: dict) -> tuple[int | None, str]:
                    """Fetch a single log entry with retry on transient errors."""
                    log_id = entry.get("id")
                    if log_id is None:
                        return None, ""

                    log_url = (
                        f"{self.base_url}/_apis/pipelines/{pipeline_id}"
                        f"/runs/{platform_job_id}/logs/{log_id}"
                        f"?api-version={API_VERSION}"
                    )

                    async with semaphore:
                        for attempt in range(2):  # 1 retry
                            try:
                                log_response = await client.get(log_url)
                                if log_response.status_code == 200:
                                    return log_id, log_response.text
                                if log_response.status_code >= 500 and attempt == 0:
                                    # Retry on 5xx errors
                                    await asyncio.sleep(0.5)
                                    continue
                                # Non-retryable error
                                logger.warning(
                                    "azure_devops_get_job_logs_individual_failed",
                                    log_id=log_id,
                                    status_code=log_response.status_code,
                                    attempt=attempt + 1,
                                    correlation_id=correlation_id,
                                )
                                return log_id, ""
                            except httpx.HTTPError as e:
                                if attempt == 0:
                                    await asyncio.sleep(0.5)
                                    continue
                                logger.warning(
                                    "azure_devops_get_job_logs_individual_error",
                                    log_id=log_id,
                                    error=str(e),
                                    correlation_id=correlation_id,
                                )
                                return log_id, ""
                    return log_id, ""

                # Fetch all logs with rate limiting
                tasks = [fetch_log(entry) for entry in log_entries]
                results = await asyncio.gather(*tasks)

                # Write to buffer in order
                for log_id, content in results:
                    if content:
                        buffer.write(content)
                        buffer.write("\n")

                combined_content = buffer.getvalue()

                # Step 3: Get current run status
                status_response = await client.get(status_url)
                status_response.raise_for_status()
                status_data = status_response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "azure_devops_get_job_logs_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_LOGS_TIMEOUT",
                message="Azure DevOps log retrieval timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "azure_devops_get_job_logs_not_found",
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
                "azure_devops_get_job_logs_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_LOGS_UNAVAILABLE",
                message=f"Azure DevOps returned HTTP {status_code} for logs",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "azure_devops_get_job_logs_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_CONNECTION_ERROR",
                message="Cannot connect to Azure DevOps for log retrieval",
                details={"platform_job_id": platform_job_id},
            ) from exc

        state = status_data.get("state", "inProgress")
        result = status_data.get("result")
        is_complete = state == "completed" and result in AZURE_DEVOPS_TERMINAL_RESULTS

        logger.info(
            "azure_devops_get_job_logs_success",
            platform_job_id=platform_job_id,
            log_entries_count=len(log_entries),
            log_length=len(combined_content),
            job_status=state,
            result=result,
            complete=is_complete,
            correlation_id=correlation_id,
        )

        return {
            "content": combined_content,
            "format": "text/plain",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "complete": is_complete,
            "job_status": state,
        }

    # ------------------------------------------------------------------
    # Cancel execution
    # ------------------------------------------------------------------

    async def cancel_execution(  # type: ignore[override]
        self,
        platform_job_id: str,
        pipeline_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> None:
        """Attempt to cancel a running pipeline run on Azure DevOps.

        Azure DevOps Pipelines API v7.1 does not expose a direct cancel
        endpoint. Instead, we use the Builds API to PATCH the build status
        to "cancelling". A pipeline run corresponds to a build.

        Args:
            platform_job_id: The run ID (also build ID) on Azure DevOps.
            pipeline_id: Azure DevOps pipeline ID (unused for cancel, kept
                         for interface consistency).
            correlation_id: Tracing correlation ID.

        Raises:
            ServiceUnavailableError: If Azure DevOps is unreachable.
        """
        # Use Builds API for cancellation: PATCH /build/builds/{buildId}
        url = (
            f"{self.base_url}/_apis/build/builds/{platform_job_id}"
            f"?api-version={API_VERSION}"
        )

        logger.info(
            "azure_devops_cancel_request",
            platform_job_id=platform_job_id,
            pipeline_id=pipeline_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=False,  # nosec B501  # noqa: S501
            ) as client:
                response = await client.patch(
                    url,
                    json={"status": "cancelling"},
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error(
                "azure_devops_cancel_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_TIMEOUT",
                message="Azure DevOps cancel request timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "azure_devops_cancel_http_error",
                platform_job_id=platform_job_id,
                status_code=exc.response.status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_HTTP_ERROR",
                message=f"Azure DevOps cancel returned HTTP {exc.response.status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "azure_devops_cancel_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="AZURE_DEVOPS_CONNECTION_ERROR",
                message="Cannot connect to Azure DevOps for cancellation",
                details={"platform_job_id": platform_job_id},
            ) from exc

        logger.info(
            "azure_devops_cancel_success",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping Azure DevOps via GET /_apis/?api-version=7.1 et valide l'authentification PAT."""
        url = f"{self.base_url}/_apis/?api-version={API_VERSION}"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("azure_devops_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("azure_devops_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz=timezone.utc),
                error_message=str(exc),
            )
