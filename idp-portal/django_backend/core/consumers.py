"""
Base WebSocket consumer with message-based JWT authentication.

Story 22.13: Token sent in first message after connection (not in URL).
Sequence: accept() → receive {type:"auth", token} → validate → send {type:"auth_success"}.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer

import structlog

from idp_auth.jwt_utils import verify_token

logger = structlog.get_logger(__name__)


class AuthenticatedWebSocketConsumer(AsyncWebsocketConsumer):
    """Base WebSocket consumer requiring JWT auth via first message.

    Subclasses implement handle_authenticated_message() for business logic.
    """

    async def connect(self) -> None:
        await self.accept()
        self.authenticated = False
        self.user_id: str | None = None
        self.ad_groups: list[str] = []

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if text_data is None:
            await self.close(code=4002)
            return

        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            logger.warning("websocket_invalid_json")
            await self.close(code=4002)
            return

        if not self.authenticated:
            if message.get("type") != "auth":
                logger.warning("websocket_auth_failed", reason="first_message_not_auth")
                await self.close(code=4001)
                return

            token = message.get("token")
            if not token:
                logger.warning("websocket_auth_failed", reason="missing_token")
                await self.close(code=4001)
                return

            payload = verify_token(token, expected_type="access")
            if payload is None:
                logger.warning("websocket_auth_failed", reason="invalid_token")
                await self.close(code=4001)
                return

            self.authenticated = True
            self.user_id = payload.sub
            self.ad_groups = payload.ad_groups
            logger.info("websocket_auth_success", user_id=self.user_id)

            await self.send(text_data=json.dumps({
                "type": "auth_success",
                "user_id": self.user_id,
            }))
            return

        await self.handle_authenticated_message(message)

    async def handle_authenticated_message(self, message: dict) -> None:
        """Override in subclasses to handle business messages after auth."""
        pass

    async def disconnect(self, code: int) -> None:
        pass
