"""Integration tests for inventory sync and cache (Story 4.2, Task 5.3).

Tests the complete flow: periodic sync, HTTP client to external inventory,
cache persistence between requests.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from app.services.inventory_service import (
    InventoryType,
    sync_inventory,
    get_inventory_items_from_cache,
    get_inventory_items,
)
from app.api.v1.inventory import list_inventory_items
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestInventorySyncFlow:
    """Integration tests for inventory sync flow (Story 4.2, Task 5.3)."""

    @pytest.mark.asyncio
    async def test_sync_persists_cache_between_requests(self):
        """Cache persists between multiple GET requests after sync."""
        from app.services.inventory_service import _inventory_cache

        # Clear cache first
        _inventory_cache.clear()

        # Mock external API responses
        mock_responses = {
            InventoryType.DATABASES: [
                {"id": "db1", "name": "Database 1", "environment": "dev"},
                {"id": "db2", "name": "Database 2", "environment": "prod"},
            ],
            InventoryType.SERVERS: [
                {"id": "srv1", "name": "Server 1", "environment": "dev"},
            ],
            InventoryType.ENVIRONMENTS: [
                {"id": "dev", "name": "Development"},
                {"id": "prod", "name": "Production"},
            ],
        }

        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                def fetch_side_effect(inv_type):
                    return mock_responses.get(inv_type, [])

                mock_fetch.side_effect = fetch_side_effect

                # Sync inventory
                await sync_inventory()

                # First request - should use cache
                items1 = await get_inventory_items(InventoryType.DATABASES)
                assert len(items1) == 2

                # Second request - should still use same cache (no new API calls)
                items2 = await get_inventory_items(InventoryType.DATABASES)
                assert len(items2) == 2
                assert items1[0].id == items2[0].id

                # Verify API was called only once per type during sync
                assert mock_fetch.call_count == 3  # Once for each type

    @pytest.mark.asyncio
    async def test_http_client_mock_external_inventory(self):
        """Test HTTP client integration with mocked external inventory API."""
        from app.services.inventory_service import _fetch_from_external_api

        # Mock httpx.AsyncClient
        mock_response_data = [
            {"id": "db1", "name": "Database 1", "environment": "dev"},
            {"id": "db2", "name": "Database 2", "environment": "prod"},
        ]

        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-inventory-api"
            mock_settings.inventory_api_timeout = 30
            mock_settings.inventory_api_token = None

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.json.return_value = {"data": mock_response_data}
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.return_value = mock_response
                mock_client_class.return_value = mock_client

                # Fetch from external API
                result = await _fetch_from_external_api(InventoryType.DATABASES)

                assert len(result) == 2
                assert result[0]["id"] == "db1"
                mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_persistence_across_multiple_syncs(self):
        """Cache persists and updates correctly across multiple sync operations."""
        from app.services.inventory_service import _inventory_cache

        _inventory_cache.clear()

        # First sync
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [{"id": "db1", "name": "DB1", "environment": "dev"}]
                await sync_inventory()

                items1 = await get_inventory_items_from_cache(InventoryType.DATABASES)
                assert len(items1) == 1
                assert items1[0].id == "db1"

        # Second sync with updated data
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [
                    {"id": "db1", "name": "DB1 Updated", "environment": "dev"},
                    {"id": "db2", "name": "DB2", "environment": "prod"},
                ]
                await sync_inventory()

                items2 = await get_inventory_items_from_cache(InventoryType.DATABASES)
                assert len(items2) == 2
                assert items2[0].name == "DB1 Updated"
                assert items2[1].id == "db2"

    @pytest.mark.asyncio
    async def test_endpoint_uses_cache_after_sync(self, client):
        """GET /inventory/{type} endpoint uses cache populated by sync."""
        from app.services.inventory_service import _inventory_cache

        _inventory_cache.clear()

        # Populate cache via sync
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [
                    {"id": "db1", "name": "Database 1", "environment": "dev"},
                ]
                await sync_inventory()

        # Call endpoint - should use cache
        response = await client.get("/api/v1/inventory/databases")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "db1"
