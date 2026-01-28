"""RBAC service: permission evaluation with in-memory cache."""

from __future__ import annotations

from cachetools import TTLCache

from app.repositories import user_repository

# Navigation tabs by profile — DBOPS sees Admin, others do not
_NAVIGATION_MAP: dict[str, list[str]] = {
    "dbops": ["catalog", "executions", "dashboard", "admin"],
}
_DEFAULT_TABS: list[str] = ["catalog", "executions", "dashboard"]

# Permission cache: key = "user_id:action_id:environment", value = bool
_permission_cache: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=60)


def get_user_navigation_permissions(profile: str) -> list[str]:
    """Return navigation tab keys based on user profile."""
    return _NAVIGATION_MAP.get(profile.lower(), _DEFAULT_TABS)


async def can_execute(user_id: int, action_id: int, environment: str) -> bool:
    """Check if user has permission to execute action in environment. Cached 60s."""
    cache_key = f"{user_id}:{action_id}:{environment}"
    if cache_key in _permission_cache:
        return _permission_cache[cache_key]

    result = await user_repository.has_permission(user_id, action_id, environment)
    _permission_cache[cache_key] = result
    return result


def invalidate_cache(user_id: int) -> None:
    """Remove all cached permissions for a user."""
    keys_to_remove = [k for k in _permission_cache if k.startswith(f"{user_id}:")]
    for key in keys_to_remove:
        del _permission_cache[key]
