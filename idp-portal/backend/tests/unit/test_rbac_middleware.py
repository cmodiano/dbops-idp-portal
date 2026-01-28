"""Tests for RBAC middleware: require_profile dependency and admin routes."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _make_token(profile: str = "dbops", username: str = "test") -> str:
    return create_access_token({"sub": "1", "username": username, "profile": profile})


class TestRequireProfile:
    """Tests for require_profile dependency."""

    async def test_dbops_can_access_admin(self, client):
        """DBOPS profile can access admin routes."""
        token = _make_token(profile="dbops")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "test", "display_name": "Test", "profile": "dbops",
            })
            response = await client.get(
                "/api/v1/admin/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            assert response.json()["data"]["status"] == "ok"

    async def test_dba_cannot_access_admin(self, client):
        """DBA profile gets 403 on admin routes."""
        token = _make_token(profile="dba_applicatif")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba", "display_name": "DBA User", "profile": "dba_applicatif",
            })
            response = await client.get(
                "/api/v1/admin/status",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 403
            assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"

    async def test_no_token_returns_401(self, client):
        """No Bearer token returns 401, not 403."""
        response = await client.get("/api/v1/admin/status")
        assert response.status_code == 401


class TestAuthMeEnriched:
    """Tests for /auth/me returning navigation_tabs."""

    async def test_dbops_gets_four_tabs(self, client):
        """DBOPS user gets 4 navigation tabs including admin."""
        token = _make_token(profile="dbops")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "karim", "display_name": "Karim B.", "profile": "dbops",
            })
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["navigation_tabs"] == ["catalog", "executions", "dashboard", "admin"]

    async def test_dba_gets_three_tabs(self, client):
        """DBA user gets 3 navigation tabs (no admin)."""
        token = _make_token(profile="dba_applicatif")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "marc", "display_name": "Marc D.", "profile": "dba_applicatif",
            })
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["navigation_tabs"] == ["catalog", "executions", "dashboard"]
            assert "admin" not in data["navigation_tabs"]

    async def test_me_still_returns_profile(self, client):
        """GET /auth/me still returns standard profile fields."""
        token = _make_token(profile="dbops")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "karim", "display_name": "Karim B.", "profile": "dbops",
            })
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = response.json()["data"]
            assert data["username"] == "karim"
            assert data["display_name"] == "Karim B."
            assert data["profile"] == "dbops"
            assert data["id"] == 1


class TestAdminRouterMounted:
    """Tests for admin router registration."""

    def test_admin_route_registered(self):
        """Admin status route is registered in the app."""
        routes = [r.path for r in app.routes]
        assert "/api/v1/admin/status" in routes
