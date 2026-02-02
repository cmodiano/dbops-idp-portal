"""Tests for scheduled execution repository (Story 11.3, Task 8).

Tests scheduled_execution_repository functions:
- create_scheduled_execution: insert and return scheduled execution ID
- get_by_id: retrieve with action enrichment
- action_exists: check action exists and is published
- get_action_parameters_schema: retrieve schema for validation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.scheduled_execution import (
    ScheduledExecutionStatus,
)
from app.repositories import scheduled_execution_repository


class TestCreateScheduledExecution:
    """Tests for scheduled_execution_repository.create_scheduled_execution (Task 2.2)."""

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_success(self):
        """create_scheduled_execution inserts record and returns ScheduledExecutionCreateResult."""
        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 2, 10, 0, 0)]

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        scheduled_at = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.create_scheduled_execution(
                user_id=1,
                action_id=5,
                environment="prod",
                parameters={"db_name": "PRODDB"},
                scheduled_at=scheduled_at,
            )

        assert result.id == 42
        assert result.status == ScheduledExecutionStatus.PENDING
        assert result.created_at == datetime(2026, 2, 2, 10, 0, 0)
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_stores_parameters_as_json(self):
        """create_scheduled_execution stores parameters as JSON string in CLOB."""
        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 2)]

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        scheduled_at = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await scheduled_execution_repository.create_scheduled_execution(
                user_id=1,
                action_id=1,
                environment="prod",
                parameters={"key": "value", "nested": {"inner": 123}},
                scheduled_at=scheduled_at,
            )

        # Check that execute was called with JSON parameters
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["parameters"] == '{"key": "value", "nested": {"inner": 123}}'
        assert params["environment"] == "prod"
        assert params["status"] == "pending"


class TestGetById:
    """Tests for scheduled_execution_repository.get_by_id (Task 2.3)."""

    @pytest.mark.asyncio
    async def test_get_by_id_with_action_enrichment(self):
        """get_by_id returns scheduled execution with action metadata."""
        scheduled_at = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        created_at = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)

        # Row: ID, ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, SCHEDULED_AT, STATUS,
        #      CREATED_AT, UPDATED_AT, ACTION_NAME, ACTION_DESCRIPTION
        mock_row = (
            42,  # ID
            5,   # ACTION_ID
            1,   # USER_ID
            "prod",  # ENVIRONMENT
            '{"db_name": "PRODDB"}',  # PARAMETERS
            scheduled_at,  # SCHEDULED_AT
            "pending",  # STATUS
            created_at,  # CREATED_AT
            None,  # UPDATED_AT
            "Patching Oracle",  # ACTION_NAME
            "Applies patches to Oracle database",  # ACTION_DESCRIPTION
        )

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.get_by_id(42)

        assert result is not None
        assert result.id == 42
        assert result.action_id == 5
        assert result.action_name == "Patching Oracle"
        assert result.action_description == "Applies patches to Oracle database"
        assert result.environment == "prod"
        assert result.status == ScheduledExecutionStatus.PENDING
        assert result.parameters == {"db_name": "PRODDB"}

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        """get_by_id returns None when scheduled execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.get_by_id(999)

        assert result is None


class TestActionExists:
    """Tests for scheduled_execution_repository.action_exists (Task 2.5)."""

    @pytest.mark.asyncio
    async def test_action_exists_published_returns_true(self):
        """action_exists returns True when action exists and is published."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.action_exists(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_action_exists_not_published_returns_false(self):
        """action_exists returns False for draft (non-published) action."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))  # Count = 0
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.action_exists(1)

        assert result is False

    @pytest.mark.asyncio
    async def test_action_exists_not_found_returns_false(self):
        """action_exists returns False when action doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.action_exists(999)

        assert result is False


class TestGetActionParametersSchema:
    """Tests for scheduled_execution_repository.get_action_parameters_schema."""

    @pytest.mark.asyncio
    async def test_get_action_parameters_schema_returns_schema(self):
        """get_action_parameters_schema returns schema dict when present."""
        schema_json = '{"type": "object", "properties": {"db_name": {"type": "string"}}}'

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(schema_json,))
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.get_action_parameters_schema(1)

        assert result == {"type": "object", "properties": {"db_name": {"type": "string"}}}

    @pytest.mark.asyncio
    async def test_get_action_parameters_schema_returns_none_when_no_schema(self):
        """get_action_parameters_schema returns None when action has no schema."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(None,))
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.get_action_parameters_schema(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_action_parameters_schema_returns_none_when_action_not_found(self):
        """get_action_parameters_schema returns None when action doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.scheduled_execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await scheduled_execution_repository.get_action_parameters_schema(999)

        assert result is None
