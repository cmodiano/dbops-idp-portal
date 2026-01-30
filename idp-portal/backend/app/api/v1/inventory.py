"""Inventory API for execution wizard dropdowns (Story 4.1, Task 2.1; Story 4.2, Task 1.4).

Provides inventory data for dynamic form fields.
Story 4.2: implements real CMDB/inventory sync with cache.
"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.models.inventory import InventoryItemResponse, InventoryListResponse
from app.services.inventory_service import (
    InventoryType,
    get_inventory_items,
    get_inventory_items_from_cache,
    sync_inventory,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/{inventory_type}", response_model=InventoryListResponse)
async def list_inventory_items(
    inventory_type: str,
    environment: str | None = Query(None, description="Filter by environment (dev, staging, prod)"),
) -> InventoryListResponse:
    """GET /api/v1/inventory/{type} - List inventory items (Story 4.1, Task 2.1; Story 4.2, Task 2.1-2.2).

    Args:
        inventory_type: Type of inventory (databases, servers, environments)
        environment: Optional environment filter

    Returns:
        InventoryListResponse with list of inventory items from cache

    Raises:
        400: Invalid inventory type
        503: Inventory unavailable (cache empty and API configured but sync failed)
    """
    # Validate inventory type
    try:
        inv_type = InventoryType(inventory_type)
    except ValueError:
        valid_types = [t.value for t in InventoryType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid inventory type: {inventory_type}. Valid types: {valid_types}",
        ) from None

    # Get items from cache
    items = await get_inventory_items(inv_type, environment=environment)

    # Task 2.2: If cache empty and API URL configured, return 503 (inventory unavailable)
    api_url = getattr(settings, "inventory_api_url", None)
    if not items and api_url:
        # Check if cache is truly empty (not just filtered)
        cache_items = await get_inventory_items_from_cache(inv_type)
        if not cache_items:
            logger.warning(
                "inventory_unavailable",
                inventory_type=inventory_type,
                reason="cache_empty_and_api_configured",
            )
            raise ServiceUnavailableError(
                code="inventory_unavailable",
                message="L'inventaire est temporairement indisponible. Veuillez réessayer plus tard.",
            )

    # Task 2.1: Return empty list with warning log if cache empty (first request before sync)
    if not items:
        logger.warning("inventory_cache_empty", inventory_type=inventory_type)

    return InventoryListResponse(data=[InventoryItemResponse(**item.to_dict()) for item in items])


async def _sync_with_error_handling() -> None:
    """Run sync_inventory with error handling to avoid silently swallowed exceptions."""
    try:
        await sync_inventory()
    except Exception as e:
        logger.error("inventory_sync_background_error", error=str(e))


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_inventory_sync(
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """POST /api/v1/inventory/sync - Trigger inventory synchronization (Story 4.2, Task 1.4).

    Requires DBOPS profile. Sync runs asynchronously in background.

    Returns:
        { "data": { "status": "sync_started", "message": "..." } }
    """
    # Trigger sync asynchronously (non-blocking) with error handling
    asyncio.create_task(_sync_with_error_handling())

    return {
        "data": {
            "status": "sync_started",
            "message": "Synchronisation de l'inventaire démarrée en arrière-plan",
        }
    }
