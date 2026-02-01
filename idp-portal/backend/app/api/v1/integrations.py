"""Integrations CRUD API (Story 2.27, 4.9). Routes under /admin/integrations, RBAC require_profile("dbops").

AC2: GET /integrations returns list (no secrets exposed).
AC3: POST/PUT create or update integrations.
AC4: All routes protected by DBOPS profile.
Story 4.9: POST /upload-icon for icon file upload.
"""

from __future__ import annotations

import uuid
from pathlib import Path as FilePath

from fastapi import APIRouter, Body, Depends, File, Path, UploadFile, status

from app.core.config import settings
from app.core.exceptions import InvalidStateError, NotFoundError
from app.core.security import require_profile
from app.schemas.integration_config import validate_integration_config
from app.models.auth import UserProfile
from app.models.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
)
from app.repositories import integration_repository
from app.repositories.integration_repository import DuplicateNameError

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=None)
async def list_integrations(
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/integrations — list all integrations (AC2).

    Returns list of integrations ordered by name. No secrets exposed (credential_ref is reference only).
    """
    items = await integration_repository.get_all()
    return {"data": [i.model_dump(mode="json") for i in items]}


@router.get("/{integration_id}", response_model=None)
async def get_integration(
    integration_id: int = Path(..., ge=1, description="Integration ID (≥1)"),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """GET /admin/integrations/{id} — get integration by ID (AC2).

    Returns:
        { "data": IntegrationResponse } or 404 if not found
    """
    integration = await integration_repository.get_by_id(integration_id)
    if integration is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Integration {integration_id} introuvable",
            details={"integration_id": integration_id},
        )
    return {"data": integration.model_dump(mode="json")}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_integration(
    payload: IntegrationCreate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """POST /admin/integrations — create integration (AC3).

    Validates type (enum), name (unique, non-empty), base_url (valid URL).
    credential_ref and icon are optional.
    config (optional): validated against JSON Schema (backend/app/schemas/integration_config_schema.json).
    If invalid → 400 with error.code "INVALID_CONFIG", error.details: { "field", "error", "schema_path" }.

    Returns:
        HTTP 201 with { "data": IntegrationResponse }
        HTTP 400 if name already exists or config invalid (Story 5.4; code INVALID_CONFIG, details.field/details.error)
        HTTP 422 if validation fails
    """
    if payload.config is not None and payload.config:
        validate_integration_config(payload.config)
    try:
        integration = await integration_repository.create(payload)
    except DuplicateNameError as e:
        raise InvalidStateError(
            code="DUPLICATE_NAME",
            message=str(e),
            details={"name": e.name},
        )
    return {"data": integration.model_dump(mode="json")}


@router.put("/{integration_id}", response_model=None)
async def update_integration(
    integration_id: int = Path(..., ge=1, description="Integration ID (≥1)"),
    payload: IntegrationUpdate = Body(...),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """PUT /admin/integrations/{id} — update integration (AC3).

    Partial update: only provided fields are updated.
    config (if provided): validated against JSON Schema; invalid → 400 INVALID_CONFIG (details.field, details.error).

    Returns:
        HTTP 200 with { "data": IntegrationResponse }
        HTTP 400 if new name already exists or config invalid (Story 5.4; code INVALID_CONFIG)
        HTTP 404 if not found
        HTTP 422 if validation fails
    """
    if payload.config is not None and payload.config:
        validate_integration_config(payload.config)
    try:
        integration = await integration_repository.update(integration_id, payload)
    except DuplicateNameError as e:
        raise InvalidStateError(
            code="DUPLICATE_NAME",
            message=str(e),
            details={"name": e.name},
        )

    if integration is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Integration {integration_id} introuvable",
            details={"integration_id": integration_id},
        )
    return {"data": integration.model_dump(mode="json")}


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: int = Path(..., ge=1, description="Integration ID (≥1)"),
    user: UserProfile = Depends(require_profile("dbops")),
) -> None:
    """DELETE /admin/integrations/{id} — delete integration (AC3).

    Returns:
        HTTP 204 on success
        HTTP 404 if not found
    """
    deleted = await integration_repository.delete(integration_id)
    if not deleted:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Integration {integration_id} introuvable",
            details={"integration_id": integration_id},
        )


@router.post("/upload-icon", status_code=status.HTTP_201_CREATED, response_model=None)
async def upload_icon(
    file: UploadFile = File(...),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """POST /admin/integrations/upload-icon — upload integration icon (Story 4.9, AC3).

    Accepts multipart/form-data with image file (PNG, JPEG, SVG).
    Validates MIME type and size (max 2MB).
    Stores file locally in backend/static/icons/ with unique UUID filename.

    Returns:
        HTTP 201 with { "data": { "icon_url": "/static/icons/{uuid}.{ext}" } }
        HTTP 400 if validation fails (invalid MIME type, size > 2MB, no file)
    """
    # Validation: MIME type (image/png, image/jpeg, image/svg+xml)
    allowed_mime_types = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml"}
    if file.content_type not in allowed_mime_types:
        raise InvalidStateError(
            code="INVALID_FILE_TYPE",
            message=f"Type MIME invalide: {file.content_type}. Acceptés: PNG, JPEG, SVG.",
            details={"content_type": file.content_type, "allowed": list(allowed_mime_types)},
        )

    # Read file content
    content = await file.read()

    # Validation: size max 2MB
    max_size_mb = 2
    max_size_bytes = max_size_mb * 1024 * 1024
    if len(content) > max_size_bytes:
        raise InvalidStateError(
            code="FILE_TOO_LARGE",
            message=f"Fichier trop volumineux: {len(content)} bytes. Maximum: {max_size_mb}MB.",
            details={"size_bytes": len(content), "max_bytes": max_size_bytes},
        )

    # Generate unique filename with UUID
    file_ext = FilePath(file.filename or "icon.png").suffix or ".png"
    unique_filename = f"{uuid.uuid4()}{file_ext}"

    # Create static/icons directory if doesn't exist (Story 4.9, LOW-9 fix: centralized path)
    icons_dir = settings.get_static_path() / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Write file to disk
    icon_path = icons_dir / unique_filename
    with open(icon_path, "wb") as f:
        f.write(content)

    # Return relative URL for frontend use
    icon_url = f"/static/icons/{unique_filename}"
    return {"data": {"icon_url": icon_url}}
