"""Tests for inventory API endpoints (Story 4.1, Task 2.1; Story 4.2, Task 1.4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status, HTTPException

from app.main import app


def _make_token(profile: str = "dbops", username: str = "test") -> str:
    """Helper to create JWT token for testing."""
    from app.core.security import create_access_token

    return create_access_token({"sub": "1", "username": username, "profile": profile})


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestListInventoryItems:
    """Tests for GET /api/v1/inventory/{type} (Task 2.1)."""

    @pytest.mark.asyncio
    async def test_get_environments_success(self, client):
        """GET /inventory/environments returns list of environments."""
        response = await client.get("/api/v1/inventory/environments")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 3

        # Check structure
        item = data["data"][0]
        assert "id" in item
        assert "name" in item
        assert "environment" in item

    @pytest.mark.asyncio
    async def test_get_databases_success(self, client):
        """GET /inventory/databases returns list of databases."""
        response = await client.get("/api/v1/inventory/databases")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_get_servers_success(self, client):
        """GET /inventory/servers returns list of servers."""
        response = await client.get("/api/v1/inventory/servers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_get_databases_filtered_by_environment(self, client):
        """GET /inventory/databases?environment=dev returns only dev databases."""
        response = await client.get("/api/v1/inventory/databases?environment=dev")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(item["environment"] == "dev" for item in data["data"])

    @pytest.mark.asyncio
    async def test_get_servers_filtered_by_environment(self, client):
        """GET /inventory/servers?environment=prod returns only prod servers."""
        response = await client.get("/api/v1/inventory/servers?environment=prod")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(item["environment"] == "prod" for item in data["data"])

    @pytest.mark.asyncio
    async def test_invalid_inventory_type_returns_400(self, client):
        """GET /inventory/invalid returns 400 with error message."""
        response = await client.get("/api/v1/inventory/invalid_type")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid inventory type" in response.json()["detail"]
        assert "databases" in response.json()["detail"]  # Lists valid types

    @pytest.mark.asyncio
    async def test_environments_contain_dev_staging_prod(self, client):
        """GET /inventory/environments includes dev, staging, prod."""
        response = await client.get("/api/v1/inventory/environments")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ids = [item["id"] for item in data["data"]]
        assert "dev" in ids
        assert "staging" in ids
        assert "prod" in ids

    @pytest.mark.asyncio
    async def test_response_structure_matches_spec(self, client):
        """Response follows { "data": [ { "id", "name", "environment" } ] } structure."""
        response = await client.get("/api/v1/inventory/databases")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, dict)
        assert "data" in data
        assert isinstance(data["data"], list)

        if len(data["data"]) > 0:
            item = data["data"][0]
            assert "id" in item
            assert "name" in item
            assert "environment" in item


class TestSyncInventory:
    """Tests for POST /api/v1/inventory/sync (Story 4.2, Task 1.4)."""

    @pytest.mark.asyncio
    async def test_sync_inventory_dbps_authorized(self, client):
        """POST /inventory/sync returns 202 Accepted for DBOPS user."""
        token = _make_token(profile="dbops")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "test", "display_name": "Test", "profile": "dbops",
            })
            with patch("app.api.deps.profile_repository") as mock_profile_repo:
                mock_profile_repo.find_by_ad_groups = AsyncMock(return_value=[
                    MagicMock(id=1, name="dbops")
                ])
                with patch("app.services.inventory_service.sync_inventory") as mock_sync:
                    response = await client.post(
                        "/api/v1/inventory/sync",
                        headers={"Authorization": f"Bearer {token}"},
                    )

                    assert response.status_code == status.HTTP_202_ACCEPTED
                    data = response.json()
                    assert "data" in data
                    assert data["data"]["status"] == "sync_started"
                    # Note: sync_inventory is called asynchronously, so we can't assert it was called

    @pytest.mark.asyncio
    async def test_sync_inventory_dba_forbidden(self, client):
        """POST /inventory/sync returns 403 Forbidden for DBA user."""
        token = _make_token(profile="dba_applicatif")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba", "display_name": "DBA User", "profile": "dba_applicatif",
            })
            response = await client.post(
                "/api/v1/inventory/sync",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_sync_inventory_response_structure(self, client):
        """POST /inventory/sync returns correct response structure."""
        token = _make_token(profile="dbops")
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "test", "display_name": "Test", "profile": "dbops",
            })
            with patch("app.api.deps.profile_repository") as mock_profile_repo:
                mock_profile_repo.find_by_ad_groups = AsyncMock(return_value=[
                    MagicMock(id=1, name="dbops")
                ])
                response = await client.post(
                    "/api/v1/inventory/sync",
                    headers={"Authorization": f"Bearer {token}"},
                )

                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                assert "data" in data
                assert "status" in data["data"]
                assert "message" in data["data"]
                assert data["data"]["status"] == "sync_started"
