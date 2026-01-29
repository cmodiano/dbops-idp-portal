"""Catalog models for Software Catalog actions (Story 2.1, FR1; Story 2.6 tags).

Defines Pydantic models for:
- ActionCategory, ActionEngine, ActionPlatform, ActionStatus enums
- ActionCreate: input model for creating actions
- ActionResponse: output model for action list
- ActionDetail: output model with full details including rbac_policies
- TagCreate, TagResponse: tag models (Story 2.6, FR11c)
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ActionCategory(str, Enum):
    """Valid action categories for Software Catalog."""
    PROVISIONING = "Provisioning"
    PATCHING = "Patching"
    ADMINISTRATION = "Administration"
    MONITORING = "Monitoring"


class ActionEngine(str, Enum):
    """Supported database engines."""
    ORACLE = "Oracle"
    SQL_SERVER = "SQL Server"
    DB2 = "DB2"


class ActionPlatform(str, Enum):
    """Execution platforms for actions."""
    AAP = "AAP"
    GITHUB_ACTIONS = "GitHub Actions"
    AZURE_DEVOPS = "Azure DevOps"
    TERRAFORM = "Terraform"


class ActionStatus(str, Enum):
    """Action lifecycle status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class ImpactLevel(str, Enum):
    """Impact levels for actions per environment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# === Story 2.6: Tag models (FR11c) ===


def normalize_tag_name(name: str) -> str:
    """Normalize tag name: lowercase, strip, replace spaces with nothing."""
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower().replace(" ", "")


class TagCreate(BaseModel):
    """Input model for creating a tag (Story 2.6, AC #5).

    Attributes:
        name: Tag name (normalized: lowercase, no spaces)
    """
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize tag name: lowercase, strip, no spaces."""
        normalized = normalize_tag_name(v)
        if not normalized:
            raise ValueError("tag name cannot be empty or whitespace only")
        return normalized


class TagResponse(BaseModel):
    """Output model for tag (Story 2.6, AC #5)."""
    id: int
    name: str
    created_at: datetime


class ActionTagsUpdateRequest(BaseModel):
    """Input for PUT /admin/actions/{id}/tags (Story 2.6, AC #5).

    Provide either tag_ids or tag_names. tag_names creates missing tags on the fly.
    """
    tag_ids: list[int] | None = None
    tag_names: list[str] | None = None

    @field_validator("tag_names")
    @classmethod
    def normalize_tag_names(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = [normalize_tag_name(s) for s in v if normalize_tag_name(s)]
        return out  # keep [] to allow "clear all tags"

    @model_validator(mode="after")
    def require_tag_ids_or_tag_names_exclusive(self) -> "ActionTagsUpdateRequest":
        if self.tag_ids is None and self.tag_names is None:
            raise ValueError("provide either tag_ids or tag_names")
        if self.tag_ids is not None and self.tag_names is not None:
            raise ValueError("provide either tag_ids or tag_names, not both")
        return self


class ActionCreate(BaseModel):
    """Input model for creating a new action (AC #2, #5).

    Attributes:
        name: Action name (1-255 chars, unique)
        description: Action description (max 4000 chars)
        category: One of Provisioning, Patching, Administration, Monitoring
        engine: Database engine (Oracle, SQL Server, DB2)
        platform: Execution platform (AAP, GitHub Actions, Azure DevOps, Terraform)
        parameters_schema: Optional JSON Schema for action parameters
        impact_rules: Optional impact rules per environment
    """
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4000)
    category: ActionCategory
    engine: ActionEngine
    platform: ActionPlatform
    parameters_schema: dict[str, Any] | None = None
    impact_rules: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip whitespace from name and validate not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")
        return stripped

    @field_validator("parameters_schema")
    @classmethod
    def validate_parameters_schema(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate parameters_schema is a valid JSON Schema structure."""
        if v is None:
            return None

        # Basic JSON Schema validation - must be an object with valid structure
        if not isinstance(v, dict):
            raise ValueError("parameters_schema must be a JSON object")

        # Check for basic JSON Schema properties if present
        valid_top_level = {"$schema", "type", "properties", "required", "additionalProperties",
                          "title", "description", "definitions", "$defs", "allOf", "anyOf", "oneOf"}
        if not v or not any(k in valid_top_level for k in v.keys()):
            raise ValueError("parameters_schema must be a valid JSON Schema with recognized properties")

        return v

    @field_validator("impact_rules")
    @classmethod
    def validate_impact_rules(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate impact_rules structure: {environment: {level: "low"|"medium"|"high"|"critical"}}."""
        if v is None:
            return None

        if not isinstance(v, dict):
            raise ValueError("impact_rules must be a JSON object")

        valid_levels = {"low", "medium", "high", "critical"}

        for env, rules in v.items():
            if not isinstance(rules, dict):
                raise ValueError(f"impact_rules[{env}] must be an object with 'level' key")

            level = rules.get("level")
            if level is None:
                raise ValueError(f"impact_rules[{env}] must have a 'level' key")

            if level not in valid_levels:
                raise ValueError(
                    f"impact_rules[{env}].level must be one of: {', '.join(valid_levels)}"
                )

        return v


class ActionResponse(BaseModel):
    """Output model for action in list views (AC #5).

    Excludes rbac_policies for list performance.
    Story 2.6: includes tags (tag names) for display.
    """
    id: int
    name: str
    description: str | None = None
    category: ActionCategory
    engine: ActionEngine
    platform: ActionPlatform
    parameters_schema: dict[str, Any] | None = None
    impact_rules: dict[str, Any] | None = None
    status: ActionStatus
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class ActionDetail(ActionResponse):
    """Output model for action detail view (AC #5).

    Includes rbac_policies for full action details.
    """
    rbac_policies: dict[str, Any] | None = None
    execution_steps: list["ExecutionStep"] | None = None
    change_type_config: dict[str, "ChangeType"] | None = None


# === Story 2.2: Execution Steps and Change Type Models ===
# === Story 2.7: ConnectorType generic connector (AC1, AC4) ===


class ConnectorType(str, Enum):
    """Generic connector types for execution steps (Story 2.7, AC1).

    Replaces is_servicenow_change flag. connector_config holds connector-specific params
    (e.g. ServiceNow change template). conditional_environments applies when step is conditional.
    """
    AAP = "aap"
    SERVICENOW = "servicenow"
    AZUREDEVOPS = "azuredevops"
    JIRA = "jira"
    GITHUB_ACTIONS = "github_actions"
    TERRAFORM = "terraform"
    NONE = "none"


class ExecutionStepType(str, Enum):
    """Types of execution steps (FR2)."""
    PREREQUISITE = "prerequisite"
    EXECUTION = "execution"
    VERIFICATION = "verification"


class ChangeType(str, Enum):
    """ServiceNow change types (FR4). Story 2.8: CAB removed; only pre-approved supported.

    change_type_config means « changement requis (pre-approuvé) » per environment.
    Stored values are exclusively "pre_approved". Legacy "cab" is converted on read (repository).
    """
    PRE_APPROVED = "pre_approved"


class ExecutionStep(BaseModel):
    """Single execution step configuration (AC #1, #2; Story 2.7: connector_type).

    Attributes:
        order: Step order (1-based, sequential)
        name: Step name (1-255 chars)
        type: Step type (prerequisite, execution, verification)
        connector_type: Generic connector (aap, servicenow, azuredevops, jira, github_actions, terraform, none).
        connector_config: Connector-specific config (e.g. ServiceNow change template). Optional.
        conditional_environments: Required when connector_type is servicenow (environments where step applies).
    """
    order: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    type: ExecutionStepType
    connector_type: ConnectorType = ConnectorType.NONE
    connector_config: dict[str, Any] | None = None
    conditional_environments: list[str] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip whitespace from name and validate not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("step name cannot be empty or whitespace only")
        return stripped

    @field_validator("conditional_environments")
    @classmethod
    def validate_conditional_environments(
        cls, v: list[str] | None, info
    ) -> list[str] | None:
        """Validate conditional_environments is required when connector_type is servicenow (Story 2.7)."""
        connector_type = info.data.get("connector_type", ConnectorType.NONE)
        if connector_type == ConnectorType.SERVICENOW and (v is None or len(v) == 0):
            raise ValueError(
                "conditional_environments is required when connector_type is servicenow"
            )
        return v


class ExecutionStepsUpdate(BaseModel):
    """Input model for updating execution steps (AC #5).

    Attributes:
        steps: Ordered list of execution steps
        change_type_config: Change type configuration per environment
    """
    steps: list[ExecutionStep]
    change_type_config: dict[str, ChangeType] | None = None

    @field_validator("steps")
    @classmethod
    def validate_steps_order(cls, v: list[ExecutionStep]) -> list[ExecutionStep]:
        """Validate steps order is unique and sequential starting from 1."""
        if not v:
            raise ValueError("at least one step is required")

        orders = [step.order for step in v]

        # Check uniqueness
        if len(orders) != len(set(orders)):
            raise ValueError("step order values must be unique")

        # Check sequential starting from 1
        expected = list(range(1, len(v) + 1))
        if sorted(orders) != expected:
            raise ValueError(
                f"step order must be sequential starting from 1 (expected {expected}, got {sorted(orders)})"
            )

        return v


# === Story 2.3: RBAC Policies Models ===


class UserProfile(str, Enum):
    """User profiles for RBAC (FR3, Story 2.3).

    Defines the four user profiles that can access actions.
    """
    DBA_APPLICATIF = "dba_applicatif"
    DBA_INFRASTRUCTURE = "dba_infrastructure"
    CLIENT_BUSINESS = "client_business"
    DBOPS = "dbops"


class EnvironmentPermission(BaseModel):
    """Permission configuration for a single environment (AC #1, #2).

    Attributes:
        profiles: List of authorized profiles for this environment
        requires_approval: Whether approval is required before execution
        approver_profiles: Profiles that can approve (required if requires_approval=True)
    """
    profiles: list[UserProfile]
    requires_approval: bool = False
    approver_profiles: list[UserProfile] | None = None

    @field_validator("profiles")
    @classmethod
    def validate_profiles_not_empty(cls, v: list[UserProfile]) -> list[UserProfile]:
        """Validate at least one profile is specified."""
        if not v:
            raise ValueError("at least one profile is required per environment")
        return v

    @field_validator("approver_profiles")
    @classmethod
    def validate_approver_profiles(
        cls, v: list[UserProfile] | None, info
    ) -> list[UserProfile] | None:
        """Validate approver_profiles is provided when requires_approval is True."""
        requires_approval = info.data.get("requires_approval", False)
        if requires_approval and (v is None or len(v) == 0):
            raise ValueError(
                "approver_profiles is required when requires_approval is True"
            )
        return v


class RbacPolicies(BaseModel):
    """RBAC policies configuration per environment (AC #1, #2).

    Attributes:
        environments: Dict mapping environment name to EnvironmentPermission
    """
    environments: dict[str, EnvironmentPermission]


class RbacPoliciesUpdate(BaseModel):
    """Input model for updating RBAC policies (AC #4).

    Attributes:
        policies: The RBAC policies configuration
    """
    policies: RbacPolicies


# === Story 2.4: Status Transition and Lifecycle Models ===


class StatusTransition(str, Enum):
    """Valid status transitions for action lifecycle (Story 2.4, AC #1, #4, #5).

    State machine:
        draft -> published (publish)
        published -> disabled (disable)
        disabled -> published (enable)
    """
    PUBLISH = "publish"
    DISABLE = "disable"
    ENABLE = "enable"


class InvalidTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""

    def __init__(self, current_status: str, transition: str, message: str | None = None):
        self.current_status = current_status
        self.transition = transition
        if message is None:
            message = f"Transition de statut invalide: {current_status} avec {transition}"
        super().__init__(message)


# Valid transitions mapping: {current_status: {allowed_transition: new_status}}
_VALID_TRANSITIONS: dict[ActionStatus, dict[StatusTransition, ActionStatus]] = {
    ActionStatus.DRAFT: {
        StatusTransition.PUBLISH: ActionStatus.PUBLISHED,
    },
    ActionStatus.PUBLISHED: {
        StatusTransition.DISABLE: ActionStatus.DISABLED,
    },
    ActionStatus.DISABLED: {
        StatusTransition.ENABLE: ActionStatus.PUBLISHED,
    },
}


def validate_transition(current_status: ActionStatus, transition: StatusTransition) -> ActionStatus:
    """Validate and return the new status for a given transition.

    Args:
        current_status: Current action status
        transition: Requested transition

    Returns:
        The new ActionStatus after the transition

    Raises:
        InvalidTransitionError: If the transition is not valid for the current status
    """
    allowed = _VALID_TRANSITIONS.get(current_status, {})
    if transition not in allowed:
        raise InvalidTransitionError(
            current_status=current_status.value,
            transition=transition.value,
        )
    return allowed[transition]


class StatusUpdateRequest(BaseModel):
    """Input model for updating action status (Story 2.4, AC #5).

    Attributes:
        transition: The status transition to apply (publish, disable, enable)
    """
    transition: StatusTransition


class ActionListItem(BaseModel):
    """Output model for action in admin dashboard list (Story 2.4, AC #2; Story 2.6 tags).

    Lightweight model for listing actions with execution stats and tags.
    """
    id: int
    name: str
    status: ActionStatus
    category: ActionCategory
    engine: ActionEngine
    created_at: datetime
    execution_count: int = 0
    tags: list[str] = Field(default_factory=list)


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""
    page: int
    page_size: int
    total_count: int
    total_pages: int


class ActionListResponse(BaseModel):
    """Response model for paginated action list (Story 2.4, AC #2)."""
    data: list[ActionListItem]
    pagination: PaginationInfo | None = None
