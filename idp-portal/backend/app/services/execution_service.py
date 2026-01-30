"""Execution service for orchestrating action executions (Story 4.3, Task 4).

Orchestrates the execution flow:
1. Load execution and steps from repository
2. Retrieve secrets from Vault (Story 4.2bis)
3. Select platform adapter (Strategy Pattern)
4. Trigger execution on platform
5. Handle errors and update step status
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from app.adapters import get_platform_adapter
from app.core.exceptions import PlatformError, VaultError
from app.models.execution import ExecutionStatus, StepStatus, StepType, ExecutionStepCreate
from app.repositories import execution_repository
from app.services.vault_service import VaultService

logger = structlog.get_logger()


class ExecutionService:
    """Service for orchestrating action executions (Story 4.3, Task 4.1).

    Coordinates between:
    - execution_repository: CRUD for executions and steps
    - vault_service: Secret retrieval (Story 4.2bis)
    - platform adapters: Triggering executions (Strategy Pattern)
    """

    def __init__(self, vault_service: VaultService) -> None:
        """Initialize service with dependencies.

        Args:
            vault_service: Service for retrieving secrets from Vault
        """
        self.vault_service = vault_service

    async def prepare_execution(
        self,
        execution_id: int,
        correlation_id: str,
    ) -> bool:
        """Prepare execution by creating step records (Story 4.3, Task 3.4).

        Called after execution record is created but before starting.
        Reads action's execution_steps definition and creates EXECUTION_STEPS records.

        Args:
            execution_id: ID of the execution to prepare
            correlation_id: Request correlation ID

        Returns:
            True if preparation succeeded
        """
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

        try:
            # Get execution to find action_id
            execution = await execution_repository.get_by_id(execution_id)
            if execution is None:
                logger.error("execution_not_found", execution_id=execution_id)
                return False

            # Get action's execution steps definition
            action_steps = await execution_repository.get_action_execution_steps(execution.action_id)

            if not action_steps:
                # No steps defined - create default platform step
                action_steps = [
                    {"order": 1, "name": "Exécution sur plateforme", "type": "platform"}
                ]

            # Create step records
            steps_to_create = [
                ExecutionStepCreate(
                    step_order=step.get("order", idx + 1),
                    step_name=step.get("name", f"Étape {idx + 1}"),
                    step_type=StepType(step.get("type", "platform")),
                )
                for idx, step in enumerate(action_steps)
            ]

            await execution_repository.create_execution_steps(execution_id, steps_to_create)

            logger.info(
                "execution_prepared",
                execution_id=execution_id,
                step_count=len(steps_to_create),
            )
            return True

        except Exception as e:
            logger.error("execution_preparation_failed", error=str(e))
            return False

    async def start_execution(
        self,
        execution_id: int,
        correlation_id: str,
    ) -> None:
        """Start execution and orchestrate steps (Story 4.3, Task 4.1).

        This is the main entry point for the execution engine.
        Called as a background task after prepare_execution.

        Args:
            execution_id: ID of the execution to start
            correlation_id: Request correlation ID for tracing
        """
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

        logger.info("execution_starting", execution_id=execution_id)

        try:
            # Update execution status to RUNNING (Task 4.2)
            await execution_repository.update_status(execution_id, ExecutionStatus.RUNNING)

            # Get execution with action and integration details
            execution = await execution_repository.get_by_id(execution_id)
            if execution is None:
                logger.error("execution_not_found", execution_id=execution_id)
                return

            action_info = await execution_repository.get_action_with_integration(execution.action_id)
            if action_info is None:
                await self._fail_execution(
                    execution_id,
                    "Action introuvable pour l'exécution",
                )
                return

            # Get execution steps
            steps = await execution_repository.get_steps_by_execution_id(execution_id)
            if not steps:
                # Should have been created by prepare_execution
                await self._fail_execution(
                    execution_id,
                    "Aucune étape d'exécution définie",
                )
                return

            # Execute each step in order
            credentials: dict[str, Any] = {}
            platform_job_id: str | None = None

            for step in steps:
                logger.info(
                    "execution_step_starting",
                    step_id=step.id,
                    step_name=step.step_name,
                    step_type=step.step_type.value,
                )

                # Update step status to RUNNING
                await execution_repository.update_step_status(step.id, StepStatus.RUNNING)

                try:
                    if step.step_type == StepType.VAULT:
                        # Retrieve secrets from Vault (AC2, AC3)
                        credentials = await self._execute_vault_step(
                            step.id,
                            action_info,
                            correlation_id,
                        )

                    elif step.step_type == StepType.PLATFORM:
                        # Trigger platform execution (AC2)
                        platform_job_id = await self._execute_platform_step(
                            step.id,
                            action_info,
                            execution.parameters or {},
                            credentials,
                            correlation_id,
                        )

                    elif step.step_type == StepType.SERVICENOW:
                        # ServiceNow integration (Story 4.5 - stub for now)
                        await self._execute_servicenow_step(step.id)

                    else:
                        # Generic step (prerequisite, verification)
                        await self._execute_generic_step(step.id)

                    # Mark step completed
                    await execution_repository.update_step_status(
                        step.id,
                        StepStatus.COMPLETED,
                        platform_job_id=platform_job_id,
                    )
                    logger.info("execution_step_completed", step_id=step.id)

                except VaultError as e:
                    # Vault unavailable - fail execution (AC3)
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Vault indisponible — exécution impossible: {e.message}",
                    )
                    return

                except PlatformError as e:
                    # Platform error - fail execution
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Erreur plateforme: {e.message}",
                    )
                    return

                except Exception as e:
                    # Unexpected error - fail execution
                    logger.error("execution_step_failed", step_id=step.id, error=str(e))
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Erreur inattendue: {str(e)}",
                    )
                    return

            # All steps completed successfully
            await execution_repository.update_status(execution_id, ExecutionStatus.COMPLETED)
            logger.info("execution_completed", execution_id=execution_id)

        except Exception as e:
            logger.error("execution_orchestration_failed", error=str(e))
            await self._fail_execution(execution_id, f"Erreur d'orchestration: {str(e)}")

    async def _execute_vault_step(
        self,
        step_id: int,
        action_info: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        """Execute Vault step - retrieve secrets (Task 4.3).

        Args:
            step_id: Step ID
            action_info: Action with integration details
            correlation_id: Request correlation ID

        Returns:
            Retrieved credentials dict

        Raises:
            VaultError: If Vault is unavailable or secret not found (AC3)
        """
        integration = action_info.get("integration")
        if not integration:
            logger.warning("no_integration_for_vault_step", step_id=step_id)
            return {}

        credential_ref = integration.get("credential_ref")
        if not credential_ref:
            logger.warning("no_credential_ref", step_id=step_id)
            return {}

        logger.info("vault_secret_retrieval_starting", credential_ref=credential_ref)

        try:
            credentials = await self.vault_service.get_secret(credential_ref, correlation_id)
            logger.info("vault_secret_retrieved", credential_ref=credential_ref)
            return credentials
        except VaultError:
            # Re-raise VaultError for proper handling (AC3)
            raise
        except Exception as e:
            raise VaultError(
                code="VAULT_UNAVAILABLE",
                message=f"Vault indisponible: {str(e)}",
            ) from e

    async def _execute_platform_step(
        self,
        step_id: int,
        action_info: dict[str, Any],
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
    ) -> str:
        """Execute platform step - trigger execution on external platform (Task 4.4-4.5).

        Args:
            step_id: Step ID
            action_info: Action with integration details
            parameters: Execution parameters
            credentials: Credentials from Vault
            correlation_id: Request correlation ID

        Returns:
            platform_job_id from adapter.trigger()

        Raises:
            PlatformError: If trigger fails
        """
        integration = action_info.get("integration")

        # Get platform type and URL
        platform_type = action_info.get("platform") or (
            integration.get("platform_type") if integration else None
        )
        base_url = integration.get("base_url") if integration else ""

        if not platform_type:
            # Default to mock adapter for testing
            platform_type = "mock"
            logger.warning("no_platform_type_using_mock", step_id=step_id)

        logger.info(
            "platform_trigger_starting",
            platform_type=platform_type,
            base_url=base_url,
        )

        try:
            adapter = get_platform_adapter(platform_type, base_url or "")
            platform_job_id = await adapter.trigger(parameters, credentials, correlation_id)

            logger.info(
                "platform_trigger_completed",
                platform_job_id=platform_job_id,
            )
            return platform_job_id

        except ValueError as e:
            # Unsupported platform
            raise PlatformError(
                code="PLATFORM_NOT_SUPPORTED",
                message=str(e),
            ) from e
        except Exception as e:
            raise PlatformError(
                code="PLATFORM_TRIGGER_FAILED",
                message=f"Erreur déclenchement plateforme: {str(e)}",
            ) from e

    async def _execute_servicenow_step(self, step_id: int) -> None:
        """Execute ServiceNow step - placeholder for Story 4.5.

        Args:
            step_id: Step ID
        """
        logger.info("servicenow_step_stub", step_id=step_id)
        # Story 4.5 will implement ServiceNow integration
        # For now, just mark as completed

    async def _execute_generic_step(self, step_id: int) -> None:
        """Execute generic step (prerequisite, verification).

        Args:
            step_id: Step ID
        """
        logger.info("generic_step_executed", step_id=step_id)
        # Generic steps complete immediately

    async def _fail_step(self, step_id: int, error_message: str) -> None:
        """Mark step as failed (Task 4.6).

        Args:
            step_id: Step ID
            error_message: Error details
        """
        await execution_repository.update_step_status(
            step_id,
            StepStatus.FAILED,
            error_message=error_message,
        )
        logger.error("execution_step_failed", step_id=step_id, error=error_message)

    async def _fail_execution(self, execution_id: int, error_message: str) -> None:
        """Mark execution as failed and skip remaining steps (Task 4.6).

        Args:
            execution_id: Execution ID
            error_message: Error details
        """
        # Skip remaining pending steps
        await execution_repository.skip_remaining_steps(execution_id)

        # Update execution status
        await execution_repository.update_status(execution_id, ExecutionStatus.FAILED)

        logger.error(
            "execution_failed",
            execution_id=execution_id,
            error=error_message,
        )


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing (Task 3.3).

    Returns:
        UUID string for correlation
    """
    return str(uuid.uuid4())
