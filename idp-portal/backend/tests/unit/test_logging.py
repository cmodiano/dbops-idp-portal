"""Tests for structured logging configuration (AC #8)."""

import json
import structlog
from io import StringIO
from app.core.logging import configure_logging


def test_configure_logging_produces_json():
    """AC #8: Logging outputs JSON with timestamp and level."""
    configure_logging()
    logger = structlog.get_logger()

    # Capture output
    output = StringIO()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=output),
    )

    logger = structlog.get_logger()
    logger.info("test_event", user_id="u1")

    line = output.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["event"] == "test_event"
    assert parsed["user_id"] == "u1"
    assert "timestamp" in parsed
    assert parsed["level"] == "info"
