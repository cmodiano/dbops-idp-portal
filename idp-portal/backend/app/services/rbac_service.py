"""RBAC service: permission evaluation with in-memory cache (Story 2.12: cumulative permissions)."""

from __future__ import annotations

from cachetools import TTLCache

from app.models.profile import CumulativePermissionsResponse
from app.repositories import (
    profile_action_permission_repository,
    profile_target_permission_repository,
    user_repository,
)

# Navigation tabs by profile — DBOPS sees Admin, others do not
_NAVIGATION_MAP: dict[str, list[str]] = {
    "dbops": ["catalog", "executions", "dashboard", "admin"],
}
_DEFAULT_TABS: list[str] = ["catalog", "executions", "dashboard"]

# Permission cache: key = "user_id:action_id:environment", value = bool
_permission_cache: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=60)

# Story 2.12: cumulative permissions cache — key = user_id, value = CumulativePermissionsResponse, TTL 60s
_cumulative_permissions_cache: TTLCache[str, CumulativePermissionsResponse] = TTLCache(
    maxsize=10000, ttl=60
)


def get_user_navigation_permissions(profile: str) -> list[str]:
    """Return navigation tab keys based on user profile."""
    return _NAVIGATION_MAP.get(profile.lower(), _DEFAULT_TABS)


async def get_cumulative_permissions(profile_ids: list[int]) -> CumulativePermissionsResponse:
    """Union of action/target/environment permissions across profiles (Story 2.12, AC2, AC4)."""
    if not profile_ids:
        return CumulativePermissionsResponse(
            actions_type="list",
            targets_type="list",
        )
    action_ids: set[int] = set()
    tag_patterns: set[str] = set()
    environments: set[str] = set()
    targets_type_all = False
    actions_type_all = False
    target_names: set[str] = set()
    target_patterns_set: set[str] = set()

    for pid in profile_ids:
        act = await profile_action_permission_repository.get_actions_permissions(pid)
        if act:
            if act.actions_type == "all":
                actions_type_all = True
            else:
                action_ids.update(act.action_ids or [])
                tag_patterns.update(act.tag_patterns or [])
            environments.update(act.environments or [])

        tgt = await profile_target_permission_repository.get_target_permissions(pid)
        if tgt:
            if tgt.targets_type == "all":
                targets_type_all = True
            else:
                target_names.update(tgt.target_names or [])
                target_patterns_set.update(tgt.target_patterns or [])

    act_type: str = "all" if actions_type_all else ("pattern" if tag_patterns else "list")
    tgt_type: str = "all" if targets_type_all else ("pattern" if target_patterns_set else "list")
    return CumulativePermissionsResponse(
        actions_type=act_type,
        action_ids=sorted(action_ids),
        tag_patterns=sorted(tag_patterns),
        environments=sorted(environments),
        targets_type=tgt_type,
        target_names=sorted(target_names),
        target_patterns=sorted(target_patterns_set),
    )


async def get_cumulative_permissions_cached(
    user_id: int, profile_ids: list[int]
) -> CumulativePermissionsResponse:
    """Get cumulative permissions with 60s TTL cache (AC4, AC5)."""
    cache_key = str(user_id)
    if cache_key in _cumulative_permissions_cache:
        return _cumulative_permissions_cache[cache_key]
    result = await get_cumulative_permissions(profile_ids)
    _cumulative_permissions_cache[cache_key] = result
    return result


def invalidate_permissions_cache() -> None:
    """Invalidate all cached cumulative permissions (AC5: on profile/permissions admin change)."""
    _cumulative_permissions_cache.clear()


def invalidate_cache(user_id: int) -> None:
    """Remove all cached permissions for a user (legacy USER_PERMISSIONS cache)."""
    keys_to_remove = [k for k in _permission_cache if k.startswith(f"{user_id}:")]
    for key in keys_to_remove:
        del _permission_cache[key]
    if str(user_id) in _cumulative_permissions_cache:
        del _cumulative_permissions_cache[str(user_id)]


async def can_execute(user_id: int, action_id: int, environment: str) -> bool:
    """Check if user has permission to execute action in environment. Cached 60s."""
    cache_key = f"{user_id}:{action_id}:{environment}"
    if cache_key in _permission_cache:
        return _permission_cache[cache_key]

    result = await user_repository.has_permission(user_id, action_id, environment)
    _permission_cache[cache_key] = result
    return result
