"""Tests for dashboard API endpoints (Story 5.1, Task 5.1; Story 8.3; Story 8.4; Story 8.5).

Tests:
- GET /api/v1/dashboard/stats: Returns aggregated statistics (AC1, AC4, Story 8.3 AC6 period filter, Story 8.4 advanced filters)
- GET /api/v1/dashboard/recent: Returns executions from last 24h (AC2, AC4)
- GET /api/v1/dashboard/stats-by-technology: Returns executions grouped by engine (Story 8.3, AC3, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/stats-by-environment: Returns executions grouped by environment (Story 8.3, AC4, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/timeseries: Executions over time (Story 8.4 filters)
- GET /api/v1/dashboard/filter-options: Available filter values (Story 8.4, AC1)
- GET /api/v1/dashboard/export/csv: Export dashboard data as CSV (Story 8.5, AC2, AC6)
- GET /api/v1/dashboard/export/pdf: Export dashboard data as PDF (Story 8.5, AC3, AC7)
"""

import pytest
from datetime import datetime, date
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
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 30

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_default_days(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology uses default 14 days."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-technology")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 14

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
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 90

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_default_days(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment uses default 14 days."""
        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            response = await client.get("/api/v1/dashboard/stats-by-environment")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 14

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
        # Check days parameter was passed (other params are None by default)
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 30

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
        # Check days parameter defaults to 14
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["days"] == 14


# --- Story 8.4: Advanced Filters Tests ---


class TestDashboardAdvancedFilters:
    """Tests for dashboard advanced filters (Story 8.4, AC7)."""

    @pytest.mark.asyncio
    async def test_get_stats_with_engine_filter(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts engine filter parameter (Story 8.4, AC2)."""
        mock_stats = {
            "executions_jour": 5,
            "taux_succes_pct": 95.0,
            "executions_en_cours": 1,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?engine=aap")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["engine"] == "aap"

    @pytest.mark.asyncio
    async def test_get_stats_with_environment_filter(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts environment filter parameter (Story 8.4, AC3)."""
        mock_stats = {
            "executions_jour": 3,
            "taux_succes_pct": 100.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?environment=prod")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["environment"] == "prod"

    @pytest.mark.asyncio
    async def test_get_stats_with_combined_filters(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts multiple filters combined (Story 8.4, AC4)."""
        mock_stats = {
            "executions_jour": 2,
            "taux_succes_pct": 100.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?engine=aap&environment=prod&status=COMPLETED")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["engine"] == "aap"
        assert call_kwargs["environment"] == "prod"
        assert call_kwargs["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_stats_with_custom_date_range(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts from_date and to_date parameters."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 90.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 1,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?from_date=2026-01-01&to_date=2026-01-31")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["from_date"] == date(2026, 1, 1)
        assert call_kwargs["to_date"] == date(2026, 1, 31)

    @pytest.mark.asyncio
    async def test_get_stats_with_tags_filter(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts tags filter as list."""
        mock_stats = {
            "executions_jour": 8,
            "taux_succes_pct": 87.5,
            "executions_en_cours": 1,
            "executions_en_erreur": 1,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?tags=oracle&tags=postgresql")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["tags"] == ["oracle", "postgresql"]

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_with_environment_filter(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology accepts environment filter (Story 8.4)."""
        mock_stats = [{"engine": "Oracle", "count": 25, "success_rate": 96.0}]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-technology?environment=prod")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["environment"] == "prod"

    @pytest.mark.asyncio
    async def test_get_stats_by_technology_with_all_filters(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-technology accepts all advanced filters (Story 8.4, AC7)."""
        mock_stats = [{"engine": "Oracle", "count": 10, "success_rate": 100.0}]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get(
                "/api/v1/dashboard/stats-by-technology?environment=prod&tags=oracle&tags=patch&status=COMPLETED&from_date=2026-01-01&to_date=2026-01-31"
            )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["environment"] == "prod"
        assert call_kwargs["tags"] == ["oracle", "patch"]
        assert call_kwargs["status"] == "COMPLETED"
        assert call_kwargs["from_date"] == date(2026, 1, 1)
        assert call_kwargs["to_date"] == date(2026, 1, 31)

    @pytest.mark.asyncio
    async def test_get_stats_by_environment_with_engine_filter(self, client, mock_auth_dba):
        """GET /dashboard/stats-by-environment accepts engine filter (Story 8.4)."""
        mock_stats = [{"environment": "prod", "count": 15, "success_rate": 100.0}]

        with patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats-by-environment?engine=aap")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["engine"] == "aap"

    @pytest.mark.asyncio
    async def test_get_timeseries_with_filters(self, client, mock_auth_dba):
        """GET /dashboard/timeseries accepts filter parameters (Story 8.4)."""
        mock_timeseries = [
            {"date": "2026-01-30", "success": 10, "failed": 1},
            {"date": "2026-01-31", "success": 8, "failed": 2},
        ]

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_timeseries

            response = await client.get("/api/v1/dashboard/timeseries?engine=aap&environment=prod")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["engine"] == "aap"
        assert call_kwargs["environment"] == "prod"


class TestGetFilterOptions:
    """Tests for GET /api/v1/dashboard/filter-options (Story 8.4, Task 14)."""

    @pytest.mark.asyncio
    async def test_get_filter_options_returns_all_option_types(self, client, mock_auth_dba):
        """GET /dashboard/filter-options returns engines, environments, tags, statuses."""
        mock_options = {
            "engines": ["Oracle", "PostgreSQL", "aap"],
            "environments": ["dev", "staging", "prod"],
            "tags": ["database", "automation", "patch"],
            "statuses": ["PENDING", "RUNNING", "COMPLETED", "FAILED"],
        }

        with patch("app.api.v1.dashboard.execution_repository.get_filter_options", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_options

            response = await client.get("/api/v1/dashboard/filter-options")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "engines" in data
        assert "environments" in data
        assert "tags" in data
        assert "statuses" in data
        assert len(data["engines"]) == 3
        assert len(data["environments"]) == 3
        assert len(data["tags"]) == 3

    @pytest.mark.asyncio
    async def test_get_filter_options_empty_data(self, client, mock_auth_dba):
        """GET /dashboard/filter-options returns empty lists when no data."""
        mock_options = {
            "engines": [],
            "environments": [],
            "tags": [],
            "statuses": ["PENDING", "RUNNING", "COMPLETED", "FAILED"],
        }

        with patch("app.api.v1.dashboard.execution_repository.get_filter_options", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_options

            response = await client.get("/api/v1/dashboard/filter-options")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["engines"] == []
        assert data["environments"] == []

    @pytest.mark.asyncio
    async def test_get_filter_options_forbidden_for_non_dba(self, client, mock_auth_viewer):
        """GET /dashboard/filter-options returns 403 for non-DBA/DBOPS profiles."""
        response = await client.get("/api/v1/dashboard/filter-options")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_filter_options_dbops_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/filter-options is accessible by DBOPS profile."""
        mock_options = {
            "engines": ["Oracle"],
            "environments": ["dev"],
            "tags": [],
            "statuses": ["COMPLETED"],
        }

        with patch("app.api.v1.dashboard.execution_repository.get_filter_options", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_options

            response = await client.get("/api/v1/dashboard/filter-options")

        assert response.status_code == status.HTTP_200_OK


class TestDashboardFiltersValidation:
    """Tests for DashboardFilters model validation (Story 8.4, Task 1)."""

    def test_dashboard_filters_validates_date_range(self):
        """DashboardFilters rejects from_date > to_date."""
        from app.models.dashboard import DashboardFilters
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DashboardFilters(from_date=date(2026, 1, 31), to_date=date(2026, 1, 1))

    def test_dashboard_filters_accepts_valid_date_range(self):
        """DashboardFilters accepts from_date <= to_date."""
        from app.models.dashboard import DashboardFilters

        filters = DashboardFilters(from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))
        assert filters.from_date == date(2026, 1, 1)
        assert filters.to_date == date(2026, 1, 31)

    def test_dashboard_filters_accepts_empty(self):
        """DashboardFilters accepts empty filters."""
        from app.models.dashboard import DashboardFilters

        filters = DashboardFilters()
        assert filters.engine is None
        assert filters.environment is None
        assert filters.tags is None

    def test_dashboard_filters_accepts_tags_list(self):
        """DashboardFilters accepts tags as list."""
        from app.models.dashboard import DashboardFilters

        filters = DashboardFilters(tags=["oracle", "postgresql"])
        assert filters.tags == ["oracle", "postgresql"]


class TestDashboardFiltersApiValidation:
    """Integration tests for DashboardFilters validation at API level (Story 8.4, Task 1.2)."""

    @pytest.mark.asyncio
    async def test_stats_rejects_invalid_date_range(self, client, mock_auth_dba):
        """GET /dashboard/stats returns 422 when from_date > to_date."""
        response = await client.get("/api/v1/dashboard/stats?from_date=2026-01-31&to_date=2026-01-01")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_stats_accepts_valid_date_range(self, client, mock_auth_dba):
        """GET /dashboard/stats accepts valid date range."""
        mock_stats = {
            "executions_jour": 5,
            "taux_succes_pct": 90.0,
            "executions_en_cours": 1,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_stats

            response = await client.get("/api/v1/dashboard/stats?from_date=2026-01-01&to_date=2026-01-31")

        assert response.status_code == status.HTTP_200_OK


# --- Story 8.5: Dashboard Export Tests ---


class TestExportDashboardCSV:
    """Tests for GET /api/v1/dashboard/export/csv (Story 8.5, AC2, AC4, AC5, AC6)."""

    @pytest.mark.asyncio
    async def test_export_csv_returns_valid_csv_with_bom(self, client, mock_auth_dba):
        """GET /dashboard/export/csv returns CSV file with UTF-8 BOM for Excel (AC5.1)."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 85.0,
            "executions_en_cours": 2,
            "executions_en_erreur": 1,
        }
        mock_tech_stats = [
            {"engine": "Oracle", "count": 50, "success": 45, "failed": 5, "success_rate": 90.0},
        ]
        mock_env_stats = [
            {"environment": "prod", "count": 30, "success": 28, "failed": 2, "success_rate": 93.3},
        ]
        mock_timeseries = [
            {"date": "2026-01-30", "success": 10, "failed": 1},
        ]

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = mock_tech_stats
            mock_env.return_value = mock_env_stats
            mock_ts.return_value = mock_timeseries

            response = await client.get("/api/v1/dashboard/export/csv")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("text/csv")

        # Check BOM UTF-8
        content = response.content.decode("utf-8")
        assert content.startswith("\ufeff")

    @pytest.mark.asyncio
    async def test_export_csv_contains_all_required_sections(self, client, mock_auth_dba):
        """GET /dashboard/export/csv contains all required sections (AC2)."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 85.0,
            "executions_en_cours": 2,
            "executions_en_erreur": 1,
        }
        mock_tech_stats = [{"engine": "Oracle", "count": 50, "success": 45, "failed": 5, "success_rate": 90.0}]
        mock_env_stats = [{"environment": "prod", "count": 30, "success": 28, "failed": 2, "success_rate": 93.3}]
        mock_timeseries = [{"date": "2026-01-30", "success": 10, "failed": 1}]

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = mock_tech_stats
            mock_env.return_value = mock_env_stats
            mock_ts.return_value = mock_timeseries

            response = await client.get("/api/v1/dashboard/export/csv")

        content = response.content.decode("utf-8")

        # Check all sections are present
        assert "# Paramètres d'analyse" in content
        assert "# Statistiques globales" in content
        assert "# Répartition par technologie" in content
        assert "# Répartition par environnement" in content
        assert "# Tendances temporelles" in content

    @pytest.mark.asyncio
    async def test_export_csv_filename_format_correct(self, client, mock_auth_dba):
        """GET /dashboard/export/csv returns filename with date/time format (AC4)."""
        mock_stats = {"executions_jour": 0, "taux_succes_pct": 0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/csv")

        assert response.status_code == status.HTTP_200_OK
        content_disposition = response.headers["content-disposition"]
        assert "dashboard-report-" in content_disposition
        assert ".csv" in content_disposition
        # Pattern: dashboard-report-YYYY-MM-DD-HH-MM.csv
        import re
        assert re.search(r'dashboard-report-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}\.csv', content_disposition)

    @pytest.mark.asyncio
    async def test_export_csv_with_filters_applied(self, client, mock_auth_dba):
        """GET /dashboard/export/csv includes filters in report (AC5)."""
        mock_stats = {"executions_jour": 5, "taux_succes_pct": 100.0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/csv?engine=aap&environment=prod")

        content = response.content.decode("utf-8")
        # Filters should be documented in report
        assert "Moteur: aap" in content
        assert "Environnement: prod" in content

    @pytest.mark.asyncio
    async def test_export_csv_without_filters_mentions_none(self, client, mock_auth_dba):
        """GET /dashboard/export/csv mentions 'Aucun' when no filters applied (Story 8.5, AC5)."""
        mock_stats = {"executions_jour": 5, "taux_succes_pct": 100.0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/csv")

        content = response.content.decode("utf-8")
        assert "Filtres appliqués,Aucun" in content

    @pytest.mark.asyncio
    async def test_export_csv_forbidden_for_non_dba(self, client, mock_auth_viewer):
        """GET /dashboard/export/csv returns 403 for non-DBA/DBOPS profiles (Story 8.5, RBAC)."""
        response = await client.get("/api/v1/dashboard/export/csv")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestExportDashboardPDF:
    """Tests for GET /api/v1/dashboard/export/pdf (Story 8.5, AC3, AC4, AC5, AC7)."""

    @pytest.mark.asyncio
    async def test_export_pdf_returns_valid_pdf(self, client, mock_auth_dba):
        """GET /dashboard/export/pdf returns valid PDF file (AC3)."""
        mock_stats = {
            "executions_jour": 10,
            "taux_succes_pct": 85.0,
            "executions_en_cours": 2,
            "executions_en_erreur": 1,
        }
        mock_tech_stats = [{"engine": "Oracle", "count": 50, "success": 45, "failed": 5, "success_rate": 90.0}]
        mock_env_stats = [{"environment": "prod", "count": 30, "success": 28, "failed": 2, "success_rate": 93.3}]
        mock_timeseries = [{"date": "2026-01-30", "success": 10, "failed": 1}]

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = mock_tech_stats
            mock_env.return_value = mock_env_stats
            mock_ts.return_value = mock_timeseries

            response = await client.get("/api/v1/dashboard/export/pdf")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/pdf"
        # PDF starts with %PDF magic bytes
        assert response.content.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_export_pdf_filename_format_correct(self, client, mock_auth_dba):
        """GET /dashboard/export/pdf returns filename with date/time format (AC4)."""
        mock_stats = {"executions_jour": 0, "taux_succes_pct": 0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/pdf")

        assert response.status_code == status.HTTP_200_OK
        content_disposition = response.headers["content-disposition"]
        assert "dashboard-report-" in content_disposition
        assert ".pdf" in content_disposition
        # Pattern: dashboard-report-YYYY-MM-DD-HH-MM.pdf
        import re
        assert re.search(r'dashboard-report-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}\.pdf', content_disposition)

    @pytest.mark.asyncio
    async def test_export_pdf_with_filters_applied(self, client, mock_auth_dba):
        """GET /dashboard/export/pdf passes filters to repository (AC5)."""
        mock_stats = {"executions_jour": 5, "taux_succes_pct": 100.0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/pdf?engine=aap&environment=prod&days=30")

        assert response.status_code == status.HTTP_200_OK
        # Verify filters were passed to repository
        call_kwargs = mock_stats_get.call_args.kwargs
        assert call_kwargs["engine"] == "aap"
        assert call_kwargs["environment"] == "prod"
        assert call_kwargs["days"] == 30

    @pytest.mark.asyncio
    async def test_export_pdf_with_custom_date_range(self, client, mock_auth_dba):
        """GET /dashboard/export/pdf accepts custom date range."""
        mock_stats = {"executions_jour": 10, "taux_succes_pct": 90.0, "executions_en_cours": 0, "executions_en_erreur": 1}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/pdf?from_date=2026-01-01&to_date=2026-01-31")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_stats_get.call_args.kwargs
        assert call_kwargs["from_date"] == date(2026, 1, 1)
        assert call_kwargs["to_date"] == date(2026, 1, 31)

    @pytest.mark.asyncio
    async def test_export_pdf_forbidden_for_non_dba(self, client, mock_auth_viewer):
        """GET /dashboard/export/pdf returns 403 for non-DBA/DBOPS profiles (AC5.8)."""
        response = await client.get("/api/v1/dashboard/export/pdf")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_export_pdf_dbops_allowed(self, client, mock_auth_dbops):
        """GET /dashboard/export/pdf is accessible by DBOPS profile."""
        mock_stats = {"executions_jour": 0, "taux_succes_pct": 0, "executions_en_cours": 0, "executions_en_erreur": 0}

        with patch("app.api.v1.dashboard.execution_repository.get_dashboard_stats", new_callable=AsyncMock) as mock_stats_get, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_technology_for_export", new_callable=AsyncMock) as mock_tech, \
             patch("app.api.v1.dashboard.execution_repository.get_stats_by_environment_for_export", new_callable=AsyncMock) as mock_env, \
             patch("app.api.v1.dashboard.execution_repository.get_dashboard_timeseries", new_callable=AsyncMock) as mock_ts:
            mock_stats_get.return_value = mock_stats
            mock_tech.return_value = []
            mock_env.return_value = []
            mock_ts.return_value = []

            response = await client.get("/api/v1/dashboard/export/pdf")

        assert response.status_code == status.HTTP_200_OK


class TestExportModels:
    """Tests for export models (Story 8.5, Task 1)."""

    def test_dashboard_export_filters_info_to_display_string_empty(self):
        """DashboardExportFiltersInfo.to_display_string() returns 'Aucun' when empty."""
        from app.models.dashboard import DashboardExportFiltersInfo

        filters = DashboardExportFiltersInfo()
        assert filters.to_display_string() == "Aucun"

    def test_dashboard_export_filters_info_to_display_string_with_filters(self):
        """DashboardExportFiltersInfo.to_display_string() returns formatted string with filters."""
        from app.models.dashboard import DashboardExportFiltersInfo

        filters = DashboardExportFiltersInfo(
            engine="aap",
            environment="prod",
            tags=["oracle", "patch"],
            status="COMPLETED",
        )
        display = filters.to_display_string()
        assert "Moteur: aap" in display
        assert "Environnement: prod" in display
        assert "Tags: oracle, patch" in display
        assert "Statut: COMPLETED" in display

    def test_dashboard_export_period_info_validation(self):
        """DashboardExportPeriodInfo requires all fields."""
        from app.models.dashboard import DashboardExportPeriodInfo

        period = DashboardExportPeriodInfo(
            from_date="2026-01-01",
            to_date="2026-01-14",
            days=14,
        )
        assert period.from_date == "2026-01-01"
        assert period.to_date == "2026-01-14"
        assert period.days == 14
