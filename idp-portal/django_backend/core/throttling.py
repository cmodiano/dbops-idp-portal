"""
Story 17.11: Rate limiting throttle classes for DRF endpoints.

Uses DRF built-in throttling with configurable rates via environment variables.
All auth views are DRF APIViews, so DRF throttling covers everything.

IMPORTANT: All throttle class scopes MUST be globally unique to avoid cache key collisions.
Current scopes: auth, token_refresh, execution, general_api, public
"""

from __future__ import annotations

from typing import Any

import structlog
from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from core.middleware import get_client_ip

logger = structlog.get_logger(__name__)


class _RateLimitEnabledMixin:
    """Skip throttling when RATELIMIT_ENABLED=false (emergency bypass).

    This mixin provides a global killswitch for rate limiting via the
    RATELIMIT_ENABLED setting. When disabled, all throttle checks are bypassed,
    allowing unlimited requests. Used for emergency situations where rate
    limiting causes operational issues.

    Returns:
        True: Allow request (bypassed or within limit)
        False: Throttle request (exceeded limit)
    """

    def allow_request(self, request: Any, view: Any) -> bool:
        if not getattr(settings, 'RATELIMIT_ENABLED', True):
            return True
        return super().allow_request(request, view)  # type: ignore[misc,no-any-return]


class AuthEndpointThrottle(_RateLimitEnabledMixin, AnonRateThrottle):
    """Rate limit for authentication endpoints (SAML login, callback, logout).

    Keyed by IP address. Default: 10 requests/minute.
    """
    scope = 'auth'

    def get_cache_key(self, request: Any, view: Any) -> str:
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request),
        }


class TokenRefreshThrottle(_RateLimitEnabledMixin, AnonRateThrottle):
    """Rate limit for token refresh endpoint.

    Keyed by IP address. Default: 20 requests/minute.
    """
    scope = 'token_refresh'

    def get_cache_key(self, request: Any, view: Any) -> str:
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request),
        }


class ExecutionThrottle(_RateLimitEnabledMixin, UserRateThrottle):
    """Rate limit for execution POST endpoint.

    Keyed by authenticated user. Default: 30 requests/minute.
    """
    scope = 'execution'


class GeneralAPIThrottle(_RateLimitEnabledMixin, UserRateThrottle):
    """Rate limit for general authenticated API endpoints.

    Keyed by authenticated user. Default: 100 requests/minute.
    """
    scope = 'general_api'


class PublicEndpointThrottle(_RateLimitEnabledMixin, AnonRateThrottle):
    """Rate limit for public/anonymous endpoints.

    Keyed by IP address. Default: 50 requests/minute.
    """
    scope = 'public'

    def get_cache_key(self, request: Any, view: Any) -> str:
        return self.cache_format % {
            'scope': self.scope,
            'ident': get_client_ip(request),
        }
