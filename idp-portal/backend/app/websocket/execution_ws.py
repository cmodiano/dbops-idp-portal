"""WebSocket manager for real-time execution timeline (Story 4.6, Task 1.1).

ExecutionWebSocketManager:
- connect(execution_id, websocket): Register client for execution updates
- disconnect(websocket): Remove client from all execution subscriptions
- broadcast_step_update(execution_id, step_data): Notify clients of step status change
- broadcast_execution_complete(execution_id): Notify clients execution finished
- broadcast_execution_failed(execution_id, error_message): Notify clients execution failed
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket
import structlog

logger = structlog.get_logger()


class ExecutionWebSocketManager:
    """Manages WebSocket connections for real-time execution updates (Story 4.6, Task 1.1).

    Stores active connections per execution_id using set().
    Thread-safe for single-threaded asyncio (no locks needed).
    """

    def __init__(self) -> None:
        # execution_id -> set of WebSocket connections
        self._connections: dict[int, set[WebSocket]] = {}
        # websocket -> execution_id (for disconnect lookup)
        self._websocket_to_execution: dict[WebSocket, int] = {}

    async def connect(self, execution_id: int, websocket: WebSocket) -> None:
        """Register a WebSocket client for execution updates.

        Args:
            execution_id: Execution to subscribe to
            websocket: Client WebSocket connection
        """
        if execution_id not in self._connections:
            self._connections[execution_id] = set()
        self._connections[execution_id].add(websocket)
        self._websocket_to_execution[websocket] = execution_id
        logger.info(
            "websocket_connected",
            execution_id=execution_id,
            client_count=len(self._connections[execution_id]),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove WebSocket from all subscriptions.

        Args:
            websocket: Client connection to remove
        """
        execution_id = self._websocket_to_execution.pop(websocket, None)
        if execution_id is not None and execution_id in self._connections:
            self._connections[execution_id].discard(websocket)
            if not self._connections[execution_id]:
                del self._connections[execution_id]
            logger.info(
                "websocket_disconnected",
                execution_id=execution_id,
            )

    async def broadcast_step_update(
        self,
        execution_id: int,
        step_data: dict[str, Any],
    ) -> None:
        """Broadcast step_update message to all clients subscribed to this execution.

        Format: {"type": "step_update", "execution_id": int, "data": {...}}

        Args:
            execution_id: Execution ID
            step_data: Dict with step_order, step_name, status, started_at, completed_at
        """
        message = {
            "type": "step_update",
            "execution_id": execution_id,
            "data": step_data,
        }
        await self._broadcast(execution_id, message)

    async def broadcast_execution_complete(self, execution_id: int) -> None:
        """Broadcast execution_complete to subscribed clients.

        Format: {"type": "execution_complete", "execution_id": int, "status": "COMPLETED"}

        Args:
            execution_id: Execution ID
        """
        message = {
            "type": "execution_complete",
            "execution_id": execution_id,
            "status": "COMPLETED",
        }
        await self._broadcast(execution_id, message)

    async def broadcast_execution_failed(
        self,
        execution_id: int,
        error_message: str,
    ) -> None:
        """Broadcast execution_failed to subscribed clients.

        Format: {"type": "execution_failed", "execution_id": int, "error_message": str}

        Args:
            execution_id: Execution ID
            error_message: Error details
        """
        message = {
            "type": "execution_failed",
            "execution_id": execution_id,
            "error_message": error_message,
        }
        await self._broadcast(execution_id, message)

    async def _broadcast(
        self,
        execution_id: int,
        message: dict[str, Any],
    ) -> None:
        """Send JSON message to all clients subscribed to execution_id.

        Removes disconnected clients on send failure.
        """
        connections = self._connections.get(execution_id, set()).copy()
        disconnected: list[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(
                    "websocket_send_failed",
                    execution_id=execution_id,
                    error=str(e),
                )
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)


# Singleton instance (Story 4.6, Task 1.4)
_execution_ws_manager: ExecutionWebSocketManager | None = None


def get_execution_ws_manager() -> ExecutionWebSocketManager:
    """Return singleton ExecutionWebSocketManager (Story 4.6, Task 1.4)."""
    global _execution_ws_manager
    if _execution_ws_manager is None:
        _execution_ws_manager = ExecutionWebSocketManager()
    return _execution_ws_manager
