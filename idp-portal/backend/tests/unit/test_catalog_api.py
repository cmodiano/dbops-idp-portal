"""Tests for catalog API endpoints (Story 2.3, AC #3).

Tests GET /api/v1/catalog/actions with RBAC filtering:
- Unauthenticated or unknown profile: all published actions (no filter)
- DBOPS: all published actions (no filter)
- Recognized profile (e.g. client_business, dba_applicatif): filtered by RBAC
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.core.security import create_access_token
from app.models.catalog import (
    ActionCategory,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionResponse,
    UserProfile,
)


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def sample_published_action():
    """Sample published ActionResponse for catalog list."""
    return ActionResponse(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        category=ActionCategory.PROVISIONING,
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        status=ActionStatus.PUBLISHED,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
    )


class TestListCatalogActions:
    """Tests for GET /api/v1/catalog/actions (Story 2.3, AC #3)."""

    @pytest.mark.asyncio
    async def test_list_catalog_actions_no_auth_returns_published(self, client, sample_published_action):
        """Without auth, returns all published actions (no RBAC filter)."""
        with patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [sample_published_action]

            response = await client.get("/api/v1/catalog/actions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "published"
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED, user_profile=None, tags_filter=None
        )

    @pytest.mark.asyncio
    async def test_list_catalog_actions_dbops_sees_all(self, client, sample_published_action):
        """DBOPS profile gets all published actions (no RBAC filter)."""
        token = create_access_token({"sub": "1", "username": "dbops-user", "profile": "dbops"})
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = [sample_published_action]

            response = await client.get(
                "/api/v1/catalog/actions",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["data"]) == 1
        # DBOPS: catalog_profile is set to None so no filter
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED, user_profile=None, tags_filter=None
        )

    @pytest.mark.asyncio
    async def test_list_catalog_actions_client_business_filtered(self, client, sample_published_action):
        """Client_business profile triggers RBAC filtering (invisible filter)."""
        token = create_access_token({"sub": "2", "username": "client-user", "profile": "client_business"})
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "client-user", "display_name": "Client", "profile": "client_business"
            })
            mock_list.return_value = [sample_published_action]

            response = await client.get(
                "/api/v1/catalog/actions",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED,
            user_profile=UserProfile.CLIENT_BUSINESS,
            tags_filter=None,
        )

    @pytest.mark.asyncio
    async def test_list_catalog_actions_dba_applicatif_filtered(self, client, sample_published_action):
        """DBA applicatif profile triggers RBAC filtering."""
        token = create_access_token({"sub": "3", "username": "dba-user", "profile": "dba_applicatif"})
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 3, "username": "dba-user", "display_name": "DBA App", "profile": "dba_applicatif"
            })
            mock_list.return_value = [sample_published_action]

            response = await client.get(
                "/api/v1/catalog/actions",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED,
            user_profile=UserProfile.DBA_APPLICATIF,
            tags_filter=None,
        )

    @pytest.mark.asyncio
    async def test_list_catalog_actions_filter_by_tags(self, client, sample_published_action):
        """GET /catalog/actions?tags=rac,dataguard passes tags_filter (Story 2.6, AC4)."""
        with patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = [sample_published_action]

            response = await client.get("/api/v1/catalog/actions?tags=rac,dataguard")

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(
            status=ActionStatus.PUBLISHED,
            user_profile=None,
            tags_filter=["rac", "dataguard"],
        )
