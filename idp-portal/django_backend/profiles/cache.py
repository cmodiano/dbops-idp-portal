"""
Cache constants and utilities for RBAC permissions.

Story 30.14 - AC3: Cache configuration for RBAC permission lookups.
Story 34.3 - NEW-3: invalidate_permissions_cache() moved here from views.py (SRP).
"""

import logging

from django.core.cache import cache

# Cache key for RBAC version — incremented on every profile/permission change.
# Individual user caches include this version, so a version bump invalidates all.
RBAC_CACHE_VERSION_KEY = 'rbac:cache_version'
RBAC_CACHE_TTL = 300  # 5 minutes

logger = logging.getLogger(__name__)


def invalidate_permissions_cache() -> None:
    """
    Invalidate RBAC permissions cache for all users.

    Deletes the global cache version key (RBAC_CACHE_VERSION_KEY), which causes
    all user-specific permission caches (rbac:permissions:user:{id}:v:{version})
    to miss on the next request. This is called after profile/permission modifications.

    TTL: 5 minutes (RBAC_CACHE_TTL).

    Story 30.14 - AC3: Cache invalidation implementation.
    Story 34.3 - NEW-3: Moved from profiles/views.py to profiles/cache.py (SRP).
    """
    try:
        cache.delete(RBAC_CACHE_VERSION_KEY)
        logger.info(
            'rbac_permissions_cache_invalidated',
            extra={'cache_key': RBAC_CACHE_VERSION_KEY, 'ttl_seconds': RBAC_CACHE_TTL},
        )
    except Exception:  # noqa: BLE001
        # Cache unavailability should not break profile operations
        logger.warning('rbac_permissions_cache_invalidation_failed', exc_info=True)
