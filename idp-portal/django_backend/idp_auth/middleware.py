"""
Authentication audit middleware.
Story M.7 - Task 7: Audit auth events.
"""

import logging

from django.conf import settings
from core.middleware import get_correlation_id

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """Extract client IP address from request, handling proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For may contain multiple IPs; first is the client
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


class AuditAuthMiddleware:
    """
    Middleware that logs authentication events to audit log.

    Events logged:
    - Failed authentication attempts (401 responses)
    - Successful auth events are logged in the views themselves

    Note: Most auth events (login, refresh, logout) are logged directly
    in the views to capture full context. This middleware catches
    authentication failures that don't reach the view layer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log 401 responses on auth endpoints (NFR10)
        if response.status_code == 401 and request.path.startswith('/api/v1/auth'):
            ip_address = get_client_ip(request)
            correlation_id = get_correlation_id()

            logger.warning(
                "auth_unauthorized_access",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "ip_address": ip_address,
                    "correlation_id": correlation_id,
                    "user_agent": request.META.get('HTTP_USER_AGENT', ''),
                }
            )

        return response
