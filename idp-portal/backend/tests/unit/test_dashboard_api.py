"""Tests for dashboard API endpoints (Story 5.1, Task 5.1; Story 8.3).

Tests:
- GET /api/v1/dashboard/stats: Returns aggregated statistics (AC1, AC4, Story 8.3 AC6 period filter)
- GET /api/v1/dashboard/recent: Returns executions from last 24h (AC2, AC4)
- GET /api/v1/dashboard/stats-by-technology: Returns executions grouped by engine (Story 8.3, AC3, AC7)
- GET /api/v1/dashboard/stats-by-environment: Returns executions grouped by environment (Story 8.3, AC4, AC7)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mock_auth_dba():
    """Mock authentication with DBA profile for dashboard access."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=1,
        username="test_dba",
        display_name="Test DBA User",
        profile="dba",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_auth_dbops():
    """Mock authentication with DBOPS profile for dashboard access."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=2,
        username="test_dbops",
        display_name="Test DBOPS User",
        profile="dbops",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_auth_viewer():
    """Mock authentication with a profile that must NOT access dashboard (Story 5.1 RBAC)."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=3,
        username="test_viewer",
        display_name="Test Viewer",
        profile="viewer",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


class TestGetDashboardStats:
    """Tests for GET /api/v1/dashboard/stats (Story 5.1, AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_all_metrics(self, client, mock_auth_dba):
        """GET /dashboard/stats returns executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur."""
        mock_stats = {
            "executions_jour": 15,
            "taux_succes_pct": 87.5,
            "executions_en_cours": 3,
            "executions_en_erreur": 2,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["executions_jour"] == 15
        assert data["data"]["taux_succes_pct"] == 87.5
        assert data["data"]["executions_en_cours"] == 3
        assert data["data"]["executions_en_erreur"] == 2

    @pytest.mark.asyncio
    async def test_get_stats_dbops_profile_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/stats is accessible by DBOPS profile."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 100.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_stats_handles_zero_executions(self, client, mock_auth_dba):
        """GET /dashboard/stats handles case with no executions gracefully."""
        mock_stats = {
            "executions_jour": 0,
            "taux_succes_pct": 0.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["executions_jour"] == 0
        assert data["data"]["taux_succes_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_requires_authentication(self, client):
        """GET /dashboard/stats returns 401 without authentication."""
        app.dependency_overrides.clear()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.auth_dev_bypass = False

            response = await client.get("/api/v1/dashboard/stats")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_stats_forbidden_for_non_dba_profile(self, client, mock_auth_viewer):
        """GET /dashboard/stats returns 403 for profile other than DBA/DBOPS (Story 5.1 RBAC)."""
        response = await client.get("/api/v1/dashboard/stats")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetDashboardRecent:
    """Tests for GET /api/v1/dashboard/recent (Story 5.1, AC2, AC4)."""

    @pytest.mark.asyncio
    async def test_get_recent_returns_executions_with_required_fields(self, client, mock_auth_dba):
        """GET /dashboard/recent returns executions (last 24h) with required fields."""
        mock_executions = [
            {
                "id": i,
                "action_name": f"Action {i}",
                "user_display_name": f"User {i}",
                "environment": "dev" if i % 2 == 0 else "prod",
                "status": "COMPLETED" if i % 3 != 0 else "FAILED",
                "created_at": datetime(2026, 1, 30, 10, i, 0).isoformat(),
            }
            for i in range(1, 11)
        ]

        with patch("app.api.v1.dashboard.execution_repository.list_recent_executions", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_executions

            response = await client.get("/api/v1/dashboard/recent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 10
        # Verify required fields are present
        first = data["data"][0]
        assert "id" in first
        assert "action_name" in first
        assert "user_display_name" in first
        assert "environment" in first
        assert "status" in first
        assert "created_at" in first

    @pytest.mark.asyncio
    async def test_get_recent_shows_all_users_executions(self, client, mock_auth_dba):
        """GET /dashboard/recent shows executions from ALL users (DBA visibility)."""
        # Executions from different users
        mock_executions = [
            {
                "id": 1,
                "action_name": "Create PDB",
                "user_display_name": "Alice DBA",
                "environment": "dev",
                "status": "COMPLETED",
                "created_at": datetime(2026, 1, 30, 10, 0, 0).isoformat(),
            },
            {
                "id": 2,
                "action_name": "Drop PDB",
                "user_display_name": "Bob Ops",
                "environment": "prod",
                "status": "RUNNING",
                "created_at": datetime(2026, 1, 30, 9, 0, 0).isoformat(),
            },
        ]

        with patch("app.api.v1.dashboard.execution_repository.list_recent_executions", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_executions

            response = await client.get("/api/v1/dashboard/recent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 2
        # Verify different users visible
        users = [e["user_display_name"] for e in data["data"]]
        assert "Alice DBA" in users
        assert "Bob Ops" in users
        # Repository called with dashboard limit (last 24h window)
        mock_list.assert_called_once_with(limit=100)

    @pytest.mark.asyncio
    async def test_get_recent_dbops_profile_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/recent is accessible by DBOPS profile."""
        with patch("app.api.v1.dashboard.execution_repository.list_recent_executions", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []

            response = await client.get("/api/v1/dashboard/recent")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_recent_empty_list(self, client, mock_auth_dba):
        """GET /dashboard/recent returns empty list when no executions exist."""
        with patch("app.api.v1.dashboard.execution_repository.list_recent_executions", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = []

            response = await client.get("/api/v1/dashboard/recent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_recent_requires_authentication(self, client):
        """GET /dashboard/recent returns 401 without authentication."""
        app.dependency_overrides.clear()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.auth_dev_bypass = False

            response = await client.get("/api/v1/dashboard/recent")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_recent_forbidden_for_non_dba_profile(self, client, mock_auth_viewer):
        """GET /dashboard/recent returns 403 for profile other than DBA/DBOPS (Story 5.1 RBAC)."""
        response = await client.get("/api/v1/dashboard/recent")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDashboardIntegration:
    """Integration tests for dashboard endpoints."""

    @pytest.mark.asyncio
    async def test_stats_and_recent_both_accessible(self, client, mock_auth_dba):
        """Both dashboard endpoints are accessible in same session."""
        mock_stats = {
            "executions_jour": 5,
            "taux_succes_pct": 80.0,
            "executions_en_cours": 1,
            "executions_en_erreur": 1,
        }
        mock_executions = [
            {
                "id": 1,
                "action_name": "Test Action",
                "user_display_name": "Test User",
                "environment": "dev",
                "status": "COMPLETED",
                "created_at": datetime(2026, 1, 30, 10, 0, 0).isoformat(),
            }
        ]

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.list_recent_executions", new_callable=AsyncMock) as mock_list:
            mock_stats_get.return_value = mock_stats
            mock_list.return_value = mock_executions

            stats_response = await client.get("/api/v1/dashboard/stats")
            recent_response = await client.get("/api/v1/dashboard/recent")

        assert stats_response.status_code == status.HTTP_200_OK
        assert recent_response.status_code == status.HTTP_200_OK
        assert stats_response.json()["data"]["executions_jour"] == 5
        assert len(recent_response.json()["data"]) == 1


# --- Story 8.3: Stats by Technology and Environment Tests ---


class TestGetStatsByTechnology:
    """Tests for GET /api/v1/dashboard/stats-by-technology (Story 8.3, AC3, AC7)."""

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_returns_engine_aggregations(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology returns engine aggregations with count and success_rate."""
        mock_stats = [
            {"engine": "Oracle", "count": 50, "success_rate": 95.0},
            {"engine": "PostgreSQL", "count": 30, "success_rate": 88.5},
            {"engine": "N/A", "count": 10, "success_rate": None},
        ]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-technology")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 3
        assert data["data"][0]["engine"] == "Oracle"
        assert data["data"][0]["count"] == 50
        assert data["data"][0]["success_rate"] == 95.0

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_with_days_parameter(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology accepts days query parameter."""
        mock_stats = [{"engine": "Oracle", "count": 100, "success_rate": 90.0}]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-technology?days=30")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=30)

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_default_days(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology uses default 14 days."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-technology")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=14)

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_empty_data(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology returns empty list when no data."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-technology")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_forbidden_for_non_dba(self, client, mock_auth_viewer):
        """GET /dashboard/stats-by-technology returns 403 for non-DBA/DBOPS profiles."""
        response = await client.get("/api/v1/dashboard/stats-by-technology")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_dbops_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/stats-by-technology is accessible by DBOPS profile."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-technology")

        assert response.status_code == status.HTTP_200_OK


class TestGetStatsByEnvironment:
    """Tests for GET /api/v1/dashboard/stats-by-environment (Story 8.3, AC4, AC7)."""

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_returns_env_aggregations(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment returns environment aggregations with count and success_rate."""
        mock_stats = [
            {"environment": "dev", "count": 40, "success_rate": 92.0},
            {"environment": "staging", "count": 25, "success_rate": 88.0},
            {"environment": "prod", "count": 20, "success_rate": 95.0},
        ]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-environment")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 3
        # Verify order: dev, staging, prod
        assert data["data"][0]["environment"] == "dev"
        assert data["data"][1]["environment"] == "staging"
        assert data["data"][2]["environment"] == "prod"

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_with_days_parameter(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment accepts days query parameter."""
        mock_stats = [{"environment": "prod", "count": 50, "success_rate": 98.0}]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-environment?days=90")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=90)

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_default_days(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment uses default 14 days."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-environment")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=14)

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_empty_data(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment returns empty list when no data."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-environment")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_forbidden_for_non_dba(self, client, mock_auth_viewer):
        """GET /dashboard/stats-by-environment returns 403 for non-DBA/DBOPS profiles."""
        response = await client.get("/api/v1/dashboard/stats-by-environment")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_dbops_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/stats-by-environment is accessible by DBOPS profile."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-environment")

        assert response.status_code == status.HTTP_200_OK


class TestGetDashboardStatsWithPeriod:
    """Tests for GET /api/v1/dashboard/stats with period filter (Story 8.3, AC6)."""

    @pytest.mark.asyncio
    async def test_get_stats_with_days_parameter(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts days query parameter."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 85.0,
            "executions_en_cours": 2,
            "executions_en_erreur": 3,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?days=30")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=30)

    @pytest.mark.asyncio
    async def test_get_stats_default_days(self, client, mock_auth_dba):
        """GET /dashboard/stats uses default 14 days."""
        mock_stats = {
            "executions_jour": 5,
            "taux_succes_pct": 90.0,
            "executions_en_cours": 1,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats")

        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(days=14)
