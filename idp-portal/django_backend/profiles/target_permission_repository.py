"""
ProfileTargetPermissionRepository — normalized read API for profile target permissions.

Story 78.15: Contract phase — legacy CLOB columns dropped (V136). All reads come
exclusively from normalized tables PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS,
PROFILE_TARGET_ATTRIBUTE_FILTERS, PROFILE_TARGET_EXCLUSIONS (created in Story 78.12,
V132/V133).

The feature flag PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED and dual-write
(sync_from_json) have been removed. Only normalized readers remain.
"""
from __future__ import annotations

from profiles.models import ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)


def get_target_names(perm: ProfileTargetPermission) -> list[str]:
    """Return target names from the normalized PROFILE_TARGET_ALLOWLIST table."""
    return get_target_names_from_normalized(perm.profile_id)


def get_target_patterns(perm: ProfileTargetPermission) -> list[str]:
    """Return target patterns from the normalized PROFILE_TARGET_PATTERNS table."""
    return get_target_patterns_from_normalized(perm.profile_id)


def get_filter_by_attribute(perm: ProfileTargetPermission) -> dict[str, list[str]] | None:
    """Return filter_by_attribute from the normalized PROFILE_TARGET_ATTRIBUTE_FILTERS table."""
    return get_filter_by_attribute_from_normalized(perm.profile_id)


def get_exclusion_patterns(perm: ProfileTargetPermission) -> list[str]:
    """Return exclusion patterns from the normalized PROFILE_TARGET_EXCLUSIONS table."""
    return get_exclusion_patterns_from_normalized(perm.profile_id)


def get_target_names_from_normalized(profile_id: int) -> list[str]:
    """Return target names from the normalized PROFILE_TARGET_ALLOWLIST table."""
    return sorted(
        ProfileTargetAllowlist.objects
        .filter(profile_id=profile_id)
        .values_list('target_name', flat=True)
    )


def get_target_patterns_from_normalized(profile_id: int) -> list[str]:
    """Return target patterns from the normalized PROFILE_TARGET_PATTERNS table."""
    return sorted(
        ProfileTargetPattern.objects
        .filter(profile_id=profile_id)
        .values_list('pattern', flat=True)
    )


def get_filter_by_attribute_from_normalized(profile_id: int) -> dict[str, list[str]] | None:
    """Return filter_by_attribute from normalized table, reconstructing the dict."""
    rows = list(ProfileTargetAttributeFilter.objects.filter(profile_id=profile_id))
    if not rows:
        return None
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row.attribute_key, []).append(row.attribute_value)
    return {k: sorted(v) for k, v in sorted(result.items())}


def get_exclusion_patterns_from_normalized(profile_id: int) -> list[str]:
    """Return exclusion patterns from the normalized PROFILE_TARGET_EXCLUSIONS table."""
    return sorted(
        ProfileTargetExclusion.objects
        .filter(profile_id=profile_id)
        .values_list('exclusion_pattern', flat=True)
    )
