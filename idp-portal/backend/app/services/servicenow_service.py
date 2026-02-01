"""ServiceNow service for change management integration (Story 4.5).

Provides ServiceNow change request creation with:
- Async HTTP client (httpx) with timeout and retry
- Vault credential retrieval at runtime
- Correlation ID propagation for traceability
- Support for pre-approved change models (automated CAB)
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import ServiceNowError, VaultError
from app.repositories import integration_repository
from app.services.vault_service import VaultService

logger = structlog.get_logger()

# ServiceNow API timeout (NFR19: 30s tolerance)
SERVICENOW_TIMEOUT = 30.0
# Retry configuration
SERVICENOW_RETRY_COUNT = 1
SERVICENOW_RETRY_DELAY = 5.0


class ServiceNowService:
    """Service for creating ServiceNow change requests (Story 4.5, Task 1).

    Integrates with ServiceNow Table API to create change requests for
    Production executions or when action configuration requires it.

    Supports:
    - Pre-approved change models (Standard Changes) - immediate approval
    - Normal changes - require CAB approval (pending status)

    Credentials are retrieved from Vault at runtime (never persisted).
    """

    def __init__(self, vault_service: VaultService) -> None:
        """Initialize service with dependencies.

        Args:
            vault_service: Service for retrieving credentials from Vault
        """
        self.vault_service = vault_service

    async def create_change(
        self,
        execution_id: int,
        action_name: str,
        environment: str,
        parameters: dict[str, Any],
        user: str,
        correlation_id: str,
        change_model_code: str | None = None,
        credential_ref: str | None = None,
    ) -> dict[str, Any]:
        """Create a ServiceNow change request (Story 4.5, AC1, AC2, AC4, AC5).

        Args:
            execution_id: IDP execution ID for correlation
            action_name: Name of the action being executed
            environment: Target environment (dev, staging, prod)
            parameters: Execution parameters (for change description)
            user: User requesting the change
            correlation_id: Request correlation ID for tracing
            change_model_code: Pre-approved change model code (optional, for Standard Changes)
            credential_ref: Vault path for ServiceNow credentials

        Returns:
            Dict with change_id (sys_id), change_number, status ("approved" or "pending_approval")

        Raises:
            ServiceNowError: If ServiceNow API fails, timeout, auth error, or invalid response
        """
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            execution_id=execution_id,
            action_name=action_name,
            environment=environment,
        )

        # Get ServiceNow configuration
        base_url = await self._get_base_url()
        if not base_url:
            raise ServiceNowError(
                code="SERVICENOW_NOT_CONFIGURED",
                message="ServiceNow integration non configurée (SERVICENOW_BASE_URL manquant)",
            )

        # Retrieve credentials from Vault (AC5, Task 1.3)
        credentials = await self._get_credentials(credential_ref, correlation_id)

        # Build change request payload (Task 1.2)
        payload = self._build_change_payload(
            action_name=action_name,
            environment=environment,
            parameters=parameters,
            user=user,
            correlation_id=correlation_id,
            change_model_code=change_model_code,
        )

        # Call ServiceNow API with retry (Task 1.5)
        endpoint = f"{base_url.rstrip('/')}/api/now/table/change_request"
        response_data = await self._call_servicenow_api(
            endpoint=endpoint,
            payload=payload,
            credentials=credentials,
            correlation_id=correlation_id,
        )

        # Parse response (Task 1.4)
        result = self._parse_change_response(response_data)

        logger.info(
            "servicenow_change_created",
            change_id=result["change_id"],
            change_number=result["change_number"],
            status=result["status"],
            change_model_code=change_model_code,
        )

        return result

    async def _get_base_url(self) -> str | None:
        """Get ServiceNow base URL from settings or integration (Task 6.1, 6.2).

        Lookup order:
        1. settings.servicenow_base_url (environment variable)
        2. ServiceNow integration from INTEGRATIONS table

        Returns:
            ServiceNow base URL or None if not configured
        """
        # First check environment variable
        base_url = getattr(settings, "servicenow_base_url", "")
        if base_url:
            return base_url

        # Fallback to ServiceNow integration in database
        servicenow_integration = await integration_repository.get_by_type("servicenow")
        if servicenow_integration and servicenow_integration.base_url:
            return servicenow_integration.base_url

        return None

    async def _get_credentials(
        self,
        credential_ref: str | None,
        correlation_id: str,
    ) -> dict[str, str]:
        """Retrieve ServiceNow credentials from Vault (Task 1.3, AC5).

        Credential lookup order:
        1. credential_ref parameter (if provided)
        2. ServiceNow integration from INTEGRATIONS table
        3. settings.servicenow_credential_ref (environment variable)

        Args:
            credential_ref: Vault path for credentials
            correlation_id: Request correlation ID

        Returns:
            Dict with 'username' and 'password'

        Raises:
            ServiceNowError: If credentials not found or invalid
        """
        if not credential_ref:
            # Try to get from ServiceNow integration in database (Task 6.2)
            servicenow_integration = await integration_repository.get_by_type("servicenow")
            if servicenow_integration and servicenow_integration.credential_ref:
                credential_ref = servicenow_integration.credential_ref
            else:
                # Fallback to environment variable
                credential_ref = getattr(settings, "servicenow_credential_ref", "")

        if not credential_ref:
            raise ServiceNowError(
                code="SERVICENOW_AUTH_ERROR",
                message="Credentials ServiceNow non configurés (credential_ref manquant)",
            )

        logger.debug("servicenow_credential_retrieval", credential_ref=credential_ref)

        try:
            credentials = await self.vault_service.get_secret(credential_ref, correlation_id)
        except VaultError:
            raise
        except Exception as e:
            logger.error("servicenow_credential_failed", credential_ref=credential_ref, error=str(e))
            raise ServiceNowError(
                code="SERVICENOW_AUTH_ERROR",
                message=f"Impossible de récupérer les credentials ServiceNow: {str(e)}",
            ) from e

        # Validate credentials structure
        if "username" not in credentials or "password" not in credentials:
            raise ServiceNowError(
                code="SERVICENOW_AUTH_ERROR",
                message="Credentials ServiceNow invalides (username/password manquants)",
            )

        return credentials

    def _build_change_payload(
        self,
        action_name: str,
        environment: str,
        parameters: dict[str, Any],
        user: str,
        correlation_id: str,
        change_model_code: str | None,
    ) -> dict[str, Any]:
        """Build ServiceNow change request payload (Task 1.2).

        Args:
            action_name: Name of the action
            environment: Target environment
            parameters: Execution parameters
            user: Requesting user
            correlation_id: Correlation ID
            change_model_code: Pre-approved change model code

        Returns:
            ServiceNow change request body
        """
        description = (
            f"Execution automatique IDP - Correlation ID: {correlation_id}\n"
            f"Action: {action_name}\n"
            f"Environnement: {environment}\n"
            f"Parametres: {json.dumps(parameters, ensure_ascii=False)}\n"
            f"Utilisateur: {user}"
        )

        payload: dict[str, Any] = {
            "short_description": f"[IDP] {action_name} - {environment}",
            "description": description,
            "requested_by": user,
            "assignment_group": "DBOPS",
            "category": "Database",
            "u_correlation_id": correlation_id,
        }

        # Add change model code if provided (for pre-approved changes)
        if change_model_code:
            payload["u_change_model"] = change_model_code

        return payload

    async def _call_servicenow_api(
        self,
        endpoint: str,
        payload: dict[str, Any],
        credentials: dict[str, str],
        correlation_id: str,
    ) -> dict[str, Any]:
        """Call ServiceNow API with timeout and retry (Task 1.2, 1.5, AC4).

        Args:
            endpoint: Full ServiceNow API URL
            payload: Request body
            credentials: Dict with username/password
            correlation_id: Correlation ID for header

        Returns:
            ServiceNow API response JSON

        Raises:
            ServiceNowError: On timeout, auth error, or API failure
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": correlation_id,
        }

        # Encode Basic Auth (Task 1.2)
        auth_string = f"{credentials['username']}:{credentials['password']}"
        auth_bytes = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {auth_bytes}"

        timeout = httpx.Timeout(SERVICENOW_TIMEOUT)
        last_error: Exception | None = None

        # Retry loop (Task 1.5: 1 retry with 5s backoff)
        for attempt in range(SERVICENOW_RETRY_COUNT + 1):
            try:
                logger.info(
                    "servicenow_api_request",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                )

                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )

                # Check response status
                if response.status_code == 401:
                    raise ServiceNowError(
                        code="SERVICENOW_AUTH_ERROR",
                        message="Authentification ServiceNow échouée (401 Unauthorized)",
                    )

                if response.status_code == 403:
                    raise ServiceNowError(
                        code="SERVICENOW_AUTH_ERROR",
                        message="Accès ServiceNow refusé (403 Forbidden)",
                    )

                if response.status_code >= 500:
                    raise ServiceNowError(
                        code="SERVICENOW_UNAVAILABLE",
                        message=f"ServiceNow indisponible (HTTP {response.status_code})",
                    )

                if response.status_code not in (200, 201):
                    raise ServiceNowError(
                        code="SERVICENOW_INVALID_RESPONSE",
                        message=f"Réponse ServiceNow inattendue (HTTP {response.status_code})",
                        details={"status_code": response.status_code, "body": response.text[:500]},
                    )

                # Parse JSON response
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    raise ServiceNowError(
                        code="SERVICENOW_INVALID_RESPONSE",
                        message="Réponse ServiceNow invalide (JSON parsing failed)",
                    ) from e

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "servicenow_timeout",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                    timeout_seconds=SERVICENOW_TIMEOUT,
                )

                # Retry if not last attempt
                if attempt < SERVICENOW_RETRY_COUNT:
                    logger.info("servicenow_retry_scheduled", delay_seconds=SERVICENOW_RETRY_DELAY)
                    await asyncio.sleep(SERVICENOW_RETRY_DELAY)
                    continue

                # Last attempt failed - raise timeout error (AC4)
                raise ServiceNowError(
                    code="SERVICENOW_TIMEOUT",
                    message="ServiceNow timeout — changement non créé",
                ) from e

            except httpx.RequestError as e:
                last_error = e
                logger.error(
                    "servicenow_request_error",
                    endpoint=endpoint,
                    error=str(e),
                )
                raise ServiceNowError(
                    code="SERVICENOW_UNAVAILABLE",
                    message=f"Erreur de connexion ServiceNow: {str(e)}",
                ) from e

            except ServiceNowError:
                # Re-raise ServiceNowError as-is
                raise

        # Should not reach here, but just in case
        raise ServiceNowError(
            code="SERVICENOW_UNAVAILABLE",
            message="ServiceNow indisponible après tous les essais",
        )

    def _parse_change_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Parse ServiceNow change response (Task 1.4).

        Args:
            response_data: Raw ServiceNow API response

        Returns:
            Dict with change_id, change_number, status

        Raises:
            ServiceNowError: If response format is invalid
        """
        # ServiceNow returns: {"result": {"sys_id": "...", "number": "CHG...", "approval": "..."}}
        result = response_data.get("result", {})

        if not isinstance(result, dict):
            raise ServiceNowError(
                code="SERVICENOW_INVALID_RESPONSE",
                message="Réponse ServiceNow invalide (result manquant)",
            )

        sys_id = result.get("sys_id")
        number = result.get("number")
        approval = result.get("approval", "")

        if not sys_id or not number:
            raise ServiceNowError(
                code="SERVICENOW_INVALID_RESPONSE",
                message="Réponse ServiceNow invalide (sys_id ou number manquant)",
                details={"result": result},
            )

        # Determine approval status
        # "approved" = pre-approved (Standard Change)
        # "not requested", "" = pending CAB approval (Normal Change)
        status = "approved" if approval.lower() == "approved" else "pending_approval"

        return {
            "change_id": sys_id,
            "change_number": number,
            "status": status,
        }
