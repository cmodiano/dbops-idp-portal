"""Custom middleware: Correlation ID, Request Logging, and CORS."""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

import structlog

CORRELATION_HEADER = "X-Idp-Request-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and propagate correlation ID (X-Idp-Request-Id) for request tracing.
    
    AC #2: Generates a UUID correlation ID if not present in request headers,
    binds it to structlog contextvars, and adds it to response headers.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_HEADER, str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        structlog.contextvars.unbind_contextvars("correlation_id")
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each HTTP request with method, path, status, duration, and user context.

    AC #3: Logs each request with method, path, status_code, duration_ms, user_id (if authenticated),
    and correlation_id (via merge_contextvars processor).

    Log levels follow architecture convention (AC #8):
    - info: 2xx success responses
    - warning: 4xx client errors
    - error: 5xx server errors
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        logger = structlog.get_logger()
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        status_code = response.status_code

        # Get user_id from contextvars (bound by get_current_user in deps.py)
        # merge_contextvars processor will include it automatically, but we make it explicit
        context_vars = structlog.contextvars.get_contextvars()
        user_id = context_vars.get("user_id")

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        
        # Explicitly include user_id if present (AC #3)
        if user_id is not None:
            log_data["user_id"] = user_id

        # Log at appropriate level based on status code
        if status_code >= 500:
            logger.error("request_completed", **log_data)
        elif status_code >= 400:
            logger.warning("request_completed", **log_data)
        else:
            logger.info("request_completed", **log_data)

        return response
