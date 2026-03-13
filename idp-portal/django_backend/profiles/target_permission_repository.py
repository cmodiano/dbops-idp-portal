"""
Story 78.12: ProfileTargetPermissionRepository — dual-read service for profile target permissions.

Provides a single API to read target permissions from either the JSON CLOB
fields (PROFILE_TARGET_PERMISSIONS) or the normalized tables (PROFILE_TARGET_ALLOWLIST,
PROFILE_TARGET_PATTERNS, PROFILE_TARGET_ATTRIBUTE_FILTERS, PROFILE_TARGET_EXCLUSIONS),
controlled by the feature flag PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED.
"""
from __future__ import annotations

import structlog
from django.conf import settings

from profiles.models import ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
    ProfileTargetExclusion,
    ProfileTargetPattern,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# JSON CLOB readers (existing behavior)
# ---------------------------------------------------------------------------

def get_target_names_from_json(perm: ProfileTargetPermission) -> list[str]:
    """Return target names from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_target_names())


def get_target_patterns_from_json(perm: ProfileTargetPermission) -> list[str]:
    """Return target patterns from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_target_patterns())


def get_filter_by_attribute_from_json(perm: ProfileTargetPermission) -> dict[str, list[str]] | None:
    """Return filter_by_attribute from JSON CLOB (sorted values for reproducibility)."""
    raw = perm.get_filter_by_attribute()
    if not raw:
        return None
    return {k: sorted(v) for k, v in sorted(raw.items())}


def get_exclusion_patterns_from_json(perm: ProfileTargetPermission) -> list[str]:
    """Return exclusion patterns from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_exclusion_patterns())


# ---------------------------------------------------------------------------
# Normalized table readers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API — dispatch based on feature flag
# ---------------------------------------------------------------------------

def get_target_names(perm: ProfileTargetPermission) -> list[str]:
    """Return target names, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_target_names_from_normalized(perm.profile_id)
    return get_target_names_from_json(perm)


def get_target_patterns(perm: ProfileTargetPermission) -> list[str]:
    """Return target patterns, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_target_patterns_from_normalized(perm.profile_id)
    return get_target_patterns_from_json(perm)


def get_filter_by_attribute(perm: ProfileTargetPermission) -> dict[str, list[str]] | None:
    """Return filter_by_attribute, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_filter_by_attribute_from_normalized(perm.profile_id)
    return get_filter_by_attribute_from_json(perm)


def get_exclusion_patterns(perm: ProfileTargetPermission) -> list[str]:
    """Return exclusion patterns, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_exclusion_patterns_from_normalized(perm.profile_id)
    return get_exclusion_patterns_from_json(perm)


# ---------------------------------------------------------------------------
# Sync — write normalized tables from JSON CLOB
# ---------------------------------------------------------------------------

def sync_from_json(profile_id: int) -> None:
    """
    Synchronize normalized tables from the JSON CLOB fields.

    Idempotent: deletes existing rows for this profile and re-inserts.
    Must be called within a transaction.atomic() block.
    """
    try:
        perm = ProfileTargetPermission.objects.get(profile_id=profile_id)
    except ProfileTargetPermission.DoesNotExist:
        # No permission record — clean up any stale normalized data
        ProfileTargetAllowlist.objects.filter(profile_id=profile_id).delete()
        ProfileTargetPattern.objects.filter(profile_id=profile_id).delete()
        ProfileTargetAttributeFilter.objects.filter(profile_id=profile_id).delete()
        ProfileTargetExclusion.objects.filter(profile_id=profile_id).delete()
        return

    # Delete existing normalized data
    ProfileTargetAllowlist.objects.filter(profile_id=profile_id).delete()
    ProfileTargetPattern.objects.filter(profile_id=profile_id).delete()
    ProfileTargetAttributeFilter.objects.filter(profile_id=profile_id).delete()
    ProfileTargetExclusion.objects.filter(profile_id=profile_id).delete()

    # Insert target names
    target_names = perm.get_target_names()
    if target_names:
        seen: set[str] = set()
        objs = []
        for name in target_names:
            if name not in seen:
                seen.add(name)
                objs.append(ProfileTargetAllowlist(profile_id=profile_id, target_name=name))
        if objs:
            ProfileTargetAllowlist.objects.bulk_create(objs)

    # Insert target patterns
    target_patterns = perm.get_target_patterns()
    if target_patterns:
        seen_p: set[str] = set()
        objs_p = []
        for pat in target_patterns:
            if pat not in seen_p:
                seen_p.add(pat)
                objs_p.append(ProfileTargetPattern(profile_id=profile_id, pattern=pat))
        if objs_p:
            ProfileTargetPattern.objects.bulk_create(objs_p)

    # Insert filter_by_attribute
    filter_by_attr = perm.get_filter_by_attribute()
    attr_count = 0
    if filter_by_attr:
        seen_af: set[tuple[str, str]] = set()
        objs_af = []
        for key, values in filter_by_attr.items():
            if isinstance(values, list):
                for val in values:
                    pair = (key, val)
                    if pair not in seen_af:
                        seen_af.add(pair)
                        objs_af.append(ProfileTargetAttributeFilter(
                            profile_id=profile_id,
                            attribute_key=key,
                            attribute_value=val,
                        ))
        if objs_af:
            ProfileTargetAttributeFilter.objects.bulk_create(objs_af)
        attr_count = len(objs_af)

    # Insert exclusion patterns
    exclusion_patterns = perm.get_exclusion_patterns()
    if exclusion_patterns:
        seen_e: set[str] = set()
        objs_e = []
        for ep in exclusion_patterns:
            if ep not in seen_e:
                seen_e.add(ep)
                objs_e.append(ProfileTargetExclusion(profile_id=profile_id, exclusion_pattern=ep))
        if objs_e:
            ProfileTargetExclusion.objects.bulk_create(objs_e)

    logger.info(
        "profile_target_permissions_synced",
        profile_id=profile_id,
        target_names_count=len(target_names),
        target_patterns_count=len(target_patterns),
        attribute_filters_count=attr_count,
        exclusion_patterns_count=len(exclusion_patterns),
    )
