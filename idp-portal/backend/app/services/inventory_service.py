"""Inventory service for dropdown data (Story 4.1, Task 2.2; Story 4.2, Task 1).

Provides inventory items for execution wizard dropdowns.
Story 4.2: implements real sync from external inventory API with in-memory cache.

Interface designed to be compatible with future CMDB/inventory integration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
import structlog
from cachetools import TTLCache

from app.core.config import settings

logger = structlog.get_logger()


class InventoryType(str, Enum):
    """Supported inventory types (Story 4.1, Task 2.1)."""
    DATABASES = "databases"
    SERVERS = "servers"
    ENVIRONMENTS = "environments"


@dataclass
class InventoryItem:
    """Inventory item for dropdown (Story 4.1, Task 2.1).

    Attributes:
        id: Unique identifier (string or number)
        name: Display name
        environment: Associated environment (optional, for databases/servers)
    """
    id: str
    name: str
    environment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        return {
            "id": self.id,
            "name": self.name,
            "environment": self.environment,
        }


# Story 4.2: Cache in-memory avec TTLCache (Task 1.2)
_inventory_cache: TTLCache[str, list[InventoryItem]] = TTLCache(
    maxsize=1000,
    ttl=getattr(settings, "inventory_cache_ttl_seconds", 3600),
)

# Fallback mock data si API externe indisponible (Story 4.1 compatibility)
_MOCK_ENVIRONMENTS = [
    InventoryItem(id="dev", name="Development", environment=None),
    InventoryItem(id="staging", name="Staging", environment=None),
    InventoryItem(id="prod", name="Production", environment=None),
]


async def _fetch_from_external_api(inventory_type: InventoryType) -> list[dict[str, Any]]:
    """Fetch inventory data from external API (Story 4.2, Task 3.1).

    Args:
        inventory_type: Type of inventory to fetch

    Returns:
        List of raw inventory items as dicts

    Raises:
        httpx.HTTPStatusError: On HTTP errors
        httpx.TimeoutException: On timeout
        Exception: On other errors
    """
    api_url = getattr(settings, "inventory_api_url", None)
    if not api_url:
        logger.warning("inventory_api_url_not_configured", inventory_type=inventory_type.value)
        return []

    timeout_seconds = getattr(settings, "inventory_api_timeout", 30)
    api_timeout = httpx.Timeout(timeout_seconds)

    # Build endpoint URL (assumes REST API: /api/v1/{type})
    endpoint = f"{api_url.rstrip('/')}/api/v1/{inventory_type.value}"

    # Prepare headers (authentication if configured)
    headers: dict[str, str] = {}
    auth_token = getattr(settings, "inventory_api_token", None)
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Handle different response formats
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            elif isinstance(data, list):
                return data
            else:
                logger.warning("inventory_api_unexpected_format", inventory_type=inventory_type.value)
                return []
    except httpx.HTTPStatusError as e:
        logger.error(
            "inventory_api_http_error",
            inventory_type=inventory_type.value,
            status_code=e.response.status_code,
            error=str(e),
        )
        raise
    except httpx.TimeoutException as e:
        logger.warning("inventory_api_timeout", inventory_type=inventory_type.value, error=str(e))
        raise
    except Exception as e:
        logger.error("inventory_api_error", inventory_type=inventory_type.value, error=str(e))
        raise


def _map_external_to_internal(raw_items: list[dict[str, Any]], inventory_type: InventoryType) -> list[InventoryItem]:
    """Map external API response to internal InventoryItem format (Story 4.2, Task 3.2).

    Args:
        raw_items: Raw items from external API
        inventory_type: Type of inventory

    Returns:
        List of InventoryItem objects
    """
    result: list[InventoryItem] = []

    for item in raw_items:
        try:
            # Extract required fields (flexible mapping)
            item_id = str(item.get("id", item.get("name", "")))
            name = str(item.get("name", item_id))
            environment = item.get("environment") if inventory_type != InventoryType.ENVIRONMENTS else None

            if item_id:
                result.append(InventoryItem(id=item_id, name=name, environment=environment))
        except Exception as e:
            logger.warning("inventory_item_mapping_failed", item=item, error=str(e))
            continue

    return result


async def sync_inventory() -> None:
    """Synchronize inventory from external API and update cache (Story 4.2, Task 1.1).

    Fetches data for all inventory types and stores in cache.
    On error, keeps existing cache and logs warning.
    """
    api_url = getattr(settings, "inventory_api_url", None)
    if not api_url:
        logger.debug("inventory_sync_skipped_no_url")
        return

    logger.info("inventory_sync_started")

    for inv_type in InventoryType:
        try:
            raw_items = await _fetch_from_external_api(inv_type)
            mapped_items = _map_external_to_internal(raw_items, inv_type)

            # Update cache
            _inventory_cache[inv_type.value] = mapped_items

            logger.info(
                "inventory_sync_success",
                inventory_type=inv_type.value,
                item_count=len(mapped_items),
            )
        except httpx.HTTPStatusError as e:
            # HTTP errors: log but keep cache
            logger.warning(
                "inventory_sync_http_error",
                inventory_type=inv_type.value,
                status_code=e.response.status_code,
            )
        except httpx.TimeoutException:
            # Timeout: log but keep cache
            logger.warning("inventory_sync_timeout", inventory_type=inv_type.value)
        except Exception as e:
            # Other errors: log but keep cache
            logger.warning("inventory_sync_error", inventory_type=inv_type.value, error=str(e))

    logger.info("inventory_sync_completed")


async def get_inventory_items_from_cache(inventory_type: InventoryType) -> list[InventoryItem]:
    """Get inventory items from cache (Story 4.2, Task 1.2).

    Args:
        inventory_type: Type of inventory

    Returns:
        List of InventoryItem from cache, or empty list if cache miss
    """
    cached = _inventory_cache.get(inventory_type.value)
    if cached is not None:
        return cached

    # Cache miss: return empty list (or fallback mock for environments)
    if inventory_type == InventoryType.ENVIRONMENTS:
        return _MOCK_ENVIRONMENTS
    return []


async def get_inventory_items(
    inventory_type: InventoryType,
    environment: str | None = None,
) -> list[InventoryItem]:
    """Get inventory items by type (Story 4.1, Task 2.2; Story 4.2, Task 2.1).

    Story 4.2: reads from cache populated by sync_inventory().

    Args:
        inventory_type: Type of inventory (databases, servers, environments)
        environment: Optional filter by environment

    Returns:
        List of InventoryItem matching the criteria
    """
    logger.debug(
        "inventory_service_get_items",
        inventory_type=inventory_type.value,
        environment=environment,
    )

    items = await get_inventory_items_from_cache(inventory_type)

    # Filter by environment if specified
    if environment:
        items = [item for item in items if item.environment == environment]

    return items


async def get_inventory_item_by_id(
    inventory_type: InventoryType,
    item_id: str,
) -> InventoryItem | None:
    """Get single inventory item by ID (Story 4.1).

    Args:
        inventory_type: Type of inventory
        item_id: Item identifier

    Returns:
        InventoryItem if found, None otherwise
    """
    items = await get_inventory_items(inventory_type)
    for item in items:
        if item.id == item_id:
            return item
    return None
