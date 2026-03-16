"""
Redis cache for execution cancellation status.
Story 86.6: Clé standardisée `cancellation:{execution_id}` et TTL 24h.

When WORKFLOW_RETRY_USE_CANCELLATION_CACHE is True, uses Django's cache framework
(backed by Redis) to reduce database queries for cancellation checks.
Cache key: `cancellation:{execution_id}` — TTL: 86400s (24 heures).
Falls back to database query when cache is disabled or unavailable.
"""

import structlog
from django.conf import settings
from django.core.cache import cache

logger = structlog.get_logger(__name__)

CANCELLATION_CACHE_TTL = 86400  # 24 heures — durée suffisante pour tous les workers actifs (Story 86.6)


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

    cache_key = f"cancellation:{execution_id}"
    try:
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return bool(cached_value)

        # Cache miss: query DB. Only cache True (cancelled) — never cache False for 24h.
        # Rationale: if mark_cancelled fails silently during a transient Redis failure,
        # a stale False would persist 24h and workers would not stop. Non-cancelled
        # executions always re-check DB; mark_cancelled() handles the True propagation.
        is_cancelled_status = _check_db(execution_id)
        if is_cancelled_status:
            cache.set(cache_key, is_cancelled_status, timeout=CANCELLATION_CACHE_TTL)
        return is_cancelled_status
    except Exception as e:  # noqa: BLE001 — resilience-boundary: Redis can fail in various ways, must fall back to DB
        # Story 20.3: Justified broad catch - Redis can fail in various ways,
        # must always fall back to DB for robustness
        logger.warning(
            "cancellation_cache_error_fallback",
            execution_id=execution_id,
            error=str(e),
            exc_info=True,
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

    cache_key = f"cancellation:{execution_id}"
    try:
        cache.set(cache_key, True, timeout=CANCELLATION_CACHE_TTL)
    except Exception as e:  # noqa: BLE001 — best-effort-non-critical: Redis failures should not break cancellation flow
        # Story 20.3: Justified broad catch - Redis failures should not break cancellation
        logger.warning(
            "cancellation_cache_mark_error",
            execution_id=execution_id,
            error=str(e),
            exc_info=True,
        )


def _check_db(execution_id: int) -> bool:
    """Check cancellation status directly from database."""
    from executions.models import Execution, ExecutionStatus
    try:
        execution = Execution.objects.only('status').get(id=execution_id)
        return execution.status == ExecutionStatus.CANCELLED
    except Execution.DoesNotExist:
        return False
