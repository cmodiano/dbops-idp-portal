"""Scheduled Executions API (Story 11.3, 11.6 - API scheduled executions).

Provides endpoints for scheduling executions:
- POST /api/v1/scheduled-executions: Create a one-time scheduled execution (Story 11.3)
- GET /api/v1/scheduled-executions: List scheduled executions with filters (Story 11.6)
- PATCH /api/v1/scheduled-executions/{id}: Cancel a scheduled execution (Story 11.6)
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
import jsonschema
import structlog

from app.api.deps import get_current_user
from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType
from app.repositories import scheduled_execution_repository
from app.core.exceptions import ForbiddenError, InvalidStateError, NotFoundError
from app.models.auth import UserProfile
from app.models.scheduled_execution import ScheduledExecutionCreate, ScheduledExecutionStatus

from app.services import rbac_service

logger = structlog.get_logger()

router = APIRouter(prefix="/scheduled-executions", tags=["scheduled-executions"])

# Profiles that can view all scheduled executions (DBOPS)
_DBOPS_PROFILES = frozenset({"dbops"})


def _is_dbops(user: UserProfile) -> bool:
    """Check if user has DBOPS profile (can see all scheduled executions)."""
    return (user.profile or "").lower() in _DBOPS_PROFILES


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
        # HIGH-1 FIX: Pass correlation_id for AC10 tracing
        result = await scheduled_execution_repository.create_scheduled_execution(
            user_id=user.id,
            action_id=payload.action_id,
            environment=payload.environment.value,
            parameters=payload.parameters,
            scheduled_at=payload.scheduled_at,
            correlation_id=correlation_id,  # HIGH-1 FIX
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


@router.get("", response_model=None)
async def list_scheduled_executions(
    user: UserProfile = Depends(get_current_user),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: pending, executed, cancelled"),
    action_id: int | None = Query(None, description="Filter by action ID"),
    scheduled_from: datetime | None = Query(None, description="Filter scheduled_at >= this datetime"),
    scheduled_to: datetime | None = Query(None, description="Filter scheduled_at <= this datetime"),
    limit: int = Query(50, ge=1, le=100, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
) -> dict:
    """GET /api/v1/scheduled-executions - List scheduled executions (Story 11.6, AC1-AC3, AC7-AC9).

    RBAC:
    - DBA: sees only their own scheduled executions
    - DBOPS: sees all scheduled executions

    Filters:
    - status: Filter by status (pending, executed, cancelled)
    - action_id: Filter by action ID
    - scheduled_from: Filter by minimum scheduled_at date
    - scheduled_to: Filter by maximum scheduled_at date

    Returns:
        { "data": [ScheduledExecutionListItem], "pagination": {...} }
    """
    logger.info(
        "list_scheduled_executions_requested",
        user_id=user.id,
        user_profile=user.profile,
        status_filter=status_filter,
        action_id=action_id,
        scheduled_from=scheduled_from.isoformat() if scheduled_from else None,
        scheduled_to=scheduled_to.isoformat() if scheduled_to else None,
    )

    # AC2: RBAC - DBOPS sees all, DBA sees only their own
    if _is_dbops(user):
        user_id_filter = None  # DBOPS sees all
    else:
        user_id_filter = user.id  # DBA sees only own

    # Validate status if provided
    if status_filter is not None:
        valid_statuses = [s.value for s in ScheduledExecutionStatus]
        if status_filter not in valid_statuses:
            raise InvalidStateError(
                code="INVALID_STATUS",
                message=f"Statut invalide: {status_filter}. Valeurs valides: {', '.join(valid_statuses)}",
                details={"status": status_filter, "valid_statuses": valid_statuses},
            )

    # Get total count for pagination
    total_count = await scheduled_execution_repository.count_scheduled_executions(
        user_id=user_id_filter,
        status=status_filter,
        action_id=action_id,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
    )

    # Get scheduled executions
    scheduled_executions = await scheduled_execution_repository.list_scheduled_executions(
        user_id=user_id_filter,
        status=status_filter,
        action_id=action_id,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        limit=limit,
        offset=offset,
    )

    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    logger.info(
        "list_scheduled_executions_returned",
        user_id=user.id,
        result_count=len(scheduled_executions),
        total_count=total_count,
    )

    return {
        "data": [se.model_dump(mode="json") for se in scheduled_executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }


@router.patch("/{scheduled_execution_id}", response_model=None)
async def cancel_scheduled_execution(
    scheduled_execution_id: int,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """PATCH /api/v1/scheduled-executions/{id} - Cancel a scheduled execution (Story 11.6, AC5, AC6).

    Cancels a pending scheduled execution. Only pending executions can be cancelled.

    RBAC:
    - DBA: can cancel their own scheduled executions
    - DBOPS: can cancel any scheduled execution

    Validations:
    - Scheduled execution must exist (404 if not)
    - Status must be "pending" (400 if already executed/cancelled)
    - User must have permission (403 if DBA trying to cancel others')

    Returns:
        { "data": { scheduled_execution_id, status: "cancelled", ... } }

    Raises:
        400: If status is not "pending"
        403: If DBA trying to cancel another user's scheduled execution
        404: If scheduled execution not found
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    try:
        logger.info(
            "cancel_scheduled_execution_requested",
            scheduled_execution_id=scheduled_execution_id,
            user_id=user.id,
            user_profile=user.profile,
        )

        # Get client IP for audit
        client_ip = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Fetch scheduled execution
        scheduled_execution = await scheduled_execution_repository.get_by_id(scheduled_execution_id)

        if scheduled_execution is None:
            logger.warning(
                "scheduled_execution_not_found",
                scheduled_execution_id=scheduled_execution_id,
            )
            raise NotFoundError(
                code="SCHEDULED_EXECUTION_NOT_FOUND",
                message="Exécution planifiée introuvable",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        # RBAC: DBA can only cancel their own, DBOPS can cancel any
        if not _is_dbops(user) and scheduled_execution.user_id != user.id:
            logger.warning(
                "cancel_permission_denied",
                scheduled_execution_id=scheduled_execution_id,
                owner_user_id=scheduled_execution.user_id,
                requester_user_id=user.id,
            )
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission d'annuler cette exécution planifiée",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        # Validate status is "pending"
        if scheduled_execution.status != ScheduledExecutionStatus.PENDING:
            logger.warning(
                "cancel_invalid_status",
                scheduled_execution_id=scheduled_execution_id,
                current_status=scheduled_execution.status.value,
            )
            raise InvalidStateError(
                code="INVALID_STATUS",
                message=f"Impossible d'annuler une exécution planifiée avec le statut '{scheduled_execution.status.value}'. "
                        f"Seules les exécutions avec le statut 'pending' peuvent être annulées.",
                details={
                    "scheduled_execution_id": scheduled_execution_id,
                    "current_status": scheduled_execution.status.value,
                },
            )

        # Update status to cancelled
        updated = await scheduled_execution_repository.update_status(
            scheduled_execution_id, ScheduledExecutionStatus.CANCELLED.value
        )

        if not updated:
            raise InvalidStateError(
                code="UPDATE_FAILED",
                message="La mise à jour a échoué (l'exécution planifiée peut avoir été modifiée)",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        # Audit log: SCHEDULED_EXECUTION_CANCELLED
        await audit_repository.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.SCHEDULED_EXECUTION_CANCELLED,
            entity_type=AuditEntityType.SCHEDULED_EXECUTION,
            entity_id=scheduled_execution_id,
            details={
                "action_id": scheduled_execution.action_id,
                "action_name": scheduled_execution.action_name,
                "scheduled_at": scheduled_execution.scheduled_at.isoformat(),
                "owner_user_id": scheduled_execution.user_id,
                "canceller_profile": user.profile,
            },
            ip_address=client_ip,
            correlation_id=correlation_id,
        )

        logger.info(
            "scheduled_execution_cancelled",
            scheduled_execution_id=scheduled_execution_id,
            user_id=user.id,
        )

        return {
            "data": {
                "scheduled_execution_id": scheduled_execution_id,
                "action_id": scheduled_execution.action_id,
                "action_name": scheduled_execution.action_name,
                "environment": scheduled_execution.environment,
                "status": ScheduledExecutionStatus.CANCELLED.value,
                "scheduled_at": scheduled_execution.scheduled_at.isoformat(),
                "created_at": scheduled_execution.created_at.isoformat(),
            }
        }
    finally:
        structlog.contextvars.clear_contextvars()
