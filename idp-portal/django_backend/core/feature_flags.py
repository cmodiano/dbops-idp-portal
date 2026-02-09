"""
Story 17.12: Feature Flag Service.

Provides a singleton service for evaluating feature flags with
cache-based performance and context-aware rollout evaluation.
"""

import hashlib
import json

import structlog
from django.core.cache import cache
from django.conf import settings
from django.db import DatabaseError, IntegrityError, OperationalError

from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Default cache TTL for feature flags (seconds)
DEFAULT_CACHE_TTL = 300  # 5 minutes


def _get_cache_ttl():
    """Get feature flags cache TTL from settings."""
    return getattr(settings, 'FEATURE_FLAGS_CACHE_TTL', DEFAULT_CACHE_TTL)


def _get_flags_source():
    """Get feature flags data source (env or database)."""
    return getattr(settings, 'FEATURE_FLAGS_SOURCE', 'env')


def _get_flags_enabled():
    """Check if feature flags system is globally enabled."""
    return getattr(settings, 'FEATURE_FLAGS_ENABLED', True)


def _load_flags_from_env():
    """Load feature flags from FEATURE_FLAGS env var (JSON)."""
    raw = getattr(settings, 'FEATURE_FLAGS', '{}')
    if not raw:
        return {}
    try:
        flags = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(flags, dict):
            logger.warning("feature_flags_env_invalid_type", type=type(flags).__name__)
            return {}
        return flags
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("feature_flags_env_parse_error", error=str(e))
        return {}


def _load_flags_from_database():
    """Load feature flags from database."""
    from core.models import FeatureFlag
    flags = {}
    try:
        for flag in FeatureFlag.objects.all():
            flags[flag.flag_key] = {
                'enabled': flag.enabled,
                'rollout_percent': flag.rollout_percent,
            }
    except (DatabaseError, IntegrityError, OperationalError) as e:
        logger.error(
            "feature_flags_db_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
            correlation_id=get_correlation_id(),
        )
        # Return empty dict (fallback) - feature flags non disponibles ne doivent pas bloquer l'app
    except Exception as e:
        # Story 22.11: Justified broad catch - Unexpected ORM errors must not break app startup
        # Pattern: Return empty dict as graceful degradation instead of raising
        logger.error(
            "feature_flags_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
            correlation_id=get_correlation_id(),
        )
        # Return empty dict (fallback) - permet à l'app de démarrer même si feature flags fail
    return flags


def _get_all_flags():
    """Get all flags from configured source, with caching."""
    cache_key = 'feature_flags:all'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    source = _get_flags_source()
    if source == 'database':
        flags = _load_flags_from_database()
    else:
        flags = _load_flags_from_env()

    cache.set(cache_key, flags, _get_cache_ttl())
    logger.debug("feature_flag_cache_miss", source=source, flag_count=len(flags))
    return flags


def _get_flag_config(flag_key):
    """Get configuration for a specific flag."""
    cache_key = f'feature_flag:{flag_key}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    all_flags = _get_all_flags()
    flag_config = all_flags.get(flag_key)

    if flag_config is not None:
        cache.set(cache_key, flag_config, _get_cache_ttl())

    return flag_config


def is_enabled(flag_key, context=None):
    """
    Check if a feature flag is enabled.

    Args:
        flag_key: The feature flag key to check.
        context: Optional dict with user_id, profile, environment for rollout evaluation.

    Returns:
        bool: True if the flag is enabled for the given context.
    """
    if not _get_flags_enabled():
        return False

    flag_config = _get_flag_config(flag_key)

    if flag_config is None:
        logger.debug("feature_flag_not_found", flag_key=flag_key)
        return False

    enabled = flag_config.get('enabled', False)
    rollout_percent = flag_config.get('rollout_percent', 100)

    if not enabled:
        return False

    # If rollout is 100%, flag is fully enabled
    if rollout_percent >= 100:
        return True

    # If rollout is 0%, flag is effectively disabled
    if rollout_percent <= 0:
        return False

    # Rollout evaluation requires user_id
    user_id = None
    if context and isinstance(context, dict):
        user_id = context.get('user_id')

    if not user_id:
        # HIGH-2 fix: No user context with partial rollout = return False for safety
        # (prevents CRON/background jobs from bypassing rollout percentage)
        logger.debug("feature_flag_no_user_context", flag_key=flag_key)
        return False

    return get_rollout_status(flag_key, str(user_id), rollout_percent)


def get_rollout_status(flag_key, user_id, rollout_percent=None):
    """
    Determine if a user is in the rollout group using consistent hashing.

    Args:
        flag_key: The feature flag key.
        user_id: The user identifier for hash-based assignment.
        rollout_percent: Override rollout percentage (uses flag config if None).

    Returns:
        bool: True if the user is in the rollout group.
    """
    if rollout_percent is None:
        flag_config = _get_flag_config(flag_key)
        if flag_config is None:
            return False
        rollout_percent = flag_config.get('rollout_percent', 100)

    # Consistent hashing: user always gets same result for same flag
    # LOW-1 fix: MD5 is safe for non-cryptographic consistent hashing (not used for security)
    hash_input = f"{flag_key}:{user_id}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
    return (hash_value % 100) < rollout_percent


def get_all_flags_status(context=None):
    """
    Get the enabled/disabled status of all flags for a given context.

    Args:
        context: Optional dict with user_id, profile, environment.

    Returns:
        dict: Mapping of flag_key -> bool (enabled status).
    """
    if not _get_flags_enabled():
        return {}

    all_flags = _get_all_flags()
    result = {}
    for flag_key in all_flags:
        result[flag_key] = is_enabled(flag_key, context)
    return result


def invalidate_cache(flag_key=None):
    """
    Invalidate feature flag cache.

    Args:
        flag_key: Specific flag to invalidate. If None, invalidates all.
    """
    if flag_key:
        cache.delete(f'feature_flag:{flag_key}')
    cache.delete('feature_flags:all')
    logger.info("feature_flag_cache_invalidated", flag_key=flag_key or "all")
