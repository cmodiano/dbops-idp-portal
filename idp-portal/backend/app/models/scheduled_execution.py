"""Scheduled Execution models for Story 11.3 - API créer exécution planifiée one-time.

Defines Pydantic models for:
- ScheduledExecutionStatus: schedule lifecycle states
- ScheduledExecutionCreate: input model for creating scheduled executions
- ScheduledExecutionResponse: output model for scheduled execution records
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.execution import ExecutionEnvironment


class ScheduledExecutionStatus(str, Enum):
    """Scheduled execution lifecycle status (Story 11.3, AC1)."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ScheduledExecutionCreate(BaseModel):
    """Input model for creating a scheduled execution (Story 11.3, AC1).

    Attributes:
        action_id: ID of the action to schedule (must be published)
        environment: Target environment (dev, staging, prod)
        parameters: Parameters conforming to action's parameters_schema
        scheduled_at: Future date/time when execution should run (ISO 8601 format)
    """
    action_id: int = Field(
        ...,
        gt=0,
        description="ID of the action to schedule (must be published)",
        json_schema_extra={"example": 1}
    )
    environment: ExecutionEnvironment = Field(
        ...,
        description="Target environment (dev, staging, prod)",
        json_schema_extra={"example": "prod"}
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution parameters (validated against action's parameters_schema)",
        json_schema_extra={"example": {"db_name": "PRODDB", "version": "19.21"}}
    )
    scheduled_at: datetime = Field(
        ...,
        description="Future date/time for execution (ISO 8601 format, must be in the future)",
        json_schema_extra={"example": "2026-03-15T14:30:00Z"}
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters_is_dict(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters is a dict."""
        if not isinstance(v, dict):
            raise ValueError("parameters must be a JSON object")
        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at_is_datetime(cls, v: datetime) -> datetime:
        """Validate scheduled_at is a datetime with timezone.

        Note: Future validation is done in the service layer to allow proper error response.
        MEDIUM-3 FIX: Enforce timezone requirement at model level.
        """
        if not isinstance(v, datetime):
            raise ValueError("scheduled_at must be a valid datetime")

        # MEDIUM-3 FIX: Reject timezone-naive datetimes
        if v.tzinfo is None:
            raise ValueError(
                "scheduled_at must include timezone information. "
                "Use ISO 8601 format: '2026-03-15T14:30:00Z' or '2026-03-15T14:30:00+00:00'"
            )

        return v


class ScheduledExecutionResponse(BaseModel):
    """Output model for scheduled execution (Story 11.3, AC1, AC7).

    Attributes:
        scheduled_execution_id: ID of the scheduled execution
        action_id: ID of the action
        action_name: Name of the action (enriched from ACTIONS_CATALOG)
        action_description: Description of the action (optional, enriched)
        environment: Target environment
        status: Current schedule status
        scheduled_at: Date/time when execution is scheduled
        parameters: Submitted parameters
        created_at: When schedule was created
        correlation_id: Request correlation ID for tracing
    """
    scheduled_execution_id: int = Field(
        ...,
        description="Unique identifier for the scheduled execution",
        json_schema_extra={"example": 42}
    )
    action_id: int = Field(
        ...,
        description="ID of the action to be executed",
        json_schema_extra={"example": 1}
    )
    action_name: str = Field(
        ...,
        description="Name of the action (from ACTIONS_CATALOG)",
        json_schema_extra={"example": "Patching Oracle"}
    )
    action_description: str | None = Field(
        None,
        description="Description of the action",
        json_schema_extra={"example": "Applies security patches to Oracle database"}
    )
    environment: str = Field(
        ...,
        description="Target execution environment",
        json_schema_extra={"example": "prod"}
    )
    status: ScheduledExecutionStatus = Field(
        ...,
        description="Current schedule status (pending, executed, cancelled)",
        json_schema_extra={"example": "pending"}
    )
    scheduled_at: datetime = Field(
        ...,
        description="Date/time when execution is scheduled (ISO 8601)",
        json_schema_extra={"example": "2026-03-15T14:30:00Z"}
    )
    parameters: dict[str, Any] | None = Field(
        None,
        description="Execution parameters submitted with the request",
        json_schema_extra={"example": {"db_name": "PRODDB"}}
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the schedule was created (ISO 8601)",
        json_schema_extra={"example": "2026-02-02T10:00:00Z"}
    )
    correlation_id: str | None = Field(
        None,
        description="Unique correlation ID for request tracing",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )


class ScheduledExecutionCreateResult(BaseModel):
    """Internal result from repository create operation (Story 11.3, Task 2).

    Minimal info returned after INSERT.
    """
    id: int
    status: ScheduledExecutionStatus
    created_at: datetime


class ScheduledExecutionWithAction(BaseModel):
    """Scheduled execution with action metadata (Story 11.3, AC7).

    Used internally by repository for JOIN results.
    """
    id: int
    action_id: int
    action_name: str
    action_description: str | None
    user_id: int
    environment: str
    parameters: dict[str, Any] | None
    scheduled_at: datetime
    status: ScheduledExecutionStatus
    created_at: datetime
    updated_at: datetime | None = None


class ScheduledExecutionListItem(BaseModel):
    """List item for scheduled executions with user info (Story 11.6, AC3, AC10).

    Used for the admin list view with enriched action and user data.
    HIGH-1 FIX: Added correlation_id for AC10 (details modal requirement).
    HIGH-2 FIX: Added execution_id for AC10 (link to effective execution when status=executed).
    """
    scheduled_execution_id: int
    action_id: int
    action_name: str
    user_id: int
    user_name: str
    environment: str
    scheduled_at: datetime
    status: ScheduledExecutionStatus
    created_at: datetime
    parameters: dict[str, Any] | None = None
    correlation_id: str | None = None  # HIGH-1 FIX: AC10 requires correlation_id in details modal
    execution_id: int | None = None  # HIGH-2 FIX: AC10 requires link to effective execution if status=executed
