"""Favorites repository using raw SQL via python-oracledb (Story 3.1 AC4, AC12, AC13, AC14).

Handles CRUD operations for USER_FAVORITES table.
"""

from __future__ import annotations

from datetime import datetime

from app.core.database import get_connection


async def list_favorites(user_id: int) -> list[dict]:
    """List all favorites for a user (AC12).

    Args:
        user_id: The user's ID

    Returns:
        List of dicts with action_id and created_at, ordered by created_at DESC
    """
    query = """
        SELECT ACTION_ID, CREATED_AT
        FROM USER_FAVORITES
        WHERE USER_ID = :user_id
        ORDER BY CREATED_AT DESC
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": user_id})
        rows = await cursor.fetchall()
        cursor.close()

    return [{"action_id": row[0], "created_at": row[1]} for row in rows]


async def add_favorite(user_id: int, action_id: int) -> None:
    """Add an action to user's favorites (AC13). Idempotent via MERGE.

    Args:
        user_id: The user's ID
        action_id: The action to add to favorites
    """
    query = """
        MERGE INTO USER_FAVORITES uf
        USING (SELECT :user_id AS USER_ID, :action_id AS ACTION_ID FROM DUAL) src
        ON (uf.USER_ID = src.USER_ID AND uf.ACTION_ID = src.ACTION_ID)
        WHEN NOT MATCHED THEN INSERT (USER_ID, ACTION_ID)
            VALUES (src.USER_ID, src.ACTION_ID)
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": user_id, "action_id": action_id})
        await conn.commit()
        cursor.close()


async def remove_favorite(user_id: int, action_id: int) -> bool:
    """Remove an action from user's favorites (AC13).

    Args:
        user_id: The user's ID
        action_id: The action to remove from favorites

    Returns:
        True if deleted, False if not found
    """
    query = """
        DELETE FROM USER_FAVORITES
        WHERE USER_ID = :user_id AND ACTION_ID = :action_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": user_id, "action_id": action_id})
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    return rowcount > 0


async def is_favorite(user_id: int, action_id: int) -> bool:
    """Check if action is in user's favorites (AC4).

    Args:
        user_id: The user's ID
        action_id: The action to check

    Returns:
        True if favorite, False otherwise
    """
    query = """
        SELECT 1 FROM USER_FAVORITES
        WHERE USER_ID = :user_id AND ACTION_ID = :action_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": user_id, "action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()

    return row is not None


async def list_recent_actions(user_id: int, limit: int = 10) -> list[dict]:
    """List recently executed actions for a user (AC5).

    Derived from EXECUTION_LOG, returns distinct action_ids ordered by most recent execution.

    Args:
        user_id: The user's ID
        limit: Maximum number of actions to return (default 10)

    Returns:
        List of dicts with action_id, name, and last_executed_at
    """
    query = """
        SELECT EL.ACTION_ID, AC.NAME, MAX(EL.STARTED_AT) AS LAST_EXECUTED_AT
        FROM EXECUTION_LOG EL
        INNER JOIN ACTIONS_CATALOG AC ON AC.ID = EL.ACTION_ID
        WHERE EL.USER_ID = :user_id
        GROUP BY EL.ACTION_ID, AC.NAME
        ORDER BY LAST_EXECUTED_AT DESC
        FETCH FIRST :limit ROWS ONLY
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": str(user_id), "limit": limit})
        rows = await cursor.fetchall()
        cursor.close()

    return [
        {
            "action_id": row[0],
            "name": row[1],
            "last_executed_at": row[2],
        }
        for row in rows
    ]
