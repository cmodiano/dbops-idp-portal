"""Security utilities: JWT token creation/verification and RBAC dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, Request
from jose import jwt, JWTError

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models.auth import TokenPayload, UserProfile


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token (8h TTL)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_refresh_token_expire_hours)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str, expected_type: str | None = None) -> TokenPayload:
    """Decode and validate a JWT token. Raises UnauthorizedError if invalid or wrong type."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        token_payload = TokenPayload(**payload)
        if expected_type and token_payload.type != expected_type:
            raise UnauthorizedError(
                code="INVALID_TOKEN_TYPE",
                message=f"Token de type '{expected_type}' attendu",
            )
        return token_payload
    except JWTError:
        raise UnauthorizedError(code="INVALID_TOKEN", message="Token invalide ou expire")


def require_profile(*allowed_profiles: str) -> Callable:
    """FastAPI dependency that checks user profile against allowed list.

    Usage: Depends(require_profile("dbops"))
    """
    from app.api.deps import get_current_user

    async def _check_profile(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.profile.lower() not in [p.lower() for p in allowed_profiles]:
            raise ForbiddenError(
                code="INSUFFICIENT_PERMISSIONS",
                message=f"Profil '{user.profile}' non autorise pour cette ressource",
            )
        return user

    return _check_profile
