"""Auth-related Pydantic models (stubs for Story 1.2)."""

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    profile: str


class TokenPayload(BaseModel):
    sub: str
    username: str
    profile: str
    exp: int
    type: str = "access"
