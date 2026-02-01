"""Profile repository using raw SQL via python-oracledb (Story 2.9, FR25a)."""

from __future__ import annotations

import oracledb

from app.core.database import get_connection
from app.core.exceptions import InvalidStateError
from app.models.profile import (
    ProfileCreate,
    ProfileListItem,
    ProfileResponse,
    ProfileUpdate,
)
from app.repositories import profile_action_permission_repository
from app.repositories import profile_target_permission_repository


def _row_to_response(row: tuple) -> ProfileResponse:
    """Map DB row (ID, NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR, CREATED_AT, UPDATED_AT) to ProfileResponse."""
    return ProfileResponse(
        id=row[0],
        name=row[1],
        description=row[2],
        ad_group=row[3],
        is_admin=bool(row[4]),
        is_auditor=bool(row[5]),
        created_at=row[6],
        updated_at=row[7],
    )


def _row_to_list_item(row: tuple, permission_count: int = 0) -> ProfileListItem:
    """Map DB row to ProfileListItem. permission_count computed from actions + targets permissions."""
    return ProfileListItem(
        id=row[0],
        name=row[1],
        ad_group=row[2],
        permission_count=permission_count,
        created_at=row[3],
    )


def _count_actions_permissions(
    actions: object | None,
) -> int:
    """Count effective action permissions (type all=1, else sum of list lengths)."""
    if actions is None:
        return 0
    a = actions
    if getattr(a, "actions_type", None) == "all":
        return 1
    return (
        len(getattr(a, "action_ids", []) or [])
        + len(getattr(a, "tag_patterns", []) or [])
        + len(getattr(a, "environments", []) or [])
    )


def _count_targets_permissions(
    targets: object | None,
) -> int:
    """Count effective target permissions (type all=1, else sum of list lengths)."""
    if targets is None:
        return 0
    t = targets
    if getattr(t, "targets_type", None) == "all":
        return 1
    return (
        len(getattr(t, "target_names", []) or [])
        + len(getattr(t, "target_patterns", []) or [])
    )


async def create(data: ProfileCreate) -> ProfileResponse:
    """Create a profile. Returns ProfileResponse."""
    query = """
        INSERT INTO PROFILES (NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR)
        VALUES (:name, :description, :ad_group, :is_admin, :is_auditor)
        RETURNING ID INTO :out_id
    """
    params = {
        "name": data.name,
        "description": data.description,
        "ad_group": data.ad_group,
        "is_admin": 1 if data.is_admin else 0,
        "is_auditor": 1 if data.is_auditor else 0,
    }
    async with get_connection() as conn:
        cursor = conn.cursor()
        out_id = cursor.var(int)
        params["out_id"] = out_id
        try:
            await cursor.execute(query, params)
            await conn.commit()
            cursor.close()
            pid = out_id.getvalue()[0]
        except oracledb.IntegrityError:
            await conn.rollback()
            raise InvalidStateError(
                code="DUPLICATE_NAME",
                message="Un profil avec ce nom existe déjà.",
                details={"name": data.name},
            ) from None
    return await get_by_id(pid)  # type: ignore[return-value]


async def get_by_id(profile_id: int) -> ProfileResponse | None:
    """Fetch profile by ID. Returns None if not found."""
    query = """
        SELECT ID, NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR, CREATED_AT, UPDATED_AT
        FROM PROFILES WHERE ID = :profile_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"profile_id": profile_id})
        row = await cursor.fetchone()
        cursor.close()
    if row is None:
        return None
    return _row_to_response(row)


async def get_by_name(name: str) -> ProfileResponse | None:
    """Fetch profile by name (Story 2.13 import upsert). Returns None if not found."""
    query = """
        SELECT ID, NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR, CREATED_AT, UPDATED_AT
        FROM PROFILES WHERE NAME = :name
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"name": name})
        row = await cursor.fetchone()
        cursor.close()
    if row is None:
        return None
    return _row_to_response(row)


async def get_all() -> list[ProfileListItem]:
    """Return all profiles for list view with permission_count from actions + targets permissions."""
    query = """
        SELECT ID, NAME, AD_GROUP, CREATED_AT
        FROM PROFILES
        ORDER BY NAME
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {})
        rows = await cursor.fetchall()
        cursor.close()
    if not rows:
        return []
    profile_ids = [row[0] for row in rows]
    actions_map = await profile_action_permission_repository.get_actions_permissions_for_profile_ids(
        profile_ids
    )
    targets_map = await profile_target_permission_repository.get_target_permissions_for_profile_ids(
        profile_ids
    )
    return [
        _row_to_list_item(
            row,
            permission_count=(
                _count_actions_permissions(actions_map.get(row[0]))
                + _count_targets_permissions(targets_map.get(row[0]))
            ),
        )
        for row in rows
    ]


async def find_by_ad_groups(ad_groups: list[str]) -> list[ProfileResponse]:
    """Return profiles whose AD_GROUP is in the given list (Story 2.12, AC1). Empty list -> empty result."""
    if not ad_groups:
        return []
    query = """
        SELECT ID, NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR, CREATED_AT, UPDATED_AT
        FROM PROFILES
        WHERE AD_GROUP IN (:ad_groups)
        ORDER BY NAME
    """
    # Oracle in-clause: bind list as multiple params
    params = {f"g{i}": g for i, g in enumerate(ad_groups)}
    placeholders = ", ".join(f":g{i}" for i in range(len(ad_groups)))
    query = query.replace(":ad_groups", placeholders)
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()
    return [_row_to_response(row) for row in rows]


async def update(profile_id: int, data: ProfileUpdate) -> ProfileResponse | None:
    """Update profile by ID. Merges non-None fields. Returns None if not found."""
    existing = await get_by_id(profile_id)
    if existing is None:
        return None
    updates: dict[str, str | int | None] = {
        "name": data.name if data.name is not None else existing.name,
        "description": data.description if data.description is not None else existing.description,
        "ad_group": data.ad_group if data.ad_group is not None else existing.ad_group,
        "is_admin": (1 if data.is_admin else 0) if data.is_admin is not None else (1 if existing.is_admin else 0),
        "is_auditor": (1 if data.is_auditor else 0) if data.is_auditor is not None else (1 if existing.is_auditor else 0),
    }
    query = """
        UPDATE PROFILES
        SET NAME = :name, DESCRIPTION = :description, AD_GROUP = :ad_group,
            IS_ADMIN = :is_admin, IS_AUDITOR = :is_auditor, UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :profile_id
    """
    params = {**updates, "profile_id": profile_id}
    async with get_connection() as conn:
        try:
            cursor = conn.cursor()
            await cursor.execute(query, params)
            await conn.commit()
            cursor.close()
        except oracledb.IntegrityError:
            await conn.rollback()
            raise InvalidStateError(
                code="DUPLICATE_NAME",
                message="Un profil avec ce nom existe déjà.",
                details={"name": updates["name"]},
            ) from None
    return await get_by_id(profile_id)


async def delete(profile_id: int) -> bool:
    """Delete profile by ID. Returns True if deleted, False if not found."""
    query = "DELETE FROM PROFILES WHERE ID = :profile_id"
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"profile_id": profile_id})
        await conn.commit()
        n = cursor.rowcount
        cursor.close()
    return n > 0
