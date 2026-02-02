"""Execution models for Story 4.1 - Wizard d'execution en 3 etapes.

Defines Pydantic models for:
- ExecutionStatus: execution lifecycle states
- ExecutionCreate: input model for creating executions
- ExecutionResponse: output model for execution records
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, computed_field


class ExecutionStatus(str, Enum):
    """Execution lifecycle status (Story 4.1, Task 1.3; Story 7.4 AC4: REJECTED)."""
    SUBMITTED = "SUBMITTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class StepStatus(str, Enum):
    """Execution step status (Story 4.3, Task 2.1)."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class StepType(str, Enum):
    """Execution step type (Story 4.3, Task 2.1)."""
    VAULT = "vault"
    SERVICENOW = "servicenow"
    PLATFORM = "platform"
    PREREQUISITE = "prerequisite"
    VERIFICATION = "verification"


class ExecutionEnvironment(str, Enum):
    """Valid execution environments (Story 4.1, AC2)."""
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class ExecutionCreate(BaseModel):
    """Input model for creating an execution (Story 4.1, Task 1.1; Story 9.2 remediation).

    Attributes:
        action_id: ID of the action to execute
        environment: Target environment (dev, staging, prod)
        parameters: Parameters conforming to action's parameters_schema
        parent_execution_id: Optional parent execution ID for remediation (Story 9.2)
    """
    action_id: int = Field(..., gt=0, description="ID of the action to execute")
    environment: ExecutionEnvironment = Field(..., description="Target environment")
    parameters: dict[str, Any] | None = Field(default=None, description="Execution parameters")
    parent_execution_id: int | None = Field(default=None, gt=0, description="Parent execution ID for remediation")

    @field_validator("parameters")
    @classmethod
    def validate_parameters_is_dict(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate parameters is a dict if provided."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("parameters must be a JSON object")
        return v


class ExecutionResponse(BaseModel):
    """Output model for execution (Story 4.1, Task 1.1; Story 7.4 approval fields; Story 9.2 remediation).

    Attributes:
        id: Execution ID
        action_id: ID of the action
        action_name: Name of the action (for display)
        user_id: ID of the user who initiated
        environment: Target environment
        parameters: Submitted parameters
        status: Current execution status
        servicenow_change_id: ServiceNow change ID if applicable
        started_at: When execution started running
        completed_at: When execution completed
        created_at: When execution was submitted
        approved_by: ID of DBA who approved/rejected (Story 7.4)
        approved_at: Timestamp of approval/rejection (Story 7.4)
        approval_comment: Comment from approver (Story 7.4)
        rejection_reason: Alias for approval_comment when REJECTED (Story 7.4)
        parent_execution_id: ID of parent execution if this is a remediation (Story 9.2)
    """
    id: int
    action_id: int
    action_name: str | None = None
    user_id: int
    user_display_name: str | None = None  # Story 7.4: for pending approvals list
    environment: ExecutionEnvironment
    parameters: dict[str, Any] | None = None
    status: ExecutionStatus
    servicenow_change_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    # Story 7.4: Approval workflow fields
    approved_by: int | None = None
    approved_at: datetime | None = None
    approval_comment: str | None = None
    # Story 9.2: Remediation linking
    parent_execution_id: int | None = None

    # Story 9-2 code-review fix: Use computed_field for proper serialization
    @computed_field
    @property
    def rejection_reason(self) -> str | None:
        """Alias for approval_comment when status is REJECTED."""
        if self.status == ExecutionStatus.REJECTED:
            return self.approval_comment
        return None


class ExecutionCreateResponse(BaseModel):
    """Response model for POST /executions (Story 4.1, Task 1.1).

    Returns minimal info after submission:
        execution_id: Created execution ID
        status: Initial status (SUBMITTED)
        correlation_id: Request correlation ID for tracing (optional, set by endpoint)
        created_at: Submission timestamp
    """
    execution_id: int
    status: ExecutionStatus
    correlation_id: str | None = None
    created_at: datetime


class ExecutionStepResponse(BaseModel):
    """Output model for execution step (Story 4.3, Task 2.1).

    Attributes:
        id: Step ID
        execution_id: Parent execution ID
        step_order: Order in execution sequence (1-based)
        step_name: Display name of the step
        step_type: Type of step (vault, servicenow, platform, etc.)
        status: Current step status
        started_at: When step started running
        completed_at: When step completed
        output: JSON output from step execution
        platform_job_id: External job ID from platform
        error_message: Error details if step failed
    """
    id: int
    execution_id: int
    step_order: int
    step_name: str
    step_type: StepType
    status: StepStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict[str, Any] | None = None
    platform_job_id: str | None = None
    error_message: str | None = None


class StepLogsResponse(BaseModel):
    """Response model for GET /executions/{id}/steps/{step_id}/logs (Story 4.7, AC6).

    Returns step logs: output, error_message, timestamps.
    """
    step_id: int
    output: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionStepCreate(BaseModel):
    """Input model for creating execution steps (Story 4.3, Task 2.2).

    Used internally when creating steps from action's execution_steps definition.
    """
    step_order: int = Field(..., ge=1, description="Order in execution sequence")
    step_name: str = Field(..., min_length=1, max_length=255, description="Display name")
    step_type: StepType = Field(..., description="Type of step")


class ActionStatsResponse(BaseModel):
    """Response model for GET /catalog/actions/{id}/stats (Story 8.1, AC1, AC4).

    Aggregated performance metrics for a specific action over the last 30 days.

    Attributes:
        success_rate: Percentage of successful executions (COMPLETED / (COMPLETED + FAILED) * 100).
                      None if no finished executions.
        avg_execution_time_ms: Average execution time in milliseconds for COMPLETED executions.
                               None if no completed executions.
        total_executions: Total number of executions in the period.
        incidents_count: Number of FAILED executions (incidents).
    """
    success_rate: float | None = Field(None, ge=0, le=100, description="Success rate percentage")
    avg_execution_time_ms: int | None = Field(None, ge=0, description="Average execution time in ms")
    total_executions: int = Field(..., ge=0, description="Total executions count")
    incidents_count: int = Field(..., ge=0, description="Number of failed executions")


# --- Story 9.2: Remediation Context Models ---


class RemediationAction(BaseModel):
    """Single remediation action details (Story 9.2, AC3).

    Attributes:
        execution_id: ID of the remediation execution
        action_name: Name of the action executed
        status: Current status of the remediation
        created_at: When the remediation was triggered
        completed_at: When the remediation completed (if finished)
    """
    execution_id: int = Field(..., description="Remediation execution ID")
    action_name: str = Field(..., description="Name of the action executed")
    status: ExecutionStatus = Field(..., description="Status of the remediation")
    created_at: datetime = Field(..., description="When remediation was triggered")
    completed_at: datetime | None = Field(None, description="When remediation completed")


class RemediationContext(BaseModel):
    """Remediation context for a failed execution (Story 9.2, AC3).

    Provides information about remediation attempts for a failed execution.

    Attributes:
        has_remediation: True if at least one remediation attempt exists
        successful_remediation: True if at least one remediation succeeded
        remediation_actions: List of all remediation attempts
    """
    has_remediation: bool = Field(..., description="Whether remediation attempts exist")
    successful_remediation: bool = Field(..., description="Whether any remediation succeeded")
    remediation_actions: list[RemediationAction] = Field(
        default_factory=list, description="List of remediation attempts"
    )


# --- Story 8.2: Admin Analytics Models ---


class EngineExecutions(BaseModel):
    """Executions count per engine (Story 8.2, AC1, Task 1.2)."""
    engine: str = Field(..., description="Engine name (Oracle, SQL Server, DB2)")
    count: int = Field(..., ge=0, description="Number of executions")


class ProfileExecutions(BaseModel):
    """Executions count per user profile (Story 8.2, AC1, Task 1.3)."""
    profile: str = Field(..., description="Profile name")
    count: int = Field(..., ge=0, description="Number of executions")


class WeeklyTrendPoint(BaseModel):
    """Weekly adoption trend point (Story 8.2, AC2, Task 1.4)."""
    week_start: str = Field(..., description="Week start date (YYYY-MM-DD)")
    engine: str = Field(..., description="Engine name")
    count: int = Field(..., ge=0, description="Number of executions")


class AdminAnalyticsResponse(BaseModel):
    """Response model for GET /admin/analytics (Story 8.2, AC1, AC4).

    Aggregated admin dashboard analytics with period filtering.

    Attributes:
        total_published_actions: Number of published actions in catalog.
        executions_by_engine: Breakdown by database engine.
        executions_by_profile: Breakdown by user profile.
        adoption_trend: Weekly trend per engine over the period.
    """
    total_published_actions: int = Field(..., ge=0, description="Published actions count")
    executions_by_engine: list[EngineExecutions] = Field(default_factory=list)
    executions_by_profile: list[ProfileExecutions] = Field(default_factory=list)
    adoption_trend: list[WeeklyTrendPoint] = Field(default_factory=list)
