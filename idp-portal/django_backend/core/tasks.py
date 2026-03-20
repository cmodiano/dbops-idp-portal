"""
Celery tasks for core app.

Story 86.9: flush_splunk_logging_handler — periodic safety flush of SplunkLoggingHandler
for Celery worker processes.
"""
from __future__ import annotations

import logging

import structlog
from celery import Task, shared_task  # type: ignore[import-untyped]
from celery.exceptions import SoftTimeLimitExceeded  # type: ignore[import-untyped]
from django.conf import settings

logger = structlog.get_logger(__name__)

_FLUSH_LIMITS = settings.CELERY_TASK_TIME_LIMITS["flush_splunk_logging_handler"]


@shared_task(
    name="core.tasks.flush_splunk_logging_handler",
    bind=True,
    max_retries=0,
    soft_time_limit=_FLUSH_LIMITS["soft"],
    time_limit=_FLUSH_LIMITS["hard"],
)
def flush_splunk_logging_handler(self: Task) -> dict:
    """Flush all SplunkLoggingHandler instances in this process.

    Intended for Celery workers: ensures buffered Splunk log events are flushed
    even if the in-process threading.Timer is delayed or missed.

    Does NOT raise — all errors are caught and logged locally.

    Returns:
        Dict with handlers_flushed, buffer_qsize, dropped_count.
    """
    from core.splunk_logging_handler import SplunkLoggingHandler  # noqa: PLC0415

    handlers_flushed = 0
    total_buffer = 0
    total_dropped = 0

    try:
        seen_ids: set = set()
        handlers_to_check: list = []
        for h in list(logging.root.handlers):
            if id(h) not in seen_ids:
                seen_ids.add(id(h))
                handlers_to_check.append(h)
        for _, lg in logging.Logger.manager.loggerDict.items():
            if isinstance(lg, logging.Logger):
                for h in lg.handlers:
                    if id(h) not in seen_ids:
                        seen_ids.add(id(h))
                        handlers_to_check.append(h)

        for h in handlers_to_check:
            if isinstance(h, SplunkLoggingHandler) and h.enabled and not h._closed:
                try:
                    h.flush()
                    handlers_flushed += 1
                    total_buffer += h._buffer.qsize()
                    total_dropped += h.dropped_count
                except SoftTimeLimitExceeded:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "splunk_flush_task_handler_error",
                        error=str(exc),
                    )

    except SoftTimeLimitExceeded:
        logger.warning(
            "splunk_flush_task_soft_time_limit",
            handlers_flushed=handlers_flushed,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "splunk_flush_task_error",
            error=str(exc),
            exc_info=True,
        )

    logger.info(
        "splunk_flush_task_complete",
        handlers_flushed=handlers_flushed,
        buffer_qsize=total_buffer,
        dropped_count=total_dropped,
    )
    return {
        "handlers_flushed": handlers_flushed,
        "buffer_qsize": total_buffer,
        "dropped_count": total_dropped,
    }
