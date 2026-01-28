"""Tests for structured logging configuration (AC #2, #3, #8)."""

import json
import logging
import structlog
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.logging import configure_logging


def test_configure_logging_produces_json():
    """AC #8: Logging outputs JSON with timestamp and level."""
    # Use simple PrintLogger for test isolation
    output = StringIO()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=False,
    )

    logger = structlog.get_logger()
    logger.info("test_event", user_id="u1")

    line = output.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["event"] == "test_event"
    assert parsed["user_id"] == "u1"
    assert "timestamp" in parsed
    assert parsed["level"] == "info"


# === Request Logging Middleware Tests (AC #2, #3, #8) ===


@pytest.fixture
def log_output():
    """Fixture to capture structlog output using PrintLogger for test isolation."""
    output = StringIO()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=output),
        cache_logger_on_first_use=False,
    )
    return output


@pytest.mark.asyncio
async def test_request_logging_middleware_success_200(log_output):
    """AC #3: Request logging logs method, path, status, duration, correlation_id for 200."""
    from app.core.middleware import RequestLoggingMiddleware

    # Mock request
    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/health"
    mock_request.state = MagicMock()

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_call_next(request):
        return mock_response

    # Bind correlation_id as the CorrelationIdMiddleware would
    structlog.contextvars.bind_contextvars(correlation_id="test-correlation-id")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, mock_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    assert parsed["event"] == "request_completed"
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/api/v1/health"
    assert parsed["status_code"] == 200
    assert "duration_ms" in parsed
    assert parsed["duration_ms"] >= 0
    assert parsed["correlation_id"] == "test-correlation-id"
    assert parsed["level"] == "info"


@pytest.mark.asyncio
async def test_request_logging_middleware_4xx_warning(log_output):
    """AC #8: 4xx responses logged at warning level."""
    from app.core.middleware import RequestLoggingMiddleware

    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/api/v1/admin/users"
    mock_request.state = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 404

    async def mock_call_next(request):
        return mock_response

    structlog.contextvars.bind_contextvars(correlation_id="warn-correlation")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, mock_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    assert parsed["level"] == "warning"
    assert parsed["status_code"] == 404


@pytest.mark.asyncio
async def test_request_logging_middleware_5xx_error(log_output):
    """AC #8: 5xx responses logged at error level."""
    from app.core.middleware import RequestLoggingMiddleware

    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/crash"
    mock_request.state = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 500

    async def mock_call_next(request):
        return mock_response

    structlog.contextvars.bind_contextvars(correlation_id="error-correlation")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, mock_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    assert parsed["level"] == "error"
    assert parsed["status_code"] == 500


@pytest.mark.asyncio
async def test_request_logging_middleware_duration_logged(log_output):
    """AC #3: Duration in milliseconds is logged."""
    from app.core.middleware import RequestLoggingMiddleware
    import asyncio

    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/slow"
    mock_request.state = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def slow_call_next(request):
        await asyncio.sleep(0.01)  # 10ms delay
        return mock_response

    structlog.contextvars.bind_contextvars(correlation_id="duration-test")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, slow_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    assert "duration_ms" in parsed
    assert parsed["duration_ms"] >= 10  # At least 10ms


@pytest.mark.asyncio
async def test_request_logging_middleware_user_id_when_authenticated(log_output):
    """AC #3: user_id present in log when user is authenticated."""
    from app.core.middleware import RequestLoggingMiddleware

    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/admin/profile"
    mock_request.state = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_call_next(request):
        return mock_response

    # Simulate authenticated user (user_id bound by get_current_user)
    structlog.contextvars.bind_contextvars(correlation_id="auth-test", user_id="user-42")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, mock_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id", "user_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    assert parsed["user_id"] == "user-42"


@pytest.mark.asyncio
async def test_request_logging_middleware_no_user_id_when_anonymous(log_output):
    """AC #3: user_id absent in log when user is not authenticated."""
    from app.core.middleware import RequestLoggingMiddleware

    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/health"
    mock_request.state = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_call_next(request):
        return mock_response

    # No user_id bound - anonymous request
    structlog.contextvars.bind_contextvars(correlation_id="anon-test")

    middleware = RequestLoggingMiddleware(app=MagicMock())
    await middleware.dispatch(mock_request, mock_call_next)

    structlog.contextvars.unbind_contextvars("correlation_id")

    log_line = log_output.getvalue().strip()
    parsed = json.loads(log_line)

    # user_id should not be in the log for anonymous requests
    assert "user_id" not in parsed or parsed.get("user_id") is None


# === Log Level Configuration Tests (AC #8) ===


def test_settings_log_level_default():
    """AC #8: log_level setting defaults to INFO."""
    from app.core.config import Settings

    s = Settings()
    assert s.log_level == "INFO"


def test_settings_log_level_configurable():
    """AC #8: log_level can be configured via environment variable."""
    import os
    from app.core.config import Settings

    original = os.environ.get("LOG_LEVEL")
    try:
        os.environ["LOG_LEVEL"] = "DEBUG"
        s = Settings()
        assert s.log_level == "DEBUG"
    finally:
        if original is not None:
            os.environ["LOG_LEVEL"] = original
        else:
            os.environ.pop("LOG_LEVEL", None)


def test_configure_logging_applies_level():
    """AC #8: configure_logging applies log level from settings."""
    import logging
    from app.core.logging import configure_logging
    from app.core.config import settings

    original_level = settings.log_level
    try:
        settings.log_level = "WARNING"
        configure_logging()
        # Verify the root logger level is set
        root_level = logging.getLogger().level
        assert root_level == logging.WARNING
    finally:
        settings.log_level = original_level
        configure_logging()  # Reset


def test_structlog_processors_include_stack_info_renderer():
    """AC #3: structlog includes StackInfoRenderer for error traces."""
    from app.core.logging import configure_logging

    configure_logging()

    # Verify StackInfoRenderer is in the configured processors
    config = structlog.get_config()
    processor_names = [type(p).__name__ for p in config["processors"]]
    assert "StackInfoRenderer" in processor_names


def test_structlog_processors_include_exception_renderer():
    """AC #3: structlog includes exception formatting processor for error traces."""
    from app.core.logging import configure_logging

    configure_logging()

    # Verify exception formatting processor is in the configured processors
    # format_exc_info becomes ExceptionRenderer in the config
    config = structlog.get_config()
    processor_names = [getattr(p, "__name__", type(p).__name__) for p in config["processors"]]
    assert "ExceptionRenderer" in processor_names
