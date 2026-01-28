"""Tests for audit repository (Story 2.4, AC #3).

Uses mocks for Oracle pool to test repository logic without database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType


class TestAuditActionTypeEnum:
    """Tests for AuditActionType enum."""

    def test_action_type_values(self):
        """Test AuditActionType enum values."""
        assert AuditActionType.ACTION_CREATED.value == "ACTION_CREATED"
        assert AuditActionType.ACTION_UPDATED.value == "ACTION_UPDATED"
        assert AuditActionType.ACTION_PUBLISHED.value == "ACTION_PUBLISHED"
        assert AuditActionType.ACTION_DISABLED.value == "ACTION_DISABLED"
        assert AuditActionType.ACTION_ENABLED.value == "ACTION_ENABLED"


class TestAuditEntityTypeEnum:
    """Tests for AuditEntityType enum."""

    def test_entity_type_values(self):
        """Test AuditEntityType enum values."""
        assert AuditEntityType.ACTION.value == "action"
        assert AuditEntityType.USER.value == "user"
        assert AuditEntityType.PERMISSION.value == "permission"


class TestCreateEntry:
    """Tests for create_entry() function."""

    @pytest.mark.asyncio
    async def test_create_entry_success(self):
        """Test creating audit entry successfully."""
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]
        mock_conn.var = MagicMock(return_value=mock_out_id)
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_PUBLISHED,
                entity_type=AuditEntityType.ACTION,
                entity_id=1,
                details={"action_name": "Create PDB", "previous_status": "draft", "new_status": "published"},
            )

        assert result == 42
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_entry_with_ip_address(self):
        """Test creating audit entry with IP address."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [43]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_DISABLED,
                entity_type=AuditEntityType.ACTION,
                entity_id=2,
                ip_address="192.168.1.1",
            )

        assert result == 43
        assert captured_params["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_create_entry_without_details(self):
        """Test creating audit entry without details."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [44]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_CREATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=3,
                details=None,
            )

        assert result == 44
        assert captured_params["details"] is None

    @pytest.mark.asyncio
    async def test_create_entry_serializes_details_to_json(self):
        """Test that details dict is serialized to JSON string."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [45]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_UPDATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=4,
                details={"key": "value"},
            )

        assert captured_params["details"] == '{"key": "value"}'
        assert isinstance(captured_params["details"], str)
