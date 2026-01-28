"""Tests for FastAPI dependency injection: get_current_user, get_optional_user."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import get_current_user, get_optional_user
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token


def _make_request(auth_header: str | None = None):
    """Create a mock FastAPI Request with optional Authorization header."""
    request = MagicMock()
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    request.headers = headers
    return request


@patch("app.api.deps.settings")
async def test_get_current_user_valid_token(mock_settings):
    """Valid Bearer token returns UserProfile."""
    mock_settings.auth_dev_bypass = False
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    request = _make_request(f"Bearer {token}")

    with patch("app.api.deps.user_repository") as mock_repo:
        mock_repo.get_by_username = AsyncMock(return_value={
            "id": 1, "username": "marc", "display_name": "Marc D.", "profile": "dbops",
        })
        user = await get_current_user(request)
        assert user.username == "marc"
        assert user.profile == "dbops"
        mock_repo.get_by_username.assert_awaited_once_with("marc")


@patch("app.api.deps.settings")
async def test_get_current_user_no_header(mock_settings):
    """Missing Authorization header raises UnauthorizedError."""
    mock_settings.auth_dev_bypass = False
    request = _make_request()
    with pytest.raises(UnauthorizedError) as exc_info:
        await get_current_user(request)
    assert exc_info.value.code == "NO_TOKEN"


@patch("app.api.deps.settings")
async def test_get_current_user_invalid_scheme(mock_settings):
    """Non-Bearer scheme raises UnauthorizedError."""
    mock_settings.auth_dev_bypass = False
    request = _make_request("Basic abc123")
    with pytest.raises(UnauthorizedError) as exc_info:
        await get_current_user(request)
    assert exc_info.value.code == "NO_TOKEN"


@patch("app.api.deps.settings")
async def test_get_current_user_invalid_token(mock_settings):
    """Tampered token raises UnauthorizedError."""
    mock_settings.auth_dev_bypass = False
    request = _make_request("Bearer invalid.token.here")
    with pytest.raises(UnauthorizedError) as exc_info:
        await get_current_user(request)
    assert exc_info.value.code == "INVALID_TOKEN"


@patch("app.api.deps.settings")
async def test_get_current_user_unknown_user(mock_settings):
    """Valid token but user not in DB raises UnauthorizedError."""
    mock_settings.auth_dev_bypass = False
    token = create_access_token({"sub": "99", "username": "ghost", "profile": "dbops"})
    request = _make_request(f"Bearer {token}")

    with patch("app.api.deps.user_repository") as mock_repo:
        mock_repo.get_by_username = AsyncMock(return_value=None)
        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(request)
        assert exc_info.value.code == "USER_NOT_FOUND"


@patch("app.api.deps.settings")
async def test_get_current_user_rejects_refresh_token(mock_settings):
    """Refresh token used as access token is rejected."""
    mock_settings.auth_dev_bypass = False
    token = create_refresh_token({"sub": "1", "username": "marc", "profile": "dbops"})
    request = _make_request(f"Bearer {token}")

    with pytest.raises(UnauthorizedError) as exc_info:
        await get_current_user(request)
    assert exc_info.value.code == "INVALID_TOKEN_TYPE"


@patch("app.api.deps.settings")
async def test_get_current_user_dev_bypass(mock_settings):
    """When auth_dev_bypass is True, returns dev user without token."""
    mock_settings.auth_dev_bypass = True
    request = _make_request()
    user = await get_current_user(request)
    assert user.username == "dev-user"
    assert user.profile == "dbops"


@patch("app.api.deps.settings")
async def test_get_optional_user_valid_token(mock_settings):
    """Valid token returns UserProfile."""
    mock_settings.auth_dev_bypass = False
    token = create_access_token({"sub": "1", "username": "marc", "profile": "dbops"})
    request = _make_request(f"Bearer {token}")

    with patch("app.api.deps.user_repository") as mock_repo:
        mock_repo.get_by_username = AsyncMock(return_value={
            "id": 1, "username": "marc", "display_name": "Marc D.", "profile": "dbops",
        })
        user = await get_optional_user(request)
        assert user is not None
        assert user.username == "marc"


@patch("app.api.deps.settings")
async def test_get_optional_user_no_header(mock_settings):
    """Missing Authorization returns None (not error)."""
    mock_settings.auth_dev_bypass = False
    request = _make_request()
    user = await get_optional_user(request)
    assert user is None


@patch("app.api.deps.settings")
async def test_get_optional_user_invalid_token(mock_settings):
    """Invalid token returns None (not error)."""
    mock_settings.auth_dev_bypass = False
    request = _make_request("Bearer bad.token.xyz")
    user = await get_optional_user(request)
    assert user is None


@patch("app.api.deps.settings")
async def test_get_optional_user_unknown_user(mock_settings):
    """Valid token but user not in DB returns None."""
    mock_settings.auth_dev_bypass = False
    token = create_access_token({"sub": "99", "username": "ghost", "profile": "dbops"})
    request = _make_request(f"Bearer {token}")

    with patch("app.api.deps.user_repository") as mock_repo:
        mock_repo.get_by_username = AsyncMock(return_value=None)
        user = await get_optional_user(request)
        assert user is None
