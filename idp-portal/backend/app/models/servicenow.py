"""ServiceNow models for Story 4.5 - Intégration ServiceNow.

Defines Pydantic models for:
- ServiceNowChangeRequest: Input for creating change requests
- ServiceNowChangeResponse: Output from ServiceNow API
"""

from typing import Any

from pydantic import BaseModel, Field


class ServiceNowChangeRequest(BaseModel):
    """Input model for ServiceNow change request creation (Story 4.5, Task 4.3).

    Maps to ServiceNow Table API POST /api/now/table/change_request body.

    Attributes:
        short_description: Change title (e.g., "[IDP] Action Name - Production")
        description: Detailed change description with correlation ID, parameters
        requested_by: User requesting the change (IDP username)
        assignment_group: ServiceNow assignment group (default: DBOPS)
        category: Change category (default: Database)
        u_change_model: Pre-approved change model code (optional, for Standard Changes)
        u_correlation_id: IDP correlation ID for traceability
    """

    short_description: str = Field(..., max_length=160, description="Change title")
    description: str = Field(..., description="Detailed change description")
    requested_by: str = Field(..., description="User requesting the change")
    assignment_group: str = Field(default="DBOPS", description="ServiceNow assignment group")
    category: str = Field(default="Database", description="Change category")
    u_change_model: str | None = Field(default=None, description="Pre-approved change model code")
    u_correlation_id: str = Field(..., description="IDP correlation ID")


class ServiceNowChangeResponse(BaseModel):
    """Output model for ServiceNow change response (Story 4.5, Task 4.3).

    Parsed from ServiceNow Table API response: {"result": {...}}

    Attributes:
        sys_id: ServiceNow record ID (change_id)
        number: Change number (e.g., "CHG0030123")
        approval: Approval status ("approved", "not requested", etc.)
        state: Change state code
    """

    sys_id: str = Field(..., description="ServiceNow record ID")
    number: str = Field(..., description="Change number (CHG...)")
    approval: str = Field(default="", description="Approval status")
    state: str | None = Field(default=None, description="Change state code")


class ServiceNowStepOutput(BaseModel):
    """Output stored in EXECUTION_STEPS.OUTPUT for ServiceNow steps (Story 4.5, Task 2.2).

    Attributes:
        change_id: ServiceNow sys_id
        change_number: Change number (e.g., "CHG0030123")
        status: "approved" or "pending_approval"
        message: Human-readable status message (optional)
    """

    change_id: str = Field(..., description="ServiceNow sys_id")
    change_number: str = Field(..., description="Change number")
    status: str = Field(..., description="approved or pending_approval")
    message: str | None = Field(default=None, description="Status message")
