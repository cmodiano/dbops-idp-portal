"""
WebSocket consumer for real-time execution updates.

Story 22.13: Inherits message-based JWT auth from AuthenticatedWebSocketConsumer.
Story 27.1: Enhanced with channel layer group messaging for AAP job monitoring.
"""
import json

import structlog

from core.consumers import AuthenticatedWebSocketConsumer

logger = structlog.get_logger(__name__)


class ExecutionConsumer(AuthenticatedWebSocketConsumer):
    """WebSocket endpoint: /ws/executions/{execution_id}

    After authentication, joins a channel group for the execution and
    forwards real-time step_update, execution_complete, log_update,
    and execution_failed messages sent by the polling task.
    """

    async def connect(self) -> None:
        self.execution_id = self.scope["url_route"]["kwargs"].get("execution_id")
        self.group_name = f"execution_{self.execution_id}"
        await super().connect()

        # CRITICAL-5 FIX: Join channel group IMMEDIATELY on connect, before first message
        # This prevents race condition where broadcasts arrive before group_add completes
        if hasattr(self, "channel_layer") and self.channel_layer is not None:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            logger.info(
                "ws_execution_group_joined_on_connect",
                execution_id=self.execution_id,
                group_name=self.group_name,
            )

    async def handle_authenticated_message(self, message: dict) -> None:
        """After auth, log successful authentication.

        CRITICAL-5 FIX: Group join moved to connect() to prevent race conditions.
        """
        logger.debug(
            "ws_execution_authenticated_message",
            execution_id=self.execution_id,
            user_id=self.user_id,
        )

    async def disconnect(self, code: int) -> None:
        """Leave the channel group on disconnect.

        MEDIUM-7 FIX: Catch exceptions from group_discard if channel layer is down.
        """
        if hasattr(self, "channel_layer") and self.channel_layer is not None:
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                logger.debug(
                    "ws_execution_group_left",
                    execution_id=self.execution_id,
                    group_name=self.group_name,
                )
            except Exception as e:  # noqa: BLE001 — best-effort-non-critical: group_discard is best-effort cleanup, must not raise
                # MEDIUM-7 FIX: Log warning but don't raise (best-effort cleanup)
                logger.warning(
                    "ws_execution_group_discard_failed",
                    execution_id=self.execution_id,
                    group_name=self.group_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
        await super().disconnect(code)

    # ---------------------------------------------------------------
    # Channel layer message handlers — called via group_send
    # ---------------------------------------------------------------

    async def step_update(self, event: dict) -> None:
        """Forward step_update event to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "step_update",
            "data": event.get("data", {}),
        }))

    async def log_update(self, event: dict) -> None:
        """Forward log_update event to WebSocket client (Story 27.1)."""
        await self.send(text_data=json.dumps({
            "type": "log_update",
            "data": event.get("data", {}),
        }))

    async def execution_complete(self, event: dict) -> None:
        """Forward execution_complete event to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "execution_complete",
            "data": event.get("data", {}),
        }))

    async def execution_failed(self, event: dict) -> None:
        """Forward execution_failed event to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "execution_failed",
            "data": event.get("data", {}),
        }))

    async def status_update(self, event: dict) -> None:
        """Forward status_update event to WebSocket client (Story 27.1)."""
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "data": event.get("data", {}),
        }))


class DashboardConsumer(AuthenticatedWebSocketConsumer):
    """WebSocket endpoint: /ws/dashboard

    After authentication, forwards real-time execution_update messages
    for the dashboard.
    """

    async def handle_authenticated_message(self, message: dict) -> None:
        pass
