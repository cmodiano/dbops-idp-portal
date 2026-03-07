"""
DRF Authentication backend for JWT tokens.
Story M.7 - Task 4.5-4.8
"""

import structlog
from typing import Any

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from idp_auth.dev_bypass import is_dev_bypass_allowed
from idp_auth.jwt_utils import verify_token
from idp_auth.models import User

logger = structlog.get_logger(__name__)


class JWTAuthentication(BaseAuthentication):
    """
    DRF Authentication backend that validates JWT tokens from Authorization header.

    Usage in views:
        authentication_classes = [JWTAuthentication]

    Or globally in settings:
        REST_FRAMEWORK = {
            'DEFAULT_AUTHENTICATION_CLASSES': ['idp_auth.authentication.JWTAuthentication']
        }
    """

    def authenticate(self, request: Any) -> tuple[User, None] | None:
        """
        Authenticate the request and return a two-tuple of (user, token).

        Returns:
            tuple: (User, None) if authentication successful
            None: if no Authorization header present (allows anonymous access)

        Raises:
            AuthenticationFailed: If token is invalid, expired, or user not found
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return None

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ', 1)[1]

        # Dev mode: Accept mock token from frontend VITE_DEV_AUTH mode
        # Centralized guard: dev bypass only when DEBUG=True (is_dev_bypass_allowed)
        is_mock_token = token == 'dev-mock-token-for-testing'
        if is_mock_token and getattr(settings, "AUTH_DEV_BYPASS", False) and not getattr(settings, "DEBUG", False):
            # SEC-6: AUTH_DEV_BYPASS=True + DEBUG=False → return None (unauthenticated)
            return None
        if is_dev_bypass_allowed() and is_mock_token:
            # SEC-6: Get or create dev user (only reached when DEBUG=True)
            dev_user, _ = User.objects.get_or_create(
                username="dev-user",
                defaults={
                    "display_name": "Dev User",
                    "profile": "dbops",
                },
            )
            dev_user.ad_groups = ["dbops"]  # type: ignore[attr-defined]  # runtime RBAC attr

            # SEC-6: Create audit entry for dev bypass authentication (traceability)
            try:
                AuditService.create_entry(
                    user_id=str(dev_user.id),
                    action_type=AuditActionType.AUTH_DEV_BYPASS_LOGIN,
                    entity_type=AuditEntityType.USER,
                    entity_id=dev_user.id,
                    details={'username': 'dev-user', 'debug': True, 'bypass_method': 'mock_token'},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
            except Exception:  # noqa: BLE001
                # Audit failure must never block authentication in dev mode
                logger.warning("auth_dev_bypass_audit_failed", username="dev-user")

            return (dev_user, None)

        # Verify token
        payload = verify_token(token, expected_type='access')
        if not payload:
            raise AuthenticationFailed('Token invalide ou expire')

        # Load user from database
        try:
            user_id = int(payload.sub)
            user = User.objects.get(id=user_id)
        except (ValueError, User.DoesNotExist):
            raise AuthenticationFailed('Utilisateur non trouve')

        # Attach ad_groups to user for RBAC resolution (Story 2.12)
        user.ad_groups = payload.ad_groups  # type: ignore[attr-defined]  # runtime RBAC attr

        return (user, None)

    def authenticate_header(self, request: Any) -> str:
        """
        Return the WWW-Authenticate header value for 401 responses.
        """
        return 'Bearer realm="api"'
