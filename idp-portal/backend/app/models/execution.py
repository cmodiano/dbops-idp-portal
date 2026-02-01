"""Execution models for Story 4.1 - Wizard d'execution en 3 etapes.

Defines Pydantic models for:
- ExecutionStatus: execution lifecycle states
- ExecutionCreate: input model for creating executions
- ExecutionResponse: output model for execution records
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    """Input model for creating an execution (Story 4.1, Task 1.1).

    Attributes:
        action_id: ID of the action to execute
        environment: Target environment (dev, staging, prod)
        parameters: Parameters conforming to action's parameters_schema
    """
    action_id: int = Field(..., gt=0, description="ID of the action to execute")
    environment: ExecutionEnvironment = Field(..., description="Target environment")
    parameters: dict[str, Any] | None = Field(default=None, description="Execution parameters")

    @field_validator("parameters")
    @classmethod
    def validate_parameters_is_dict(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate parameters is a dict if provided."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("parameters must be a JSON object")
        return v


class ExecutionResponse(BaseModel):
    """Output model for execution (Story 4.1, Task 1.1; Story 7.4 approval fields).

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
