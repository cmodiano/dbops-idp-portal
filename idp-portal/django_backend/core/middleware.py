"""
Core middleware for the IDP Portal Django backend.
Story M.7 - Task 7: Security and audit middleware.
"""

import logging
import uuid
from threading import local

from django.conf import settings

logger = logging.getLogger(__name__)

# Thread-local storage for correlation ID
_correlation_id = local()


def get_correlation_id() -> str | None:
    """Get the current request's correlation ID from thread-local storage."""
    return getattr(_correlation_id, 'value', None)


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in thread-local storage."""
    _correlation_id.value = correlation_id


class CorrelationIdMiddleware:
    """
    Middleware that generates and propagates X-Idp-Request-Id header.

    If the incoming request has an X-Idp-Request-Id header, it uses that value.
    Otherwise, it generates a new UUID for the request.

    The correlation ID is:
    - Stored in thread-local for access throughout the request
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

        # Process request
        response = self.get_response(request)

        # Add to response headers
        response['X-Idp-Request-Id'] = correlation_id

        # Clear thread-local after request
        set_correlation_id(None)

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
