"""
Terraform Cloud adapter for remote execution management.

Story 27.5: TerraformCloudAdapter with trigger(), get_status(), get_job_logs(),
cancel_execution() for Terraform Cloud REST API v2.

Terraform Cloud specifics vs AAP/Tower/Azure DevOps/GitHub Actions:
- POST /runs returns 201 Created with full run object (run_id immediately available)
- Logs via log-read-url from plan/apply resources (not ZIP, not direct endpoint)
- Single complex status field with 18+ states (plan/apply lifecycle)
- Auth: Bearer token (User/Team/Organization API tokens)
- Requires organization/workspace for endpoint URLs
- JSON API spec format (application/vnd.api+json)
"""
# Responsabilité : Adaptateur Terraform Cloud (JSON API spec, 18+ états plan/apply, logs via
# log-read-url) — volume justifié par la complexité protocolaire inhérente à TFC (Story 35.4 AC3).
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import structlog

from adapters.base_adapter import BaseAdapter
from adapters.status_mappers import (
    TERRAFORM_CLOUD_STATUS_MAP as TERRAFORM_CLOUD_STATUS_MAP,
    TERRAFORM_CLOUD_TERMINAL_STATUSES as TERRAFORM_CLOUD_TERMINAL_STATUSES,
    map_terraform_cloud_status as map_terraform_cloud_status,
)
from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckResult, HealthCheckStatus, IHealthCheckable

logger = structlog.get_logger(__name__)

# Timeout for Terraform Cloud API calls (seconds)
TERRAFORM_CLOUD_DEFAULT_TIMEOUT = 30.0
TERRAFORM_CLOUD_LOGS_TIMEOUT = 60.0

# Terraform Cloud JSON API headers
TERRAFORM_CLOUD_CONTENT_TYPE = "application/vnd.api+json"


class TerraformCloudAdapter(BaseAdapter, IHealthCheckable):
    """Adapter for interacting with Terraform Cloud REST API v2.

    Requires base_url, organization, and auth_headers at init.
    base_url format: https://app.terraform.io/api/v2

    Inherits from BaseAdapter to implement Strategy Pattern (Stories 27.1-27.5).
    """

    def __init__(
        self,
        base_url: str,
        auth_headers: dict[str, str],
        organization: str = "",
        timeout: float = TERRAFORM_CLOUD_DEFAULT_TIMEOUT,
        verify_ssl: bool = True,
    ) -> None:
        if not organization:
            raise ValueError("Terraform Cloud adapter requires non-empty 'organization'")
        self.base_url = base_url.rstrip("/")
        self.auth_headers = {
            **auth_headers,
            "Content-Type": TERRAFORM_CLOUD_CONTENT_TYPE,
        }
        self.organization = organization
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    # ------------------------------------------------------------------
    # Trigger (launch) — POST /runs
    # ------------------------------------------------------------------

    async def trigger(
        self,
        workspace_id: str = "",
        auto_apply: bool = False,
        target_addrs: list[str] | None = None,
        variables: list[dict] | None = None,
        message: str = "",
        is_destroy: bool = False,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Launch a Terraform Cloud run via POST /runs.

        Terraform Cloud returns 201 Created with full run object (run_id immediately).

        Args:
            workspace_id: Terraform Cloud workspace ID (e.g. "ws-xxxxx").
            auto_apply: Auto-apply after plan succeeds.
            target_addrs: Terraform target addresses (e.g. ["module.vpc"]).
            variables: Run-specific variables.
            message: Description of the run.
            is_destroy: Whether this is a destroy run.
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'platform_job_id', 'status', 'url'.

        Raises:
            ServiceUnavailableError: If Terraform Cloud is unreachable or returns error.
        """
        if not workspace_id:
            raise ServiceUnavailableError(
                code="TERRAFORM_MISSING_WORKSPACE",
                message="workspace_id is required to trigger a Terraform Cloud run",
            )

        url = f"{self.base_url}/runs"

        # Build JSON API payload
        attributes: dict = {
            "auto-apply": auto_apply,
            "is-destroy": is_destroy,
        }
        if message:
            attributes["message"] = message
        if target_addrs:
            attributes["target-addrs"] = target_addrs

        payload: dict = {
            "data": {
                "type": "runs",
                "attributes": attributes,
                "relationships": {
                    "workspace": {
                        "data": {
                            "type": "workspaces",
                            "id": workspace_id,
                        }
                    }
                },
            }
        }

        if variables:
            payload["data"]["attributes"]["variables"] = variables

        logger.info(
            "terraform_cloud_trigger_request",
            url=url,
            workspace_id=workspace_id,
            auto_apply=auto_apply,
            organization=self.organization,
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
                "terraform_cloud_trigger_timeout",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_TIMEOUT",
                message="Terraform Cloud did not respond in time",
                details={"url": url},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            error_detail = self._extract_error_detail(exc.response)
            logger.error(
                "terraform_cloud_trigger_http_error",
                url=url,
                status_code=status_code,
                correlation_id=correlation_id,
                error=error_detail,
            )
            # Map specific HTTP errors to meaningful codes
            code = self._map_http_error_code(status_code, error_detail)
            raise ServiceUnavailableError(
                code=code,
                message=f"Terraform Cloud returned HTTP {status_code}: {error_detail}",
                details={"url": url, "status_code": status_code},
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "terraform_cloud_trigger_connection_error",
                url=url,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_CONNECTION_ERROR",
                message="Cannot connect to Terraform Cloud",
                details={"url": url},
            ) from exc

        # Extract run_id from 201 Created response
        run_data = data.get("data", {})
        run_id = run_data.get("id", "")
        run_status = run_data.get("attributes", {}).get("status", "pending")

        logger.info(
            "terraform_cloud_trigger_success",
            platform_job_id=run_id,
            workspace_id=workspace_id,
            run_status=run_status,
            correlation_id=correlation_id,
        )

        return {
            "platform_job_id": run_id,
            "status": map_terraform_cloud_status(run_status),
            "url": self._build_run_url(run_id),
        }

    # ------------------------------------------------------------------
    # Get status — GET /runs/{run_id}
    # ------------------------------------------------------------------

    async def get_status(
        self,
        platform_job_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Get current status of a Terraform Cloud run.

        Args:
            platform_job_id: Terraform Cloud run ID (e.g. "run-xxxxx").
            correlation_id: Tracing correlation ID.

        Returns:
            Dict with 'status' (IDP mapping), 'terraform_cloud_status',
            'created_at', 'updated_at'.

        Raises:
            ServiceUnavailableError: If Terraform Cloud is unreachable.
        """
        url = f"{self.base_url}/runs/{platform_job_id}"

        logger.info(
            "terraform_cloud_get_status_request",
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
                "terraform_cloud_get_status_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_TIMEOUT",
                message="Terraform Cloud status check timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "terraform_cloud_get_status_not_found",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                return {
                    "status": "SUBMITTED",
                    "terraform_cloud_status": "not_found",
                    "created_at": None,
                    "updated_at": None,
                }
            logger.error(
                "terraform_cloud_get_status_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_HTTP_ERROR",
                message=f"Terraform Cloud returned HTTP {status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "terraform_cloud_get_status_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_CONNECTION_ERROR",
                message="Cannot connect to Terraform Cloud",
                details={"platform_job_id": platform_job_id},
            ) from exc

        attributes = data.get("data", {}).get("attributes", {})
        tc_status = attributes.get("status", "pending")
        idp_status = map_terraform_cloud_status(tc_status)

        logger.info(
            "terraform_cloud_get_status_success",
            platform_job_id=platform_job_id,
            terraform_cloud_status=tc_status,
            idp_status=idp_status,
            correlation_id=correlation_id,
        )

        return {
            "status": idp_status,
            "terraform_cloud_status": tc_status,
            "created_at": attributes.get("created-at"),
            "updated_at": attributes.get("status-timestamps", {}).get(tc_status),
        }

    # ------------------------------------------------------------------
    # Get job logs — via log-read-url from plan/apply resources
    # ------------------------------------------------------------------

    async def get_job_logs(
        self,
        platform_job_id: str,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> dict:
        """Retrieve logs for a Terraform Cloud run (plan + apply).

        Terraform Cloud logs are accessed via log-read-url from plan/apply resources.
        Plan logs are always available; apply logs only when apply phase starts.

        Args:
            platform_job_id: Terraform Cloud run ID (e.g. "run-xxxxx").
            correlation_id: Tracing correlation ID.

        Returns:
            Unified log dict with 'content', 'format', 'timestamp', 'complete', 'job_status'.

        Raises:
            ServiceUnavailableError: If Terraform Cloud is unreachable.
        """
        run_url = f"{self.base_url}/runs/{platform_job_id}"

        logger.info(
            "terraform_cloud_get_job_logs_request",
            platform_job_id=platform_job_id,
            correlation_id=correlation_id,
        )

        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=TERRAFORM_CLOUD_LOGS_TIMEOUT,
                follow_redirects=True,
                verify=self.verify_ssl,
            ) as client:
                # Step 1: Get run status and plan/apply resource IDs
                run_response = await client.get(run_url)
                run_response.raise_for_status()
                run_data = run_response.json()

                attributes = run_data.get("data", {}).get("attributes", {})
                tc_status = attributes.get("status", "pending")
                relationships = run_data.get("data", {}).get("relationships", {})

                # Step 2: Fetch plan logs
                plan_logs = await self._fetch_resource_logs(
                    client, relationships, "plan", correlation_id
                )

                # Step 3: Fetch apply logs (only if apply phase started or completed)
                # Note: "fetching" is an early initialization phase, no apply logs yet
                apply_logs = ""
                apply_phase_statuses = {
                    "apply_queued", "applying", "applied",
                    "errored", "canceled", "force_canceled",
                    # Note: "fetching", "pending", "plan_queued", "planning", "planned" → no apply logs
                }
                if tc_status in apply_phase_statuses:
                    apply_logs = await self._fetch_resource_logs(
                        client, relationships, "apply", correlation_id
                    )

                # Combine logs (memory-efficient: avoid f-string duplication for large logs)
                parts = []
                if plan_logs:
                    parts.extend(["=== Plan Logs ===\n", plan_logs])
                if apply_logs:
                    if parts:  # Add separator if we already have plan logs
                        parts.append("\n\n")
                    parts.extend(["=== Apply Logs ===\n", apply_logs])
                combined = "".join(parts) if parts else ""

        except httpx.TimeoutException as exc:
            logger.error(
                "terraform_cloud_get_job_logs_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_LOGS_TIMEOUT",
                message="Terraform Cloud log retrieval timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                logger.warning(
                    "terraform_cloud_get_job_logs_not_found",
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
                "terraform_cloud_get_job_logs_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_LOGS_UNAVAILABLE",
                message=f"Terraform Cloud returned HTTP {status_code} for logs",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "terraform_cloud_get_job_logs_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_CONNECTION_ERROR",
                message="Cannot connect to Terraform Cloud for log retrieval",
                details={"platform_job_id": platform_job_id},
            ) from exc

        is_complete = tc_status in TERRAFORM_CLOUD_TERMINAL_STATUSES

        logger.info(
            "terraform_cloud_get_job_logs_success",
            platform_job_id=platform_job_id,
            log_length=len(combined),
            job_status=tc_status,
            complete=is_complete,
            correlation_id=correlation_id,
        )

        return {
            "content": combined,
            "format": "text/plain",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "complete": is_complete,
            "job_status": tc_status,
        }

    async def _fetch_resource_logs(
        self,
        client: httpx.AsyncClient,
        relationships: dict,
        resource_type: str,
        correlation_id: str | None = None,
    ) -> str:
        """Fetch logs for a plan or apply resource via its log-read-url.

        Args:
            client: Active httpx AsyncClient.
            relationships: Run relationships dict from JSON API response.
            resource_type: "plan" or "apply".
            correlation_id: Tracing correlation ID.

        Returns:
            Log text content, or empty string if not available.
        """
        resource_ref = relationships.get(resource_type, {}).get("data", {})
        resource_id = resource_ref.get("id", "")
        if not resource_id:
            return ""

        # GET the resource to obtain log-read-url
        # Terraform Cloud uses irregular pluralization: /plans/{id} and /applies/{id}
        RESOURCE_PLURAL = {
            "plan": "plans",
            "apply": "applies",  # NOT "applys"
        }
        plural = RESOURCE_PLURAL.get(resource_type, f"{resource_type}s")
        resource_url = f"{self.base_url}/{plural}/{resource_id}"
        try:
            resource_response = await client.get(resource_url)
            resource_response.raise_for_status()
            resource_data = resource_response.json()

            log_read_url = (
                resource_data.get("data", {})
                .get("attributes", {})
                .get("log-read-url", "")
            )
            if not log_read_url:
                return ""

            # Download raw log text
            log_response = await client.get(log_read_url)
            log_response.raise_for_status()

            logger.debug(
                f"terraform_cloud_{resource_type}_logs_fetched",
                resource_id=resource_id,
                log_length=len(log_response.text),
                correlation_id=correlation_id,
            )
            return log_response.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.debug(
                    f"terraform_cloud_{resource_type}_logs_not_available",
                    resource_id=resource_id,
                    correlation_id=correlation_id,
                )
                return ""
            raise
        except httpx.HTTPError:
            logger.warning(
                f"terraform_cloud_{resource_type}_logs_fetch_error",
                resource_id=resource_id,
                correlation_id=correlation_id,
            )
            return ""

    # ------------------------------------------------------------------
    # Cancel execution — POST /runs/{run_id}/actions/cancel
    # ------------------------------------------------------------------

    async def cancel_execution(
        self,
        platform_job_id: str,
        force: bool = False,
        correlation_id: str | None = None,
        **kwargs: object,
    ) -> None:
        """Cancel a running Terraform Cloud run.

        Args:
            platform_job_id: Terraform Cloud run ID.
            force: Use force-cancel instead of cancel.
            correlation_id: Tracing correlation ID.

        Raises:
            ServiceUnavailableError: If Terraform Cloud is unreachable or cancel fails.
        """
        action = "force-cancel" if force else "cancel"
        url = f"{self.base_url}/runs/{platform_job_id}/actions/{action}"

        logger.info(
            "terraform_cloud_cancel_request",
            platform_job_id=platform_job_id,
            force=force,
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
                "terraform_cloud_cancel_timeout",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_TIMEOUT",
                message="Terraform Cloud cancel request timed out",
                details={"platform_job_id": platform_job_id},
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 409:
                logger.warning(
                    "terraform_cloud_cancel_conflict",
                    platform_job_id=platform_job_id,
                    correlation_id=correlation_id,
                )
                raise ServiceUnavailableError(
                    code="TERRAFORM_CANCEL_CONFLICT",
                    message="Run already completed, cannot cancel",
                    details={
                        "platform_job_id": platform_job_id,
                        "status_code": 409,
                    },
                ) from exc
            if status_code == 404:
                raise ServiceUnavailableError(
                    code="TERRAFORM_RUN_NOT_FOUND",
                    message="Run not found",
                    details={
                        "platform_job_id": platform_job_id,
                        "status_code": 404,
                    },
                ) from exc
            logger.error(
                "terraform_cloud_cancel_http_error",
                platform_job_id=platform_job_id,
                status_code=status_code,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_HTTP_ERROR",
                message=f"Terraform Cloud cancel returned HTTP {status_code}",
                details={
                    "platform_job_id": platform_job_id,
                    "status_code": status_code,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "terraform_cloud_cancel_connection_error",
                platform_job_id=platform_job_id,
                correlation_id=correlation_id,
                error=str(exc),
            )
            raise ServiceUnavailableError(
                code="TERRAFORM_CONNECTION_ERROR",
                message="Cannot connect to Terraform Cloud for cancellation",
                details={"platform_job_id": platform_job_id},
            ) from exc

        logger.info(
            "terraform_cloud_cancel_success",
            platform_job_id=platform_job_id,
            force=force,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_run_url(self, run_id: str) -> str:
        """Build the Terraform Cloud UI URL for a run."""
        # Use app.terraform.io URL format
        base = self.base_url.replace("/api/v2", "")
        return f"{base}/app/{self.organization}/runs/{run_id}" if run_id else ""

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Extract error detail from Terraform Cloud JSON API error response."""
        try:
            data = response.json()
            errors = data.get("errors", [])
            if errors:
                return "; ".join(
                    e.get("detail", e.get("title", "Unknown error"))
                    for e in errors
                )
        except (ValueError, AttributeError):
            pass
        return response.text[:200] if response.text else "Unknown error"

    @staticmethod
    def _map_http_error_code(status_code: int, error_detail: str) -> str:
        """Map HTTP status codes to Terraform-specific error codes."""
        if status_code == 401:
            return "TERRAFORM_AUTH_FAILED"
        if status_code == 404:
            return "TERRAFORM_RUN_NOT_FOUND"
        if status_code == 409:
            if "locked" in error_detail.lower():
                return "TERRAFORM_WORKSPACE_LOCKED"
            return "TERRAFORM_CANCEL_CONFLICT"
        if status_code == 422:
            if "policy" in error_detail.lower():
                return "TERRAFORM_POLICY_FAILED"
            return "TERRAFORM_VALIDATION_ERROR"
        return "TERRAFORM_HTTP_ERROR"

    # ------------------------------------------------------------------
    # Health check — Story 51.1
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthCheckResult:
        """Valide la connectivité et le token Terraform Cloud via GET /api/v2/account/details.

        /api/v2/account/details est un endpoint authentifié : retourne 401 si le token
        est invalide, contrairement à /api/v2/ping qui est non authentifié.
        """
        # Use /account/details (authenticated) to validate the Bearer token.
        # /ping is unauthenticated and would not detect invalid tokens.
        url = f"{self.base_url}/account/details"
        try:
            async with httpx.AsyncClient(
                headers=self.auth_headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            logger.info("terraform_cloud_health_check_ok", base_url=self.base_url)
            return HealthCheckResult(
                status=HealthCheckStatus.OK,
                checked_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("terraform_cloud_health_check_error", base_url=self.base_url, error=str(exc))
            return HealthCheckResult(
                status=HealthCheckStatus.ERROR,
                checked_at=datetime.now(tz=timezone.utc),
                error_message=str(exc),
            )
