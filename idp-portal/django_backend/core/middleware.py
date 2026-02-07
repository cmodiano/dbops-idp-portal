"""
Core middleware for the IDP Portal Django backend.
Story M.7 - Task 7: Security and audit middleware.
Story M.8 - Task 3/4: Request/Response logging and correlation ID propagation.
"""

import time
import uuid
from threading import local

import structlog

# Thread-local storage for correlation ID
_correlation_id = local()

# Get structlog logger for this module
logger = structlog.get_logger(__name__)


def get_correlation_id() -> str | None:
    """Get the current request's correlation ID from thread-local storage."""
    return getattr(_correlation_id, 'value', None)


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID in thread-local storage."""
    _correlation_id.value = correlation_id


def get_client_ip(request) -> str:
    """
    Extract client IP address from request, handling proxies.

    Checks X-Forwarded-For header first (for reverse proxy scenarios),
    then falls back to REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For may contain multiple IPs; first is the client
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class CorrelationIdMiddleware:
    """
    Middleware that generates and propagates X-Idp-Request-Id header.

    If the incoming request has an X-Idp-Request-Id header, it uses that value.
    Otherwise, it generates a new UUID for the request.

    The correlation ID is:
    - Stored in thread-local for access throughout the request
    - Bound to structlog contextvars for automatic inclusion in all logs
    - Added to the response headers
    - Available via get_correlation_id() function
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get or generate correlation ID
        correlation_id = request.META.get('HTTP_X_IDP_REQUEST_ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in thread-local for access in views/services
        set_correlation_id(correlation_id)

        # Add to request for easy access
        request.correlation_id = correlation_id

        # Bind to structlog contextvars for automatic inclusion in all logs
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Process request
        response = self.get_response(request)

        # Add to response headers
        response['X-Idp-Request-Id'] = correlation_id

        # Clear thread-local and structlog contextvars after request
        set_correlation_id(None)
        structlog.contextvars.unbind_contextvars('correlation_id')

        return response


class RequestResponseLoggingMiddleware:
    """
    Middleware that logs each HTTP request with method, path, status, duration, and user context.

    Story M.8 - Task 3: Request/Response logging middleware.

    Logs two events per request:
    - "request_received": When request enters (method, path, correlation_id, user_id, ip_address, user_agent)
    - "request_completed": When response exits (status_code, duration_ms, correlation_id, user_id)

    On exceptions, logs:
    - "request_failed": With exception details and traceback

    Log levels follow architecture convention:
    - INFO: 2xx success responses
    - WARNING: 4xx client errors
    - ERROR: 5xx server errors
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        correlation_id = get_correlation_id()

        # Get user_id if authenticated (may be None at this point)
        user_id = self._get_user_id(request)

        # Log request received
        logger.info(
            "request_received",
            correlation_id=correlation_id,
            method=request.method,
            path=request.path,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            user_id=user_id,
        )

        try:
            response = self.get_response(request)
            duration_ms = int((time.time() - start_time) * 1000)

            # Get user_id again after auth middleware has run
            user_id = self._get_user_id(request)

            # Log request completed at appropriate level based on status code
            log_data = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_id": user_id,
            }

            if response.status_code >= 500:
                logger.error("request_completed", **log_data)
            elif response.status_code >= 400:
                logger.warning("request_completed", **log_data)
            else:
                logger.info("request_completed", **log_data)

            return response

        except Exception as e:
            # Story 17.6: Justified broad catch - Middleware must not break request chain
            duration_ms = int((time.time() - start_time) * 1000)
            user_id = self._get_user_id(request)

            logger.error(
                "request_failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.path,
                duration_ms=duration_ms,
                user_id=user_id,
                exception=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise

    def _get_user_id(self, request) -> str | None:
        """Extract user ID from request if authenticated."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user.id)
        return None


class SecurityHeadersMiddleware:
    """
    Middleware that adds security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Cache-Control: no-store (for API responses)

    Note: HSTS is typically handled at the reverse proxy level (Nginx),
    but can be added here if needed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Security headers (NFR6)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Prevent caching of API responses with sensitive data
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'

        return response
