"""Profiles CRUD API (Story 2.9, FR25a). Routes under /admin/profiles, RBAC require_profile(\"dbops\").

Cache invalidation: no RBAC/profile cache yet. When RBAC service (2.10–2.12) is in place,
invalidate on create/update/delete.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.exceptions import NotFoundError
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.models.profile import ProfileCreate, ProfileListItem, ProfileResponse, ProfileUpdate
from app.repositories import profile_repository

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=None)
async def list_profiles(
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/profiles — list all profiles (AC #3)."""
    items = await profile_repository.get_all()
    return {"data": [p.model_dump(mode="json") for p in items]}


@router.get("/{profile_id}", response_model=None)
async def get_profile(
    profile_id: int,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/profiles/{id} — get profile by ID (AC #2, #4)."""
    profile = await profile_repository.get_by_id(profile_id)
    if profile is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    return {"data": profile.model_dump(mode="json")}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_profile(
    payload: ProfileCreate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """POST /admin/profiles — create profile (AC #2, #5). Returns 201."""
    profile = await profile_repository.create(payload)
    return {"data": profile.model_dump(mode="json")}


@router.put("/{profile_id}", response_model=None)
async def update_profile(
    profile_id: int,
    payload: ProfileUpdate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """PUT /admin/profiles/{id} — update profile (AC #4)."""
    profile = await profile_repository.update(profile_id, payload)
    if profile is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    return {"data": profile.model_dump(mode="json")}


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: int,
    user: UserProfile = Depends(require_profile("dbops")),
) -> None:
    """DELETE /admin/profiles/{id} — delete profile. Returns 204 or 404."""
    deleted = await profile_repository.delete(profile_id)
    if not deleted:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
