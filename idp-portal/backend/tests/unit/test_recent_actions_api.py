"""Tests for recent actions API endpoint (Story 3.1 AC5)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import users
from app.models.auth import UserProfile


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return UserProfile(
        id=1,
        username="test-user",
        display_name="Test User",
        profile="dba",
        profile_ids=[1],
        cumulative_permissions=None,
    )


@pytest.fixture
def app(mock_user):
    """Create test FastAPI app with users router."""
    test_app = FastAPI()
    test_app.include_router(users.router, prefix="/api/v1")

    async def override_get_current_user():
        return mock_user

    test_app.dependency_overrides[users.get_current_user] = override_get_current_user
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestListRecentActions:
    """Tests for GET /api/v1/users/me/recent-actions (AC5)."""

    def test_list_recent_actions_returns_empty_list(self, client):
        """AC5: Returns empty data array when no recent actions."""
        with patch("app.api.v1.users.favorites_repository") as mock_repo:
            mock_repo.list_recent_actions = AsyncMock(return_value=[])

            response = client.get("/api/v1/users/me/recent-actions")

            assert response.status_code == 200
            assert response.json() == {"data": []}
            mock_repo.list_recent_actions.assert_called_once_with(user_id=1, limit=10)

    def test_list_recent_actions_returns_distinct_actions(self, client):
        """AC5: Returns distinct action_ids ordered by most recent execution."""
        now = datetime(2026, 1, 29, 12, 0, 0)
        with patch("app.api.v1.users.favorites_repository") as mock_repo:
            mock_repo.list_recent_actions = AsyncMock(return_value=[
                {"action_id": 101, "name": "Create PDB", "last_executed_at": now},
                {"action_id": 102, "name": "Patch DB", "last_executed_at": now},
            ])

            response = client.get("/api/v1/users/me/recent-actions")

            assert response.status_code == 200
            data = response.json()["data"]
            assert len(data) == 2
            assert data[0]["action_id"] == 101
            assert data[0]["name"] == "Create PDB"
            assert data[1]["action_id"] == 102

    def test_list_recent_actions_with_limit(self, client):
        """AC5: Supports optional limit parameter."""
        with patch("app.api.v1.users.favorites_repository") as mock_repo:
            mock_repo.list_recent_actions = AsyncMock(return_value=[])

            response = client.get("/api/v1/users/me/recent-actions?limit=5")

            assert response.status_code == 200
            mock_repo.list_recent_actions.assert_called_once_with(user_id=1, limit=5)
