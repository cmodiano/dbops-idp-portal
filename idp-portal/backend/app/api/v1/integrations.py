"""Integrations CRUD API (Story 2.27). Routes under /admin/integrations, RBAC require_profile("dbops").

AC2: GET /integrations returns list (no secrets exposed).
AC3: POST/PUT create or update integrations.
AC4: All routes protected by DBOPS profile.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Path, status

from app.core.exceptions import InvalidStateError, NotFoundError
from app.core.security import require_profile
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

    Returns:
        HTTP 201 with { "data": IntegrationResponse }
        HTTP 400 if name already exists
        HTTP 422 if validation fails
    """
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

    Returns:
        HTTP 200 with { "data": IntegrationResponse }
        HTTP 400 if new name already exists
        HTTP 404 if not found
        HTTP 422 if validation fails
    """
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
