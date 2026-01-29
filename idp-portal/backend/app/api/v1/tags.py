"""Tags API (Story 2.6, AC #5).

GET /api/v1/tags returns all tags. Public for catalogue autocomplete.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.repositories import catalog_repository

router = APIRouter()


@router.get("/tags")
async def list_tags() -> dict:
    """Return all tags (Story 2.6, AC #5).

    Used for autocomplete in admin Tags section and catalogue filter.
    Returns:
        { "data": list[TagResponse] }
    """
    tags = await catalog_repository.get_all_tags()
    return {"data": [t.model_dump(mode="json") for t in tags]}
