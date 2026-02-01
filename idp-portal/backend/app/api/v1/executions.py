"""Executions API (Story 4.1, Task 1.1, 1.4 + Story 4.3, Task 3; Story 7.4 Approval Workflow).

Provides endpoints for execution submission and retrieval.
- POST /api/v1/executions: Submit a new execution
- GET /api/v1/executions/{id}: Get execution by ID
- GET /api/v1/executions: List user's executions
- GET /api/v1/executions/{id}/steps: Get execution steps
- POST /api/v1/executions/{id}/approve: DBA approves execution (Story 7.4)
- POST /api/v1/executions/{id}/reject: DBA rejects execution (Story 7.4)
- GET /api/v1/executions/pending-approvals: List pending approvals (Story 7.4)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
import jsonschema
import structlog

from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.api.services import get_vault_service
from app.repositories import audit_repository, catalog_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType
from app.core.exceptions import ForbiddenError, InvalidStateError, NotFoundError
from app.models.auth import UserProfile
from app.models.execution import ExecutionCreate, ExecutionStatus, StepLogsResponse


class ApprovalRequest(BaseModel):
    """Request body for approve/reject endpoints (Story 7.4)."""
    comment: str | None = Field(default=None, max_length=1000)
from app.repositories import execution_repository
from app.services import rbac_service
from app.services.execution_service import ExecutionService, generate_correlation_id
from app.websocket.execution_ws import get_execution_ws_manager
from app.websocket.dashboard_ws import get_dashboard_ws_manager
from app.api.services import get_servicenow_service

logger = structlog.get_logger()

router = APIRouter(prefix="/executions", tags=["executions"])

# Profiles that can view any execution (e.g. from dashboard recent list)
_EXECUTION_VIEW_ANY_PROFILES = frozenset({"dba", "dbops"})

# Profiles that can approve/reject executions (Story 7.4, AC2, AC3, AC4)
_APPROVAL_PROFILES = frozenset({"dba", "dbops"})


def _can_approve(user: UserProfile) -> bool:
    """True if user can approve/reject executions (Story 7.4)."""
    return (user.profile or "").lower() in _APPROVAL_PROFILES


def _can_view_execution(execution_user_id: int, user: UserProfile) -> bool:
    """True if user may view this execution (owner or DBA/DBOPS)."""
    if user.id == execution_user_id:
        return True
    return (user.profile or "").lower() in _EXECUTION_VIEW_ANY_PROFILES


def _validate_parameters_against_schema(
    parameters: dict[str, Any] | None,
    schema: dict[str, Any] | None,
) -> None:
    """Validate parameters against JSON Schema (Story 4.1, Task 1.4).

    Args:
        parameters: User-provided parameters
        schema: Action's parameters_schema

    Raises:
        InvalidStateError: If validation fails with field details
    """
    if schema is None:
        # No schema = no validation required
        return

    if parameters is None:
        parameters = {}

    # Ensure schema rejects extra properties unless explicitly allowed
    # Create a copy of schema with additionalProperties: false if not specified
    validation_schema = dict(schema)
    if "additionalProperties" not in validation_schema:
        validation_schema["additionalProperties"] = False

    # Also ensure each property rejects extra properties
    if "properties" in validation_schema and isinstance(validation_schema["properties"], dict):
        for prop_name, prop_schema in validation_schema["properties"].items():
            if isinstance(prop_schema, dict) and "additionalProperties" not in prop_schema:
                prop_schema["additionalProperties"] = False

    try:
        jsonschema.validate(instance=parameters, schema=validation_schema)
    except jsonschema.ValidationError as e:
        # Extract field path for error details
        field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        raise InvalidStateError(
            code="INVALID_PARAMETERS",
            message=f"Parametre invalide: {e.message}",
            details={
                "field": field_path,
                "error": e.message,
                "schema_path": list(e.schema_path),
            },
        ) from e
    except jsonschema.SchemaError as e:
        # Schema itself is invalid - this shouldn't happen if action was validated on creation
        raise InvalidStateError(
            code="INVALID_SCHEMA",
            message="Le schema de parametres de l'action est invalide",
            details={"error": str(e)},
        ) from e


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_execution(
    payload: ExecutionCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """POST /api/v1/executions - Submit a new execution (Story 4.1, AC3, AC4, AC5 + Story 4.3).

    Validates:
    - action_id exists and is published
    - environment is valid (dev, staging, prod)
    - parameters conform to action's parameters_schema (Task 1.4)

    Creates execution record, prepares steps, and starts background execution (Story 4.3).

    Returns:
        { "data": { "execution_id": int, "status": "SUBMITTED", "correlation_id": str, "created_at": datetime } }

    Raises:
        400 INVALID_PARAMETERS: If parameters validation fails
        404 ACTION_NOT_FOUND: If action doesn't exist or not published
    """
    # Generate correlation ID for request tracing (Story 4.3, Task 3.3)
    correlation_id = generate_correlation_id()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    logger.info(
        "execution_create_started",
        action_id=payload.action_id,
        environment=payload.environment.value,
        user_id=user.id,
    )

    # Check action exists and is published
    action_exists = await execution_repository.action_exists(payload.action_id)
    if not action_exists:
        raise NotFoundError(
            code="ACTION_NOT_FOUND",
            message="Action introuvable ou non publiee",
            details={"action_id": payload.action_id},
        )

    # RBAC: Check user has permission to execute this action in this environment (Task 3.2)
    has_permission = await rbac_service.can_execute(
        user_id=user.id,
        action_id=payload.action_id,
        environment=payload.environment.value,
    )
    if not has_permission:
        raise ForbiddenError(
            code="PERMISSION_DENIED",
            message="Vous n'avez pas la permission d'executer cette action dans cet environnement",
            details={
                "action_id": payload.action_id,
                "environment": payload.environment.value,
            },
        )

    # Validate parameters against action's schema (Task 1.4)
    schema = await execution_repository.get_action_parameters_schema(payload.action_id)
    _validate_parameters_against_schema(payload.parameters, schema)

    # Story 7.4 AC1: Check if approval is required for this action/environment
    requires_approval = await catalog_repository.get_requires_approval(
        payload.action_id, payload.environment.value
    )

    # Get client IP address (Story 6.1, AC5)
    client_ip = request.client.host if request.client else None
    # Check for X-Forwarded-For header if behind proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    if requires_approval:
        # Story 7.4 AC1: Create execution with PENDING_APPROVAL status, do NOT start execution
        result = await execution_repository.create_execution_pending_approval(
            user_id=user.id,
            action_id=payload.action_id,
            environment=payload.environment.value,
            parameters=payload.parameters,
        )

        execution_id = result.execution_id

        # Audit: EXECUTION_PENDING_APPROVAL (Story 7.4)
        await audit_repository.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.EXECUTION_PENDING_APPROVAL,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                "action_id": payload.action_id,
                "environment": payload.environment.value,
                "parameters": payload.parameters,
                "rbac_context": {"user_id": user.id, "profile": user.profile},
                "requires_approval": True,
            },
            ip_address=client_ip,
            correlation_id=correlation_id,
        )

        # Notify DBA via WebSocket (Story 7.4 AC6)
        dashboard_ws_manager = get_dashboard_ws_manager()
        action = await catalog_repository.get_by_id(payload.action_id)
        action_name = action.name if action else None
        await dashboard_ws_manager.broadcast_approval_required(
            execution_id=execution_id,
            action_name=action_name,
            user_display_name=user.display_name,
            environment=payload.environment.value,
        )

        logger.info(
            "execution_pending_approval",
            execution_id=execution_id,
            status="PENDING_APPROVAL",
            action_id=payload.action_id,
            environment=payload.environment.value,
        )

        return {
            "data": {
                "execution_id": execution_id,
                "status": result.status.value,
                "requires_approval": True,
                "correlation_id": correlation_id,
                "created_at": result.created_at.isoformat(),
            }
        }

    # Standard flow: no approval required
    # Create execution record (Story 4.1)
    result = await execution_repository.create_execution(
        user_id=user.id,
        action_id=payload.action_id,
        environment=payload.environment.value,
        parameters=payload.parameters,
    )

    execution_id = result.execution_id

    # Audit: EXECUTION_SUBMITTED (Story 6.1, AC1)
    await audit_repository.create_entry(
        user_id=str(user.id),
        action_type=AuditActionType.EXECUTION_SUBMITTED,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=execution_id,
        details={
            "action_id": payload.action_id,
            "environment": payload.environment.value,
            "parameters": payload.parameters,
            "rbac_context": {"user_id": user.id, "profile": user.profile},
        },
        ip_address=client_ip,
        correlation_id=correlation_id,
    )

    # Prepare execution steps (Story 4.3, Task 3.4; Story 4.5, Task 2)
    vault_service = get_vault_service()
    servicenow_service = await get_servicenow_service(vault_service)
    execution_service = ExecutionService(
        vault_service,
        servicenow_service,
        ws_manager=get_execution_ws_manager(),
        dashboard_ws_manager=get_dashboard_ws_manager(),
    )
    await execution_service.prepare_execution(execution_id, correlation_id)

    # Trigger background execution (Story 4.3, Task 3.6); pass client_ip for audit AC5 (Story 6.1)
    background_tasks.add_task(
        execution_service.start_execution,
        execution_id,
        correlation_id,
        client_ip=client_ip,
    )

    logger.info(
        "execution_created",
        execution_id=execution_id,
        status="SUBMITTED",
    )

    # Return response with correlation_id (NFR2: < 3s)
    return {
        "data": {
            "execution_id": execution_id,
            "status": result.status.value,
            "correlation_id": correlation_id,
            "created_at": result.created_at.isoformat(),
        }
    }


# --- Story 7.4: Approval Workflow Endpoints ---
# NOTE: These routes MUST be defined before routes with {execution_id} parameter
# to avoid FastAPI interpreting "pending-approvals" as an integer execution_id.


@router.get("/pending-approvals", response_model=None)
async def list_pending_approvals(
    user: UserProfile = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    count_only: bool = False,
) -> dict:
    """GET /api/v1/executions/pending-approvals - List pending approvals (Story 7.4, AC2, AC6).

    DBA/DBOPS only endpoint. Lists all executions waiting for approval.

    Args:
        count_only: If true, return only the count (for badge)

    Returns:
        { "data": list[ExecutionResponse], "pagination": {...} }
        OR { "count": int } if count_only=true

    Raises:
        403: If user is not DBA/DBOPS
    """
    if not _can_approve(user):
        raise ForbiddenError(
            code="PERMISSION_DENIED",
            message="Seuls les DBA et DBOPS peuvent consulter les approbations en attente",
            details={"user_profile": user.profile},
        )

    if count_only:
        count = await execution_repository.count_pending_approvals()
        return {"count": count}

    limit = min(max(1, limit), 100)
    offset = max(offset, 0)
    total_count = await execution_repository.count_pending_approvals()
    executions = await execution_repository.list_pending_approvals(
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        "data": [e.model_dump(mode="json") for e in executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/{execution_id}", response_model=None)
async def get_execution(
    execution_id: int,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/executions/{id} - Get execution by ID (Story 4.1).

    Returns execution if it belongs to the current user.

    Returns:
        { "data": ExecutionResponse }

    Raises:
        404: If execution not found or doesn't belong to user
    """
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None or not _can_view_execution(execution.user_id, user):
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    return {"data": execution.model_dump(mode="json")}


@router.get("", response_model=None)
async def list_executions(
    user: UserProfile = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """GET /api/v1/executions - List user's executions (Story 4.1, 4.8 AC4).

    Returns:
        { "data": list[ExecutionResponse], "pagination": { page, page_size, total_count, total_pages } }
    """
    limit = min(max(1, limit), 100)
    offset = max(offset, 0)
    total_count = await execution_repository.count_by_user(user_id=user.id)
    executions = await execution_repository.list_by_user(
        user_id=user.id,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1
    return {
        "data": [e.model_dump(mode="json") for e in executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.get("/{execution_id}/steps", response_model=None)
async def get_execution_steps(
    execution_id: int,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/executions/{id}/steps - Get execution steps (Story 4.3).

    Returns steps for an execution owned by the current user.

    Returns:
        { "data": list[ExecutionStepResponse] }

    Raises:
        404: If execution not found or doesn't belong to user
    """
    # Verify execution exists and user may view it (owner or DBA/DBOPS)
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None or not _can_view_execution(execution.user_id, user):
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    # Get steps
    steps = await execution_repository.get_steps_by_execution_id(execution_id)

    return {"data": [s.model_dump(mode="json") for s in steps]}


@router.get("/{execution_id}/steps/{step_id}/logs", response_model=None)
async def get_step_logs(
    execution_id: int,
    step_id: int,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/executions/{id}/steps/{step_id}/logs - Get step logs (Story 4.7, AC6).

    Returns logs for a single step: output, error_message, started_at, completed_at.
    RBAC: same as GET execution (execution must belong to current user).

    Returns:
        { "data": { "step_id": int, "output": {...}, "error_message": str|null, "started_at", "completed_at" } }

    Raises:
        404: Execution or step not found, or execution not owned by user
    """
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None or not _can_view_execution(execution.user_id, user):
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    step = await execution_repository.get_step_by_id(step_id)

    if step is None or step.execution_id != execution_id:
        raise NotFoundError(
            code="STEP_NOT_FOUND",
            message="Etape introuvable",
            details={"execution_id": execution_id, "step_id": step_id},
        )

    logs = StepLogsResponse(
        step_id=step.id,
        output=step.output,
        error_message=step.error_message,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )
    return {"data": logs.model_dump(mode="json")}


@router.post("/{execution_id}/approve", status_code=status.HTTP_200_OK, response_model=None)
async def approve_execution(
    execution_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    user: UserProfile = Depends(get_current_user),
    payload: ApprovalRequest | None = None,
) -> dict:
    """POST /api/v1/executions/{id}/approve - DBA approves execution (Story 7.4, AC3, AC5).

    Validates:
    - User has DBA/DBOPS profile
    - Execution exists and status is PENDING_APPROVAL
    - User is not the requester (cannot self-approve)

    On approval:
    - Updates status to SUBMITTED
    - Records approver, timestamp, comment
    - Starts background execution
    - Creates AUDIT_LOG entry

    Returns:
        { "data": { "execution_id": int, "status": "SUBMITTED", "approved_by": int } }

    Raises:
        403: If user cannot approve or is self-approving
        404: If execution not found or not in PENDING_APPROVAL status
    """
    correlation_id = generate_correlation_id()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    if not _can_approve(user):
        raise ForbiddenError(
            code="PERMISSION_DENIED",
            message="Seuls les DBA et DBOPS peuvent approuver les executions",
            details={"user_profile": user.profile},
        )

    # Check execution exists and is pending approval
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None:
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    if execution.status != ExecutionStatus.PENDING_APPROVAL:
        raise InvalidStateError(
            code="INVALID_STATUS",
            message="L'execution n'est pas en attente d'approbation",
            details={"execution_id": execution_id, "current_status": execution.status.value},
        )

    # Prevent self-approval
    if execution.user_id == user.id:
        raise ForbiddenError(
            code="SELF_APPROVAL_FORBIDDEN",
            message="Vous ne pouvez pas approuver votre propre demande d'execution",
            details={"execution_id": execution_id, "requester_id": execution.user_id},
        )

    # Extract comment from payload
    comment = payload.comment if payload else None

    # Approve the execution
    approved = await execution_repository.approve(execution_id, user.id, comment)

    if not approved:
        raise InvalidStateError(
            code="APPROVAL_FAILED",
            message="L'approbation a echoue (execution peut avoir ete modifiee)",
            details={"execution_id": execution_id},
        )

    # Get client IP for audit
    client_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Audit: EXECUTION_APPROVED (Story 7.4)
    await audit_repository.create_entry(
        user_id=str(user.id),
        action_type=AuditActionType.EXECUTION_APPROVED,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=execution_id,
        details={
            "action_id": execution.action_id,
            "environment": execution.environment.value,
            "requester_id": execution.user_id,
            "approver_id": user.id,
            "approver_profile": user.profile,
            "comment": comment,
        },
        ip_address=client_ip,
        correlation_id=correlation_id,
    )

    # Prepare and start execution (Story 4.3 flow)
    vault_service = get_vault_service()
    servicenow_service = await get_servicenow_service(vault_service)
    execution_service = ExecutionService(
        vault_service,
        servicenow_service,
        ws_manager=get_execution_ws_manager(),
        dashboard_ws_manager=get_dashboard_ws_manager(),
    )
    await execution_service.prepare_execution(execution_id, correlation_id)

    # Start execution in background
    background_tasks.add_task(
        execution_service.start_execution,
        execution_id,
        correlation_id,
        client_ip=client_ip,
    )

    logger.info(
        "execution_approved",
        execution_id=execution_id,
        approver_id=user.id,
    )

    return {
        "data": {
            "execution_id": execution_id,
            "status": ExecutionStatus.SUBMITTED.value,
            "approved_by": user.id,
            "correlation_id": correlation_id,
        }
    }


@router.post("/{execution_id}/reject", status_code=status.HTTP_200_OK, response_model=None)
async def reject_execution(
    execution_id: int,
    request: Request,
    user: UserProfile = Depends(get_current_user),
    payload: ApprovalRequest | None = None,
) -> dict:
    """POST /api/v1/executions/{id}/reject - DBA rejects execution (Story 7.4, AC4, AC5).

    Validates:
    - User has DBA/DBOPS profile
    - Execution exists and status is PENDING_APPROVAL

    On rejection:
    - Updates status to REJECTED
    - Records rejector, timestamp, comment
    - Creates AUDIT_LOG entry

    Returns:
        { "data": { "execution_id": int, "status": "REJECTED", "rejected_by": int } }

    Raises:
        403: If user cannot reject
        404: If execution not found or not in PENDING_APPROVAL status
    """
    correlation_id = generate_correlation_id()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    if not _can_approve(user):
        raise ForbiddenError(
            code="PERMISSION_DENIED",
            message="Seuls les DBA et DBOPS peuvent refuser les executions",
            details={"user_profile": user.profile},
        )

    # Check execution exists and is pending approval
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None:
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    if execution.status != ExecutionStatus.PENDING_APPROVAL:
        raise InvalidStateError(
            code="INVALID_STATUS",
            message="L'execution n'est pas en attente d'approbation",
            details={"execution_id": execution_id, "current_status": execution.status.value},
        )

    # Extract comment from payload
    comment = payload.comment if payload else None

    # Reject the execution
    rejected = await execution_repository.reject(execution_id, user.id, comment)

    if not rejected:
        raise InvalidStateError(
            code="REJECTION_FAILED",
            message="Le refus a echoue (execution peut avoir ete modifiee)",
            details={"execution_id": execution_id},
        )

    # Get client IP for audit
    client_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Audit: EXECUTION_REJECTED (Story 7.4)
    await audit_repository.create_entry(
        user_id=str(user.id),
        action_type=AuditActionType.EXECUTION_REJECTED,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=execution_id,
        details={
            "action_id": execution.action_id,
            "environment": execution.environment.value,
            "requester_id": execution.user_id,
            "rejector_id": user.id,
            "rejector_profile": user.profile,
            "comment": comment,
        },
        ip_address=client_ip,
        correlation_id=correlation_id,
    )

    logger.info(
        "execution_rejected",
        execution_id=execution_id,
        rejector_id=user.id,
    )

    return {
        "data": {
            "execution_id": execution_id,
            "status": ExecutionStatus.REJECTED.value,
            "rejected_by": user.id,
            "rejection_reason": comment,
        }
    }
