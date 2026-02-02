"""Scheduled Executions API (Story 11.3 - API créer exécution planifiée one-time).

Provides endpoints for scheduling executions:
- POST /api/v1/scheduled-executions: Create a one-time scheduled execution
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Request, status
import jsonschema
import structlog

from app.api.deps import get_current_user
from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType
from app.repositories import scheduled_execution_repository
from app.core.exceptions import ForbiddenError, InvalidStateError, NotFoundError
from app.models.auth import UserProfile
from app.models.scheduled_execution import ScheduledExecutionCreate

from app.services import rbac_service

logger = structlog.get_logger()

router = APIRouter(prefix="/scheduled-executions", tags=["scheduled-executions"])


def _validate_parameters_against_schema(
    parameters: dict[str, Any] | None,
    schema: dict[str, Any] | None,
) -> None:
    """Validate parameters against JSON Schema (Story 11.3, AC4).

    Args:
        parameters: User-provided parameters
        schema: Action's parameters_schema

    Raises:
        InvalidStateError: If validation fails with field details

    Fixes:
        - HIGH-1: Deep copy schema to avoid mutation
        - MEDIUM-1: Recursive validation of nested objects
    """
    if schema is None:
        # No schema = no validation required
        return

    if parameters is None:
        parameters = {}

    # HIGH-1 FIX: Deep copy to avoid mutating original schema
    validation_schema = copy.deepcopy(schema)

    # MEDIUM-1 FIX: Recursively apply additionalProperties: false to all nested objects
    def _secure_schema_recursive(schema_obj: dict[str, Any]) -> None:
        """Recursively add additionalProperties: false to all object schemas."""
        if isinstance(schema_obj, dict):
            if schema_obj.get("type") == "object" and "additionalProperties" not in schema_obj:
                schema_obj["additionalProperties"] = False

            # Recurse into properties
            if "properties" in schema_obj and isinstance(schema_obj["properties"], dict):
                for prop_schema in schema_obj["properties"].values():
                    _secure_schema_recursive(prop_schema)

            # Recurse into items (for arrays)
            if "items" in schema_obj:
                _secure_schema_recursive(schema_obj["items"])

            # Recurse into allOf, anyOf, oneOf
            for key in ["allOf", "anyOf", "oneOf"]:
                if key in schema_obj and isinstance(schema_obj[key], list):
                    for subschema in schema_obj[key]:
                        _secure_schema_recursive(subschema)

    # Apply security to root and all nested levels
    if "additionalProperties" not in validation_schema:
        validation_schema["additionalProperties"] = False
    _secure_schema_recursive(validation_schema)

    try:
        jsonschema.validate(instance=parameters, schema=validation_schema)
    except jsonschema.ValidationError as e:
        # Extract field path for error details
        field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"

        # LOW-2 FIX: Log validation failure
        logger.warning(
            "parameter_validation_failed",
            field=field_path,
            error=e.message,
            parameters=parameters,
        )

        raise InvalidStateError(
            code="INVALID_PARAMETERS",
            message=f"Paramètre invalide: {e.message}",
            details={
                "field": field_path,
                "error": e.message,
                "schema_path": list(e.schema_path),
            },
        ) from e
    except jsonschema.SchemaError as e:
        # Schema itself is invalid
        logger.error(
            "invalid_action_schema",
            error=str(e),
            schema=schema,
        )
        raise InvalidStateError(
            code="INVALID_SCHEMA",
            message="Le schéma de paramètres de l'action est invalide",
            details={"error": str(e)},
        ) from e


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_scheduled_execution(
    payload: ScheduledExecutionCreate,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """POST /api/v1/scheduled-executions - Create a one-time scheduled execution (Story 11.3).

    Creates a scheduled execution for a future date/time.

    **Request Body:**
    - action_id (int): ID of the action to schedule (must be published)
    - environment (string): Target environment (dev, staging, prod)
    - parameters (object): Execution parameters (validated against action schema)
    - scheduled_at (datetime): Future date/time when execution should run (ISO 8601 with timezone)

    **Validations:**
    - AC1: action_id exists and is published
    - AC2: scheduled_at is in the future and has timezone
    - AC3: User has RBAC permission for action × environment
    - AC4: parameters conform to action's parameters_schema
    - AC5: action exists and is published (404 if not)

    **Returns:**
    - 201 Created with scheduled execution details (AC1)
    - 400 INVALID_SCHEDULED_DATE: if scheduled_at is in past or missing timezone (AC2)
    - 400 INVALID_PARAMETERS: if parameters validation fails (AC4)
    - 403 PERMISSION_DENIED: if user cannot schedule this action (AC3)
    - 404 ACTION_NOT_FOUND: if action doesn't exist or not published (AC5)

    **Security Notes:**
    - MEDIUM-2 TODO: Rate limiting should be added in future to prevent abuse
      (currently no limit on number of scheduled executions per user)

    **Response Example:**
    ```json
    {
      "data": {
        "scheduled_execution_id": 42,
        "action_id": 1,
        "action_name": "Patching Oracle",
        "environment": "prod",
        "status": "pending",
        "scheduled_at": "2026-03-15T14:30:00Z",
        "parameters": {"db_name": "PRODDB"},
        "created_at": "2026-02-02T10:00:00Z",
        "correlation_id": "uuid-here"
      }
    }
    ```
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # HIGH-3 FIX: Ensure correlation_id cleanup in finally block
    try:
        logger.info(
            "scheduled_execution_create_started",
            action_id=payload.action_id,
            environment=payload.environment.value,
            user_id=user.id,
            scheduled_at=payload.scheduled_at.isoformat(),
        )

        # Get client IP address (AC6 - for audit)
        client_ip = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # AC2: Validate that scheduled_at is in the future
        now = datetime.now(timezone.utc)

        # MEDIUM-3 FIX: Timezone validation now enforced at Pydantic model level
        # scheduled_at is guaranteed to have timezone here
        scheduled_at = payload.scheduled_at

        if scheduled_at <= now:
            # LOW-2 FIX: Log validation failure
            logger.warning(
                "scheduled_at_in_past",
                scheduled_at=payload.scheduled_at.isoformat(),
                current_time=now.isoformat(),
                user_id=user.id,
            )
            raise InvalidStateError(
                code="INVALID_SCHEDULED_DATE",
                message="La date planifiée doit être dans le futur",
                details={
                    "scheduled_at": payload.scheduled_at.isoformat(),
                    "current_time": now.isoformat(),
                },
            )

        # AC5: Check action exists and is published
        action_exists = await scheduled_execution_repository.action_exists(payload.action_id)
        if not action_exists:
            # LOW-2 FIX: Log validation failure
            logger.warning(
                "action_not_found",
                action_id=payload.action_id,
                user_id=user.id,
            )
            raise NotFoundError(
                code="ACTION_NOT_FOUND",
                message="Action introuvable ou non publiée",
                details={"action_id": payload.action_id},
            )

        # AC3: RBAC - Check user has permission to execute this action in this environment
        has_permission = await rbac_service.can_execute(
            user_id=user.id,
            action_id=payload.action_id,
            environment=payload.environment.value,
        )
        if not has_permission:
            # LOW-2 FIX: Log permission denial
            logger.warning(
                "permission_denied",
                action_id=payload.action_id,
                environment=payload.environment.value,
                user_id=user.id,
                profile=user.profile,
            )
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission de planifier cette action dans cet environnement",
                details={
                    "action_id": payload.action_id,
                    "environment": payload.environment.value,
                },
            )

        # AC4: Validate parameters against action's schema
        schema = await scheduled_execution_repository.get_action_parameters_schema(payload.action_id)
        _validate_parameters_against_schema(payload.parameters, schema)

        # AC1: Create scheduled execution record
        result = await scheduled_execution_repository.create_scheduled_execution(
            user_id=user.id,
            action_id=payload.action_id,
            environment=payload.environment.value,
            parameters=payload.parameters,
            scheduled_at=payload.scheduled_at,
        )

        scheduled_execution_id = result.id

        # AC7: Get enriched data with action metadata
        enriched = await scheduled_execution_repository.get_by_id(scheduled_execution_id)

        # AC6: Create audit log entry
        await audit_repository.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.SCHEDULED_EXECUTION_CREATED,
            entity_type=AuditEntityType.SCHEDULED_EXECUTION,
            entity_id=scheduled_execution_id,
            details={
                "action_id": payload.action_id,
                "environment": payload.environment.value,
                "parameters": payload.parameters,
                "scheduled_at": payload.scheduled_at.isoformat(),
                "rbac_context": {"user_id": user.id, "profile": user.profile},
            },
            ip_address=client_ip,
            correlation_id=correlation_id,
        )

        logger.info(
            "scheduled_execution_created",
            scheduled_execution_id=scheduled_execution_id,
            status="pending",
            action_id=payload.action_id,
            environment=payload.environment.value,
        )

        # Return response wrapped in "data" as per API convention
        return {
            "data": {
                "scheduled_execution_id": scheduled_execution_id,
                "action_id": payload.action_id,
                "action_name": enriched.action_name if enriched else None,
                "environment": payload.environment.value,
                "status": result.status.value,
                "scheduled_at": payload.scheduled_at.isoformat(),
                "parameters": payload.parameters,
                "created_at": result.created_at.isoformat(),
                "correlation_id": correlation_id,
            }
        }
    finally:
        # HIGH-3 FIX: Clean up correlation_id from context vars
        structlog.contextvars.clear_contextvars()
