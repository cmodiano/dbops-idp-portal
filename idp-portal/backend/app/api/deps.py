"""FastAPI dependency injection: authentication and authorization."""

from __future__ import annotations

from fastapi import Request
import structlog

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import verify_token
from app.models.auth import UserProfile
from app.repositories import user_repository

# Dev bypass user for local development without IdP
_DEV_USER = UserProfile(id=0, username="dev-user", display_name="Dev User", profile="dbops")


async def get_current_user(request: Request) -> UserProfile:
    """Extract Bearer token, verify JWT, return UserProfile. Raises 401 if invalid.

    Also binds user_id to structlog contextvars for request logging (AC #3).
    """
    if settings.auth_dev_bypass:
        structlog.contextvars.bind_contextvars(user_id=str(_DEV_USER.id))
        return _DEV_USER

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError(code="NO_TOKEN", message="Token d'authentification requis")

    token = auth_header.split(" ")[1]
    payload = verify_token(token, expected_type="access")

    user = await user_repository.get_by_username(payload.username)
    if not user:
        raise UnauthorizedError(code="USER_NOT_FOUND", message="Utilisateur introuvable")

    user_profile = UserProfile(**user)
    # Bind user_id to structlog for request logging (AC #3)
    structlog.contextvars.bind_contextvars(user_id=str(user_profile.id))
    return user_profile


async def get_optional_user(request: Request) -> UserProfile | None:
    """Same as get_current_user but returns None if no token present."""
    if settings.auth_dev_bypass:
        return _DEV_USER

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        payload = verify_token(token, expected_type="access")
    except UnauthorizedError:
        return None

    user = await user_repository.get_by_username(payload.username)
    if not user:
        return None

    return UserProfile(**user)
