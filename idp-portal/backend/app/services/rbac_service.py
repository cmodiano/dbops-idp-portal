"""RBAC service: permission evaluation with in-memory cache (Story 2.12: cumulative permissions).

Story 7.3: Granular RBAC by action x profile x environment.
"""

from __future__ import annotations

import structlog
from cachetools import TTLCache

from app.models.profile import CumulativePermissionsResponse
from app.repositories import (
    catalog_repository,
    profile_action_permission_repository,
    profile_repository,
    profile_target_permission_repository,
    user_repository,
)

logger = structlog.get_logger()

# Navigation tabs by profile — DBOPS sees Admin, others do not
_NAVIGATION_MAP: dict[str, list[str]] = {
    "dbops": ["catalog", "executions", "dashboard", "admin"],
}
_DEFAULT_TABS: list[str] = ["catalog", "executions", "dashboard"]

# Story 7.1: Business profiles for simplified UI
# Includes variations for backward compatibility with seed data
_BUSINESS_PROFILES: set[str] = {"client_business", "business"}

# Permission cache: key = "user_id:action_id:environment", value = bool
_permission_cache: TTLCache[str, bool] = TTLCache(maxsize=10000, ttl=60)

# Story 2.12: cumulative permissions cache — key = user_id, value = CumulativePermissionsResponse, TTL 60s
_cumulative_permissions_cache: TTLCache[str, CumulativePermissionsResponse] = TTLCache(
    maxsize=10000, ttl=60
)


def get_user_navigation_permissions(profile: str) -> list[str]:
    """Return navigation tab keys based on user profile."""
    return _NAVIGATION_MAP.get(profile.lower(), _DEFAULT_TABS)


def is_business_profile(profile: str) -> bool:
    """Story 7.1: Check if profile is a business profile (simplified UI)."""
    return profile.lower() in _BUSINESS_PROFILES


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
    """Invalidate all cached permissions (AC5: on profile/permissions admin change).

    Clears both the cumulative permissions cache and the per-request permission cache
    to ensure permission changes take effect immediately.
    """
    _cumulative_permissions_cache.clear()
    _permission_cache.clear()


def invalidate_cache(user_id: int) -> None:
    """Remove all cached permissions for a user (legacy USER_PERMISSIONS cache)."""
    keys_to_remove = [k for k in _permission_cache if k.startswith(f"{user_id}:")]
    for key in keys_to_remove:
        del _permission_cache[key]
    if str(user_id) in _cumulative_permissions_cache:
        del _cumulative_permissions_cache[str(user_id)]


async def can_execute(user_id: int, action_id: int, environment: str) -> bool:
    """Check if user has permission to execute action in environment (Story 7.3, AC4, AC5).

    Evaluates granular RBAC combining action x profile x environment:
    1. Get user's profile IDs from AD groups
    2. Get cumulative permissions (cached 60s)
    3. Check environment is in allowed environments
    4. Check action permission by: actions_type="all", action_id in list, or tag_patterns match

    Args:
        user_id: User ID to check permissions for
        action_id: Action ID being executed
        environment: Target environment (DEV, STAGING, PROD, etc.)

    Returns:
        True if user has permission, False otherwise
    """
    cache_key = f"{user_id}:{action_id}:{environment}"
    if cache_key in _permission_cache:
        cached_result = _permission_cache[cache_key]
        logger.debug(
            "rbac_can_execute_cache_hit",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
            result=cached_result,
        )
        return cached_result

    # Get user's profile IDs
    user_data = await user_repository.get_by_id(user_id)
    if not user_data:
        logger.warning(
            "rbac_permission_denied_user_not_found",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
        )
        _permission_cache[cache_key] = False
        return False

    # Get profiles by AD group (user's profile field)
    user_profile = user_data.get("profile")
    if not user_profile:
        logger.warning(
            "rbac_permission_denied_no_profile",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
        )
        _permission_cache[cache_key] = False
        return False

    profiles = await profile_repository.find_by_ad_groups([user_profile.lower()])
    profile_ids = [p.id for p in profiles] if profiles else []

    if not profile_ids:
        logger.warning(
            "rbac_permission_denied_no_profile_ids",
            user_id=user_id,
            user_profile=user_profile,
            action_id=action_id,
            environment=environment,
        )
        _permission_cache[cache_key] = False
        return False

    # Get cumulative permissions (cached)
    perms = await get_cumulative_permissions_cached(user_id, profile_ids)

    # Check environment permission
    allowed_envs = [e.upper() for e in (perms.environments or [])]
    env_upper = environment.upper()
    if env_upper not in allowed_envs:
        logger.warning(
            "rbac_permission_denied_environment",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
            allowed_environments=perms.environments,
        )
        _permission_cache[cache_key] = False
        return False

    # Check action permission based on actions_type
    if perms.actions_type == "all":
        logger.info(
            "rbac_permission_granted_all_actions",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
        )
        _permission_cache[cache_key] = True
        return True

    # Check if action_id is in allowed list
    if action_id in (perms.action_ids or []):
        logger.info(
            "rbac_permission_granted_action_id",
            user_id=user_id,
            action_id=action_id,
            environment=environment,
        )
        _permission_cache[cache_key] = True
        return True

    # Check tag patterns match
    if perms.tag_patterns:
        action_tags = await catalog_repository.get_tags_for_action(action_id)
        matching_tags = set(action_tags) & set(perms.tag_patterns)
        if matching_tags:
            logger.info(
                "rbac_permission_granted_tag_pattern",
                user_id=user_id,
                action_id=action_id,
                environment=environment,
                matching_tags=list(matching_tags),
            )
            _permission_cache[cache_key] = True
            return True

    logger.warning(
        "rbac_permission_denied_no_match",
        user_id=user_id,
        action_id=action_id,
        environment=environment,
        actions_type=perms.actions_type,
        action_ids=perms.action_ids,
        tag_patterns=perms.tag_patterns,
    )
    _permission_cache[cache_key] = False
    return False
