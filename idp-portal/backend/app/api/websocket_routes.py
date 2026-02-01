"""WebSocket routes for real-time execution timeline (Story 4.6, Task 1.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from app.models.auth import UserProfile
from starlette import status

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import verify_token
from app.repositories import execution_repository, user_repository
from app.websocket.execution_ws import get_execution_ws_manager
from app.websocket.dashboard_ws import get_dashboard_ws_manager
from app.api.deps import _DEV_USER_FALLBACK

import structlog

logger = structlog.get_logger()

router = APIRouter()


async def _resolve_user_from_token(token: str | None) -> "UserProfile":
    """Resolve user from JWT token. Raises UnauthorizedError if invalid."""
    from app.models.auth import UserProfile

    if settings.auth_dev_bypass:
        return _DEV_USER_FALLBACK

    if not token or not token.strip():
        raise UnauthorizedError(code="NO_TOKEN", message="Token d'authentification requis")

    payload = verify_token(token.strip(), expected_type="access")
    user = await user_repository.get_by_username(payload.username)
    if not user:
        raise UnauthorizedError(code="USER_NOT_FOUND", message="Utilisateur introuvable")

    # Minimal UserProfile for RBAC check (profile resolution not needed for execution ownership)
    return UserProfile(
        id=user["id"],
        username=user.get("username", ""),
        display_name=user.get("display_name", ""),
        profile=user.get("profile", ""),
    )


@router.websocket("/executions/{execution_id}")
async def websocket_execution_timeline(websocket: WebSocket, execution_id: int) -> None:
    """WebSocket endpoint for real-time execution timeline (Story 4.6, Task 1.2).

    Query param: ?token=<jwt> for authentication.
    RBAC: User must own the execution (execution.user_id == user.id).

    Security: Validates auth and RBAC BEFORE accepting WebSocket connection (HIGH-1 fix).
    """
    # HIGH-1 FIX: Validate auth and RBAC BEFORE accepting connection
    # Get token from query string (Story 4.6, Task 1.2)
    token = websocket.query_params.get("token")

    try:
        user = await _resolve_user_from_token(token)
    except UnauthorizedError as e:
        logger.warning("websocket_auth_failed", execution_id=execution_id, error=e.message)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # RBAC: Verify user has access to this execution (Story 4.6, Task 1.2)
    execution = await execution_repository.get_by_id(execution_id)
    if execution is None or execution.user_id != user.id:
        logger.warning(
            "websocket_rbac_denied",
            execution_id=execution_id,
            user_id=user.id,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Auth and RBAC validated - now accept the connection
    await websocket.accept()

    try:
        manager = get_execution_ws_manager()
        await manager.connect(execution_id, websocket)

        # Send connection_ack (Story 4.6, Task 1.3 format)
        await websocket.send_json({
            "type": "connection_ack",
            "execution_id": execution_id,
        })

        # Keep connection alive; client receives broadcasts via manager
        try:
            while True:
                # Await messages to keep connection open; we don't process client messages
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            pass

    finally:
        manager = get_execution_ws_manager()
        manager.disconnect(websocket)


# Allowed profiles for dashboard WebSocket (Story 5.2, Task 1.2)
_DASHBOARD_ALLOWED_PROFILES = frozenset({"dba", "dbops"})


@router.websocket("/dashboard")
async def websocket_dashboard(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time dashboard updates (Story 5.2, Task 1.2).

    Query param: ?token=<jwt> for authentication.
    RBAC: User must have DBA or DBOPS profile.

    Broadcasts execution_update messages when executions change status.
    """
    # Validate auth BEFORE accepting connection
    token = websocket.query_params.get("token")

    try:
        user = await _resolve_user_from_token(token)
    except UnauthorizedError as e:
        logger.warning("dashboard_websocket_auth_failed", error=e.message)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # RBAC: Verify user has DBA or DBOPS profile (Story 5.2, Task 1.2)
    if (user.profile or "").lower() not in _DASHBOARD_ALLOWED_PROFILES:
        logger.warning(
            "dashboard_websocket_rbac_denied",
            user_id=user.id,
            profile=user.profile,
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Auth and RBAC validated - now accept the connection
    await websocket.accept()

    try:
        manager = get_dashboard_ws_manager()
        await manager.connect(user.id, websocket)

        # Send connection_ack (Story 5.2, Task 1.2)
        await websocket.send_json({
            "type": "connection_ack",
        })

        # Keep connection alive; client receives broadcasts via manager
        try:
            while True:
                _ = await websocket.receive_text()
        except WebSocketDisconnect:
            pass

    finally:
        manager = get_dashboard_ws_manager()
        manager.disconnect(websocket)
