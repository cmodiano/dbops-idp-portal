"""Tests for Dashboard WebSocket (Story 5.2, Task 5.1).

Tests:
- DashboardWebSocketManager: connect, disconnect, broadcast
- /ws/dashboard endpoint: auth, RBAC (DBA/DBOPS only), message format
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


class TestDashboardWebSocketManager:
    """Tests for DashboardWebSocketManager (Story 5.2, Task 1.1)."""

    @pytest.mark.asyncio
    async def test_connect_registers_user_client(self):
        """connect() registers WebSocket for user_id (Task 1.1)."""
        from app.websocket.dashboard_ws import DashboardWebSocketManager

        manager = DashboardWebSocketManager()
        ws = MagicMock(spec=["send_json", "close"])

        await manager.connect(user_id=1, websocket=ws)

        assert 1 in manager._user_connections
        assert ws in manager._user_connections[1]
        assert manager._websocket_to_user[ws] == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self):
        """disconnect() removes WebSocket from all subscriptions (Task 1.1)."""
        from app.websocket.dashboard_ws import DashboardWebSocketManager

        manager = DashboardWebSocketManager()
        ws = MagicMock(spec=["send_json", "close"])

        await manager.connect(user_id=1, websocket=ws)
        manager.disconnect(ws)

        assert 1 not in manager._user_connections
        assert ws not in manager._websocket_to_user

    @pytest.mark.asyncio
    async def test_broadcast_execution_update_sends_to_all_clients(self):
        """broadcast_execution_update sends to ALL connected dashboard clients (Task 1.3)."""
        from app.websocket.dashboard_ws import DashboardWebSocketManager

        manager = DashboardWebSocketManager()
        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await manager.connect(user_id=1, websocket=ws1)
        await manager.connect(user_id=2, websocket=ws2)

        await manager.broadcast_execution_update(
            execution_id=42,
            status="COMPLETED",
            action_name="Test Action",
        )

        # Both clients should receive the message
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

        # Verify message format (Task 1.4)
        msg1 = ws1.send_json.call_args[0][0]
        assert msg1["type"] == "execution_update"
        assert msg1["execution_id"] == 42
        assert msg1["status"] == "COMPLETED"
        assert msg1["action_name"] == "Test Action"

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_clients(self):
        """broadcast removes clients that fail to receive (Task 1.3)."""
        from app.websocket.dashboard_ws import DashboardWebSocketManager

        manager = DashboardWebSocketManager()
        ws1 = MagicMock()
        ws1.send_json = AsyncMock(side_effect=Exception("Connection lost"))
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()

        await manager.connect(user_id=1, websocket=ws1)
        await manager.connect(user_id=2, websocket=ws2)

        await manager.broadcast_execution_update(
            execution_id=42,
            status="FAILED",
        )

        # ws1 should be disconnected after failure
        assert ws1 not in manager._websocket_to_user
        # ws2 should still be connected
        assert ws2 in manager._websocket_to_user

    @pytest.mark.asyncio
    async def test_broadcast_with_step_summary(self):
        """broadcast includes step_summary when provided (Task 1.4)."""
        from app.websocket.dashboard_ws import DashboardWebSocketManager

        manager = DashboardWebSocketManager()
        ws = MagicMock()
        ws.send_json = AsyncMock()

        await manager.connect(user_id=1, websocket=ws)

        await manager.broadcast_execution_update(
            execution_id=1,
            status="RUNNING",
            step_summary="Vault (2/3)",
        )

        msg = ws.send_json.call_args[0][0]
        assert msg["step_summary"] == "Vault (2/3)"


class TestDashboardWebSocketEndpoint:
    """Tests for /ws/dashboard endpoint (Story 5.2, Task 1.2, 5.1)."""

    def test_websocket_connect_with_valid_dba_token(self, client):
        """DBA profile can connect to /ws/dashboard (Task 1.2)."""
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.verify_token") as mock_verify,
            patch("app.api.websocket_routes.user_repository.get_by_username", new_callable=AsyncMock) as mock_user,
        ):
            mock_settings.auth_dev_bypass = False
            mock_verify.return_value = MagicMock(username="dba_user")
            mock_user.return_value = {
                "id": 1,
                "username": "dba_user",
                "display_name": "DBA User",
                "profile": "dba",
            }

            with client.websocket_connect("/ws/dashboard?token=valid-token") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_ack"

    def test_websocket_connect_with_valid_dbops_token(self, client):
        """DBOPS profile can connect to /ws/dashboard (Task 1.2)."""
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.verify_token") as mock_verify,
            patch("app.api.websocket_routes.user_repository.get_by_username", new_callable=AsyncMock) as mock_user,
        ):
            mock_settings.auth_dev_bypass = False
            mock_verify.return_value = MagicMock(username="dbops_user")
            mock_user.return_value = {
                "id": 2,
                "username": "dbops_user",
                "display_name": "DBOPS User",
                "profile": "dbops",
            }

            with client.websocket_connect("/ws/dashboard?token=valid-token") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_ack"

    def test_websocket_rejects_non_dba_dbops_profile(self, client):
        """Non-DBA/DBOPS profile rejected from /ws/dashboard (RBAC, Task 1.2)."""
        with (
            patch("app.api.websocket_routes.settings") as mock_settings,
            patch("app.api.websocket_routes.verify_token") as mock_verify,
            patch("app.api.websocket_routes.user_repository.get_by_username", new_callable=AsyncMock) as mock_user,
        ):
            mock_settings.auth_dev_bypass = False
            mock_verify.return_value = MagicMock(username="regular_user")
            mock_user.return_value = {
                "id": 3,
                "username": "regular_user",
                "display_name": "Regular User",
                "profile": "business",  # Not DBA or DBOPS
            }

            with pytest.raises(Exception):
                with client.websocket_connect("/ws/dashboard?token=valid-token") as websocket:
                    websocket.receive_json()

    def test_websocket_rejects_without_token(self, client):
        """Connection rejected without token (Task 1.2)."""
        with patch("app.api.websocket_routes.settings") as mock_settings:
            mock_settings.auth_dev_bypass = False

            with pytest.raises(Exception):
                with client.websocket_connect("/ws/dashboard") as websocket:
                    websocket.receive_json()

    def test_websocket_dev_bypass_allows_connection(self, client):
        """With auth_dev_bypass, connect without token succeeds (Task 1.2)."""
        with patch("app.api.websocket_routes.settings") as mock_settings:
            mock_settings.auth_dev_bypass = True

            with client.websocket_connect("/ws/dashboard") as websocket:
                msg = websocket.receive_json()
                assert msg["type"] == "connection_ack"
