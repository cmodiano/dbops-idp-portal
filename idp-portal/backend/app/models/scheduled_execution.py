"""Scheduled Execution models for Story 11.3, 11.7, 11.8 - API scheduled executions.

Defines Pydantic models for:
- ScheduledExecutionStatus: schedule lifecycle states
- ScheduledExecutionCreate: input model for creating scheduled executions
- ScheduledExecutionResponse: output model for scheduled execution records
- RecurringPattern models: daily/weekly/cron recurrence support (Story 11.7, 11.8)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from croniter import croniter
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.execution import ExecutionEnvironment


# === Recurring Pattern Types (Story 11.7, 11.8) ===


class RecurringPatternType(str, Enum):
    """Pattern type for recurring executions (Story 11.7 AC1-AC3, Story 11.8 AC4)."""
    DAILY = "daily"
    WEEKLY = "weekly"
    CRON = "cron"  # Story 11.8: Advanced cron expressions


class DailyPatternConfig(BaseModel):
    """Configuration for daily recurring pattern (Story 11.7, AC2).

    Attributes:
        hour: Hour of day (0-23) when execution runs
        minute: Minute of hour (0-59) when execution runs
    """
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute of hour (0-59)")


class WeeklyPatternConfig(BaseModel):
    """Configuration for weekly recurring pattern (Story 11.7, AC3).

    Attributes:
        day_of_week: Day of week (1=Monday, 7=Sunday)
        hour: Hour of day (0-23) when execution runs
        minute: Minute of hour (0-59) when execution runs
    """
    day_of_week: int = Field(
        ..., ge=1, le=7,
        description="Day of week: 1=Monday, 2=Tuesday, ..., 7=Sunday"
    )
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute of hour (0-59)")


class CronPatternConfig(BaseModel):
    """Configuration for cron recurring pattern (Story 11.8, AC4, AC5).

    Supports standard 5-field cron expressions: minute hour day month day_of_week

    Attributes:
        cron_expression: Cron expression string (5 fields)
    """
    cron_expression: str = Field(
        ...,
        description="Cron expression (5 fields: minute hour day month day_of_week)",
        json_schema_extra={"example": "0 2 * * 1-5"},
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        """Validate cron expression format using croniter (Story 11.8, AC5)."""
        if not v or not v.strip():
            raise ValueError("Expression cron requise")

        v = v.strip()

        if not croniter.is_valid(v):
            raise ValueError(
                "Expression cron invalide. Format attendu : minute hour day month day_of_week"
            )

        return v


class RecurringPatternRequest(BaseModel):
    """Recurring pattern in creation request (Story 11.7 AC2-AC3, Story 11.8 AC4).

    Attributes:
        pattern_type: Type of recurrence ('daily', 'weekly', or 'cron')
        pattern_config: Configuration specific to the pattern type
    """
    pattern_type: Literal["daily", "weekly", "cron"] = Field(
        ..., description="Pattern type: 'daily', 'weekly', or 'cron'"
    )
    pattern_config: dict[str, Any] = Field(
        ..., description="Pattern configuration (hour, minute, day_of_week for weekly, cron_expression for cron)"
    )

    @field_validator("pattern_config")
    @classmethod
    def validate_pattern_config(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """Validate pattern_config has required fields for the pattern_type."""
        # Note: pattern_type validation happens in model_validator below
        return v

    @model_validator(mode="after")
    def validate_pattern_config_matches_type(self):
        """Validate pattern_config matches pattern_type (Story 11.7 AC6, Story 11.8 AC5)."""
        if self.pattern_type == "daily":
            # Validate DailyPatternConfig fields
            if "hour" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : hour et minute requis pour pattern daily"
                )
            if "minute" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : hour et minute requis pour pattern daily"
                )
            hour = self.pattern_config.get("hour")
            minute = self.pattern_config.get("minute")
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                raise ValueError(
                    "Valeur invalide pour hour : doit être entre 0 et 23"
                )
            if not isinstance(minute, int) or minute < 0 or minute > 59:
                raise ValueError(
                    "Valeur invalide pour minute : doit être entre 0 et 59"
                )
        elif self.pattern_type == "weekly":
            # Validate WeeklyPatternConfig fields
            if "day_of_week" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"
                )
            if "hour" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"
                )
            if "minute" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"
                )
            day_of_week = self.pattern_config.get("day_of_week")
            hour = self.pattern_config.get("hour")
            minute = self.pattern_config.get("minute")
            if not isinstance(day_of_week, int) or day_of_week < 1 or day_of_week > 7:
                raise ValueError(
                    "Valeur invalide pour day_of_week : doit être entre 1 (lundi) et 7 (dimanche)"
                )
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                raise ValueError(
                    "Valeur invalide pour hour : doit être entre 0 et 23"
                )
            if not isinstance(minute, int) or minute < 0 or minute > 59:
                raise ValueError(
                    "Valeur invalide pour minute : doit être entre 0 et 59"
                )
        elif self.pattern_type == "cron":
            # Validate CronPatternConfig fields (Story 11.8, AC5)
            if "cron_expression" not in self.pattern_config:
                raise ValueError(
                    "Pattern config incomplet : cron_expression requis pour pattern cron"
                )
            cron_expression = self.pattern_config.get("cron_expression")
            if not isinstance(cron_expression, str) or not cron_expression.strip():
                raise ValueError(
                    "Expression cron requise et doit être une chaîne non vide"
                )
            # Validate cron expression with croniter
            if not croniter.is_valid(cron_expression.strip()):
                raise ValueError(
                    f"Expression cron invalide : {cron_expression}. "
                    f"Format attendu : minute hour day month day_of_week"
                )
        return self


class RecurringPatternResponse(BaseModel):
    """Recurring pattern in API responses (Story 11.7, AC7, AC8).

    Attributes:
        pattern_type: Type of recurrence ('daily' or 'weekly')
        pattern_config: Configuration dict (hour, minute, day_of_week)
        next_execution_date: Next scheduled execution datetime
        is_active: Whether the recurrence is active
    """
    pattern_type: str = Field(..., description="Pattern type: 'daily' or 'weekly'")
    pattern_config: dict[str, Any] = Field(..., description="Pattern configuration")
    next_execution_date: datetime | None = Field(
        None, description="Next scheduled execution datetime (UTC)"
    )
    is_active: bool = Field(..., description="Whether the recurrence is active")


class RecurringPatternToggle(BaseModel):
    """Request to toggle is_active for a recurring pattern (Story 11.7, AC9, AC10).

    Attributes:
        is_active: New active state for the recurring pattern
    """
    is_active: bool = Field(..., description="New active state")


class ScheduledExecutionStatus(str, Enum):
    """Scheduled execution lifecycle status (Story 11.3, AC1)."""
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class ScheduledExecutionCreate(BaseModel):
    """Input model for creating a scheduled execution (Story 11.3, 11.7).

    Supports two modes:
    - One-time: scheduled_at is required, recurring_pattern is None
    - Recurring: recurring_pattern is required, scheduled_at is None

    Attributes:
        action_id: ID of the action to schedule (must be published)
        environment: Target environment (dev, staging, prod)
        parameters: Parameters conforming to action's parameters_schema
        scheduled_at: Future date/time for one-time execution (ISO 8601 format)
        recurring_pattern: Pattern for recurring execution (Story 11.7)
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
    scheduled_at: datetime | None = Field(
        None,
        description="Future date/time for one-time execution (ISO 8601 format, mutually exclusive with recurring_pattern)",
        json_schema_extra={"example": "2026-03-15T14:30:00Z"}
    )
    recurring_pattern: RecurringPatternRequest | None = Field(
        None,
        description="Recurring pattern configuration (Story 11.7, mutually exclusive with scheduled_at)"
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
    def validate_scheduled_at_is_datetime(cls, v: datetime | None) -> datetime | None:
        """Validate scheduled_at is a datetime with timezone if provided.

        Note: Future validation is done in the service layer to allow proper error response.
        MEDIUM-3 FIX: Enforce timezone requirement at model level.
        """
        if v is None:
            return v

        if not isinstance(v, datetime):
            raise ValueError("scheduled_at must be a valid datetime")

        # MEDIUM-3 FIX: Reject timezone-naive datetimes
        if v.tzinfo is None:
            raise ValueError(
                "scheduled_at must include timezone information. "
                "Use ISO 8601 format: '2026-03-15T14:30:00Z' or '2026-03-15T14:30:00+00:00'"
            )

        return v

    @model_validator(mode="after")
    def validate_scheduling_type(self):
        """Ensure either scheduled_at OR recurring_pattern is provided, not both (Story 11.7)."""
        if self.scheduled_at is not None and self.recurring_pattern is not None:
            raise ValueError(
                "Impossible de spécifier à la fois scheduled_at et recurring_pattern"
            )
        if self.scheduled_at is None and self.recurring_pattern is None:
            raise ValueError(
                "Doit spécifier soit scheduled_at (one-time) soit recurring_pattern (récurrent)"
            )
        return self


class ScheduledExecutionResponse(BaseModel):
    """Output model for scheduled execution (Story 11.3, 11.7).

    Attributes:
        scheduled_execution_id: ID of the scheduled execution
        action_id: ID of the action
        action_name: Name of the action (enriched from ACTIONS_CATALOG)
        action_description: Description of the action (optional, enriched)
        environment: Target environment
        status: Current schedule status
        scheduled_at: Date/time when execution is scheduled (NULL for recurring)
        parameters: Submitted parameters
        created_at: When schedule was created
        correlation_id: Request correlation ID for tracing
        recurring_pattern: Recurring pattern info if applicable (Story 11.7)
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
    scheduled_at: datetime | None = Field(
        None,
        description="Date/time when execution is scheduled (ISO 8601, NULL for recurring)",
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
    recurring_pattern: RecurringPatternResponse | None = Field(
        None,
        description="Recurring pattern info for recurring executions (Story 11.7)"
    )


class ScheduledExecutionCreateResult(BaseModel):
    """Internal result from repository create operation (Story 11.3, Task 2).

    Minimal info returned after INSERT.
    """
    id: int
    status: ScheduledExecutionStatus
    created_at: datetime


class ScheduledExecutionWithAction(BaseModel):
    """Scheduled execution with action metadata (Story 11.3, AC7, Story 11.7).

    Used internally by repository for JOIN results.
    Story 11.7: scheduled_at is optional for recurring executions.
    """
    id: int
    action_id: int
    action_name: str
    action_description: str | None
    user_id: int
    environment: str
    parameters: dict[str, Any] | None
    scheduled_at: datetime | None = None  # Story 11.7: NULL for recurring executions
    status: ScheduledExecutionStatus
    created_at: datetime
    updated_at: datetime | None = None
    recurring_pattern: RecurringPatternResponse | None = None  # Story 11.7: Recurring pattern info


class ScheduledExecutionListItem(BaseModel):
    """List item for scheduled executions with user info (Story 11.6, 11.7).

    Used for the admin list view with enriched action and user data.
    HIGH-1 FIX: Added correlation_id for AC10 (details modal requirement).
    HIGH-2 FIX: Added execution_id for AC10 (link to effective execution when status=executed).
    Story 11.7: Added recurring_pattern for recurring executions.
    """
    scheduled_execution_id: int
    action_id: int
    action_name: str
    user_id: int
    user_name: str
    environment: str
    scheduled_at: datetime | None  # Story 11.7: NULL for recurring executions
    status: ScheduledExecutionStatus
    created_at: datetime
    parameters: dict[str, Any] | None = None
    correlation_id: str | None = None  # HIGH-1 FIX: AC10 requires correlation_id in details modal
    execution_id: int | None = None  # HIGH-2 FIX: AC10 requires link to effective execution if status=executed
    recurring_pattern: RecurringPatternResponse | None = None  # Story 11.7: Recurring pattern info


# === Story 11.10: External Scheduler API Models ===


class ScheduledExecutionPendingItem(BaseModel):
    """Pending execution item for external scheduler API (Story 11.10, AC1).

    Enriched with action and user info via JOINs.
    Used by GET /api/v1/scheduled-executions/pending endpoint.

    Attributes:
        scheduled_execution_id: ID of the scheduled execution
        action_id: ID of the action to execute
        action_name: Name of the action (from ACTIONS_CATALOG JOIN)
        user_id: ID of the user who created the schedule
        user_name: Username (from USERS JOIN)
        environment: Target environment (dev, staging, prod)
        parameters: Execution parameters (CLOB JSON)
        scheduled_at: Date/time for one-time execution (NULL for recurring)
        recurring_pattern: Pattern info for recurring executions
        correlation_id: Correlation ID for tracing
        created_at: When schedule was created
    """
    scheduled_execution_id: int = Field(..., description="ID de l'exécution planifiée")
    action_id: int = Field(..., description="ID de l'action à exécuter")
    action_name: str = Field(..., description="Nom de l'action")
    user_id: int = Field(..., description="ID de l'utilisateur ayant créé l'exécution")
    user_name: str = Field(..., description="Nom d'utilisateur")
    environment: str = Field(..., description="Environnement (dev, staging, prod)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Paramètres de l'action")
    scheduled_at: datetime | None = Field(None, description="Date/heure planifiée (NULL pour recurring)")
    recurring_pattern: RecurringPatternResponse | None = Field(None, description="Pattern de récurrence si applicable")
    correlation_id: str = Field(..., description="Correlation ID pour tracing")
    created_at: datetime = Field(..., description="Date de création")


class ScheduledExecutionUpdateRequest(BaseModel):
    """Request to update scheduled execution status (Story 11.10, AC4).

    Used by PATCH /api/v1/scheduled-executions/{id} to mark as executed.

    Attributes:
        status: New status ("cancelled" or "executed")
        execution_id: ID of the created execution (required when status="executed")
    """
    status: Literal["cancelled", "executed"] = Field(
        ..., description="Nouveau statut"
    )
    execution_id: int | None = Field(
        None, description="ID de l'exécution créée (requis si status=executed)"
    )

    @model_validator(mode="after")
    def validate_execution_id_required_for_executed(self):
        """Validate execution_id is present when status=executed (Story 11.10, AC6)."""
        if self.status == "executed" and self.execution_id is None:
            raise ValueError(
                "execution_id est requis lors de la transition vers status 'executed'"
            )
        return self
