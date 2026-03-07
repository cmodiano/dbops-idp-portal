"""
WebSocket consumer for real-time execution updates.

Story 22.13: Inherits message-based JWT auth from AuthenticatedWebSocketConsumer.
Story 27.1: Enhanced with channel layer group messaging for AAP job monitoring.
"""
import json

import structlog
from channels.exceptions import StopConsumer

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
        if not self.execution_id:
            logger.error("ws_execution_missing_execution_id")
            await self.close()
            return
        self.group_name = f"execution_{self.execution_id}"
        self._group_joined = False  # SEC-2: tracked for accurate disconnect logging
        await super().connect()
        # SEC-2 FIX: group_add déplacé après auth+authz dans receive().
        # Trade-off: on accepte la légère fenêtre CRITICAL-5 (race condition early broadcast)
        # au profit de la sécurité (un utilisateur non autorisé ne peut pas joindre le groupe).

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """Override to add execution access check after JWT authentication (SEC-2)."""
        was_authenticated = self.authenticated
        await super().receive(text_data=text_data, bytes_data=bytes_data)

        # If just authenticated: check execution access before joining group
        if not was_authenticated and self.authenticated:
            try:
                authorized = await self._check_execution_access()
            except Exception as e:  # noqa: BLE001 — fail-secure: any unexpected DB error → deny
                logger.error(
                    "ws_execution_access_check_failed",
                    execution_id=self.execution_id,
                    user_id=self.user_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                await self.close(code=4003)
                return
            if not authorized:
                logger.warning(
                    "ws_execution_access_denied",
                    execution_id=self.execution_id,
                    user_id=self.user_id,
                )
                await self.close(code=4003)
                return
            if hasattr(self, "channel_layer") and self.channel_layer is not None:
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                self._group_joined = True
                logger.info(
                    "ws_execution_group_joined",
                    execution_id=self.execution_id,
                    group_name=self.group_name,
                    user_id=self.user_id,
                )

    async def _check_execution_access(self) -> bool:
        """Check if authenticated user (self.user_id) has access to self.execution_id.

        Returns True if user is owner OR has admin profile (is_admin=1).
        SEC-2 fix: prevents information leak via WebSocket.
        """
        from django.contrib.auth import get_user_model  # local import — avoids circular

        from executions.models import Execution

        if not self.execution_id or not self.user_id:
            return False

        User = get_user_model()
        execution_id: str = self.execution_id
        user_id: str = self.user_id
        try:
            execution = await Execution.objects.aget(id=execution_id)
        except Execution.DoesNotExist:
            logger.warning(
                "ws_execution_not_found",
                execution_id=self.execution_id,
                user_id=self.user_id,
            )
            return False

        # Owner check
        if str(execution.user_id) == user_id:
            logger.info(
                "ws_execution_access_granted_owner",
                execution_id=self.execution_id,
                user_id=self.user_id,
            )
            return True

        # Admin check (Profile.is_admin=1 via reverse FK relation)
        is_admin = await User.objects.filter(
            id=user_id, profiles__is_admin=1  # type: ignore[misc]
        ).aexists()
        if is_admin:
            logger.info(
                "ws_execution_access_granted_admin",
                execution_id=self.execution_id,
                user_id=self.user_id,
            )
        return is_admin

    async def handle_authenticated_message(self, message: dict) -> None:
        """After auth, log successful authentication."""
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
                if getattr(self, "_group_joined", False):
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

    async def _safe_send(self, payload: dict) -> None:
        """Send JSON payload, suppressing errors on closing connections."""
        try:
            await self.send(text_data=json.dumps(payload))
        except StopConsumer:
            return
        except Exception as e:  # noqa: BLE001 — best-effort-non-critical: log dropped messages on closing sockets
            logger.debug("ws_execution_send_failed", error=str(e), error_type=type(e).__name__)

    async def step_update(self, event: dict) -> None:
        """Forward step_update event to WebSocket client."""
        await self._safe_send({"type": "step_update", "data": event.get("data", {})})

    async def log_update(self, event: dict) -> None:
        """Forward log_update event to WebSocket client (Story 27.1)."""
        await self._safe_send({"type": "log_update", "data": event.get("data", {})})

    async def execution_complete(self, event: dict) -> None:
        """Forward execution_complete event to WebSocket client."""
        await self._safe_send({"type": "execution_complete", "data": event.get("data", {})})

    async def execution_failed(self, event: dict) -> None:
        """Forward execution_failed event to WebSocket client."""
        await self._safe_send({"type": "execution_failed", "data": event.get("data", {})})

    async def status_update(self, event: dict) -> None:
        """Forward status_update event to WebSocket client (Story 27.1)."""
        await self._safe_send({"type": "status_update", "data": event.get("data", {})})


class DashboardConsumer(AuthenticatedWebSocketConsumer):
    """WebSocket endpoint: /ws/dashboard

    After authentication, forwards real-time execution_update messages
    for the dashboard.
    """

    async def handle_authenticated_message(self, message: dict) -> None:
        pass
