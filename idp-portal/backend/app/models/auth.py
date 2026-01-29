"""Auth-related Pydantic models. Story 1.2 (base), Story 2.12 (profile_ids, cumulative_permissions, ad_groups)."""

from typing import Any

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    profile: str
    profile_ids: list[int] | None = None  # Story 2.12: resolved from ad_groups
    cumulative_permissions: Any = None  # CumulativePermissionsResponse when multi-profile


class TokenPayload(BaseModel):
    sub: str
    username: str
    profile: str
    exp: int
    type: str = "access"
    ad_groups: list[str] | None = None  # Story 2.12: multi-profile resolution
