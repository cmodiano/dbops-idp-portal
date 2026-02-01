"""User repository using raw SQL via python-oracledb."""

from __future__ import annotations

from app.core.database import get_connection


async def get_by_username(username: str) -> dict | None:
    """Fetch a user by username. Returns dict or None."""
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(
            "SELECT ID, USERNAME, DISPLAY_NAME, PROFILE, SAML_SUBJECT, CREATED_AT, UPDATED_AT "
            "FROM USERS WHERE USERNAME = :username",
            {"username": username},
        )
        row = await cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "profile": row[3],
            "saml_subject": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }


async def get_by_id(user_id: int) -> dict | None:
    """Fetch a user by ID. Returns dict or None."""
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(
            "SELECT ID, USERNAME, DISPLAY_NAME, PROFILE, SAML_SUBJECT, CREATED_AT, UPDATED_AT "
            "FROM USERS WHERE ID = :user_id",
            {"user_id": user_id},
        )
        row = await cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2],
            "profile": row[3],
            "saml_subject": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }


async def get_user_permissions(user_id: int) -> list[dict]:
    """Fetch all permissions for a user. Returns list of dicts."""
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(
            "SELECT USER_ID, ACTION_ID, ENVIRONMENT, GRANTED_BY, GRANTED_AT "
            "FROM USER_PERMISSIONS WHERE USER_ID = :user_id",
            {"user_id": user_id},
        )
        rows = await cursor.fetchall()
        cursor.close()
        return [
            {
                "user_id": row[0],
                "action_id": row[1],
                "environment": row[2],
                "granted_by": row[3],
                "granted_at": row[4],
            }
            for row in rows
        ]


async def has_permission(user_id: int, action_id: int, environment: str) -> bool:
    """Check if user has permission for action in environment."""
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(
            "SELECT 1 FROM USER_PERMISSIONS "
            "WHERE USER_ID = :user_id AND ACTION_ID = :action_id AND ENVIRONMENT = :environment",
            {"user_id": user_id, "action_id": action_id, "environment": environment},
        )
        row = await cursor.fetchone()
        cursor.close()
        return row is not None


async def create_or_update(
    username: str,
    display_name: str | None,
    profile: str,
    saml_subject: str | None,
) -> dict:
    """Create or update a user via MERGE (atomic upsert). Returns the user dict."""
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(
            "MERGE INTO USERS u "
            "USING (SELECT :username AS USERNAME FROM DUAL) src "
            "ON (u.USERNAME = src.USERNAME) "
            "WHEN MATCHED THEN UPDATE SET "
            "  u.DISPLAY_NAME = :display_name, "
            "  u.PROFILE = :profile, "
            "  u.SAML_SUBJECT = :saml_subject, "
            "  u.UPDATED_AT = SYSTIMESTAMP "
            "WHEN NOT MATCHED THEN INSERT "
            "  (USERNAME, DISPLAY_NAME, PROFILE, SAML_SUBJECT) "
            "  VALUES (:username, :display_name, :profile, :saml_subject)",
            {
                "username": username,
                "display_name": display_name,
                "profile": profile,
                "saml_subject": saml_subject,
            },
        )
        await conn.commit()
        cursor.close()

    return await get_by_username(username)  # type: ignore[return-value]
