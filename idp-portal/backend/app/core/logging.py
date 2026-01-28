"""Structured logging configuration using structlog."""

import logging
import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON output and log level from settings.

    Log levels follow architecture convention (AC #8):
    - debug: Technical detail, SQL queries
    - info: Successful business actions
    - warning: Unusual non-blocking situations
    - error: Recoverable failures
    - critical: Irrecoverable failures
    """
    # Set stdlib logging level based on settings (validated by Pydantic)
    # Handle both enum and string cases (string when modified in tests)
    level_str = settings.log_level.value if hasattr(settings.log_level, 'value') else settings.log_level
    log_level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
