"""
DRF Authentication backend for JWT tokens.
Story M.7 - Task 4.5-4.8
"""

from typing import Any

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from idp_auth.jwt_utils import verify_token
from idp_auth.models import User


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
        # Check both AUTH_DEV_BYPASS setting and token value
        is_dev_bypass = getattr(settings, 'AUTH_DEV_BYPASS', False)
        is_mock_token = token == 'dev-mock-token-for-testing'
        
        if is_dev_bypass and is_mock_token:
            # Get or create dev user (same as SAMLLoginView dev bypass)
            dev_user, _ = User.objects.get_or_create(
                username="dev-user",
                defaults={
                    "display_name": "Dev User",
                    "profile": "dbops",
                },
            )
            dev_user.ad_groups = ["dbops"]  # type: ignore[attr-defined]  # runtime RBAC attr
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
