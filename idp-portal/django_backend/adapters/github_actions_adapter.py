"""
GitHub Actions adapter for remote execution management.

Story 27.4: GitHubActionsAdapter with trigger(), get_status(), get_job_logs(),
cancel_execution() for GitHub Actions REST API v3.

GitHub Actions specifics vs AAP/Tower/Azure DevOps:
- POST /workflows/{workflow_id}/dispatches returns 204 No Content (no run_id)
- run_id recovered via polling GET /runs with timestamp filters
- Logs are a ZIP archive via an expiring redirect (1 min)
- Two status fields: status + conclusion (like Azure DevOps state + result)
- Requires owner/repo in every endpoint URL
- Auth: Bearer PAT (fine-grained recommended) or GitHub App token
"""
# Responsabilité : Adaptateur GitHub Actions (dispatch sans run_id → polling, logs en ZIP,
# 2 champs status/conclusion) — volume justifié par la complexité protocolaire GHA (Story 35.4 AC3).
from __future__ import annotations

import asyncio
import io
import zipfile
from datetime import datetime, timezone

import httpx
import structlog

from adapters.base_adapter import BaseAdapter
from adapters.status_mappers import (
    GITHUB_ACTIONS_TERMINAL_CONCLUSIONS as GITHUB_ACTIONS_TERMINAL_CONCLUSIONS,
    map_github_actions_status,
)
from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

_map_github_actions_status = map_github_actions_status  # backward compat alias for existing tests

# Timeout for GitHub Actions API calls (seconds)
GITHUB_ACTIONS_DEFAULT_TIMEOUT = 30.0
GITHUB_ACTIONS_LOGS_TIMEOUT = 60.0

# GitHub API headers
GITHUB_API_ACCEPT = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"

# Polling settings for run_id discovery after workflow_dispatch
RUN_ID_POLL_DELAY = 3.0  # seconds to wait before first poll
RUN_ID_POLL_MAX_ATTEMPTS = 5
RUN_ID_POLL_INTERVAL = 2.0  # seconds between retries


class GitHubActionsAdapter(BaseAdapter, IHealthCheckable):
    """Adapter for interacting with GitHub Actions REST API v3.

    Requires base_url, owner, repo, and auth_headers at init.
    base_url format: https://api.github.com (or Enterprise URL)

    Inherits from BaseAdapter to implement Strategy Pattern (Stories 27.1-27.4).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        owner: str = "",
        repo: str = "",
        timeout: float = GITHUB_ACTIONS_DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
    ) -> None:
        if not owner or not repo:
            raise ValueError("GitHub Actions adapter requires non-empty 'owner' and 'repo'")
        self.base_url = base_url.rstrip("/")
        self.auth_headers = {
            **auth_headers,
            "Accept": GITHUB_API_ACCEPT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        self.owner = owner
        self.repo = repo
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def _repos_url(self) -> str:
        """Build the /repos/{owner}/{repo} base URL."""
        return f"{self.base_url}/repos/{self.owner}/{self.repo}"

    # ------------------------------------------------------------------
    # Trigger (launch) — workflow_dispatch
    # ------------------------------------------------------------------

    async def trigger(
        self,
        workflow_id: str = "",
        ref: str = "main",
        inputs: dict | None = None,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Launch a workflow run on GitHub Actions via workflow_dispatch.

        GitHub Actions POST /dispatches returns 204 No Content (no run_id).
        We recover the run_id via polling GET /runs with timestamp filters.

        Args:
            workflow_id: GitHub Actions workflow ID or filename (e.g. "deploy.yaml").
            ref: Git ref (branch or tag) to run the workflow on.
            inputs: Optional workflow input parameters (max 25).
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'platform_job_id', 'status', 'url'.

        Raises:
            ServiceUnavailableError: If GitHub is unreachable or returns error.
        """
        dispatch_url = (
            f"{self._repos_url()}/actions/workflows/{workflow_id}/dispatches"
        )

        payload: dict = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs

        # Record timestamp before dispatch for run_id polling
        trigger_timestamp = datetime.now(tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        logger.info(
            "github_actions_trigger_request",
            url=dispatch_url,
            workflow_id=workflow_id,
            ref=ref,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(dispatch_url, json=payload)
                response.raise_for_status()

                # 204 No Content expected — now poll for run_id
                run_id = await self._poll_run_id(
                    client,
                    workflow_id=workflow_id,
                    trigger_timestamp=trigger_timestamp,
                    correlation_id=correlation_id,
                )
        except httpx.TimeoutException as exc:
            logger.error(
                "github_actions_trigger_timeout",
                url=dispatch_url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_TIMEOUT",
                message="GitHub Actions did not respond in time",
                details={"url": dispatch_url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "github_actions_trigger_http_error",
                url=dispatch_url,
                status_code=exc.response.status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_HTTP_ERROR",
                message=f"GitHub Actions returned HTTP {exc.response.status_code}",
                details={
                    "url": dispatch_url,
                    "status_code": exc.response.status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "github_actions_trigger_connection_error",
                url=dispatch_url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_CONNECTION_ERROR",
                message="Cannot connect to GitHub Actions",
                details={"url": dispatch_url},
            ) from exc

        logger.info(
            "github_actions_trigger_success",
            platform_job_id=run_id,
            workflow_id=workflow_id,
            correlation_id=correlation_id,
        )

        return {
            "platform_job_id": run_id,
            "status": "SUBMITTED",
            "url": (
                f"https://github.com/{self.owner}/{self.repo}"
                f"/actions/runs/{run_id}"
                if run_id
                else ""
            ),
        }

    async def _poll_run_id(
        self,
        client: httpx.AsyncClient,
        workflow_id: str,
        trigger_timestamp: str,
        correlation_id: str | None = None,
    ) -> str:
        """Poll for the run_id after workflow_dispatch (returns 204 No Content).

        Args:
            client: Active httpx AsyncClient.
            workflow_id: Workflow ID or filename.
            trigger_timestamp: ISO timestamp just before dispatch.
            correlation_id: Tracing correlation ID.

        Returns:
            Run ID as string.

        Raises:
            ServiceUnavailableError: If run_id cannot be found after max attempts.
        """
        runs_url = (
            f"{self._repos_url()}/actions/runs"
            f"?event=workflow_dispatch&created=>{trigger_timestamp}&per_page=1"
        )

        await asyncio.sleep(RUN_ID_POLL_DELAY)

        for attempt in range(RUN_ID_POLL_MAX_ATTEMPTS):
            try:
                response = await client.get(runs_url)
                response.raise_for_status()
                data = response.json()
                runs = data.get("workflow_runs", [])
                if runs:
                    run_id = str(runs[0].get("id", ""))
                    if run_id:
                        logger.info(
                            "github_actions_run_id_found",
                            run_id=run_id,
                            attempt=attempt + 1,
                            correlation_id=correlation_id,
                        )
                        return run_id
            except httpx.HTTPError as exc:
                logger.warning(
                    "github_actions_run_id_poll_error",
                    attempt=attempt + 1,
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                # Continue to next attempt despite HTTP errors

            if attempt < RUN_ID_POLL_MAX_ATTEMPTS - 1:
                await asyncio.sleep(RUN_ID_POLL_INTERVAL)

        logger.error(
            "github_actions_run_id_not_found",
            workflow_id=workflow_id,
            trigger_timestamp=trigger_timestamp,
            max_attempts=RUN_ID_POLL_MAX_ATTEMPTS,
            correlation_id=correlation_id,
        )
        raise ServiceUnavailableError(
            code="GITHUB_ACTIONS_RUN_NOT_FOUND",
            message="Could not find run_id after workflow_dispatch",
            details={
                "workflow_id": workflow_id,
                "trigger_timestamp": trigger_timestamp,
            },
        )

    # ------------------------------------------------------------------
    # Get status
    # ------------------------------------------------------------------

    async def get_status(
        self,
        platform_job_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Get current status of a GitHub Actions workflow run.

        Args:
            platform_job_id: GitHub Actions run ID.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status' (IDP mapping), 'github_actions_status',
            'github_actions_conclusion', 'created_at', 'updated_at'.

        Raises:
            ServiceUnavailableError: If GitHub is unreachable.
        """
        url = f"{self._repos_url()}/actions/runs/{platform_job_id}"

        logger.info(
            "github_actions_get_status_request",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "github_actions_get_status_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_TIMEOUT",
                message="GitHub Actions status check timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "github_actions_get_status_not_found",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                return {
                    "status": "SUBMITTED",
                    "github_actions_status": "not_found",
                    "github_actions_conclusion": None,
                    "created_at": None,
                    "updated_at": None,
                }
            logger.error(
                "github_actions_get_status_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_HTTP_ERROR",
                message=f"GitHub Actions returned HTTP {status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "github_actions_get_status_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_CONNECTION_ERROR",
                message="Cannot connect to GitHub Actions",
                details={"platform_job_id": platform_job_id},
            ) from exc

        gh_status = data.get("status", "queued")
        gh_conclusion = data.get("conclusion")
        idp_status = map_github_actions_status(gh_status, gh_conclusion)

        logger.info(
            "github_actions_get_status_success",
            platform_job_id=platform_job_id,
            github_status=gh_status,
            github_conclusion=gh_conclusion,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )

        return {
            "status": idp_status,
            "github_actions_status": gh_status,
            "github_actions_conclusion": gh_conclusion,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    # ------------------------------------------------------------------
    # Get job logs — ZIP archive with expiring redirect
    # ------------------------------------------------------------------

    async def get_job_logs(
        self,
        platform_job_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Retrieve logs for a GitHub Actions workflow run.

        GitHub Actions logs are a ZIP archive accessed via an expiring redirect.
        Logs are only available when status == completed.

        Args:
            platform_job_id: GitHub Actions run ID.
            correlation_id: Tracing correlation ID.

        Returns:
            Unified log dict:
            {
                "content": str,           # Combined log text from ZIP
                "format": "text/plain",
                "timestamp": str,          # ISO timestamp of retrieval
                "complete": bool,          # True if run is in terminal state
                "job_status": str,         # GitHub Actions status at retrieval
            }

        Raises:
            ServiceUnavailableError: If GitHub is unreachable.
        """
        status_url = f"{self._repos_url()}/actions/runs/{platform_job_id}"
        logs_url = f"{self._repos_url()}/actions/runs/{platform_job_id}/logs"

        logger.info(
            "github_actions_get_job_logs_request",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,  # Use consistent timeout with status check
                follow_redirects=True,
                verify=self.verify_ssl,
            ) as client:
                # Step 1: Get current run status
                status_response = await client.get(status_url)
                status_response.raise_for_status()
                status_data = status_response.json()

                gh_status = status_data.get("status", "queued")
                gh_conclusion = status_data.get("conclusion")

                # Logs only available when completed
                if gh_status != "completed":
                    logger.info(
                        "github_actions_get_job_logs_not_ready",
                        platform_job_id=platform_job_id,
                        github_status=gh_status,
                        correlation_id=correlation_id,
                    )
                    return {
                        "content": "",
                        "format": "text/plain",
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                        "complete": False,
                        "job_status": gh_status,
                    }

                # Step 2: Download ZIP logs (follow redirect)
                logs_response = await client.get(logs_url)
                logs_response.raise_for_status()

                # Step 3: Extract logs from ZIP archive
                combined_content = self._extract_logs_from_zip(
                    logs_response.content,
                    correlation_id=correlation_id,
                )
        except httpx.TimeoutException as exc:
            logger.error(
                "github_actions_get_job_logs_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_LOGS_TIMEOUT",
                message="GitHub Actions log retrieval timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "github_actions_get_job_logs_not_found",
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
                "github_actions_get_job_logs_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_LOGS_UNAVAILABLE",
                message=f"GitHub Actions returned HTTP {status_code} for logs",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "github_actions_get_job_logs_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_CONNECTION_ERROR",
                message="Cannot connect to GitHub Actions for log retrieval",
                details={"platform_job_id": platform_job_id},
            ) from exc

        is_complete = (
            gh_status == "completed"
            and gh_conclusion in GITHUB_ACTIONS_TERMINAL_CONCLUSIONS
        )

        logger.info(
            "github_actions_get_job_logs_success",
            platform_job_id=platform_job_id,
            log_length=len(combined_content),
            job_status=gh_status,
            conclusion=gh_conclusion,
            complete=is_complete,
            correlation_id=correlation_id,
        )

        return {
            "content": combined_content,
            "format": "text/plain",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "complete": is_complete,
            "job_status": gh_status,
        }

    @staticmethod
    def _extract_logs_from_zip(
        zip_content: bytes,
        correlation_id: str | None = None,
    ) -> str:
        """Extract and concatenate all log files from a ZIP archive.

        Args:
            zip_content: Raw ZIP bytes from GitHub Actions logs endpoint.
            correlation_id: Tracing correlation ID.

        Returns:
            Concatenated log text.
        """
        buffer = io.StringIO()
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                for name in sorted(zf.namelist()):
                    if name.endswith("/"):
                        continue  # skip directories
                    content = zf.read(name).decode("utf-8", errors="replace")
                    buffer.write(f"=== {name} ===\n")
                    buffer.write(content)
                    buffer.write("\n")
        except zipfile.BadZipFile:
            logger.warning(
                "github_actions_logs_bad_zip",
                correlation_id=correlation_id,
            )
            return ""
        return buffer.getvalue()

    # ------------------------------------------------------------------
    # Cancel execution
    # ------------------------------------------------------------------

    async def cancel_execution(
        self,
        platform_job_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> None:
        """Cancel a running workflow run on GitHub Actions.

        Args:
            platform_job_id: GitHub Actions run ID.
            correlation_id: Tracing correlation ID.

        Raises:
            ServiceUnavailableError: If GitHub is unreachable or cancel fails.
        """
        url = f"{self._repos_url()}/actions/runs/{platform_job_id}/cancel"

        logger.info(
            "github_actions_cancel_request",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(url)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error(
                "github_actions_cancel_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_TIMEOUT",
                message="GitHub Actions cancel request timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 409:
                logger.warning(
                    "github_actions_cancel_conflict",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                raise ServiceUnavailableError(
                    code="GITHUB_ACTIONS_CANCEL_CONFLICT",
                    message="Run already completed, cannot cancel",
                    details={
                        "platform_job_id": platform_job_id,
                        "status_code": 409,
                    },
                ) from exc
            logger.error(
                "github_actions_cancel_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_HTTP_ERROR",
                message=f"GitHub Actions cancel returned HTTP {status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "github_actions_cancel_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="GITHUB_ACTIONS_CONNECTION_ERROR",
                message="Cannot connect to GitHub Actions for cancellation",
                details={"platform_job_id": platform_job_id},
            ) from exc

        logger.info(
            "github_actions_cancel_success",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Ping GitHub API via GET {base_url}/ et valide le token Bearer."""
        url = f"{self.base_url}/"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("github_actions_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("github_actions_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz=timezone.utc),
                error_message=str(exc),
            )
