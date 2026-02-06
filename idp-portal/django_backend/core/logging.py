"""
Structured logging configuration using structlog.
Story M.8 - Logging structuré JSON pour observabilité.

This module configures structlog for Django with JSON output format,
enabling unified log analysis in Splunk.

Log levels follow architecture convention:
- DEBUG: Technical detail, SQL queries (not in production)
- INFO: Successful business actions, request/response
- WARNING: Unusual non-blocking situations
- ERROR: Recoverable failures, exceptions
- CRITICAL: Irrecoverable failures (DB down, etc.)
"""

import logging
import os

import structlog


def configure_structlog() -> None:
    """
    Configure structlog with JSON output for structured logging.

    Configuration features:
    - JSON output format for Splunk ingestion
    - ISO8601 UTC timestamps
    - Context variable merging (correlation_id, user_id)
    - Exception formatting with stack traces
    """
    # Determine log level from environment (default INFO for production)
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # Merge context variables (correlation_id, user_id bound via bind_contextvars)
            structlog.contextvars.merge_contextvars,
            # Filter by log level
            structlog.stdlib.filter_by_level,
            # Add log level to event dict
            structlog.processors.add_log_level,
            # Add ISO8601 UTC timestamp
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Render stack info
            structlog.processors.StackInfoRenderer(),
            # Format exception info
            structlog.processors.format_exc_info,
            # Render as JSON
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured structlog BoundLogger instance
    """
    return structlog.get_logger(name)
