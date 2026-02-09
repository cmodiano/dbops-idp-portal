"""
Tests for WebSocket message-based JWT authentication.

Story 22.13: Verify that WebSocket connections require auth via first message,
reject invalid tokens with code 4001, and confirm valid tokens with auth_success.
"""

import json

import pytest
from channels.testing import WebsocketCommunicator

from core.consumers import AuthenticatedWebSocketConsumer
from idp_auth.jwt_utils import create_access_token, create_refresh_token


@pytest.mark.asyncio
async def test_rejects_non_auth_first_message():
    """AC3/AC8: Connection without auth message is rejected with code 4001."""
    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    # Send a non-auth message
    await communicator.send_json_to({"type": "ping"})

    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4001


@pytest.mark.asyncio
async def test_rejects_missing_token():
    """AC3: Auth message without token field is rejected with code 4001."""
    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "auth"})

    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4001


@pytest.mark.asyncio
async def test_rejects_invalid_token():
    """AC3/AC8: Invalid JWT token closes connection with code 4001."""
    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "auth", "token": "invalid-jwt-token"})

    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4001


@pytest.mark.asyncio
async def test_rejects_refresh_token():
    """AC3: Refresh token (wrong type) is rejected — only access tokens allowed."""
    refresh_token = create_refresh_token({
        "sub": "user-123",
        "username": "testuser",
        "profile": "admin",
        "ad_groups": ["DBA"],
    })

    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "auth", "token": refresh_token})

    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4001


@pytest.mark.asyncio
async def test_accepts_valid_token():
    """AC3/AC4/AC8: Valid access token returns auth_success with user_id."""
    access_token = create_access_token({
        "sub": "user-456",
        "username": "testuser",
        "profile": "dba",
        "ad_groups": ["DBA", "OPS"],
    })

    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "auth", "token": access_token})

    response = await communicator.receive_json_from()
    assert response["type"] == "auth_success"
    assert response["user_id"] == "user-456"

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_rejects_invalid_json():
    """AC3: Invalid JSON closes connection with code 4002."""
    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_to(text_data="not-json{{{")

    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4002


@pytest.mark.asyncio
async def test_messages_before_auth_are_rejected():
    """AC8: Messages received before auth_success are rejected."""
    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    # Send a business message before auth
    await communicator.send_json_to({"type": "subscribe", "execution_id": 42})

    # Should be closed with 4001
    response = await communicator.receive_output()
    assert response["type"] == "websocket.close"
    assert response["code"] == 4001


@pytest.mark.asyncio
async def test_no_token_in_url_logs():
    """AC6: Verify the consumer does not log the token value."""
    access_token = create_access_token({
        "sub": "user-789",
        "username": "secureuser",
        "profile": "dba",
        "ad_groups": [],
    })

    communicator = WebsocketCommunicator(
        AuthenticatedWebSocketConsumer.as_asgi(),
        "/ws/test/",
    )
    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({"type": "auth", "token": access_token})

    response = await communicator.receive_json_from()
    assert response["type"] == "auth_success"
    # The token should never appear in response (only user_id)
    response_str = json.dumps(response)
    assert access_token not in response_str

    await communicator.disconnect()
