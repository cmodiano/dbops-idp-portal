"""AAP (Ansible Automation Platform) adapter (Story 4.4, 4.10, 5.3).

Implements platform adapter for triggering and monitoring jobs on AAP/Tower.
Story 4.10: supports job_template and workflow_job resource types.
Story 5.3: if integration has config (auth_flow steps), obtain_token then call_api; else legacy auth_flow + credential_ref.
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
        self._resource_type: str = "job_template"  # job_template | workflow_job (Story 4.10)

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

    async def _resolve_credentials_from_config(
        self,
        credentials: dict[str, Any],
        integration: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        """If integration has config with obtain_token step, POST to token_url and merge token into credentials (Story 5.3).

        Raises:
            PlatformError: If token acquisition fails (code-review fix HIGH-1: explicit failure instead of silent fallback)
        """
        config = integration.get("config") or {}
        steps = config.get("auth_flow") or []
        obtain = next((s for s in steps if s.get("step") == "obtain_token"), None)
        if not obtain:
            return credentials

        token_url = integration.get("token_url") or integration.get("base_url")
        if not token_url:
            logger.warning("aap_config_obtain_token_no_url", correlation_id=correlation_id)
            raise PlatformError(
                code="AAP_TOKEN_URL_MISSING",
                message="Config spécifie obtain_token mais token_url est absent",
            )

        cred_spec = obtain.get("credentials") or {}
        keys = cred_spec.get("keys") or []
        body = {k: credentials.get(k) for k in keys if k in credentials}
        response_token_path = obtain.get("response_token_path") or "access_token"

        try:
            client = await self._get_client()
            response = await client.post(token_url, json=body)
            response.raise_for_status()
            data = response.json()
            # Support path like "access_token" or nested "data.access_token"
            token = data
            for part in response_token_path.split("."):
                token = token.get(part) if isinstance(token, dict) else None
            if token and isinstance(token, str):
                logger.info(
                    "aap_config_obtain_token_success",
                    correlation_id=correlation_id,
                    token_url=token_url,
                )
                return {**credentials, "token": token}
            # Token not found in response at expected path
            logger.error(
                "aap_config_obtain_token_path_not_found",
                correlation_id=correlation_id,
                response_token_path=response_token_path,
            )
            raise PlatformError(
                code="AAP_TOKEN_NOT_IN_RESPONSE",
                message=f"Token non trouvé dans la réponse au path '{response_token_path}'",
            )
        except PlatformError:
            raise
        except Exception as e:
            logger.error(
                "aap_config_obtain_token_failed",
                correlation_id=correlation_id,
                token_url=token_url,
                error=str(e),
            )
            raise PlatformError(
                code="AAP_TOKEN_ACQUISITION_FAILED",
                message=f"Échec obtention token: {str(e)}",
            ) from e

    async def trigger(
        self,
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
        *,
        integration: dict[str, Any] | None = None,
    ) -> str:
        """Trigger job template or workflow job execution on AAP (Story 4.4, 4.10, 5.3).

        If integration has config with obtain_token step, resolves token first (Story 5.3).
        Otherwise uses credentials as-is (legacy auth_flow + credential_ref).

        Sends POST to job_templates/{id}/launch/ or workflow_job_templates/{id}/launch/
        according to resource_type (default job_template).

        Args:
            parameters: Must contain job_template_id or workflow_job_template_id; optional extra_vars
            credentials: Vault credentials (token or username/password)
            correlation_id: Request correlation ID for tracing
            integration: Optional integration dict with token_url, config (Story 5.3)

        Returns:
            AAP job ID as string

        Raises:
            ValueError: If template id missing
            PlatformError: If AAP unavailable, auth fails, or template not found
        """
        # Story 5.3: resolve token from config flow if present
        if integration and (integration.get("config") or integration.get("token_url")):
            credentials = await self._resolve_credentials_from_config(
                credentials, integration, correlation_id
            )

        # Story 4.10: resource_type job_template | workflow_job (AC2, AC3)
        resource_type = parameters.get("resource_type", "job_template")
        self._resource_type = resource_type

        if resource_type == "workflow_job":
            raw_id = parameters.get("workflow_job_template_id")
            if raw_id is None or raw_id == "":
                raise ValueError("workflow_job_template_id requis pour AAP (resource_type=workflow_job)")
            try:
                template_id = int(raw_id)
            except (TypeError, ValueError):
                raise ValueError("workflow_job_template_id doit etre un entier") from None
            if template_id < 1:
                raise ValueError("workflow_job_template_id doit etre strictement positif")
            url = f"{self.base_url}/api/v2/workflow_job_templates/{template_id}/launch/"
        else:
            raw_id = parameters.get("job_template_id")
            if raw_id is None or raw_id == "":
                raise ValueError("job_template_id requis pour AAP")
            try:
                template_id = int(raw_id)
            except (TypeError, ValueError):
                raise ValueError("job_template_id doit etre un entier") from None
            if template_id < 1:
                raise ValueError("job_template_id doit etre strictement positif")
            url = f"{self.base_url}/api/v2/job_templates/{template_id}/launch/"

        # Store credentials for later get_status calls
        self._credentials = credentials

        auth, headers = self._get_auth_headers(credentials)

        # Exclude adapter params from extra_vars (Story 4.10)
        adapter_keys = {"resource_type", "job_template_id", "workflow_job_template_id", "template_id"}
        extra_vars = {k: v for k, v in parameters.items() if k not in adapter_keys}
        body = {"extra_vars": extra_vars} if extra_vars else {}

        log_event = "aap_workflow_trigger_started" if resource_type == "workflow_job" else "aap_trigger_started"
        logger.info(
            log_event,
            template_id=template_id,
            resource_type=resource_type,
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
                resource_type=resource_type,
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
                resource_type=resource_type,
                correlation_id=correlation_id,
                status_code=status_code,
            )

            if status_code in (400, 401, 403):
                raise PlatformError(
                    code="AAP_AUTH_ERROR",
                    message="Authentification AAP échouée",
                )
            elif status_code == 404:
                if resource_type == "workflow_job":
                    raise PlatformError(
                        code="AAP_WORKFLOW_JOB_TEMPLATE_NOT_FOUND",
                        message=f"Workflow job template AAP introuvable: {template_id}",
                    )
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
        """Get current status of AAP job (Story 4.4, 4.10).

        Polls /api/v2/jobs/{id}/ or /api/v2/workflow_jobs/{id}/ according to resource_type.

        Args:
            platform_job_id: AAP job ID from trigger()

        Returns:
            Dict with status, output, and error_message

        Raises:
            PlatformError: If job not found (404)
        """
        if self._resource_type == "workflow_job":
            url = f"{self.base_url}/api/v2/workflow_jobs/{platform_job_id}/"
        else:
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
            status_code = e.response.status_code
            if status_code == 404:
                if self._resource_type == "workflow_job":
                    raise PlatformError(
                        code="AAP_WORKFLOW_JOB_NOT_FOUND",
                        message=f"Workflow job AAP introuvable: {platform_job_id}",
                    )
                raise PlatformError(
                    code="AAP_JOB_NOT_FOUND",
                    message=f"Job AAP introuvable: {platform_job_id}",
                )
            logger.error(
                "aap_get_status_http_error",
                job_id=platform_job_id,
                resource_type=self._resource_type,
                status_code=status_code,
            )
            raise PlatformError(
                code="AAP_ERROR",
                message=f"Erreur AAP HTTP {status_code}",
            ) from e

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
