"""Tests for WebSocket execution timeline (Story 4.6, Task 5.1).

Tests:
- WebSocket connect with auth, disconnect
- broadcast_step_update received by client
- RBAC: user cannot connect to another user's execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app (Story 4.6, Task 5.1 - Starlette TestClient for WebSocket)."""
    return TestClient(app)


@pytest.fixture
def mock_execution_owner():
    """Execution owned by user_id=1."""
    from datetime import datetime
    from app.models.execution import ExecutionResponse, ExecutionStatus, ExecutionEnvironment

    return ExecutionResponse(
        id=1,
        action_id=10,
        action_name="Test Action",
        user_id=1,
        environment=ExecutionEnvironment.DEV,
        parameters=None,
        status=ExecutionStatus.RUNNING,
        servicenow_change_id=None,
        started_at=None,
        completed_at=None,
        created_at=datetime(2026, 1, 30, 10, 0, 0),
    )


class TestExecutionWebSocketManager:
    """Tests for ExecutionWebSocketManager (Story 4.6, Task 1.1)."""

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Manager connect and disconnect updates connection sets."""
        from app.websocket.execution_ws import ExecutionWebSocketManager

        manager = ExecutionWebSocketManager()
        ws = MagicMock(spec=["send_json", "close"])

        await manager.connect(1, ws)
        assert 1 in manager._connections
        assert ws in manager._connections[1]
        assert manager._websocket_to_execution[ws] == 1

        manager.disconnect(ws)
        assert 1 not in manager._connections
        assert ws not in manager._websocket_to_execution

    @pytest.mark.asyncio
    async def test_broadcast_step_update_sends_to_connected_clients(self):
        """broadcast_step_update sends JSON to all clients subscribed to execution."""
        from app.websocket.execution_ws import ExecutionWebSocketManager

        manager = ExecutionWebSocketManager()
        ws = MagicMock()
        ws.send_json = AsyncMock()

        await manager.connect(1, ws)

        step_data = {
            "step_order": 1,
            "step_name": "Vault",
            "status": "RUNNING",
            "started_at": "2026-01-30T10:00:00",
            "completed_at": None,
        }
        await manager.broadcast_step_update(1, step_data)

        ws.send_json.assert_called_once()
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "step_update"
        assert call_args["execution_id"] == 1
        assert call_args["data"] == step_data


class TestWebSocketEndpoint:
    """Tests for /ws/executions/{id} endpoint (Story 4.6, Task 1.2, 5.1)."""

    def test_websocket_connect_with_token_receives_connection_ack(self, client, mock_execution_owner):
        """Connect with valid token receives connection_ack and can receive messages."""
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get,
            patch("app.api.websocket_routes.verify_token") as mock_verify,
            patch("app.api.websocket_routes.user_repository.get_by_username", new_callable=AsyncMock) as mock_user,
        ):
            mock_settings.auth_dev_bypass = False
            mock_get.return_value = mock_execution_owner
            mock_verify.return_value = MagicMock(username="test_user")
            mock_user.return_value = {"id": 1, "username": "test_user", "display_name": "Test", "profile": "dbops"}

            with client.websocket_connect("/ws/executions/1?token=valid-token") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_ack"
                assert msg["execution_id"] == 1

    def test_websocket_rejects_when_execution_not_owned(self, client, mock_execution_owner):
        """User cannot connect to execution owned by another user (RBAC).

        HIGH-1 FIX: Connection is now rejected BEFORE accept(), so WebSocket
        connection fails immediately without receiving any message.
        """
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get,
            patch("app.api.websocket_routes.verify_token") as mock_verify,
            patch("app.api.websocket_routes.user_repository.get_by_username", new_callable=AsyncMock) as mock_user,
        ):
            mock_settings.auth_dev_bypass = False
            mock_get.return_value = mock_execution_owner  # owned by user_id=1
            mock_verify.return_value = MagicMock(username="other_user")
            mock_user.return_value = {"id": 99, "username": "other_user", "display_name": "Other", "profile": "dba"}

            # HIGH-1 FIX: Connection is rejected before accept - raises exception
            with pytest.raises(Exception):  # WebSocket closes with 1008 before accept
                with client.websocket_connect("/ws/executions/1?token=valid-token") as websocket:
                    websocket.receive_json()

    def test_websocket_rejects_without_token_before_accept(self, client):
        """HIGH-1 FIX: WebSocket rejects connection BEFORE accept when no token provided."""
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
        ):
            mock_settings.auth_dev_bypass = False

            # Should raise exception because connection is rejected before accept
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/executions/1") as websocket:
                    # Should never get here - connection rejected before accept
                    websocket.receive_json()

    def test_websocket_connect_dev_bypass(self, client):
        """With auth_dev_bypass, connect without token succeeds for dev user (id=0)."""
        from datetime import datetime
        from app.models.execution import ExecutionResponse, ExecutionStatus, ExecutionEnvironment

        # _DEV_USER_FALLBACK has id=0, so execution must be owned by user_id=0
        execution_owned_by_dev = ExecutionResponse(
            id=1,
            action_id=10,
            action_name="Test Action",
            user_id=0,
            environment=ExecutionEnvironment.DEV,
            parameters=None,
            status=ExecutionStatus.RUNNING,
            servicenow_change_id=None,
            started_at=None,
            completed_at=None,
            created_at=datetime(2026, 1, 30, 10, 0, 0),
        )
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get,
        ):
            mock_settings.auth_dev_bypass = True
            mock_get.return_value = execution_owned_by_dev

            with client.websocket_connect("/ws/executions/1") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_ack"
                assert msg["execution_id"] == 1
