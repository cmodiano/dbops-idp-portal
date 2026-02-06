"""
JWT token generation and validation utilities.
Story M.7 - Task 4
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from django.conf import settings
from jose import jwt, JWTError


class TokenPayload:
    """Token payload data class."""

    def __init__(
        self,
        sub: str,
        username: str,
        profile: str,
        ad_groups: list[str] | None = None,
        type: str = "access",
        exp: datetime | None = None,
        **kwargs,  # Accept extra fields from JWT
    ):
        self.sub = sub
        self.username = username
        self.profile = profile
        self.ad_groups = ad_groups or []
        self.type = type
        self.exp = exp


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Token payload data (sub, username, profile, ad_groups)
        expires_delta: Optional custom expiration delta. Defaults to JWT_ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        str: Encoded JWT access token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token (longer TTL).

    Args:
        data: Token payload data (sub, username, profile, ad_groups)

    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str, expected_type: str | None = None) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string
        expected_type: Optional expected token type ('access' or 'refresh')

    Returns:
        TokenPayload if valid, None if invalid or expired

    Raises:
        InvalidTokenError: If token type doesn't match expected_type
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        token_payload = TokenPayload(**payload)

        # Check token type if specified
        if expected_type and token_payload.type != expected_type:
            return None

        return token_payload
    except JWTError:
        return None


def decode_token_unsafe(token: str) -> dict[str, Any] | None:
    """Decode JWT token without verification (for debugging only).

    Args:
        token: JWT token string

    Returns:
        dict: Decoded payload if valid format, None otherwise
    """
    try:
        # Use get_unverified_claims to avoid exposing secret key
        return jwt.get_unverified_claims(token)
    except JWTError:
        return None
