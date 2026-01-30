"""Inventory API response models (Story 4.2, Task 2.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InventoryItemResponse(BaseModel):
    """Response model for a single inventory item (Story 4.2, Task 2.3)."""

    id: str
    name: str
    environment: str | None = Field(None, description="Environment for databases/servers, null for environments")


class InventoryListResponse(BaseModel):
    """Response model for inventory list (Story 4.2, Task 2.3)."""

    data: list[InventoryItemResponse]
