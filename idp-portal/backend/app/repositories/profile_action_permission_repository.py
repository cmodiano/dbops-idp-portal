"""Profile action permissions repository (Story 2.10, AC2–AC5). Raw SQL oracledb."""

from __future__ import annotations

import json

from app.core.database import get_connection
from app.models.profile import (
    ProfileActionPermissionsResponse,
    ProfileActionPermissionsUpdate,
)


def _json_load_list(data: str | None) -> list[int] | list[str]:
    """Parse CLOB JSON array to list. Returns empty list if None or invalid."""
    if data is None or (isinstance(data, str) and data.strip() in ("", "null")):
        return []
    try:
        out = json.loads(data)
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return []


def _json_dump_list(items: list[int] | list[str] | None) -> str | None:
    """Serialize list to JSON string for CLOB."""
    if items is None or len(items) == 0:
        return None
    return json.dumps(items)


async def get_actions_permissions(profile_id: int) -> ProfileActionPermissionsResponse | None:
    """Fetch actions permissions for a profile. Returns None if no row (profile has no permissions set)."""
    query = """
        SELECT PERMISSION_TYPE, ACTION_IDS_JSON, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON
        FROM PROFILE_ACTION_PERMISSIONS
        WHERE PROFILE_ID = :profile_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"profile_id": profile_id})
        row = await cursor.fetchone()
        cursor.close()
    if row is None:
        return None
    perm_type = row[0].upper() if row[0] else "ALL"
    type_map = {"LIST": "list", "PATTERN": "pattern", "ALL": "all"}
    action_ids = _json_load_list(row[1]) if isinstance(row[1], str) else []
    tag_patterns = _json_load_list(row[2]) if isinstance(row[2], str) else []
    environments = _json_load_list(row[3]) if isinstance(row[3], str) else []
    return ProfileActionPermissionsResponse(
        actions_type=type_map.get(perm_type, "all"),
        action_ids=action_ids if isinstance(action_ids, list) and all(isinstance(x, int) for x in action_ids) else [],
        tag_patterns=tag_patterns if isinstance(tag_patterns, list) and all(isinstance(x, str) for x in tag_patterns) else [],
        environments=environments if isinstance(environments, list) and all(isinstance(x, str) for x in environments) else [],
    )


async def get_actions_permissions_for_profile_ids(
    profile_ids: list[int],
) -> dict[int, ProfileActionPermissionsResponse]:
    """Fetch actions permissions for multiple profiles. Returns dict profile_id -> response (missing = no row)."""
    if not profile_ids:
        return {}
    # Oracle IN clause with bind vars
    placeholders = ", ".join(f":p{i}" for i in range(len(profile_ids)))
    query = f"""
        SELECT PROFILE_ID, PERMISSION_TYPE, ACTION_IDS_JSON, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON
        FROM PROFILE_ACTION_PERMISSIONS
        WHERE PROFILE_ID IN ({placeholders})
    """
    params = {f"p{i}": pid for i, pid in enumerate(profile_ids)}
    result: dict[int, ProfileActionPermissionsResponse] = {}
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()
    type_map = {"LIST": "list", "PATTERN": "pattern", "ALL": "all"}
    for row in rows:
        profile_id = row[0]
        perm_type = (row[1] or "ALL").upper()
        action_ids = _json_load_list(row[2]) if isinstance(row[2], str) else []
        tag_patterns = _json_load_list(row[3]) if isinstance(row[3], str) else []
        environments = _json_load_list(row[4]) if isinstance(row[4], str) else []
        if not isinstance(action_ids, list) or not all(isinstance(x, int) for x in action_ids):
            action_ids = []
        if not isinstance(tag_patterns, list) or not all(isinstance(x, str) for x in tag_patterns):
            tag_patterns = []
        if not isinstance(environments, list) or not all(isinstance(x, str) for x in environments):
            environments = []
        result[profile_id] = ProfileActionPermissionsResponse(
            actions_type=type_map.get(perm_type, "all"),
            action_ids=action_ids,
            tag_patterns=tag_patterns,
            environments=environments,
        )
    return result


async def set_actions_permissions(
    profile_id: int,
    payload: ProfileActionPermissionsUpdate,
) -> ProfileActionPermissionsResponse:
    """Upsert one row per profile. Replaces existing permissions."""
    type_to_db = {"list": "LIST", "pattern": "PATTERN", "all": "ALL"}
    perm_type = type_to_db[payload.actions_type]
    action_ids_json = _json_dump_list(payload.action_ids) if payload.action_ids else None
    tag_patterns_json = _json_dump_list(payload.tag_patterns) if payload.tag_patterns else None
    environments_json = _json_dump_list(payload.environments) if payload.environments else None

    merge_sql = """
        MERGE INTO PROFILE_ACTION_PERMISSIONS t
        USING (SELECT :profile_id AS PROFILE_ID FROM DUAL) s
        ON (t.PROFILE_ID = s.PROFILE_ID)
        WHEN MATCHED THEN
            UPDATE SET
                PERMISSION_TYPE = :perm_type,
                ACTION_IDS_JSON = :action_ids_json,
                TAG_PATTERNS_JSON = :tag_patterns_json,
                ENVIRONMENTS_JSON = :environments_json,
                UPDATED_AT = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (PROFILE_ID, PERMISSION_TYPE, ACTION_IDS_JSON, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON)
            VALUES (:profile_id, :perm_type, :action_ids_json, :tag_patterns_json, :environments_json)
    """
    params = {
        "profile_id": profile_id,
        "perm_type": perm_type,
        "action_ids_json": action_ids_json,
        "tag_patterns_json": tag_patterns_json,
        "environments_json": environments_json,
    }
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(merge_sql, params)
        await conn.commit()
        cursor.close()

    return ProfileActionPermissionsResponse(
        actions_type=payload.actions_type,
        action_ids=payload.action_ids or [],
        tag_patterns=payload.tag_patterns or [],
        environments=payload.environments or [],
    )
