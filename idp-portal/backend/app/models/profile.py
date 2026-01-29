"""Profile models for dynamic profiles and AD group mapping (Story 2.9, FR25a)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileCreate(BaseModel):
    """Input model for creating a profile (AC #2, #5).

    name and ad_group required; is_admin / is_auditor booleans.
    """

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4000)
    ad_group: str = Field(..., min_length=1, max_length=512)
    is_admin: bool = False
    is_auditor: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")
        return stripped

    @field_validator("ad_group")
    @classmethod
    def strip_ad_group(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("ad_group cannot be empty or whitespace only")
        return stripped


class ProfileUpdate(BaseModel):
    """Input model for updating a profile (AC #4). All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4000)
    ad_group: str | None = Field(None, min_length=1, max_length=512)
    is_admin: bool | None = None
    is_auditor: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @field_validator("ad_group")
    @classmethod
    def strip_ad_group(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class ProfileResponse(BaseModel):
    """Output model for a single profile (AC #2, #4, #5)."""

    id: int
    name: str
    description: str | None
    ad_group: str
    is_admin: bool
    is_auditor: bool
    created_at: datetime
    updated_at: datetime


class ProfileListItem(BaseModel):
    """Output model for profile list (AC #3). permission_count = 0 until 2.10."""

    id: int
    name: str
    ad_group: str
    permission_count: int = 0
    created_at: datetime


# --- Story 2.10: Actions / environnements par profil (AC2, AC3, AC4, AC5) ---

class ProfileActionPermissionsUpdate(BaseModel):
    """Input model for PUT /admin/profiles/{id}/actions (AC2, AC3, AC4, AC5).

    actions_type: 'list' | 'pattern' | 'all'. Validation: list → action_ids required;
    pattern → tag_patterns required; all → no extra required. environments optional.
    """

    actions_type: Literal["list", "pattern", "all"] = Field(...)
    action_ids: list[int] | None = None
    tag_patterns: list[str] | None = None
    environments: list[str] | None = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ProfileActionPermissionsUpdate":
        if self.actions_type == "list":
            if not self.action_ids:
                raise ValueError("action_ids is required when actions_type is 'list'")
            if self.tag_patterns:
                raise ValueError("tag_patterns must be empty when actions_type is 'list'")
        elif self.actions_type == "pattern":
            if not self.tag_patterns:
                raise ValueError("tag_patterns is required when actions_type is 'pattern'")
            if self.action_ids:
                raise ValueError("action_ids must be empty when actions_type is 'pattern'")
        else:  # all
            if self.action_ids or self.tag_patterns:
                raise ValueError("action_ids and tag_patterns must be empty when actions_type is 'all'")
        return self


class ProfileActionPermissionsResponse(BaseModel):
    """Output model for GET/PUT profile actions permissions (AC2, AC3, AC4, AC5)."""

    actions_type: Literal["list", "pattern", "all"]
    action_ids: list[int] = Field(default_factory=list)
    tag_patterns: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)


# --- Story 2.11: Targets par profil (AC1–AC5) ---

class ProfileTargetPermissionsUpdate(BaseModel):
    """Input model for PUT /admin/profiles/{id}/targets (AC1–AC5).

    targets_type: 'list' | 'pattern' | 'all'. list → target_names required;
    pattern → target_patterns required; all → no extra required.
    """

    targets_type: Literal["list", "pattern", "all"] = Field(...)
    target_names: list[str] | None = None
    target_patterns: list[str] | None = None

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ProfileTargetPermissionsUpdate":
        if self.targets_type == "list":
            if not self.target_names:
                raise ValueError("target_names is required when targets_type is 'list'")
            if self.target_patterns:
                raise ValueError("target_patterns must be empty when targets_type is 'list'")
        elif self.targets_type == "pattern":
            if not self.target_patterns:
                raise ValueError("target_patterns is required when targets_type is 'pattern'")
            if self.target_names:
                raise ValueError("target_names must be empty when targets_type is 'pattern'")
        else:  # all
            if self.target_names or self.target_patterns:
                raise ValueError("target_names and target_patterns must be empty when targets_type is 'all'")
        return self


class ProfileTargetPermissionsResponse(BaseModel):
    """Output model for GET/PUT profile target permissions (AC1–AC5)."""

    targets_type: Literal["list", "pattern", "all"]
    target_names: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)


# --- Story 2.12: Cumulative permissions (union across profiles) ---


class CumulativePermissionsResponse(BaseModel):
    """Unified permissions for a user with multiple profiles (AC2, AC4). Union of all profiles."""

    actions_type: Literal["list", "pattern", "all"] = "all"
    action_ids: list[int] = Field(default_factory=list)
    tag_patterns: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    targets_type: Literal["list", "pattern", "all"] = "all"
    target_names: list[str] = Field(default_factory=list)
    target_patterns: list[str] = Field(default_factory=list)
