"""Tests for favorites_repository (Story 3.1 AC4, AC12, AC13, AC14)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories import favorites_repository


@pytest.fixture
def mock_connection():
    """Mock database connection context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.close = AsyncMock()
    conn.execute = AsyncMock(return_value=cursor)
    conn.commit = AsyncMock()
    return conn, cursor


@pytest.mark.asyncio
async def test_list_favorites_returns_empty_list_when_no_favorites(mock_connection):
    """AC12: list_favorites returns empty list when user has no favorites."""
    conn, cursor = mock_connection
    cursor.fetchall = AsyncMock(return_value=[])

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.list_favorites(user_id=1)

        assert result == []
        conn.execute.assert_called_once()
        assert "USER_ID" in conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_list_favorites_returns_favorites_with_created_at(mock_connection):
    """AC12: list_favorites returns action_id and created_at for each favorite."""
    conn, cursor = mock_connection
    now = datetime(2026, 1, 29, 12, 0, 0)
    cursor.fetchall = AsyncMock(return_value=[
        (101, now),
        (102, now),
    ])

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.list_favorites(user_id=1)

        assert len(result) == 2
        assert result[0]["action_id"] == 101
        assert result[0]["created_at"] == now
        assert result[1]["action_id"] == 102


@pytest.mark.asyncio
async def test_add_favorite_inserts_record(mock_connection):
    """AC13: add_favorite inserts into USER_FAVORITES."""
    conn, cursor = mock_connection

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        await favorites_repository.add_favorite(user_id=1, action_id=101)

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT" in sql or "MERGE" in sql
        assert "USER_FAVORITES" in sql
        conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_favorite_is_idempotent(mock_connection):
    """AC13: add_favorite should not fail if favorite already exists (idempotent)."""
    conn, cursor = mock_connection

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        # Should not raise even if already exists (MERGE or ON CONFLICT)
        await favorites_repository.add_favorite(user_id=1, action_id=101)

        # Verify MERGE is used for idempotency
        sql = conn.execute.call_args[0][0]
        assert "MERGE" in sql


@pytest.mark.asyncio
async def test_remove_favorite_deletes_record(mock_connection):
    """AC13: remove_favorite deletes from USER_FAVORITES."""
    conn, cursor = mock_connection
    cursor.rowcount = 1

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.remove_favorite(user_id=1, action_id=101)

        conn.execute.assert_called_once()
        sql = conn.execute.call_args[0][0]
        assert "DELETE" in sql
        assert "USER_FAVORITES" in sql
        conn.commit.assert_called_once()
        assert result is True


@pytest.mark.asyncio
async def test_remove_favorite_returns_false_if_not_found(mock_connection):
    """AC13: remove_favorite returns False if favorite doesn't exist."""
    conn, cursor = mock_connection
    cursor.rowcount = 0

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.remove_favorite(user_id=1, action_id=999)

        assert result is False


@pytest.mark.asyncio
async def test_is_favorite_returns_true_when_exists(mock_connection):
    """AC4: is_favorite returns True when user has action in favorites."""
    conn, cursor = mock_connection
    cursor.fetchone = AsyncMock(return_value=(1,))

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.is_favorite(user_id=1, action_id=101)

        assert result is True


@pytest.mark.asyncio
async def test_is_favorite_returns_false_when_not_exists(mock_connection):
    """AC4: is_favorite returns False when action is not in user's favorites."""
    conn, cursor = mock_connection
    cursor.fetchone = AsyncMock(return_value=None)

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.is_favorite(user_id=1, action_id=101)

        assert result is False


@pytest.mark.asyncio
async def test_list_recent_actions_returns_empty_list(mock_connection):
    """AC5: list_recent_actions returns empty list when no recent executions."""
    conn, cursor = mock_connection
    cursor.fetchall = AsyncMock(return_value=[])

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.list_recent_actions(user_id=1)

        assert result == []
        conn.execute.assert_called_once()
        assert "EXECUTION_LOG" in conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_list_recent_actions_returns_distinct_actions(mock_connection):
    """AC5: list_recent_actions returns distinct actions ordered by last execution."""
    conn, cursor = mock_connection
    now = datetime(2026, 1, 29, 12, 0, 0)
    cursor.fetchall = AsyncMock(return_value=[
        (101, "Create PDB", now),
        (102, "Patch DB", now),
    ])

    with patch("app.repositories.favorites_repository.get_connection") as mock_get_conn:
        mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
        mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await favorites_repository.list_recent_actions(user_id=1, limit=10)

        assert len(result) == 2
        assert result[0]["action_id"] == 101
        assert result[0]["name"] == "Create PDB"
        assert result[0]["last_executed_at"] == now
