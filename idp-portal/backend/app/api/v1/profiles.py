"""Profiles CRUD API (Story 2.9, FR25a). Routes under /admin/profiles, RBAC require_profile(\"dbops\").

Story 2.12: invalidate cumulative permissions cache on profile/permissions CRUD (AC5).
Story 2.13: GET /export, POST /import YAML (AC1, AC2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import InvalidStateError, NotFoundError
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.services import rbac_service
from app.services import profile_export_import_service
from app.models.profile import (
    ProfileActionPermissionsUpdate,
    ProfileActionPermissionsResponse,
    ProfileCreate,
    ProfileListItem,
    ProfileResponse,
    ProfileUpdate,
    ProfileTargetPermissionsUpdate,
    ProfileTargetPermissionsResponse,
)
from app.repositories import profile_repository
from app.repositories import profile_action_permission_repository
from app.repositories import profile_target_permission_repository

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=None)
async def list_profiles(
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/profiles — list all profiles (AC #3)."""
    items = await profile_repository.get_all()
    return {"data": [p.model_dump(mode="json") for p in items]}


@router.get("/export", response_class=Response)
async def export_profiles_yaml_route(
    user: UserProfile = Depends(require_profile("dbops")),
) -> Response:
    """GET /admin/profiles/export — download profiles as YAML (Story 2.13, AC1, AC5)."""
    content = await profile_export_import_service.export_profiles_yaml()
    return Response(
        content=content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=profiles.yaml"},
    )


@router.post("/import", response_model=None)
async def import_profiles_yaml_route(
    file: UploadFile = File(..., description="Fichier YAML (.yaml, .yml)"),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """POST /admin/profiles/import — import profiles from YAML (Story 2.13, AC2, AC3, AC4)."""
    if not file.filename or not (file.filename.endswith(".yaml") or file.filename.endswith(".yml")):
        raise InvalidStateError(
            code="INVALID_FILE",
            message="Le fichier doit être un YAML (.yaml ou .yml).",
            details={"filename": file.filename or ""},
        )
    content = await file.read()
    try:
        created, updated = await profile_export_import_service.import_profiles_yaml(content)
    except InvalidStateError:
        raise
    rbac_service.invalidate_permissions_cache()
    payload = {"data": {"created": created, "updated": updated}}
    if updated == 0 and created > 0:
        return JSONResponse(content=payload, status_code=status.HTTP_201_CREATED)
    return payload


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
    rbac_service.invalidate_permissions_cache()
    return {"data": profile.model_dump(mode="json")}


@router.put("/{profile_id}/actions", response_model=None)
async def set_profile_actions(
    profile_id: int,
    payload: ProfileActionPermissionsUpdate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """PUT /admin/profiles/{id}/actions — set actions/env permissions (AC2–AC5). Returns 200 with updated data."""
    existing = await profile_repository.get_by_id(profile_id)
    if existing is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    result = await profile_action_permission_repository.set_actions_permissions(profile_id, payload)
    rbac_service.invalidate_permissions_cache()
    return {"data": result.model_dump(mode="json")}


@router.get("/{profile_id}/actions", response_model=None)
async def get_profile_actions(
    profile_id: int,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/profiles/{id}/actions — get actions permissions (AC2–AC5). Default 'all' when no row."""
    existing = await profile_repository.get_by_id(profile_id)
    if existing is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    perms = await profile_action_permission_repository.get_actions_permissions(profile_id)
    if perms is None:
        perms = ProfileActionPermissionsResponse(
            actions_type="all",
            action_ids=[],
            tag_patterns=[],
            environments=[],
        )
    return {"data": perms.model_dump(mode="json")}


@router.put("/{profile_id}/targets", response_model=None)
async def set_profile_targets(
    profile_id: int,
    payload: ProfileTargetPermissionsUpdate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """PUT /admin/profiles/{id}/targets — set target permissions (AC2, AC3, AC5). Returns 200 with updated data."""
    existing = await profile_repository.get_by_id(profile_id)
    if existing is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    result = await profile_target_permission_repository.set_target_permissions(profile_id, payload)
    rbac_service.invalidate_permissions_cache()
    return {"data": result.model_dump(mode="json")}


@router.get("/{profile_id}/targets", response_model=None)
async def get_profile_targets(
    profile_id: int,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/profiles/{id}/targets — get target permissions (AC1–AC5). Default 'all' when no row."""
    existing = await profile_repository.get_by_id(profile_id)
    if existing is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Profil {profile_id} introuvable",
            details={"profile_id": profile_id},
        )
    perms = await profile_target_permission_repository.get_target_permissions(profile_id)
    if perms is None:
        perms = ProfileTargetPermissionsResponse(
            targets_type="all",
            target_names=[],
            target_patterns=[],
        )
    return {"data": perms.model_dump(mode="json")}


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
    rbac_service.invalidate_permissions_cache()
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
    rbac_service.invalidate_permissions_cache()