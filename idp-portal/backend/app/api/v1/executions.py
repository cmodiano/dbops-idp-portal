"""Executions API (Story 4.1, Task 1.1, 1.4 + Story 4.3, Task 3).

Provides endpoints for execution submission and retrieval.
- POST /api/v1/executions: Submit a new execution
- GET /api/v1/executions/{id}: Get execution by ID
- GET /api/v1/executions: List user's executions
- GET /api/v1/executions/{id}/steps: Get execution steps
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, status
import jsonschema
import structlog

from app.api.deps import get_current_user
from app.api.services import get_vault_service
from app.core.exceptions import ForbiddenError, InvalidStateError, NotFoundError
from app.models.auth import UserProfile
from app.models.execution import ExecutionCreate
from app.repositories import execution_repository
from app.services import rbac_service
from app.services.execution_service import ExecutionService, generate_correlation_id

logger = structlog.get_logger()

router = APIRouter(prefix="/executions", tags=["executions"])


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

    # Create execution record (Story 4.1)
    result = await execution_repository.create_execution(
        user_id=user.id,
        action_id=payload.action_id,
        environment=payload.environment.value,
        parameters=payload.parameters,
    )

    execution_id = result.execution_id

    # Prepare execution steps (Story 4.3, Task 3.4)
    vault_service = get_vault_service()
    execution_service = ExecutionService(vault_service)
    await execution_service.prepare_execution(execution_id, correlation_id)

    # Trigger background execution (Story 4.3, Task 3.6)
    background_tasks.add_task(
        execution_service.start_execution,
        execution_id,
        correlation_id,
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

    if execution is None or execution.user_id != user.id:
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
    """GET /api/v1/executions - List user's executions (Story 4.1).

    Returns:
        { "data": list[ExecutionResponse] }
    """
    executions = await execution_repository.list_by_user(
        user_id=user.id,
        limit=min(limit, 100),  # Cap at 100
        offset=max(offset, 0),
    )

    return {"data": [e.model_dump(mode="json") for e in executions]}


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
    # Verify execution exists and belongs to user
    execution = await execution_repository.get_by_id(execution_id)

    if execution is None or execution.user_id != user.id:
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Execution introuvable",
            details={"execution_id": execution_id},
        )

    # Get steps
    steps = await execution_repository.get_steps_by_execution_id(execution_id)

    return {"data": [s.model_dump(mode="json") for s in steps]}
