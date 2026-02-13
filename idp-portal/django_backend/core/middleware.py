"""
Core middleware for the IDP Portal Django backend.
Story M.7 - Task 7: Security and audit middleware.
Story M.8 - Task 3/4: Request/Response logging and correlation ID propagation.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from threading import local

import structlog
from django.http import HttpRequest, HttpResponse

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


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract client IP address from request, handling proxies.

    Checks X-Forwarded-For header first (for reverse proxy scenarios),
    then falls back to REMOTE_ADDR.

    Logs a warning if X-Forwarded-For contains more than 2 IPs, as this
    may indicate IP spoofing attempts.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For may contain multiple IPs; first is the client
        ips = [ip.strip() for ip in x_forwarded_for.split(',')]
        # Log potential spoofing if more than 2 IPs (client + proxy)
        if len(ips) > 2:
            logger.warning(
                "suspicious_xff_header",
                xff_header=x_forwarded_for,
                ip_count=len(ips),
                extracted_client_ip=ips[0],
                message="X-Forwarded-For contains excessive IPs - potential spoofing"
            )
        return str(ips[0])
    return str(request.META.get('REMOTE_ADDR', ''))


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

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Get or generate correlation ID
        correlation_id = request.META.get('HTTP_X_IDP_REQUEST_ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in thread-local for access in views/services
        set_correlation_id(correlation_id)

        # Add to request for easy access
        request.correlation_id = correlation_id  # type: ignore[attr-defined]  # dynamic attr for downstream access

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


class RateLimitHeadersMiddleware:
    """
    Middleware that adds X-RateLimit-* headers to responses and logs 429 violations.

    Story 17.11: Rate limiting headers and structured logging.

    Headers added on 429 responses:
    - Retry-After: seconds until rate limit resets
    - X-RateLimit-Limit: maximum requests allowed in the window
    - X-RateLimit-Remaining: requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp when the window resets

    On non-429 responses, DRF throttle classes already set these via
    the throttle's wait() method, but we ensure consistent headers.
    """

    # Paths exempt from rate limit header injection (health checks, metrics)
    EXEMPT_PATHS = ('/api/v1/health', '/health', '/metrics')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Skip exempt paths
        if request.path.rstrip('/') in (p.rstrip('/') for p in self.EXEMPT_PATHS):
            return response

        # On 429 responses, add Retry-After and log the violation
        if response.status_code == 429:
            # DRF sets Retry-After header automatically; extract wait time
            retry_after = response.get('Retry-After', '')
            if retry_after:
                try:
                    wait_seconds = int(float(retry_after))
                    response['Retry-After'] = str(wait_seconds)
                except (ValueError, TypeError):
                    pass

            # Log rate limit violation with structured logging
            correlation_id = get_correlation_id()
            user_id = None
            if hasattr(request, 'user') and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
                user_id = str(request.user.id)

            logger.warning(
                "rate_limit_exceeded",
                correlation_id=correlation_id,
                ip_address=get_client_ip(request),
                user_id=user_id,
                endpoint=request.path,
                method=request.method,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

        return response


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
