"""
Database resilience middleware for Data Guard failover/switchover detection.

Story 32.1: Detects DB connection loss (OperationalError, InterfaceError, DatabaseError)
and attempts recovery by purging dead connections and retrying the request.

Story 32.2: Bounded retry with exponential backoff, idempotency protection for writes,
and structured 503 response on exhaustion.

This middleware is a safety net — Django's CONN_HEALTH_CHECKS (4.1+) handles most cases
by validating connections before reuse. This catches errors that slip through.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import structlog
from django.conf import settings
from django.db import OperationalError, close_old_connections, connection
from django.db.utils import DatabaseError, InterfaceError
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# ORA error codes indicating connection/network issues (Data Guard failover)
CONNECTION_ERROR_CODES = frozenset({
    3113,   # ORA-03113: end-of-file on communication channel
    3114,   # ORA-03114: not connected to ORACLE
    1033,   # ORA-01033: ORACLE initialization or shutdown in progress
    12541,  # ORA-12541: TNS:no listener
    12543,  # ORA-12543: TNS:destination host unreachable
    3135,   # ORA-03135: connection lost contact
    12571,  # ORA-12571: TNS:packet writer failure
    28,     # ORA-00028: your session has been killed
    1012,   # ORA-01012: not logged on
    12170,  # ORA-12170: TNS:connect timeout occurred
    12514,  # ORA-12514: TNS:listener does not currently know of service
})

# ORA codes that may indicate mid-commit failure (uncertain state)
MID_COMMIT_ORA_CODES = frozenset({
    3113,   # ORA-03113: end-of-file on communication channel (can happen mid-commit)
    3114,   # ORA-03114: not connected to ORACLE
})

# HTTP methods considered safe for retry (no side effects)
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})


def _is_connection_error(exc: Exception) -> bool:
    """Determine if an exception is a DB connection error (vs. query/logic error)."""
    if isinstance(exc, InterfaceError):
        return True
    if isinstance(exc, (OperationalError, DatabaseError)):
        error_str = str(exc)
        # Check for ORA codes
        for code in CONNECTION_ERROR_CODES:
            if f"ORA-{code:05d}" in error_str:
                return True
        # Generic connection loss patterns
        lower = error_str.lower()
        if any(pattern in lower for pattern in (
            'not connected',
            'connection lost',
            'end-of-file',
            'lost contact',
            'no listener',
        )):
            return True
    return False


def _extract_ora_code(exc: Exception) -> str | None:
    """Extract ORA error code from exception message."""
    error_str = str(exc)
    for code in CONNECTION_ERROR_CODES:
        ora_str = f"ORA-{code:05d}"
        if ora_str in error_str:
            return ora_str
    return None


def _is_mid_commit_error(exc: Exception) -> bool:
    """Determine if error may have occurred during COMMIT (uncertain state).

    If the connection was in an atomic block and the error is one that can
    occur mid-commit (ORA-03113, ORA-03114), the transaction state is uncertain
    and retrying would risk double-writes.
    """
    if isinstance(exc, InterfaceError):
        # InterfaceError = connection dead before commit → safe to retry
        return False

    ora_code = _extract_ora_code(exc)
    if ora_code is None:
        return False

    code_num = int(ora_code.split('-')[1])
    if code_num not in MID_COMMIT_ORA_CODES:
        return False

    # If connection.in_atomic_block is True after the error, the atomic context
    # was still active → error happened inside transaction → pre-commit → safe.
    # If it's False, Django already cleaned up the atomic block, which can mean
    # the error happened during or after commit → uncertain.
    try:
        return not connection.in_atomic_block
    except Exception:
        # If we can't check, assume worst case
        return True


def _is_retry_safe(request: HttpRequest, exc: Exception) -> bool:
    """Determine if retrying the request is safe.

    Read-only methods are always safe to retry.
    Write methods are safe only if the error occurred before COMMIT.
    """
    if request.method in SAFE_METHODS:
        return True

    # For write methods, check if error is mid-commit
    if _is_mid_commit_error(exc):
        return False

    return True


def _calculate_backoff(attempt: int) -> float:
    """Calculate backoff delay for a retry attempt.

    attempt 0 (first retry): DB_RETRY_BACKOFF_BASE
    attempt 1: DB_RETRY_BACKOFF_BASE * 2
    attempt N: DB_RETRY_BACKOFF_BASE * 2^N, capped at 5s
    """
    base: float = float(getattr(settings, 'DB_RETRY_BACKOFF_BASE', 0.5))
    delay = base * (2 ** attempt)
    return min(delay, 5.0)


class DatabaseResilienceMiddleware:
    """
    Middleware that detects DB connection loss and attempts bounded retry.

    On connection error:
    1. Logs db_connection_lost event
    2. Checks if retry is safe (idempotency for write methods)
    3. Retries with exponential backoff up to DB_RETRY_MAX_ATTEMPTS
    4. On success: logs db_connection_restored
    5. On exhaustion: returns 503 with structured JSON error

    Placed after CorrelationIdMiddleware to have correlation_id available.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except (OperationalError, InterfaceError, DatabaseError) as exc:
            if not _is_connection_error(exc):
                raise

            return self._handle_connection_error(request, exc)

    def _handle_connection_error(
        self, request: HttpRequest, exc: Exception
    ) -> HttpResponse:
        """Handle a DB connection error with bounded retry logic."""
        correlation_id = get_correlation_id()
        ora_code = _extract_ora_code(exc)
        max_attempts = getattr(settings, 'DB_RETRY_MAX_ATTEMPTS', 3)
        time_window = getattr(settings, 'DB_RETRY_TIME_WINDOW_SECONDS', 120)
        start_time = time.monotonic()

        logger.warning(
            "db_connection_lost",
            correlation_id=correlation_id,
            error_type=type(exc).__name__,
            error_code=ora_code,
            error=str(exc),
            method=request.method,
            path=request.path,
        )

        # Check idempotency for write methods
        if not _is_retry_safe(request, exc):
            logger.error(
                "db_retry_unsafe_write",
                correlation_id=correlation_id,
                error_code=ora_code,
                method=request.method,
                path=request.path,
                reason="mid_commit_error",
            )
            return self._build_503_response(correlation_id, reason="mid_commit_error")

        # Bounded retry loop
        for attempt in range(max_attempts):
            # Check time window BEFORE logging or sleeping (avoids misleading log if window exceeded)
            elapsed_seconds = time.monotonic() - start_time
            if elapsed_seconds >= time_window:
                logger.error(
                    "db_retry_time_window_exceeded",
                    correlation_id=correlation_id,
                    total_duration_ms=int(elapsed_seconds * 1000),
                    time_window_seconds=time_window,
                    method=request.method,
                    path=request.path,
                )
                return self._build_503_response(correlation_id, reason="time_window_exceeded")

            # Backoff: first attempt (0) is immediate, subsequent have delay
            backoff = _calculate_backoff(attempt - 1) if attempt > 0 else 0
            logger.warning(
                "db_retry_attempt",
                correlation_id=correlation_id,
                attempt_number=attempt + 1,
                max_attempts=max_attempts,
                backoff_seconds=backoff,
                method=request.method,
                path=request.path,
            )

            if attempt > 0:
                time.sleep(backoff)

            # Purge dead connections and verify
            close_old_connections()
            try:
                connection.ensure_connection()
            except Exception as conn_exc:
                logger.warning(
                    "db_reconnect_failed",
                    correlation_id=correlation_id,
                    attempt_number=attempt + 1,
                    max_attempts=max_attempts,
                    error=str(conn_exc),
                    method=request.method,
                    path=request.path,
                )
                continue

            # Retry the request
            try:
                response = self.get_response(request)
                logger.info(
                    "db_connection_restored",
                    correlation_id=correlation_id,
                    method=request.method,
                    path=request.path,
                    original_error_code=ora_code,
                    attempt_number=attempt + 1,
                    total_duration_ms=int((time.monotonic() - start_time) * 1000),
                )
                return response
            except (OperationalError, InterfaceError, DatabaseError) as retry_exc:
                if not _is_connection_error(retry_exc):
                    raise
                # Check idempotency again for write retries
                if not _is_retry_safe(request, retry_exc):
                    logger.error(
                        "db_retry_unsafe_write",
                        correlation_id=correlation_id,
                        error_code=_extract_ora_code(retry_exc),
                        method=request.method,
                        path=request.path,
                        reason="mid_commit_error_on_retry",
                        attempt_number=attempt + 1,
                    )
                    return self._build_503_response(correlation_id, reason="mid_commit_error")
                exc = retry_exc
                continue

        # All retries exhausted
        total_duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "db_retry_exhausted",
            correlation_id=correlation_id,
            total_attempts=max_attempts,
            total_duration_ms=total_duration_ms,
            error_type=type(exc).__name__,
            error_code=_extract_ora_code(exc),
            method=request.method,
            path=request.path,
        )

        return self._build_503_response(correlation_id, reason="retry_exhausted")

    @staticmethod
    def _build_503_response(
        correlation_id: str | None,
        reason: str = "retry_exhausted",
    ) -> JsonResponse:
        """Build structured 503 JSON response.

        Args:
            correlation_id: Request correlation ID for tracing.
            reason: One of "retry_exhausted", "time_window_exceeded", "mid_commit_error".
        """
        messages = {
            "retry_exhausted": (
                "Base de données temporairement indisponible après bascule. "
                "Veuillez réessayer dans quelques instants."
            ),
            "time_window_exceeded": (
                "Dépassement de la fenêtre de bascule. "
                "Veuillez réessayer."
            ),
            "mid_commit_error": (
                "Résultat incertain après coupure réseau pendant le commit. "
                "Veuillez vérifier l'état de l'opération."
            ),
        }
        response = JsonResponse(
            {
                "error": {
                    "code": "DB_UNAVAILABLE",
                    "reason": reason,
                    "message": messages.get(reason, messages["retry_exhausted"]),
                    "correlation_id": correlation_id,
                }
            },
            status=503,
        )
        response["Retry-After"] = "30"
        return response
