"""Profile target permissions repository (Story 2.11, AC1–AC5). Raw SQL oracledb."""

from __future__ import annotations

import fnmatch
import json

from app.core.database import get_connection
from app.models.profile import (
    ProfileTargetPermissionsResponse,
    ProfileTargetPermissionsUpdate,
)


def _json_load_str_list(data: str | None) -> list[str]:
    """Parse CLOB JSON array to list of strings. Returns empty list if None or invalid."""
    if data is None or (isinstance(data, str) and data.strip() in ("", "null")):
        return []
    try:
        out = json.loads(data)
        if not isinstance(out, list):
            return []
        return [str(x) for x in out]
    except (json.JSONDecodeError, TypeError):
        return []


def _json_dump_list(items: list[str] | None) -> str | None:
    """Serialize list to JSON string for CLOB."""
    if items is None or len(items) == 0:
        return None
    return json.dumps(items)


async def get_target_permissions(profile_id: int) -> ProfileTargetPermissionsResponse | None:
    """Fetch target permissions for a profile. Returns None if no row."""
    query = """
        SELECT PERMISSION_TYPE, TARGET_NAMES_JSON, TARGET_PATTERNS_JSON
        FROM PROFILE_TARGET_PERMISSIONS
        WHERE PROFILE_ID = :profile_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(query, {"profile_id": profile_id})
        row = await cursor.fetchone()
        await cursor.close()
    if row is None:
        return None
    perm_type = row[0].upper() if row[0] else "ALL"
    type_map = {"LIST": "list", "PATTERN": "pattern", "ALL": "all"}
    target_names = _json_load_str_list(row[1]) if row[1] else []
    target_patterns = _json_load_str_list(row[2]) if row[2] else []
    return ProfileTargetPermissionsResponse(
        targets_type=type_map.get(perm_type, "all"),
        target_names=target_names,
        target_patterns=target_patterns,
    )


async def set_target_permissions(
    profile_id: int,
    payload: ProfileTargetPermissionsUpdate,
) -> ProfileTargetPermissionsResponse:
    """Upsert one row per profile. Replaces existing target permissions."""
    type_to_db = {"list": "LIST", "pattern": "PATTERN", "all": "ALL"}
    perm_type = type_to_db[payload.targets_type]
    target_names_json = _json_dump_list(payload.target_names) if payload.target_names else None
    target_patterns_json = _json_dump_list(payload.target_patterns) if payload.target_patterns else None

    merge_sql = """
        MERGE INTO PROFILE_TARGET_PERMISSIONS t
        USING (SELECT :profile_id AS PROFILE_ID FROM DUAL) s
        ON (t.PROFILE_ID = s.PROFILE_ID)
        WHEN MATCHED THEN
            UPDATE SET
                PERMISSION_TYPE = :perm_type,
                TARGET_NAMES_JSON = :target_names_json,
                TARGET_PATTERNS_JSON = :target_patterns_json,
                UPDATED_AT = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (PROFILE_ID, PERMISSION_TYPE, TARGET_NAMES_JSON, TARGET_PATTERNS_JSON)
            VALUES (:profile_id, :perm_type, :target_names_json, :target_patterns_json)
    """
    params = {
        "profile_id": profile_id,
        "perm_type": perm_type,
        "target_names_json": target_names_json,
        "target_patterns_json": target_patterns_json,
    }
    async with get_connection() as conn:
        cursor = await conn.execute(merge_sql, params)
        await conn.commit()
        await cursor.close()

    return ProfileTargetPermissionsResponse(
        targets_type=payload.targets_type,
        target_names=payload.target_names or [],
        target_patterns=payload.target_patterns or [],
    )


def match_targets(
    user_permissions: list[ProfileTargetPermissionsResponse],
    available_targets: list[str],
) -> list[str]:
    """Cumulate target permissions across profiles and filter against inventory (AC4).

    user_permissions: list of target permission responses (one per user profile).
    available_targets: inventory of target names (e.g. from Epic 4 later).
    Returns: sorted list of unique target names allowed (subset of available_targets).
    """
    allowed: set[str] = set()
    available_set = set(available_targets)

    for perm in user_permissions:
        if perm.targets_type == "all":
            allowed.update(available_targets)
            continue
        if perm.targets_type == "list":
            for name in perm.target_names or []:
                if name in available_set:
                    allowed.add(name)
            continue
        if perm.targets_type == "pattern":
            for pattern in perm.target_patterns or []:
                for t in available_targets:
                    if fnmatch.fnmatch(t, pattern):
                        allowed.add(t)

    return sorted(allowed)
