"""
Cache constants for RBAC permissions.

Story 30.14 - AC3: Cache configuration for RBAC permission lookups.
"""

# Cache key for RBAC version — incremented on every profile/permission change.
# Individual user caches include this version, so a version bump invalidates all.
RBAC_CACHE_VERSION_KEY = 'rbac:cache_version'
RBAC_CACHE_TTL = 300  # 5 minutes
