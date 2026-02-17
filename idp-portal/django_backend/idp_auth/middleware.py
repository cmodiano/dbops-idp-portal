"""
Authentication audit middleware.
Story M.7 - Task 7: Audit auth events.
Story M.8 - Task 8: Migrate to structlog for structured JSON logging.
"""

import structlog

from typing import Any, Callable

from core.middleware import get_correlation_id, get_client_ip

logger = structlog.get_logger(__name__)


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

    def __init__(self, get_response: Callable[[Any], Any]) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        response = self.get_response(request)

        # Log 401 responses on auth endpoints (NFR10)
        if response.status_code == 401 and request.path.startswith('/api/v1/auth'):
            ip_address = get_client_ip(request)
            correlation_id = get_correlation_id()

            logger.warning(
                "auth_unauthorized_access",
                path=request.path,
                method=request.method,
                ip_address=ip_address,
                correlation_id=correlation_id,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )

        return response
