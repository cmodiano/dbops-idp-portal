"""Profile models for dynamic profiles and AD group mapping (Story 2.9, FR25a)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
