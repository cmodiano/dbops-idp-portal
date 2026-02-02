"""Scheduled Executions API (Story 11.3, 11.6, 11.7, 11.8 - API scheduled executions).

Provides endpoints for scheduling executions:
- POST /api/v1/scheduled-executions: Create a scheduled execution (one-time or recurring) (Story 11.3, 11.7, 11.8)
- GET /api/v1/scheduled-executions: List scheduled executions with filters (Story 11.6)
- PATCH /api/v1/scheduled-executions/{id}: Cancel a scheduled execution (Story 11.6)
- PATCH /api/v1/scheduled-executions/{id}/recurring-pattern: Toggle recurring pattern is_active (Story 11.7)
- GET /api/v1/scheduled-executions/validate-cron: Validate cron expression (Story 11.8)
- GET /api/v1/scheduled-executions/cron-next-executions: Preview next N cron executions (Story 11.8)
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
import uuid

from croniter import croniter
from fastapi import APIRouter, Depends, Query, Request, status
import jsonschema
import structlog

from app.api.deps import get_current_user
from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType
from app.repositories import scheduled_execution_repository
from app.core.exceptions import ForbiddenError, InvalidStateError, NotFoundError
from app.models.auth import UserProfile
from app.models.scheduled_execution import (
    ScheduledExecutionCreate,
    ScheduledExecutionStatus,
    RecurringPatternToggle,
)
from app.utils.recurrence import calculate_next_execution_date

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
    """POST /api/v1/scheduled-executions - Create a scheduled execution (Story 11.3, 11.7).

    Creates a scheduled execution for a future date/time (one-time) or recurring pattern.

    **Request Body:**
    - action_id (int): ID of the action to schedule (must be published)
    - environment (string): Target environment (dev, staging, prod)
    - parameters (object): Execution parameters (validated against action schema)
    - scheduled_at (datetime): Future date/time for one-time execution (mutually exclusive with recurring_pattern)
    - recurring_pattern (object): Recurring pattern config (Story 11.7, mutually exclusive with scheduled_at)
      - pattern_type: "daily" or "weekly"
      - pattern_config: {"hour": int, "minute": int} or {"day_of_week": int, "hour": int, "minute": int}

    **Validations:**
    - AC1: action_id exists and is published
    - AC2: scheduled_at is in the future and has timezone (if one-time)
    - AC3: User has RBAC permission for action × environment
    - AC4: parameters conform to action's parameters_schema
    - AC5: action exists and is published (404 if not)
    - AC6 (11.7): recurring_pattern.pattern_config is valid for pattern_type

    **Returns:**
    - 201 Created with scheduled execution details
    - 400 INVALID_SCHEDULED_DATE: if scheduled_at is in past or missing timezone
    - 400 INVALID_PARAMETERS: if parameters validation fails
    - 400 Pattern validation errors (Story 11.7, AC6)
    - 403 PERMISSION_DENIED: if user cannot schedule this action
    - 404 ACTION_NOT_FOUND: if action doesn't exist or not published

    **Response Example (recurring):**
    ```json
    {
      "data": {
        "scheduled_execution_id": 42,
        "action_id": 1,
        "action_name": "Patching Oracle",
        "environment": "prod",
        "status": "pending",
        "scheduled_at": null,
        "parameters": {"db_name": "PRODDB"},
        "created_at": "2026-02-02T10:00:00Z",
        "correlation_id": "uuid-here",
        "recurring_pattern": {
          "pattern_type": "daily",
          "pattern_config": {"hour": 2, "minute": 30},
          "next_execution_date": "2026-02-03T02:30:00Z",
          "is_active": true
        }
      }
    }
    ```
    """
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # HIGH-3 FIX: Ensure correlation_id cleanup in finally block
    try:
        # Story 11.7: Determine if one-time or recurring
        is_recurring = payload.recurring_pattern is not None

        logger.info(
            "scheduled_execution_create_started",
            action_id=payload.action_id,
            environment=payload.environment.value,
            user_id=user.id,
            scheduled_at=payload.scheduled_at.isoformat() if payload.scheduled_at else None,
            is_recurring=is_recurring,
            pattern_type=payload.recurring_pattern.pattern_type if is_recurring else None,
        )

        # Get client IP address (AC6 - for audit)
        client_ip = request.client.host if request.client else None
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        now = datetime.now(timezone.utc)

        # Validate scheduled_at for one-time executions
        if not is_recurring:
            # AC2: Validate that scheduled_at is in the future
            scheduled_at = payload.scheduled_at

            if scheduled_at <= now:
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

        # Story 11.7: Prepare recurring pattern data if applicable
        recurring_pattern_data = None
        if is_recurring:
            pattern = payload.recurring_pattern
            # Calculate next_execution_date
            next_execution_date = calculate_next_execution_date(
                pattern_type=pattern.pattern_type,
                pattern_config=pattern.pattern_config,
                reference_datetime=now,
            )

            recurring_pattern_data = {
                "pattern_type": pattern.pattern_type,
                "pattern_config": pattern.pattern_config,
                "next_execution_date": next_execution_date,
                "is_active": True,
            }

        # Create scheduled execution record
        result = await scheduled_execution_repository.create_scheduled_execution(
            user_id=user.id,
            action_id=payload.action_id,
            environment=payload.environment.value,
            parameters=payload.parameters,
            scheduled_at=payload.scheduled_at,  # NULL for recurring
            correlation_id=correlation_id,
            recurring_pattern=recurring_pattern_data,  # Story 11.7
        )

        scheduled_execution_id = result.id

        # Get enriched data with action metadata
        enriched = await scheduled_execution_repository.get_by_id(scheduled_execution_id)

        # Audit log entry
        audit_action_type = (
            AuditActionType.SCHEDULED_EXECUTION_RECURRING_CREATED
            if is_recurring
            else AuditActionType.SCHEDULED_EXECUTION_CREATED
        )

        await audit_repository.create_entry(
            user_id=str(user.id),
            action_type=audit_action_type,
            entity_type=AuditEntityType.SCHEDULED_EXECUTION,
            entity_id=scheduled_execution_id,
            details={
                "action_id": payload.action_id,
                "environment": payload.environment.value,
                "parameters": payload.parameters,
                "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
                "recurring_pattern": recurring_pattern_data if is_recurring else None,
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
            is_recurring=is_recurring,
        )

        # Build response
        response_data = {
            "scheduled_execution_id": scheduled_execution_id,
            "action_id": payload.action_id,
            "action_name": enriched.action_name if enriched else None,
            "environment": payload.environment.value,
            "status": result.status.value,
            "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
            "parameters": payload.parameters,
            "created_at": result.created_at.isoformat(),
            "correlation_id": correlation_id,
        }

        # Story 11.7: Include recurring_pattern in response
        if is_recurring:
            next_exec_iso = (
                recurring_pattern_data["next_execution_date"].isoformat()
                if recurring_pattern_data["next_execution_date"] is not None
                else None
            )
            response_data["recurring_pattern"] = {
                "pattern_type": recurring_pattern_data["pattern_type"],
                "pattern_config": recurring_pattern_data["pattern_config"],
                "next_execution_date": next_exec_iso,
                "is_active": recurring_pattern_data["is_active"],
            }

        return {"data": response_data}
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
                "scheduled_at": scheduled_execution.scheduled_at.isoformat() if scheduled_execution.scheduled_at else None,
                "created_at": scheduled_execution.created_at.isoformat(),
            }
        }
    finally:
        structlog.contextvars.clear_contextvars()


@router.patch("/{scheduled_execution_id}/recurring-pattern", response_model=None)
async def toggle_recurring_pattern(
    scheduled_execution_id: int,
    payload: RecurringPatternToggle,
    request: Request,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """PATCH /api/v1/scheduled-executions/{id}/recurring-pattern - Toggle recurring pattern (Story 11.7).

    Enables or disables a recurring pattern. When enabling, recalculates next_execution_date.

    **Request Body:**
    - is_active (bool): New active state for the recurring pattern

    **RBAC:**
    - DBA: can toggle their own scheduled executions
    - DBOPS: can toggle any scheduled execution

    **Validations:**
    - Scheduled execution must exist (404 if not)
    - Scheduled execution must have a recurring pattern (404 if one-time)
    - User must have permission (403 if DBA trying to toggle others')

    **Returns:**
    - 200 OK with updated recurring pattern info
    - 403 PERMISSION_DENIED: if DBA trying to toggle another user's pattern
    - 404 SCHEDULED_EXECUTION_NOT_FOUND: if scheduled execution not found
    - 404 RECURRING_PATTERN_NOT_FOUND: if scheduled execution is one-time (no recurring pattern)

    **Response Example:**
    ```json
    {
      "data": {
        "pattern_type": "daily",
        "pattern_config": {"hour": 2, "minute": 30},
        "next_execution_date": "2026-02-03T02:30:00Z",
        "is_active": false
      }
    }
    ```
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    try:
        logger.info(
            "toggle_recurring_pattern_requested",
            scheduled_execution_id=scheduled_execution_id,
            is_active=payload.is_active,
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

        # RBAC: DBA can only toggle their own, DBOPS can toggle any
        if not _is_dbops(user) and scheduled_execution.user_id != user.id:
            logger.warning(
                "toggle_permission_denied",
                scheduled_execution_id=scheduled_execution_id,
                owner_user_id=scheduled_execution.user_id,
                requester_user_id=user.id,
            )
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission de modifier cette récurrence",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        # Get existing recurring pattern
        existing_pattern = await scheduled_execution_repository.get_recurring_pattern(scheduled_execution_id)
        if existing_pattern is None:
            logger.warning(
                "recurring_pattern_not_found",
                scheduled_execution_id=scheduled_execution_id,
            )
            raise NotFoundError(
                code="RECURRING_PATTERN_NOT_FOUND",
                message="Cette exécution planifiée n'a pas de pattern de récurrence (exécution unique)",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        # Calculate new next_execution_date if enabling (AC10)
        new_next_execution_date = None
        if payload.is_active:
            new_next_execution_date = calculate_next_execution_date(
                pattern_type=existing_pattern.pattern_type,
                pattern_config=existing_pattern.pattern_config,
                reference_datetime=datetime.now(timezone.utc),
            )

        # Update recurring pattern
        updated_pattern = await scheduled_execution_repository.update_recurring_pattern_status(
            scheduled_execution_id=scheduled_execution_id,
            is_active=payload.is_active,
            new_next_execution_date=new_next_execution_date,
        )

        # Audit log
        audit_action_type = (
            AuditActionType.SCHEDULED_EXECUTION_RECURRING_ENABLED
            if payload.is_active
            else AuditActionType.SCHEDULED_EXECUTION_RECURRING_DISABLED
        )

        await audit_repository.create_entry(
            user_id=str(user.id),
            action_type=audit_action_type,
            entity_type=AuditEntityType.SCHEDULED_EXECUTION,
            entity_id=scheduled_execution_id,
            details={
                "pattern_type": existing_pattern.pattern_type,
                "pattern_config": existing_pattern.pattern_config,
                "is_active": payload.is_active,
                "next_execution_date": new_next_execution_date.isoformat() if new_next_execution_date else None,
            },
            ip_address=client_ip,
            correlation_id=correlation_id,
        )

        logger.info(
            "recurring_pattern_toggled",
            scheduled_execution_id=scheduled_execution_id,
            is_active=payload.is_active,
            user_id=user.id,
        )

        return {
            "data": {
                "pattern_type": updated_pattern.pattern_type,
                "pattern_config": updated_pattern.pattern_config,
                "next_execution_date": updated_pattern.next_execution_date.isoformat() if updated_pattern.next_execution_date else None,
                "is_active": updated_pattern.is_active,
            }
        }
    finally:
        structlog.contextvars.clear_contextvars()


@router.get("/validate-cron", response_model=None)
async def validate_cron_expression(
    expression: str = Query(..., description="Cron expression to validate"),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/scheduled-executions/validate-cron - Validate a cron expression (Story 11.8, AC2).

    Validates a cron expression syntactically and semantically using croniter.

    **Query Parameters:**
    - expression (str): Cron expression to validate (5 fields: minute hour day month day_of_week)

    **Returns:**
    - 200 OK: {"valid": true/false, "error": "error message if invalid"}

    **Examples:**
    - Valid: "0 2 * * 1-5" → {"valid": true, "error": ""}
    - Invalid: "99 99 * * *" → {"valid": false, "error": "Expression cron invalide..."}
    """
    logger.info(
        "validate_cron_requested",
        expression=expression,
        user_id=user.id,
    )

    try:
        # First check: syntax validation
        if not croniter.is_valid(expression):
            return {
                "valid": False,
                "error": "Expression cron invalide. Format attendu : minute hour day month day_of_week",
            }

        # Second check: semantic validation - try to get next execution
        reference = datetime.now(timezone.utc)
        cron = croniter(expression, reference)
        _ = cron.get_next(datetime)  # Test iteration works

        logger.info(
            "cron_validation_success",
            expression=expression,
            user_id=user.id,
        )

        return {"valid": True, "error": ""}

    except Exception as e:
        logger.warning(
            "cron_validation_failed",
            expression=expression,
            error=str(e),
            user_id=user.id,
        )
        return {
            "valid": False,
            "error": f"Expression cron invalide : {str(e)}",
        }


@router.get("/cron-next-executions", response_model=None)
async def get_cron_next_executions(
    expression: str = Query(..., description="Cron expression"),
    count: int = Query(5, ge=1, le=10, description="Number of next executions to return"),
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/scheduled-executions/cron-next-executions - Preview next N cron executions (Story 11.8, AC2).

    Calculates the next N execution dates for a given cron expression.

    **Query Parameters:**
    - expression (str): Cron expression (5 fields: minute hour day month day_of_week)
    - count (int): Number of next executions to return (1-10, default: 5)

    **Returns:**
    - 200 OK: {"executions": ["2026-02-03T02:00:00+00:00", ...]}

    **Raises:**
    - 400: If cron expression is invalid

    **Example:**
    - expression: "0 2 * * 1-5", count: 5
    - Returns next 5 weekday mornings at 2:00 AM UTC
    """
    logger.info(
        "cron_next_executions_requested",
        expression=expression,
        count=count,
        user_id=user.id,
    )

    # Validate expression first
    if not croniter.is_valid(expression):
        raise InvalidStateError(
            code="INVALID_CRON_EXPRESSION",
            message="Expression cron invalide. Format attendu : minute hour day month day_of_week",
            details={"expression": expression},
        )

    try:
        # Calculate next executions
        reference = datetime.now(timezone.utc)
        cron = croniter(expression, reference)

        executions = []
        for _ in range(count):
            next_exec = cron.get_next(datetime)
            # Ensure UTC timezone
            if next_exec.tzinfo is None:
                next_exec = next_exec.replace(tzinfo=timezone.utc)
            executions.append(next_exec.isoformat())

        logger.info(
            "cron_next_executions_calculated",
            expression=expression,
            count=len(executions),
            user_id=user.id,
        )

        return {"executions": executions}

    except Exception as e:
        logger.error(
            "cron_next_executions_error",
            expression=expression,
            error=str(e),
            user_id=user.id,
        )
        raise InvalidStateError(
            code="CRON_CALCULATION_ERROR",
            message=f"Erreur lors du calcul des prochaines exécutions : {str(e)}",
            details={"expression": expression},
        ) from e
