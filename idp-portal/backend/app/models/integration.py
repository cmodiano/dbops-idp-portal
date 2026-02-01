"""Integration models for remote platform configuration (Story 2.27, 4.9, 5.3).

Defines Pydantic models for:
- AuthFlow: enum of supported authentication flows
- IntegrationCreate: input model for creating integrations
- IntegrationUpdate: input model for updating integrations
- IntegrationResponse: output model for integration (no secrets exposed)

Story 4.9: Type is now free-form string (not enum), auth_flow added for execution flow.
Story 5.3: token_url (optional) and config (optional JSON flow steps + credentials per step).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AuthFlow(str, Enum):
    """Supported authentication flows for integrations (Story 4.9, AC2).
    
    - token: Bearer token (Authorization: Bearer <token>)
    - basic: Basic auth (Authorization: Basic <base64(user:pass)>)
    - basic_then_token: Basic auth then exchange for token (POST /auth/login → Bearer)
    - pat: Personal Access Token (Authorization: token <pat> or X-Api-Key: <pat>)
    """
    TOKEN = "token"
    BASIC = "basic"
    BASIC_THEN_TOKEN = "basic_then_token"
    PAT = "pat"


class IntegrationCreate(BaseModel):
    """Input model for creating an integration (Story 2.27, 4.9, 5.3).

    Attributes:
        type: Integration type - free-form platform name (1-100 chars, Story 4.9 AC1)
        name: Unique integration name (1-255 chars)
        base_url: Base URL of the remote platform (valid URL format)
        credential_ref: Optional Vault path or logical name for credentials (NFR7: no secrets stored)
        icon: Optional icon identifier (preset name, URL, or uploaded icon path)
        auth_flow: Optional authentication flow (token, basic, basic_then_token, pat) (Story 4.9 AC2)
        token_url: Optional URL for token acquisition (Story 5.3 AC1); validated http(s)
        config: Optional JSON flow steps + credentials per step (Story 5.3 AC2); no secret values
    """
    type: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., min_length=1, max_length=2000)
    credential_ref: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=500)
    auth_flow: AuthFlow | None = None
    token_url: str | None = Field(None, max_length=2000)
    config: dict | None = None

    @field_validator("type")
    @classmethod
    def strip_type(cls, v: str) -> str:
        """Strip whitespace from type and validate not empty (Story 4.9 AC1)."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("type cannot be empty or whitespace only")
        return stripped

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

    @field_validator("token_url")
    @classmethod
    def validate_token_url(cls, v: str | None) -> str | None:
        """Validate token_url is a valid http(s) URL when provided (Story 5.3 AC1)."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("token_url must be a valid URL starting with http:// or https://")
        return stripped

    # config: validated in API layer via JSON Schema (Story 5.4) to return 400 INVALID_CONFIG


class IntegrationUpdate(BaseModel):
    """Input model for updating an integration (Story 2.27, 4.9, 5.3).

    All fields optional for partial update. Same validation as IntegrationCreate.
    """
    type: str | None = Field(None, min_length=1, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=255)
    base_url: str | None = Field(None, min_length=1, max_length=2000)
    credential_ref: str | None = Field(None, max_length=500)
    icon: str | None = Field(None, max_length=500)
    auth_flow: AuthFlow | None = None
    token_url: str | None = Field(None, max_length=2000)
    config: dict | None = None

    @field_validator("type")
    @classmethod
    def strip_type(cls, v: str | None) -> str | None:
        """Strip whitespace from type and validate not empty (Story 4.9 AC1)."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("type cannot be empty or whitespace only")
        return stripped

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

    @field_validator("token_url")
    @classmethod
    def validate_token_url(cls, v: str | None) -> str | None:
        """Validate token_url is a valid http(s) URL when provided (Story 5.3 AC1)."""
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("token_url must be a valid URL starting with http:// or https://")
        return stripped

    # config: validated in API layer via JSON Schema (Story 5.4) to return 400 INVALID_CONFIG


class IntegrationResponse(BaseModel):
    """Output model for integration (Story 2.27, 4.9, 5.3).

    Note: credential_ref and config contain references/keys only, no secret values.
    """
    id: int
    type: str
    name: str
    base_url: str
    credential_ref: str | None = None
    icon: str | None = None
    auth_flow: AuthFlow | None = None
    token_url: str | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime
