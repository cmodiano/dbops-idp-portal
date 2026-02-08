"""
Redis cache for execution cancellation status.
Story 20.3 AC5: Optimize refresh_from_db() overhead for high-volume retry workflows.

When WORKFLOW_RETRY_USE_CANCELLATION_CACHE is True, uses Django's cache framework
(backed by Redis) to reduce database queries for cancellation checks.
Falls back to database query when cache is disabled or unavailable.
"""

import structlog
from django.conf import settings
from django.core.cache import cache

logger = structlog.get_logger(__name__)

CANCELLATION_CACHE_TTL = 60  # seconds


def is_cancelled(execution_id: int) -> bool:
    """
    Check if an execution is cancelled, using Redis cache if enabled.

    Falls back to database query if cache is disabled or unavailable.

    Args:
        execution_id: ID of the execution

    Returns:
        True if execution is cancelled, False otherwise
    """
    cache_enabled = getattr(settings, 'WORKFLOW_RETRY_USE_CANCELLATION_CACHE', False)

    if not cache_enabled:
        return _check_db(execution_id)

    cache_key = f"execution_cancelled:{execution_id}"
    try:
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        # Cache miss: query DB and populate cache
        is_cancelled_status = _check_db(execution_id)
        cache.set(cache_key, is_cancelled_status, timeout=CANCELLATION_CACHE_TTL)
        return is_cancelled_status
    except Exception as e:
        # Story 20.3: Justified broad catch - Redis can fail in various ways,
        # must always fall back to DB for robustness
        logger.warning(
            "cancellation_cache_error_fallback",
            execution_id=execution_id,
            error=str(e),
        )
        return _check_db(execution_id)


def mark_cancelled(execution_id: int) -> None:
    """
    Mark an execution as cancelled in the cache.

    Should be called when an execution is cancelled to immediately
    update the cache for pending retry tasks.

    Args:
        execution_id: ID of the execution
    """
    cache_enabled = getattr(settings, 'WORKFLOW_RETRY_USE_CANCELLATION_CACHE', False)
    if not cache_enabled:
        return

    cache_key = f"execution_cancelled:{execution_id}"
    try:
        cache.set(cache_key, True, timeout=CANCELLATION_CACHE_TTL)
    except Exception as e:
        # Story 20.3: Justified broad catch - Redis failures should not break cancellation
        logger.warning(
            "cancellation_cache_mark_error",
            execution_id=execution_id,
            error=str(e),
        )


def _check_db(execution_id: int) -> bool:
    """Check cancellation status directly from database."""
    from executions.models import Execution, ExecutionStatus
    try:
        execution = Execution.objects.only('status').get(id=execution_id)
        return execution.status == ExecutionStatus.CANCELLED
    except Execution.DoesNotExist:
        return False
