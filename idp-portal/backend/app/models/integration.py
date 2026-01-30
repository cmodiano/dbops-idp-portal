"""Integration models for remote platform configuration (Story 2.27).

Defines Pydantic models for:
- IntegrationType: enum of supported platform types
- IntegrationCreate: input model for creating integrations
- IntegrationUpdate: input model for updating integrations
- IntegrationResponse: output model for integration (no secrets exposed)
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class IntegrationType(str, Enum):
    """Supported integration types (aligned with ConnectorType from catalog models)."""
    AAP = "aap"
    SERVICENOW = "servicenow"
    TERRAFORM = "terraform"
    AZUREDEVOPS = "azuredevops"
    JIRA = "jira"
    GITHUB_ACTIONS = "github_actions"


class IntegrationCreate(BaseModel):
    """Input model for creating an integration (Story 2.27, AC3).

    Attributes:
        type: Integration type (aap, servicenow, terraform, azuredevops, jira, github_actions)
        name: Unique integration name (1-255 chars)
        base_url: Base URL of the remote platform (valid URL format)
        credential_ref: Optional Vault path or logical name for credentials (NFR7: no secrets stored)
        icon: Optional icon identifier (preset name or URL)
    """
    type: IntegrationType
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., min_length=1, max_length=2000)
    credential_ref: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip whitespace from name and validate not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")
        return stripped

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base_url is a valid URL format."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("base_url cannot be empty or whitespace only")
        # Basic URL validation: must start with http:// or https://
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("base_url must be a valid URL starting with http:// or https://")
        return stripped


class IntegrationUpdate(BaseModel):
    """Input model for updating an integration (Story 2.27, AC3).

    All fields optional for partial update. Same validation as IntegrationCreate.
    """
    type: IntegrationType | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    base_url: str | None = Field(None, min_length=1, max_length=2000)
    credential_ref: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        """Strip whitespace from name and validate not empty."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")
        return stripped

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate base_url is a valid URL format."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("base_url cannot be empty or whitespace only")
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("base_url must be a valid URL starting with http:// or https://")
        return stripped


class IntegrationResponse(BaseModel):
    """Output model for integration (Story 2.27, AC2).

    Note: credential_ref is included (reference only, no secret value).
    """
    id: int
    type: IntegrationType
    name: str
    base_url: str
    credential_ref: str | None = None
    icon: str | None = None
    created_at: datetime
    updated_at: datetime
