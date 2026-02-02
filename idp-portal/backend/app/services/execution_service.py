"""Execution service for orchestrating action executions (Story 4.3, Task 4; Story 4.5, Task 2).

Orchestrates the execution flow:
1. Load execution and steps from repository
2. Retrieve secrets from Vault (Story 4.2bis)
3. Select platform adapter (Strategy Pattern)
4. Trigger execution on platform
5. Create ServiceNow change if required (Story 4.5)
6. Handle errors and update step status
7. Identify remediation suggestions for failed executions (Story 9.1)
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.adapters import get_platform_adapter
from app.core.exceptions import PlatformError, ServiceNowError, VaultError
from app.models.execution import ExecutionStatus, StepStatus, StepType, ExecutionStepCreate
from app.models.catalog import RemediationSuggestion
from app.repositories import audit_repository, execution_repository, catalog_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType
from app.services.vault_service import VaultService

if TYPE_CHECKING:
    from app.services.servicenow_service import ServiceNowService
    from app.websocket.execution_ws import ExecutionWebSocketManager
    from app.websocket.dashboard_ws import DashboardWebSocketManager

logger = structlog.get_logger()

# Story 6.2: Tag conventions for audit evidence enrichment
# =========================================================
# Actions with these tags will have enriched audit DETAILS in AUDIT_LOG.
#
# PATCHING_TAG ("patching"):
#   Audit DETAILS JSON schema:
#   {
#     "status": "COMPLETED|FAILED",
#     "steps_summary": [...],
#     "version_source": str | null,    # Source version (from execution parameters)
#     "version_target": str | null,    # Target version (from execution parameters)
#     "patch_result": "success|failed", # Derived from execution outcome
#     "components_modified": list[str] | null  # Components patched (from parameters["components"])
#   }
#
# PRIVILEGE_ACCOUNT_TAG ("compte-privileges"):
#   Audit DETAILS JSON schema:
#   {
#     "status": "COMPLETED|FAILED",
#     "steps_summary": [...],
#     "justification": str | null,     # Justification for account creation
#     "approbateur": str | null,       # Approver email/name
#     "privilege_scope": str | null    # Scope of privileges (DBA, SYSDBA, etc.)
#   }
#
# Regular actions (no special tags): standard DETAILS structure unchanged.

PATCHING_TAG = "patching"
PRIVILEGE_ACCOUNT_TAG = "compte-privileges"


def _build_patching_evidence(parameters: dict[str, Any], result: str) -> dict[str, Any]:
    """Build patching evidence fields for audit (Story 6.2, AC1, AC3, AC4).

    Enriches audit DETAILS with patching-specific fields for SOC1 compliance.
    Values are extracted from execution parameters; missing values are null.
    Logs warnings when expected SOC1 evidence fields are missing.

    Args:
        parameters: Execution parameters containing patching info:
            - version_source: Source version before patching
            - version_target: Target version after patching
            - components: List of components being patched
        result: "success" or "failed" based on execution outcome

    Returns:
        Dict with version_source, version_target, patch_result, components_modified
    """
    # Log warnings for missing SOC1 evidence fields (code-review fix)
    missing_fields = []
    if not parameters.get("version_source"):
        missing_fields.append("version_source")
    if not parameters.get("version_target"):
        missing_fields.append("version_target")
    if not parameters.get("components"):
        missing_fields.append("components")
    if missing_fields:
        logger.warning("patching_evidence_incomplete", missing_fields=missing_fields)

    return {
        "version_source": parameters.get("version_source"),
        "version_target": parameters.get("version_target"),
        "patch_result": result,
        "components_modified": parameters.get("components"),
    }


def _build_privilege_account_evidence(parameters: dict[str, Any]) -> dict[str, Any]:
    """Build compte à privilèges evidence fields for audit (Story 6.2, AC2, AC3, AC4).

    Enriches audit DETAILS with privilege account fields for SOC1 compliance.
    Values are extracted from execution parameters; missing values are null.
    Logs warnings when expected SOC1 evidence fields are missing.

    Args:
        parameters: Execution parameters containing privilege account info:
            - justification: Reason for account creation (e.g., ticket reference)
            - approbateur: Approver email or name
            - privilege_scope: Scope of privileges granted (e.g., DBA, SYSDBA)

    Returns:
        Dict with justification, approbateur, privilege_scope
    """
    # Log warnings for missing SOC1 evidence fields (code-review fix)
    missing_fields = []
    if not parameters.get("justification"):
        missing_fields.append("justification")
    if not parameters.get("approbateur"):
        missing_fields.append("approbateur")
    if not parameters.get("privilege_scope"):
        missing_fields.append("privilege_scope")
    if missing_fields:
        logger.warning("privilege_account_evidence_incomplete", missing_fields=missing_fields)

    return {
        "justification": parameters.get("justification"),
        "approbateur": parameters.get("approbateur"),
        "privilege_scope": parameters.get("privilege_scope"),
    }


class ExecutionService:
    """Service for orchestrating action executions (Story 4.3, Task 4.1; Story 4.5, Task 2.1).

    Coordinates between:
    - execution_repository: CRUD for executions and steps
    - vault_service: Secret retrieval (Story 4.2bis)
    - servicenow_service: Change management (Story 4.5)
    - platform adapters: Triggering executions (Strategy Pattern)
    """

    def __init__(
        self,
        vault_service: VaultService,
        servicenow_service: "ServiceNowService | None" = None,
        ws_manager: "ExecutionWebSocketManager | None" = None,
        dashboard_ws_manager: "DashboardWebSocketManager | None" = None,
    ) -> None:
        """Initialize service with dependencies.

        Args:
            vault_service: Service for retrieving secrets from Vault
            servicenow_service: Service for ServiceNow change management (optional)
            ws_manager: WebSocket manager for real-time timeline (Story 4.6, optional)
            dashboard_ws_manager: WebSocket manager for dashboard updates (Story 5.2, optional)
        """
        self.vault_service = vault_service
        self.servicenow_service = servicenow_service
        self.ws_manager = ws_manager
        self.dashboard_ws_manager = dashboard_ws_manager

    async def _broadcast_step_update(self, step_id: int) -> None:
        """Broadcast step_update to WebSocket clients (Story 4.6, Task 1.4)."""
        if not self.ws_manager:
            return
        step = await execution_repository.get_step_by_id(step_id)
        if step is None:
            return
        step_data = {
            "step_order": step.step_order,
            "step_name": step.step_name,
            "status": step.status.value,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        }
        await self.ws_manager.broadcast_step_update(step.execution_id, step_data)

    async def _broadcast_dashboard_update(
        self,
        execution_id: int,
        status: str,
        action_name: str | None = None,
        step_summary: str | None = None,
    ) -> None:
        """Broadcast execution_update to dashboard WebSocket clients (Story 5.2, Task 1.3).

        Args:
            execution_id: Execution ID
            status: Execution status (RUNNING, COMPLETED, FAILED, etc.)
            action_name: Optional action name for display
            step_summary: Optional step summary for display
        """
        if not self.dashboard_ws_manager:
            return
        await self.dashboard_ws_manager.broadcast_execution_update(
            execution_id=execution_id,
            status=status,
            action_name=action_name,
            step_summary=step_summary,
        )

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
        client_ip: str | None = None,
    ) -> None:
        """Start execution and orchestrate steps (Story 4.3, Task 4.1).

        This is the main entry point for the execution engine.
        Called as a background task after prepare_execution.

        Args:
            execution_id: ID of the execution to start
            correlation_id: Request correlation ID for tracing
            client_ip: Client IP from submission request (Story 6.1, AC5)
        """
        self._client_ip = client_ip
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            execution_id=execution_id,
        )

        logger.info("execution_starting", execution_id=execution_id)

        try:
            # Get execution details for audit
            execution_for_audit = await execution_repository.get_by_id(execution_id)

            # Audit: EXECUTION_STARTED (Story 6.1, AC1, AC5)
            if execution_for_audit:
                await audit_repository.create_entry(
                    user_id=str(execution_for_audit.user_id),
                    action_type=AuditActionType.EXECUTION_STARTED,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=execution_id,
                    details={
                        "action_id": execution_for_audit.action_id,
                        "environment": execution_for_audit.environment.value
                        if hasattr(execution_for_audit.environment, "value")
                        else str(execution_for_audit.environment),
                    },
                    ip_address=self._client_ip,
                    correlation_id=correlation_id,
                )

            # Update execution status to RUNNING (Task 4.2)
            await execution_repository.update_status(execution_id, ExecutionStatus.RUNNING)

            # Broadcast to dashboard (Story 5.2, Task 1.3) — null-safe (code-review fix)
            execution_for_broadcast = await execution_repository.get_by_id(execution_id)
            if execution_for_broadcast:
                action_info_broadcast = await execution_repository.get_action_with_integration(
                    execution_for_broadcast.action_id
                )
                await self._broadcast_dashboard_update(
                    execution_id,
                    "RUNNING",
                    action_name=action_info_broadcast.get("name") if action_info_broadcast else None,
                )

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
                    correlation_id=correlation_id,
                )
                return

            # Get execution steps
            steps = await execution_repository.get_steps_by_execution_id(execution_id)
            if not steps:
                # Should have been created by prepare_execution
                await self._fail_execution(
                    execution_id,
                    "Aucune étape d'exécution définie",
                    correlation_id=correlation_id,
                )
                return

            # Execute each step in order
            credentials: dict[str, Any] = {}
            platform_job_id: str | None = None
            step_output: dict[str, Any] | None = None  # AC2: output for step (e.g. ServiceNow change_number)

            for step in steps:
                step_output = None
                logger.info(
                    "execution_step_starting",
                    step_id=step.id,
                    step_name=step.step_name,
                    step_type=step.step_type.value,
                )

                # Update step status to RUNNING
                await execution_repository.update_step_status(step.id, StepStatus.RUNNING)
                await self._broadcast_step_update(step.id)
                # Dashboard: step progress (Story 5.2, Task 1.3 — code-review)
                step_summary = f"{step.step_name} ({step.step_order}/{len(steps)})"
                await self._broadcast_dashboard_update(
                    execution_id,
                    "RUNNING",
                    action_name=action_info.get("name") if action_info else None,
                    step_summary=step_summary,
                )

                try:
                    if step.step_type == StepType.VAULT:
                        # Retrieve secrets from Vault (AC2, AC3)
                        credentials = await self._execute_vault_step(
                            step.id,
                            action_info,
                            correlation_id,
                        )

                    elif step.step_type == StepType.PLATFORM:
                        # Trigger platform execution (AC2); step_order for connector_config merge (Story 4.10)
                        platform_job_id = await self._execute_platform_step(
                            step.id,
                            step.step_order,
                            action_info,
                            execution.parameters or {},
                            credentials,
                            correlation_id,
                        )

                    elif step.step_type == StepType.SERVICENOW:
                        # ServiceNow change management (Story 4.5, Task 2.1)
                        servicenow_result = await self._execute_servicenow_step(
                            step.id,
                            execution.id,
                            action_info,
                            execution.environment.value if hasattr(execution.environment, 'value') else str(execution.environment),
                            execution.parameters or {},
                            execution.user_id,
                            correlation_id,
                        )
                        # Check if execution should be suspended (pending CAB approval)
                        if servicenow_result and servicenow_result.get("status") == "pending_approval":
                            # Update step to running (not completed) - waiting for approval
                            await execution_repository.update_step_status(
                                step.id,
                                StepStatus.RUNNING,
                                output=servicenow_result,
                            )
                            await self._broadcast_step_update(step.id)
                            # Update execution to pending approval
                            await execution_repository.update_status(
                                execution.id,
                                ExecutionStatus.PENDING_APPROVAL,
                                servicenow_change_id=servicenow_result.get("change_id"),
                            )
                            logger.info(
                                "execution_pending_cab_approval",
                                execution_id=execution.id,
                                change_number=servicenow_result.get("change_number"),
                            )
                            # Stop execution - will resume after CAB approval
                            return
                        # Approved: store output for timeline (AC2 - change_number display)
                        if servicenow_result:
                            step_output = servicenow_result

                    else:
                        # Generic step (prerequisite, verification)
                        await self._execute_generic_step(step.id)

                    # Mark step completed (AC2: pass step_output for ServiceNow approved)
                    await execution_repository.update_step_status(
                        step.id,
                        StepStatus.COMPLETED,
                        output=step_output,
                        platform_job_id=platform_job_id,
                    )
                    await self._broadcast_step_update(step.id)
                    # Dashboard: step progress (Story 5.2, Task 1.3 — code-review)
                    step_summary_done = f"{step.step_name} ({step.step_order}/{len(steps)})"
                    await self._broadcast_dashboard_update(
                        execution_id,
                        "RUNNING",
                        action_name=action_info.get("name") if action_info else None,
                        step_summary=step_summary_done,
                    )
                    logger.info("execution_step_completed", step_id=step.id)

                except VaultError as e:
                    # Vault unavailable - fail execution (AC3)
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Vault indisponible — exécution impossible: {e.message}",
                        correlation_id=correlation_id,
                    )
                    return

                except PlatformError as e:
                    # Platform error - fail execution
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Erreur plateforme: {e.message}",
                        correlation_id=correlation_id,
                    )
                    return

                except ServiceNowError as e:
                    # ServiceNow error - fail execution (Story 4.5, Task 2.4)
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"ServiceNow indisponible — changement non créé: {e.message}",
                        correlation_id=correlation_id,
                    )
                    return

                except Exception as e:
                    # Unexpected error - fail execution
                    logger.error("execution_step_failed", step_id=step.id, error=str(e))
                    await self._fail_step(step.id, str(e))
                    await self._fail_execution(
                        execution_id,
                        f"Erreur inattendue: {str(e)}",
                        correlation_id=correlation_id,
                    )
                    return

            # All steps completed successfully
            await execution_repository.update_status(execution_id, ExecutionStatus.COMPLETED)

            # Audit: EXECUTION_COMPLETED (Story 6.1, AC1, AC5; Story 6.2, AC1-AC4)
            step_summary = [
                {"order": s.step_order, "name": s.step_name, "status": s.status.value}
                for s in steps
            ]
            audit_details: dict[str, Any] = {
                "status": "COMPLETED",
                "steps_summary": step_summary,
            }

            # Story 6.2: Enrich audit details for patching or compte-privileges actions
            try:
                action_tags = await catalog_repository.get_tags_for_action(execution.action_id) or []
            except Exception as e:
                logger.error("failed_to_retrieve_action_tags", action_id=execution.action_id, error=str(e))
                action_tags = []  # Fallback to regular audit
            exec_params = execution.parameters or {}
            if PATCHING_TAG in action_tags:
                audit_details.update(_build_patching_evidence(exec_params, "success"))
            elif PRIVILEGE_ACCOUNT_TAG in action_tags:
                audit_details.update(_build_privilege_account_evidence(exec_params))

            await audit_repository.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_COMPLETED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details=audit_details,
                ip_address=getattr(self, "_client_ip", None),
                correlation_id=correlation_id,
            )

            if self.ws_manager:
                await self.ws_manager.broadcast_execution_complete(execution_id)
            # Broadcast to dashboard (Story 5.2, Task 1.3)
            await self._broadcast_dashboard_update(
                execution_id,
                "COMPLETED",
                action_name=action_info.get("name") if action_info else None,
            )
            logger.info("execution_completed", execution_id=execution_id)

        except Exception as e:
            logger.error("execution_orchestration_failed", error=str(e))
            await self._fail_execution(
                execution_id,
                f"Erreur d'orchestration: {str(e)}",
                correlation_id=correlation_id,
            )

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

    def _merge_aap_connector_config(
        self,
        step_order: int,
        action_info: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge AAP step connector_config (resource_type, template id) with execution parameters (Story 4.10, AC1).

        Args:
            step_order: Current step order (1-based)
            action_info: Action with execution_steps
            parameters: Execution parameters (user extra_vars)

        Returns:
            Merged dict: connector_config (resource_type, job_template_id/workflow_job_template_id) + parameters
        """
        merged = dict(parameters)
        execution_steps = action_info.get("execution_steps") or []
        step_def = next(
            (s for s in execution_steps if s.get("order") == step_order),
            None,
        )
        if not step_def:
            return merged
        connector_config = step_def.get("connector_config") or {}
        resource_type = connector_config.get("resource_type", "job_template")
        template_id = (
            connector_config.get("workflow_job_template_id")
            or connector_config.get("job_template_id")
            or connector_config.get("template_id")
        )
        if template_id is not None:
            merged["resource_type"] = resource_type
            if resource_type == "workflow_job":
                merged["workflow_job_template_id"] = template_id
            else:
                merged["job_template_id"] = template_id
        return merged

    async def _execute_platform_step(
        self,
        step_id: int,
        step_order: int,
        action_info: dict[str, Any],
        parameters: dict[str, Any],
        credentials: dict[str, Any],
        correlation_id: str,
    ) -> str:
        """Execute platform step - trigger execution on external platform (Task 4.4-4.5).

        Args:
            step_id: Step ID
            step_order: Step order (1-based) for connector_config lookup (Story 4.10)
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

        # Merge AAP connector_config (resource_type, template id) with parameters (Story 4.10)
        if platform_type and str(platform_type).lower() == "aap":
            parameters = self._merge_aap_connector_config(step_order, action_info, parameters)

        logger.info(
            "platform_trigger_starting",
            platform_type=platform_type,
            base_url=base_url,
        )

        try:
            adapter = get_platform_adapter(platform_type, base_url or "")
            platform_job_id = await adapter.trigger(
                parameters, credentials, correlation_id, integration=integration
            )

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

    async def _execute_servicenow_step(
        self,
        step_id: int,
        execution_id: int,
        action_info: dict[str, Any],
        environment: str,
        parameters: dict[str, Any],
        user_id: int,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """Execute ServiceNow step - create change request (Story 4.5, Task 2.1-2.2).

        Args:
            step_id: Step ID
            execution_id: Execution ID
            action_info: Action with integration details
            environment: Target environment
            parameters: Execution parameters
            user_id: User ID
            correlation_id: Request correlation ID

        Returns:
            Dict with change_id, change_number, status or None if ServiceNow disabled

        Raises:
            ServiceNowError: If ServiceNow API fails
        """
        if self.servicenow_service is None:
            # ServiceNow not configured - skip step
            logger.warning("servicenow_not_configured", step_id=step_id)
            return None

        # Get action details
        action_name = action_info.get("name", "Unknown Action")

        # Get change_model_code from action (for pre-approved changes)
        # Check in execution_steps first, then action-level config
        change_model_code = None
        execution_steps = action_info.get("execution_steps", [])
        for step_def in execution_steps:
            if step_def.get("type") == "servicenow":
                change_model_code = step_def.get("change_model_code")
                break

        # Fallback to action-level change_model_code (Story 2.21)
        if not change_model_code:
            change_model_code = action_info.get("change_model_code")

        # Get credential_ref from ServiceNow integration (if any)
        credential_ref = None
        integration = action_info.get("integration")
        if integration and integration.get("platform_type") == "servicenow":
            credential_ref = integration.get("credential_ref")

        # Get user info for requested_by field
        # For now, use user_id; in production, resolve to username
        user = f"user_{user_id}"

        logger.info(
            "servicenow_step_starting",
            step_id=step_id,
            execution_id=execution_id,
            action_name=action_name,
            environment=environment,
            change_model_code=change_model_code,
        )

        # Create ServiceNow change request
        result = await self.servicenow_service.create_change(
            execution_id=execution_id,
            action_name=action_name,
            environment=environment,
            parameters=parameters,
            user=user,
            correlation_id=correlation_id,
            change_model_code=change_model_code,
            credential_ref=credential_ref,
        )

        # Audit: SERVICENOW_CHANGE_CREATED (Story 6.1, AC2, AC5) — right after create_change so audit is not lost
        change_type = "pre-approved" if change_model_code else "CAB"
        try:
            await audit_repository.create_entry(
                user_id=str(user_id),
                action_type=AuditActionType.SERVICENOW_CHANGE_CREATED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details={
                    "servicenow_change_id": result.get("change_id"),
                    "change_number": result.get("change_number"),
                    "change_type": change_type,
                    "approval_status": result.get("status"),
                    "change_model_code": change_model_code,
                },
                ip_address=getattr(self, "_client_ip", None),
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.critical(
                "audit_servicenow_change_created_failed",
                execution_id=execution_id,
                error=str(e),
            )

        # Store change_id in EXECUTIONS table (Task 2.3)
        if result.get("status") == "approved":
            await execution_repository.update_status(
                execution_id,
                ExecutionStatus.RUNNING,  # Keep running since approved
                servicenow_change_id=result.get("change_id"),
            )

        logger.info(
            "servicenow_step_result",
            step_id=step_id,
            change_id=result.get("change_id"),
            change_number=result.get("change_number"),
            status=result.get("status"),
        )

        return result

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
        await self._broadcast_step_update(step_id)
        logger.error("execution_step_failed", step_id=step_id, error=error_message)

    async def _fail_execution(
        self,
        execution_id: int,
        error_message: str,
        correlation_id: str | None = None,
    ) -> None:
        """Mark execution as failed and skip remaining steps (Task 4.6).

        Args:
            execution_id: Execution ID
            error_message: Error details
            correlation_id: Optional correlation ID for audit
        """
        # Skip remaining pending steps
        await execution_repository.skip_remaining_steps(execution_id)

        # Update execution status
        await execution_repository.update_status(execution_id, ExecutionStatus.FAILED)

        # Broadcast to dashboard (Story 5.2, Task 1.3)
        execution = await execution_repository.get_by_id(execution_id)
        action_info = None
        if execution:
            action_info = await execution_repository.get_action_with_integration(execution.action_id)

            # Audit: EXECUTION_FAILED (Story 6.1, AC1, AC5; Story 6.2, AC1-AC4)
            audit_details: dict[str, Any] = {
                "status": "FAILED",
                "error_message": error_message,
                "action_id": execution.action_id,
            }

            # Story 6.2: Enrich audit details for patching or compte-privileges actions
            try:
                action_tags = await catalog_repository.get_tags_for_action(execution.action_id) or []
            except Exception as e:
                logger.error("failed_to_retrieve_action_tags", action_id=execution.action_id, error=str(e))
                action_tags = []  # Fallback to regular audit
            exec_params = execution.parameters or {}
            if PATCHING_TAG in action_tags:
                audit_details.update(_build_patching_evidence(exec_params, "failed"))
            elif PRIVILEGE_ACCOUNT_TAG in action_tags:
                audit_details.update(_build_privilege_account_evidence(exec_params))

            await audit_repository.create_entry(
                user_id=str(execution.user_id),
                action_type=AuditActionType.EXECUTION_FAILED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=execution_id,
                details=audit_details,
                ip_address=getattr(self, "_client_ip", None),
                correlation_id=correlation_id,
            )

        if self.ws_manager:
            await self.ws_manager.broadcast_execution_failed(execution_id, error_message)

        await self._broadcast_dashboard_update(
            execution_id,
            "FAILED",
            action_name=action_info.get("name") if action_info else None,
        )

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


# === Story 9.1: Remediation Suggestions (FR36) ===


async def get_remediation_suggestions(execution_id: int) -> list[RemediationSuggestion]:
    """Identify applicable corrective actions for a failed execution (Story 9.1, AC2, AC5).

    Algorithm:
    1. Load execution + steps (find step with FAILED status)
    2. Extract error_message, environment, engine from failed step
    3. Load all published actions with remediation_rules configured
    4. For each action's rules, match:
       a. error_pattern regex against error_message
       b. environment in rule.environments
    5. Score matches: exact engine match (+10) > partial match (+1)
    6. Return top 3 suggestions sorted by relevance score

    Args:
        execution_id: ID of the failed execution

    Returns:
        List of RemediationSuggestion (max 3), empty if no match or execution not failed
    """
    # 1. Load execution
    execution = await execution_repository.get_by_id(execution_id)
    if execution is None:
        logger.debug("get_remediation_suggestions_execution_not_found", execution_id=execution_id)
        return []

    # Only suggest remediation for FAILED executions
    if execution.status != ExecutionStatus.FAILED:
        logger.debug(
            "get_remediation_suggestions_not_failed",
            execution_id=execution_id,
            status=execution.status.value,
        )
        return []

    # 2. Get steps and find failed step
    steps = await execution_repository.get_steps_by_execution_id(execution_id)
    failed_step = next((s for s in steps if s.status == StepStatus.FAILED), None)

    if failed_step is None or not failed_step.error_message:
        logger.debug(
            "get_remediation_suggestions_no_failed_step_or_error",
            execution_id=execution_id,
        )
        return []

    error_message = failed_step.error_message
    environment = execution.environment.value if hasattr(execution.environment, "value") else str(execution.environment)

    # Get engine from the action
    action_info = await execution_repository.get_action_with_integration(execution.action_id)
    engine = action_info.get("engine") if action_info else None

    logger.info(
        "get_remediation_suggestions_matching",
        execution_id=execution_id,
        error_message=error_message[:100] if error_message else None,
        environment=environment,
        engine=engine,
    )

    # 3. Load actions with remediation rules
    actions_with_rules = await catalog_repository.get_actions_with_remediation_rules()

    if not actions_with_rules:
        logger.debug("get_remediation_suggestions_no_actions_with_rules")
        return []

    # 4. Match rules
    suggestions: list[dict[str, Any]] = []

    for action in actions_with_rules:
        if not action.remediation_rules:
            continue

        for rule in action.remediation_rules:
            # a. Match regex error_pattern
            try:
                if not re.search(rule.error_pattern, error_message, re.IGNORECASE):
                    continue
            except re.error as e:
                logger.warning(
                    "get_remediation_suggestions_invalid_regex",
                    action_id=action.id,
                    error_pattern=rule.error_pattern,
                    error=str(e),
                )
                continue

            # b. Check environment
            if environment.lower() not in [env.lower() for env in rule.environments]:
                continue

            # c. Score pertinence
            score = 1  # Base score for match
            if engine and action.engine and action.engine.value == engine:
                score += 10  # Bonus for exact engine match

            suggestions.append({
                "action": action,
                "rule": rule,
                "score": score,
            })

    # 5. Sort by score descending, deduplicate by target_action_id (keep highest score)
    seen_action_ids: set[int] = set()
    unique_suggestions: list[dict[str, Any]] = []

    for s in sorted(suggestions, key=lambda x: x["score"], reverse=True):
        target_action_id = s["rule"].target_action_id
        if target_action_id not in seen_action_ids:
            seen_action_ids.add(target_action_id)
            unique_suggestions.append(s)

    # 6. Return top 3 - fetch target action details
    top_suggestions = unique_suggestions[:3]

    result = []
    for s in top_suggestions:
        target_action_id = s["rule"].target_action_id
        target_action = await catalog_repository.get_by_id(target_action_id)
        if target_action:
            result.append(
                RemediationSuggestion(
                    action_id=target_action.id,
                    action_name=target_action.name,
                    action_description=target_action.description,
                    matching_rule=s["rule"],
                )
            )

    logger.info(
        "get_remediation_suggestions_result",
        execution_id=execution_id,
        suggestions_count=len(result),
        action_ids=[r.action_id for r in result],
    )

    return result
