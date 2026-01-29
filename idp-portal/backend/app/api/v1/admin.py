"""Admin routes: protected by DBOPS profile requirement (Story 2.1, AC #5).

All endpoints require DBOPS profile for access.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import NotFoundError, InvalidStateError
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.models.catalog import (
    ActionCreate,
    ActionResponse,
    ActionDetail,
    ActionStatus,
    ActionCategory,
    ActionEngine,
    ExecutionStepsUpdate,
    RbacPoliciesUpdate,
    StatusUpdateRequest,
    ActionTagsUpdateRequest,
    InvalidTransitionError,
    ActionListResponse,
)
from app.repositories import catalog_repository
from app.repositories.catalog_repository import InvalidStateError as RepoInvalidStateError

from app.api.v1 import profiles

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(profiles.router)


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


@router.get("/actions", response_model=ActionListResponse)
async def list_actions(
    status: ActionStatus | None = None,
    category: ActionCategory | None = None,
    engine: ActionEngine | None = None,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(25, ge=1, description="Items per page"),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """List all actions for admin dashboard (Story 2.4, AC #2).

    Returns all actions (all statuses) with execution counts.
    No RBAC filtering - DBOPS sees everything.

    Args:
        status: Optional filter by status (draft, published, disabled)
        category: Optional filter by category
        engine: Optional filter by engine
        page: Page number (1-based, default 1)
        page_size: Items per page (default 25)

    Returns:
        { "data": list[ActionListItem], "pagination": PaginationInfo }
    """
    actions, pagination = await catalog_repository.list_all_admin(
        status=status,
        category=category,
        engine=engine,
        page=page,
        page_size=page_size,
    )
    return {
        "data": [a.model_dump(mode="json") for a in actions],
        "pagination": pagination.model_dump(mode="json"),
    }


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
    """Update execution steps and change type config for an action (Story 2.2, AC #5; Story 2.7 connector_type).

    Body: steps with connector_type (aap, servicenow, azuredevops, jira, github_actions, terraform, none)
    and connector_config; conditional_environments required when connector_type is servicenow.
    Only allowed for actions in 'draft' status.

    Returns:
        HTTP 200 with { "data": ActionDetail } on success
        HTTP 404 if action not found
        HTTP 400 if action is not in draft status
        HTTP 422 if validation fails (e.g. servicenow without conditional_environments)
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


@router.put("/actions/{action_id}")
async def update_action_metadata(
    action_id: int,
    data: ActionCreate,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Update action metadata (Story 2.4, AC #3).

    Allowed for all statuses (published actions can have metadata updated).
    Execution steps and RBAC can only be changed in draft status.

    Returns:
        HTTP 200 with { "data": ActionDetail } on success
        HTTP 404 if action not found
        HTTP 422 if validation fails
    """
    action = await catalog_repository.update_action(
        action_id,
        action_update=data,
        user_id=str(user.id),
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


@router.put("/actions/{action_id}/tags")
async def update_action_tags(
    action_id: int,
    data: ActionTagsUpdateRequest,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Update tags for an action (Story 2.6, AC #5).

    Body: { "tag_ids": [1, 2, 3] } or { "tag_names": ["rac", "dataguard"] }.
    tag_names creates missing tags on the fly (create_tag_if_not_exists).
    Replaces all tags for the action.

    Returns:
        { "data": ActionDetail } or 404 if action not found
    """
    action = await catalog_repository.get_by_id(action_id)
    if action is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )
    if data.tag_names is not None:
        seen: set[str] = set()
        tag_ids = []
        for n in data.tag_names:
            if n not in seen:
                seen.add(n)
                tag_ids.append(await catalog_repository.create_tag_if_not_exists(n))
    else:
        tag_ids = data.tag_ids or []
    await catalog_repository.set_action_tags(action_id, tag_ids)
    updated = await catalog_repository.get_by_id(action_id)
    if updated is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )
    return {"data": updated.model_dump(mode="json")}


@router.patch("/actions/{action_id}/status")
async def update_action_status(
    action_id: int,
    data: StatusUpdateRequest,
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """Update action status via a valid transition (Story 2.4, AC #1, #4, #5).

    Valid transitions:
    - draft -> published (publish)
    - published -> disabled (disable)
    - disabled -> published (enable)

    Returns:
        HTTP 200 with { "data": ActionDetail } on success
        HTTP 404 if action not found
        HTTP 400 if transition is invalid for current status
    """
    try:
        action = await catalog_repository.update_status(
            action_id,
            transition=data.transition,
            user_id=str(user.id),
        )
    except InvalidTransitionError as e:
        raise InvalidStateError(
            code="INVALID_STATE",
            message=str(e),
            details={"current_status": e.current_status, "transition": e.transition},
        )

    if action is None:
        raise NotFoundError(
            code="NOT_FOUND",
            message=f"Action {action_id} introuvable",
            details={"action_id": action_id},
        )

    return {"data": action.model_dump(mode="json")}
