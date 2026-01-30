"""AAP (Ansible Automation Platform) adapter (Story 4.4).

Implements platform adapter for triggering and monitoring jobs on AAP/Tower.
Uses Strategy Pattern - inherits from BaseAdapter interface.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.adapters.base_adapter import BaseAdapter
from app.core.exceptions import PlatformError

logger = structlog.get_logger(__name__)

# AAP status to unified status mapping
_AAP_STATUS_MAP: dict[str, str] = {
    "pending": "running",
    "waiting": "running",
    "running": "running",
    "successful": "completed",
    "failed": "failed",
    "error": "failed",
    "canceled": "cancelled",
}


class AAPAdapter(BaseAdapter):
    """Adapter for Ansible Automation Platform (AAP/Tower) (Story 4.4, AC1-5).

    Implements BaseAdapter interface for AAP platform:
    - trigger(): Launch job template on AAP
    - get_status(): Poll job status
    - parse_callback(): Parse webhook notifications

    Attributes:
        platform_type: Always "aap"
        base_url: AAP Tower base URL (e.g., "https://aap.example.com")
    """

    def __init__(self, platform_type: str = "aap", base_url: str = "") -> None:
        """Initialize AAP adapter with platform configuration.

        Args:
            platform_type: Platform type identifier (default: "aap")
            base_url: AAP Tower base URL
        """
        super().__init__(platform_type, base_url)
        self._client: httpx.AsyncClient | None = None
        self._credentials: dict[str, Any] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx async client with timeout."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    def _get_auth_headers(self, credentials: dict[str, Any]) -> tuple[httpx.BasicAuth | None, dict[str, str]]:
        """Get authentication from credentials (Task 5.1).

        Supports two formats:
        - Bearer token: {"token": "..."}
        - Basic auth: {"username": "...", "password": "..."}

        Args:
            credentials: Credentials dict from Vault

        Returns:
            Tuple of (auth, headers) for httpx request
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if "token" in credentials:
            # Bearer token authentication
            headers["Authorization"] = f"Bearer {credentials['token']}"
            return None, headers
        else:
            # Basic authentication
            auth = httpx.BasicAuth(
                username=credentials.get("username", ""),
                password=credentials.get("password", ""),
            )
            return auth, headers

    async def trigger(
        self,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
    ) -> str:
        """Trigger job template execution on AAP (Story 4.4, AC1).

        Sends POST request to AAP /api/v2/job_templates/{id}/launch/ endpoint.

        Args:
            parameters: Must contain "job_template_id", optional "extra_vars"
            credentials: Vault credentials (token or username/password)
            correlation_id: Request correlation ID for tracing

        Returns:
            AAP job ID as string

        Raises:
            ValueError: If job_template_id missing in parameters
            PlatformError: If AAP unavailable, auth fails, or template not found
        """
        # Extract job_template_id (Task 1.4)
        template_id = parameters.get("job_template_id")
        if not template_id:
            raise ValueError("job_template_id requis pour AAP")

        # Store credentials for later get_status calls
        self._credentials = credentials

        # Build request
        url = f"{self.base_url}/api/v2/job_templates/{template_id}/launch/"
        auth, headers = self._get_auth_headers(credentials)

        # Extract extra_vars from parameters
        extra_vars = {k: v for k, v in parameters.items() if k != "job_template_id"}
        body = {"extra_vars": extra_vars} if extra_vars else {}

        logger.info(
            "aap_trigger_started",
            template_id=template_id,
            correlation_id=correlation_id,
            url=url,
        )

        try:
            client = await self._get_client()
            response = await client.post(url, json=body, auth=auth, headers=headers)
            response.raise_for_status()

            data = response.json()
            job_id = str(data.get("id", ""))

            logger.info(
                "aap_trigger_success",
                template_id=template_id,
                job_id=job_id,
                correlation_id=correlation_id,
            )

            return job_id

        except httpx.TimeoutException:
            logger.error(
                "aap_trigger_timeout",
                template_id=template_id,
                correlation_id=correlation_id,
            )
            raise PlatformError(
                code="AAP_UNAVAILABLE",
                message="Plateforme AAP indisponible (timeout)",
            )

        except httpx.ConnectError as e:
            logger.error(
                "aap_trigger_connect_error",
                template_id=template_id,
                correlation_id=correlation_id,
                error=str(e),
            )
            raise PlatformError(
                code="AAP_UNAVAILABLE",
                message="Plateforme AAP indisponible (erreur connexion)",
            )

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(
                "aap_trigger_http_error",
                template_id=template_id,
                correlation_id=correlation_id,
                status_code=status_code,
            )

            if status_code in (400, 401, 403):
                raise PlatformError(
                    code="AAP_AUTH_ERROR",
                    message="Authentification AAP échouée",
                )
            elif status_code == 404:
                raise PlatformError(
                    code="AAP_JOB_TEMPLATE_NOT_FOUND",
                    message=f"Job template AAP introuvable: {template_id}",
                )
            else:
                raise PlatformError(
                    code="AAP_ERROR",
                    message=f"Erreur AAP HTTP {status_code}",
                )

    async def get_status(self, platform_job_id: str) -> dict[str, Any]:
        """Get current status of AAP job (Story 4.4, AC3).

        Polls AAP /api/v2/jobs/{id}/ endpoint for job status.

        Args:
            platform_job_id: AAP job ID from trigger()

        Returns:
            Dict with status, output, and error_message

        Raises:
            PlatformError: If job not found (404)
        """
        url = f"{self.base_url}/api/v2/jobs/{platform_job_id}/"
        auth, headers = self._get_auth_headers(self._credentials)

        try:
            client = await self._get_client()
            response = await client.get(url, auth=auth, headers=headers)
            response.raise_for_status()

            data = response.json()
            return self._parse_job_response(data)

        except httpx.TimeoutException:
            # On timeout, assume job still running (Task 2.2)
            logger.warning(
                "aap_get_status_timeout",
                job_id=platform_job_id,
            )
            return {
                "status": "running",
                "output": {},
                "error_message": None,
            }

        except httpx.ConnectError:
            # On network error, assume job still running (Task 2.2)
            logger.warning(
                "aap_get_status_connect_error",
                job_id=platform_job_id,
            )
            return {
                "status": "running",
                "output": {},
                "error_message": None,
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise PlatformError(
                    code="AAP_JOB_NOT_FOUND",
                    message=f"Job AAP introuvable: {platform_job_id}",
                )
            raise

    async def parse_callback(self, callback_data: dict[str, Any]) -> dict[str, Any]:
        """Parse AAP webhook callback data (Story 4.4, AC4).

        Extracts job information from AAP webhook payload.
        This method is pure (no side effects) for idempotency (NFR18).

        Args:
            callback_data: Raw webhook payload from AAP

        Returns:
            Dict with platform_job_id, status, output, error_message

        Raises:
            PlatformError: If callback data is invalid (missing job_id)
        """
        # Extract job_id (AAP uses "id" or "job_id")
        job_id = callback_data.get("id") or callback_data.get("job_id")
        if not job_id:
            raise PlatformError(
                code="AAP_INVALID_CALLBACK",
                message="Callback AAP invalide - job_id manquant",
            )

        return self._parse_job_response(callback_data, job_id=str(job_id))

    def _parse_job_response(
        self, data: dict[str, Any], job_id: str | None = None
    ) -> dict[str, Any]:
        """Parse AAP job response to unified format (Task 2.3, 3.1).

        Args:
            data: AAP API response or webhook payload
            job_id: Override job_id if provided

        Returns:
            Dict with platform_job_id, status, output, error_message
        """
        aap_status = data.get("status", "")
        unified_status = _AAP_STATUS_MAP.get(aap_status, "running")

        # Extract error from traceback or explanation
        error_message = None
        if unified_status == "failed":
            error_message = data.get("result_traceback") or data.get("job_explanation")

        # Build output dict
        output: dict[str, Any] = {}
        if "artifacts" in data:
            output["artifacts"] = data["artifacts"]
        if "result_traceback" in data and data["result_traceback"]:
            output["traceback"] = data["result_traceback"]
        if "job_explanation" in data and data["job_explanation"]:
            output["explanation"] = data["job_explanation"]

        result = {
            "status": unified_status,
            "output": output,
            "error_message": error_message,
        }

        if job_id:
            result["platform_job_id"] = job_id
        elif "id" in data:
            result["platform_job_id"] = str(data["id"])

        return result
