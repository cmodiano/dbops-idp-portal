"""Tests for JWT token creation and verification."""

from datetime import timedelta
import time

import pytest
from jose import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, verify_token


def test_create_access_token_returns_string():
    """create_access_token returns a JWT string."""
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_payload():
    """Access token payload contains expected fields."""
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "1"
    assert payload["username"] == "marc"
    assert payload["profile"] == "dbops"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_access_token_custom_expiry():
    """Access token respects custom expiry delta."""
    token = create_access_token({"sub": "1", "username": "x", "profile": "y"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert "exp" in payload


def test_create_refresh_token_returns_string():
    """create_refresh_token returns a JWT string."""
    token = create_refresh_token({"sub": "1", "username": "marc", "profile": "dbops"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token_payload():
    """Refresh token payload contains expected fields and type=refresh."""
    token = create_refresh_token({"sub": "1", "username": "marc", "profile": "dbops"})
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "1"
    assert payload["type"] == "refresh"
    assert "exp" in payload


def test_verify_token_valid():
    """verify_token decodes a valid token into TokenPayload."""
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    payload = verify_token(token)
    assert payload.sub == "1"
    assert payload.username == "marc"
    assert payload.profile == "dbops"
    assert payload.type == "access"


def test_verify_token_expired():
    """verify_token raises UnauthorizedError for expired tokens."""
    token = create_access_token(
        {"sub": "1", "username": "marc", "profile": "dbops"},
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token(token)
    assert exc_info.value.code == "INVALID_TOKEN"
    assert exc_info.value.status_code == 401


def test_verify_token_invalid():
    """verify_token raises UnauthorizedError for tampered tokens."""
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token("invalid.token.string")
    assert exc_info.value.code == "INVALID_TOKEN"


def test_verify_token_wrong_secret():
    """verify_token raises UnauthorizedError for tokens signed with wrong key."""
    token = jwt.encode(
        {"sub": "1", "username": "marc", "profile": "dbops", "exp": int(time.time()) + 3600},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token(token)
    assert exc_info.value.code == "INVALID_TOKEN"


def test_verify_token_expected_type_access():
    """verify_token with expected_type='access' accepts access tokens."""
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    payload = verify_token(token, expected_type="access")
    assert payload.type == "access"


def test_verify_token_expected_type_refresh():
    """verify_token with expected_type='refresh' accepts refresh tokens."""
    token = create_refresh_token({"sub": "1", "username": "marc", "profile": "dbops"})
    payload = verify_token(token, expected_type="refresh")
    assert payload.type == "refresh"


def test_verify_token_wrong_type_rejects():
    """verify_token rejects refresh token when access expected."""
    token = create_refresh_token({"sub": "1", "username": "marc", "profile": "dbops"})
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token(token, expected_type="access")
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"


def test_verify_token_access_as_refresh_rejects():
    """verify_token rejects access token when refresh expected."""
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_token(token, expected_type="refresh")
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"
