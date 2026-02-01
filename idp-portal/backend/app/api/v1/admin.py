"""Admin routes: protected by DBOPS profile requirement (Story 2.1, AC #5).

All endpoints require DBOPS profile for access.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.exceptions import NotFoundError, InvalidStateError
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.models.catalog import ActionCreate, ActionStatus, ExecutionStepsUpdate, RbacPoliciesUpdate
from app.repositories import catalog_repository
from app.repositories.catalog_repository import InvalidStateError as RepoInvalidStateError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status(user: UserProfile = Depends(require_profile("dbops"))):
    """Admin status endpoint. Requires DBOPS profile."""
    return {"data": {"status": "ok"}}


@router.post("/actions", status_code=status.HTTP_201_CREATED)
async def create_action(
    action: ActionCreate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Create a new action in the catalog (AC #5).

    Returns:
        HTTP 201 with { "data": ActionResponse }
    """
    result = await catalog_repository.create(action, user_id=user.id)
    return {"data": result.model_dump(mode="json")}


@router.get("/actions")
async def list_actions(
    status_filter: ActionStatus | None = None,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """List all actions in the catalog (AC #5).

    Args:
        status_filter: Optional filter by status (draft, published, disabled)

    Returns:
        { "data": list[ActionResponse] }
    """
    actions = await catalog_repository.list_all(status=status_filter)
    return {"data": [a.model_dump(mode="json") for a in actions]}


@router.get("/actions/{action_id}")
async def get_action(
    action_id: int,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Get action details by ID (AC #5).

    Returns:
        { "data": ActionDetail } or 404 if not found
    """
    action = await catalog_repository.get_by_id(action_id)
    if action is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )
    return {"data": action.model_dump(mode="json")}


@router.put("/actions/{action_id}/steps")
async def update_action_steps(
    action_id: int,
    data: ExecutionStepsUpdate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Update execution steps and change type config for an action (Story 2.2, AC #5).

    Only allowed for actions in 'draft' status.

    Returns:
        HTTP 200 with { "data": ActionDetail } on success
        HTTP 404 if action not found
        HTTP 400 if action is not in draft status
        HTTP 422 if validation fails
    """
    try:
        action = await catalog_repository.update_execution_steps(
            action_id,
            steps=data.steps,
            change_type_config=data.change_type_config,
        )
    except RepoInvalidStateError as e:
        raise InvalidStateError(
            code="INVALID_STATE",
            message=str(e),
            details={"status": e.current_status},
        )

    if action is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )

    return {"data": action.model_dump(mode="json")}


@router.put("/actions/{action_id}/rbac")
async def update_action_rbac(
    action_id: int,
    data: RbacPoliciesUpdate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Update RBAC policies for an action (Story 2.3, AC #4).

    Only allowed for actions in 'draft' status.

    Returns:
        HTTP 200 with { "data": ActionDetail } on success
        HTTP 404 if action not found
        HTTP 400 if action is not in draft status
        HTTP 422 if validation fails
    """
    try:
        action = await catalog_repository.update_rbac_policies(
            action_id,
            policies=data.policies,
        )
    except RepoInvalidStateError as e:
        raise InvalidStateError(
            code="INVALID_STATE",
            message=str(e),
            details={"status": e.current_status},
        )

    if action is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )

    return {"data": action.model_dump(mode="json")}
