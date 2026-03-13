"""
Story 78.11: ProfileActionPermissionRepository — dual-read service for profile action permissions.

Provides a single API to read action permissions from either the JSON CLOB
fields (PROFILE_ACTION_PERMISSIONS) or the normalized tables (PROFILE_ACTION_ALLOWLIST,
PROFILE_ACTION_TAG_PATTERNS, PROFILE_ACTION_ENVS), controlled by the feature flag
PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED.
"""
from __future__ import annotations

import structlog
from django.conf import settings

from profiles.models import ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
    ProfileActionEnv,
    ProfileActionTagPattern,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# JSON CLOB readers (existing behavior)
# ---------------------------------------------------------------------------

def get_action_ids_from_json(perm: ProfileActionPermission) -> list[int]:
    """Return action IDs from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_action_ids())


def get_tag_patterns_from_json(perm: ProfileActionPermission) -> list[str]:
    """Return tag patterns from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_tag_patterns())


def get_environments_from_json(perm: ProfileActionPermission) -> list[str]:
    """Return environments from the JSON CLOB field (sorted for reproducibility)."""
    return sorted(perm.get_environments())


# ---------------------------------------------------------------------------
# Normalized table readers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API — dispatch based on feature flag
# ---------------------------------------------------------------------------

def get_action_ids(perm: ProfileActionPermission) -> list[int]:
    """Return action IDs, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_action_ids_from_normalized(perm.profile_id)
    return get_action_ids_from_json(perm)


def get_tag_patterns(perm: ProfileActionPermission) -> list[str]:
    """Return tag patterns, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_tag_patterns_from_normalized(perm.profile_id)
    return get_tag_patterns_from_json(perm)


def get_environments(perm: ProfileActionPermission) -> list[str]:
    """Return environments, dispatching based on feature flag."""
    if getattr(settings, 'PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED', False):
        return get_environments_from_normalized(perm.profile_id)
    return get_environments_from_json(perm)


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
        perm = ProfileActionPermission.objects.get(profile_id=profile_id)
    except ProfileActionPermission.DoesNotExist:
        # No permission record — clean up any stale normalized data
        ProfileActionAllowlist.objects.filter(profile_id=profile_id).delete()
        ProfileActionTagPattern.objects.filter(profile_id=profile_id).delete()
        ProfileActionEnv.objects.filter(profile_id=profile_id).delete()
        return

    # Delete existing normalized data
    ProfileActionAllowlist.objects.filter(profile_id=profile_id).delete()
    ProfileActionTagPattern.objects.filter(profile_id=profile_id).delete()
    ProfileActionEnv.objects.filter(profile_id=profile_id).delete()

    # Insert action IDs
    action_ids = perm.get_action_ids()
    if action_ids:
        seen: set[int] = set()
        objs = []
        for aid in action_ids:
            if aid not in seen:
                seen.add(aid)
                objs.append(ProfileActionAllowlist(profile_id=profile_id, action_id=aid))
        if objs:
            ProfileActionAllowlist.objects.bulk_create(objs)

    # Insert tag patterns
    tag_patterns = perm.get_tag_patterns()
    if tag_patterns:
        seen_str: set[str] = set()
        objs_tp = []
        for tp in tag_patterns:
            if tp not in seen_str:
                seen_str.add(tp)
                objs_tp.append(ProfileActionTagPattern(profile_id=profile_id, tag_pattern=tp))
        if objs_tp:
            ProfileActionTagPattern.objects.bulk_create(objs_tp)

    # Insert environments
    environments = perm.get_environments()
    if environments:
        seen_env: set[str] = set()
        objs_env = []
        for env in environments:
            if env not in seen_env:
                seen_env.add(env)
                objs_env.append(ProfileActionEnv(profile_id=profile_id, environment=env))
        if objs_env:
            ProfileActionEnv.objects.bulk_create(objs_env)

    logger.info(
        "profile_action_permissions_synced",
        profile_id=profile_id,
        action_ids_count=len(action_ids),
        tag_patterns_count=len(tag_patterns),
        environments_count=len(environments),
    )
