"""User-related routes: favorites, recent actions (Story 3.1 AC4, AC5, AC12, AC13).

Routes under /users/me for current user operations.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.auth import UserProfile
from app.repositories import catalog_repository, favorites_repository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/favorites", response_model=None)
async def list_favorites(
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/users/me/favorites — list user's favorite actions (AC12).

    Returns:
        { "data": [ { "action_id", "created_at" } ] }
    """
    favorites = await favorites_repository.list_favorites(user.id)
    return {
        "data": [
            {
                "action_id": f["action_id"],
                "created_at": f["created_at"].isoformat() if f["created_at"] else None,
            }
            for f in favorites
        ]
    }


@router.post("/me/favorites/{action_id}", status_code=status.HTTP_201_CREATED, response_model=None)
async def add_favorite(
    action_id: int,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """POST /api/v1/users/me/favorites/{action_id} — add action to favorites (AC13).

    Idempotent: returns 201 even if already a favorite.
    Returns 404 if action does not exist.

    Returns:
        { "data": { "action_id", "message" } }
    """
    existing = await catalog_repository.get_by_id(action_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action introuvable",
        )
    await favorites_repository.add_favorite(user_id=user.id, action_id=action_id)
    return {"data": {"action_id": action_id, "message": "Action ajoutée aux favoris"}}


@router.delete("/me/favorites/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(
    action_id: int,
    user: UserProfile = Depends(get_current_user),
) -> None:
    """DELETE /api/v1/users/me/favorites/{action_id} — remove action from favorites (AC13).

    Idempotent: returns 204 even if not a favorite.
    """
    await favorites_repository.remove_favorite(user_id=user.id, action_id=action_id)


@router.get("/me/recent-actions", response_model=None)
async def list_recent_actions(
    limit: int = 10,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """GET /api/v1/users/me/recent-actions — list recently executed actions (AC5).

    Args:
        limit: Maximum number of actions to return (default 10, max 50)

    Returns:
        { "data": [ { "action_id", "name", "last_executed_at" } ] }
    """
    limit = min(limit, 50)  # Cap at 50
    recent = await favorites_repository.list_recent_actions(user_id=user.id, limit=limit)
    return {
        "data": [
            {
                "action_id": r["action_id"],
                "name": r["name"],
                "last_executed_at": r["last_executed_at"].isoformat() if r["last_executed_at"] else None,
            }
            for r in recent
        ]
    }
