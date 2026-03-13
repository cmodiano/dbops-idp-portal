"""
ProfileActionPermissionRepository — normalized read API for profile action permissions.

Story 78.15: Contract phase — legacy CLOB columns dropped (V136). All reads come
exclusively from normalized tables PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS,
PROFILE_ACTION_ENVS (created in Story 78.11, V130/V131).

The feature flag PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED and dual-write
(sync_from_json) have been removed. Only normalized readers remain.
"""
from __future__ import annotations

from profiles.models import ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)


def get_action_ids(perm: ProfileActionPermission) -> list[int]:
    """Return action IDs from the normalized PROFILE_ACTION_ALLOWLIST table."""
    return get_action_ids_from_normalized(perm.profile_id)


def get_tag_patterns(perm: ProfileActionPermission) -> list[str]:
    """Return tag patterns from the normalized PROFILE_ACTION_TAG_PATTERNS table."""
    return get_tag_patterns_from_normalized(perm.profile_id)


def get_environments(perm: ProfileActionPermission) -> list[str]:
    """Return environments from the normalized PROFILE_ACTION_ENVS table."""
    return get_environments_from_normalized(perm.profile_id)


def get_action_ids_from_normalized(profile_id: int) -> list[int]:
    """Return action IDs from the normalized PROFILE_ACTION_ALLOWLIST table."""
    return sorted(
        ProfileActionAllowlist.objects
        .filter(profile_id=profile_id)
        .values_list('action_id', flat=True)
    )


def get_tag_patterns_from_normalized(profile_id: int) -> list[str]:
    """Return tag patterns from the normalized PROFILE_ACTION_TAG_PATTERNS table."""
    return sorted(
        ProfileActionTagPattern.objects
        .filter(profile_id=profile_id)
        .values_list('tag_pattern', flat=True)
    )


def get_environments_from_normalized(profile_id: int) -> list[str]:
    """Return environments from the normalized PROFILE_ACTION_ENVS table."""
    return sorted(
        ProfileActionEnv.objects
        .filter(profile_id=profile_id)
        .values_list('environment', flat=True)
    )
