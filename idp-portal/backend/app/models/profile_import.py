"""Profile YAML import/export models (Story 2.13, AC5, Task 1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProfileYamlActions(BaseModel):
    """Actions block in YAML: type 'pattern' | 'list' | 'all'. 'all' = no restrictions (1.3)."""

    type: Literal["pattern", "list", "all"] = Field(...)
    patterns: list[str] | None = None
    action_ids: list[int] | None = Field(None, alias="list")

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ProfileYamlActions":
        if self.type == "pattern":
            if not self.patterns:
                raise ValueError("patterns is required when actions type is 'pattern'")
            if self.action_ids is not None:
                raise ValueError("action_ids (list) must be empty when actions type is 'pattern'")
        elif self.type == "list":
            if self.action_ids is None:
                raise ValueError("list (action_ids) is required when actions type is 'list'")
            if self.patterns:
                raise ValueError("patterns must be empty when actions type is 'list'")
        else:  # all
            if self.patterns or self.action_ids is not None:
                raise ValueError("patterns and list must be empty when actions type is 'all'")
        return self


class ProfileYamlTargets(BaseModel):
    """Targets block in YAML: type 'pattern' | 'list' | 'all'. 'all' = no restrictions (1.3)."""

    type: Literal["pattern", "list", "all"] = Field(...)
    patterns: list[str] | None = None
    target_names: list[str] | None = Field(None, alias="list")

    @model_validator(mode="after")
    def validate_type_fields(self) -> "ProfileYamlTargets":
        if self.type == "pattern":
            if not self.patterns:
                raise ValueError("patterns is required when targets type is 'pattern'")
            if self.target_names is not None:
                raise ValueError("target_names (list) must be empty when targets type is 'pattern'")
        elif self.type == "list":
            if self.target_names is None:
                raise ValueError("list (target_names) is required when targets type is 'list'")
            if self.patterns:
                raise ValueError("patterns must be empty when targets type is 'list'")
        else:  # all
            if self.patterns or self.target_names is not None:
                raise ValueError("patterns and list must be empty when targets type is 'all'")
        return self


class ProfileYamlItem(BaseModel):
    """Single profile in YAML (AC5, Task 1.1): name, description, ad_group, is_admin, is_auditor, actions, targets, environments."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4000)
    ad_group: str = Field(..., min_length=1, max_length=512)
    is_admin: bool = False
    is_auditor: bool = False
    actions: ProfileYamlActions = Field(...)
    targets: ProfileYamlTargets = Field(...)
    environments: list[str] = Field(default_factory=list)


class ProfilesYamlImport(BaseModel):
    """Root model for uploaded YAML (Task 1.2): profiles list."""

    profiles: list[ProfileYamlItem] = Field(...)
