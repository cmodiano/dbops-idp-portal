"""WebSocket manager for real-time dashboard updates (Story 5.2, Task 1.1).

DashboardWebSocketManager:
- connect(user_id, websocket): Register client for dashboard updates
- disconnect(websocket): Remove client from subscriptions
- broadcast_execution_update(execution_id, status, ...): Notify all clients of execution status change
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class DashboardWebSocketManager:
    """Manages WebSocket connections for real-time dashboard updates (Story 5.2, Task 1.1).

    Unlike ExecutionWebSocketManager (per-execution), this broadcasts to ALL connected
    dashboard clients regardless of user. DBA/DBOPS see all executions.
    """

    def __init__(self) -> None:
        # user_id -> set of WebSocket connections (for tracking)
        self._user_connections: dict[int, set[WebSocket]] = {}
        # websocket -> user_id (for disconnect lookup)
        self._websocket_to_user: dict[WebSocket, int] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Register a WebSocket client for dashboard updates.

        Args:
            user_id: User ID of the connected client
            websocket: Client WebSocket connection
        """
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(websocket)
        self._websocket_to_user[websocket] = user_id
        logger.info(
            "dashboard_websocket_connected",
            user_id=user_id,
            total_clients=len(self._websocket_to_user),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket from all subscriptions.

        Args:
            websocket: Client connection to remove
        """
        user_id = self._websocket_to_user.pop(websocket, None)
        if user_id is not None and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]
            logger.info(
                "dashboard_websocket_disconnected",
                user_id=user_id,
                total_clients=len(self._websocket_to_user),
            )

    async def broadcast_execution_update(
        self,
        execution_id: int,
        status: str,
        action_name: str | None = None,
        step_summary: str | None = None,
    ) -> None:
        """Broadcast execution_update message to ALL dashboard clients (Task 1.3).

        Format: {"type": "execution_update", "execution_id": int, "status": str, ...}

        Args:
            execution_id: Execution ID
            status: Execution status (RUNNING, COMPLETED, FAILED, etc.)
            action_name: Optional action name for display
            step_summary: Optional step summary (e.g., "Vault (2/3)")
        """
        message: dict[str, Any] = {
            "type": "execution_update",
            "execution_id": execution_id,
            "status": status,
        }
        if action_name is not None:
            message["action_name"] = action_name
        if step_summary is not None:
            message["step_summary"] = step_summary

        await self._broadcast(message)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        """Send JSON message to ALL connected dashboard clients.

        Removes disconnected clients on send failure.
        """
        # Get all connected websockets
        all_websockets = list(self._websocket_to_user.keys())
        disconnected: list[WebSocket] = []

        for ws in all_websockets:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(
                    "dashboard_websocket_send_failed",
                    error=str(e),
                )
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)


# Singleton instance (Story 5.2, Task 1.4)
_dashboard_ws_manager: DashboardWebSocketManager | None = None


def get_dashboard_ws_manager() -> DashboardWebSocketManager:
    """Return singleton DashboardWebSocketManager (Story 5.2, Task 1.4)."""
    global _dashboard_ws_manager
    if _dashboard_ws_manager is None:
        _dashboard_ws_manager = DashboardWebSocketManager()
    return _dashboard_ws_manager
