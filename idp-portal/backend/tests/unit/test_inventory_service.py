"""Tests for inventory service (Story 4.1, Task 2.2; Story 4.2, Task 1)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from cachetools import TTLCache

from app.services.inventory_service import (
    InventoryType,
    InventoryItem,
    get_inventory_items,
    get_inventory_item_by_id,
    sync_inventory,
    get_inventory_items_from_cache,
)


class TestInventoryItem:
    """Tests for InventoryItem dataclass."""

    def test_inventory_item_to_dict(self):
        """InventoryItem.to_dict() returns expected dict."""
        item = InventoryItem(id="db1", name="Database 1", environment="dev")
        result = item.to_dict()
        assert result == {
            "id": "db1",
            "name": "Database 1",
            "environment": "dev",
        }

    def test_inventory_item_to_dict_without_environment(self):
        """InventoryItem.to_dict() handles None environment."""
        item = InventoryItem(id="env1", name="Development")
        result = item.to_dict()
        assert result["environment"] is None


class TestGetInventoryItems:
    """Tests for get_inventory_items (Task 2.2)."""

    @pytest.mark.asyncio
    async def test_get_environments_returns_list(self):
        """get_inventory_items(environments) returns dev, staging, prod."""
        items = await get_inventory_items(InventoryType.ENVIRONMENTS)
        assert len(items) >= 3
        ids = [item.id for item in items]
        assert "dev" in ids
        assert "staging" in ids
        assert "prod" in ids

    @pytest.mark.asyncio
    async def test_get_databases_returns_list(self):
        """get_inventory_items(databases) returns database list."""
        items = await get_inventory_items(InventoryType.DATABASES)
        assert len(items) > 0
        assert all(isinstance(item, InventoryItem) for item in items)
        assert all(item.environment in ("dev", "staging", "prod") for item in items)

    @pytest.mark.asyncio
    async def test_get_servers_returns_list(self):
        """get_inventory_items(servers) returns server list."""
        items = await get_inventory_items(InventoryType.SERVERS)
        assert len(items) > 0
        assert all(isinstance(item, InventoryItem) for item in items)

    @pytest.mark.asyncio
    async def test_get_databases_filtered_by_environment(self):
        """get_inventory_items(databases, environment='dev') returns only dev databases."""
        items = await get_inventory_items(InventoryType.DATABASES, environment="dev")
        assert len(items) > 0
        assert all(item.environment == "dev" for item in items)

    @pytest.mark.asyncio
    async def test_get_servers_filtered_by_environment(self):
        """get_inventory_items(servers, environment='prod') returns only prod servers."""
        items = await get_inventory_items(InventoryType.SERVERS, environment="prod")
        assert len(items) > 0
        assert all(item.environment == "prod" for item in items)

    @pytest.mark.asyncio
    async def test_get_environments_ignores_environment_filter(self):
        """get_inventory_items(environments) ignores environment filter (returns all)."""
        items = await get_inventory_items(InventoryType.ENVIRONMENTS, environment="dev")
        # Should still return all environments since environment filter doesn't apply
        ids = [item.id for item in items]
        assert "dev" in ids
        assert "staging" in ids
        assert "prod" in ids


class TestGetInventoryItemById:
    """Tests for get_inventory_item_by_id."""

    @pytest.mark.asyncio
    async def test_get_item_by_id_found(self):
        """get_inventory_item_by_id returns item when found."""
        result = await get_inventory_item_by_id(InventoryType.ENVIRONMENTS, "dev")
        assert result is not None
        assert result.id == "dev"
        assert result.name == "Development"

    @pytest.mark.asyncio
    async def test_get_item_by_id_not_found(self):
        """get_inventory_item_by_id returns None when not found."""
        result = await get_inventory_item_by_id(InventoryType.ENVIRONMENTS, "nonexistent")
        assert result is None


class TestSyncInventory:
    """Tests for sync_inventory (Story 4.2, Task 1.1)."""

    @pytest.mark.asyncio
    async def test_sync_inventory_success(self):
        """sync_inventory() successfully fetches and caches data from external API."""
        mock_response_databases = [
            {"id": "db1", "name": "Database 1", "environment": "dev"},
            {"id": "db2", "name": "Database 2", "environment": "prod"},
        ]
        mock_response_servers = [
            {"id": "srv1", "name": "Server 1", "environment": "dev"},
        ]
        mock_response_environments = [
            {"id": "dev", "name": "Development"},
            {"id": "prod", "name": "Production"},
        ]

        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.side_effect = [
                    mock_response_databases,
                    mock_response_servers,
                    mock_response_environments,
                ]
                await sync_inventory()

                # Verify cache was populated
                databases = await get_inventory_items_from_cache(InventoryType.DATABASES)
                assert len(databases) == 2
                assert databases[0].id == "db1"

    @pytest.mark.asyncio
    async def test_sync_inventory_api_error_keeps_cache(self):
        """sync_inventory() keeps existing cache when API call fails."""
        from app.services.inventory_service import _inventory_cache

        # First sync to populate cache
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [{"id": "db1", "name": "DB1", "environment": "dev"}]
                await sync_inventory()

        # Second sync fails but cache remains
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.side_effect = Exception("API Error")
                await sync_inventory()

                # Cache should still have old data
                databases = await get_inventory_items_from_cache(InventoryType.DATABASES)
                assert len(databases) == 1
                assert databases[0].id == "db1"

    @pytest.mark.asyncio
    async def test_sync_inventory_timeout_keeps_cache(self):
        """sync_inventory() handles timeout gracefully and keeps cache."""
        from httpx import TimeoutException

        # First sync to populate cache
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [{"id": "db1", "name": "DB1", "environment": "dev"}]
                await sync_inventory()

        # Second sync times out
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.side_effect = TimeoutException("Request timeout")
                await sync_inventory()

                # Cache should still have old data
                databases = await get_inventory_items_from_cache(InventoryType.DATABASES)
                assert len(databases) == 1


class TestInventoryCache:
    """Tests for inventory cache (Story 4.2, Task 1.2)."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self):
        """get_inventory_items_from_cache() returns cached data when available."""
        # Populate cache
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [{"id": "db1", "name": "DB1", "environment": "dev"}]
                await sync_inventory()

        # Should return from cache without API call
        items = await get_inventory_items_from_cache(InventoryType.DATABASES)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_cache_miss_returns_empty_list(self):
        """get_inventory_items_from_cache() returns empty list when cache is empty."""
        # Clear cache
        from app.services.inventory_service import _inventory_cache
        _inventory_cache.clear()

        items = await get_inventory_items_from_cache(InventoryType.DATABASES)
        assert items == []

    @pytest.mark.asyncio
    async def test_cache_structure(self):
        """Cache structure is correct (TTL testing requires freezegun for full validation)."""
        from app.services.inventory_service import _inventory_cache

        # Populate cache
        with patch("app.services.inventory_service.settings") as mock_settings:
            mock_settings.inventory_api_url = "http://test-api"
            with patch("app.services.inventory_service._fetch_from_external_api") as mock_fetch:
                mock_fetch.return_value = [{"id": "db1", "name": "DB1", "environment": "dev"}]
                await sync_inventory()

        # Verify cache structure
        assert isinstance(_inventory_cache, TTLCache)
        items = await get_inventory_items_from_cache(InventoryType.DATABASES)
        assert isinstance(items, list)
        assert len(items) == 1
