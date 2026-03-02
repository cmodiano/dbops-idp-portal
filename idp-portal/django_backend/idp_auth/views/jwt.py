"""
Views for JWT token management endpoints.
Extracted from idp_auth/views.py — Story 54.7 (MAINT-BE-2).
"""

import structlog

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from idp_auth.serializers import (
    UserProfileSerializer,
    TokenRefreshResponseSerializer,
)
from idp_auth.jwt_utils import verify_token, create_access_token
from profiles.services import ProfileService
from profiles.models import Profile
from core.rbac import get_user_navigation_permissions, is_business_profile
from core.exceptions import UnauthorizedError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.throttling import TokenRefreshThrottle, PublicEndpointThrottle

logger = structlog.get_logger(__name__)


class CurrentUserProfileView(APIView):
    """
    GET /auth/me - Return current user profile with navigation permissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        Return the authenticated user's profile with navigation permissions.

        Story 7.1: Includes is_business_profile flag for simplified UI.
        """
        user = request.user

        # Get profile name
        profile_name = getattr(user, 'profile', '')
        if isinstance(profile_name, str):
            profile_name = profile_name.lower()
        elif hasattr(profile_name, 'name'):
            profile_name = profile_name.name.lower()
        elif hasattr(profile_name, 'code'):
            profile_name = profile_name.code.lower()

        # Get AD groups from JWT token (attached by JWTAuthentication)
        ad_groups = getattr(user, 'ad_groups', [])
        if not ad_groups and profile_name:
            ad_groups = [profile_name]

        # Resolve profiles by AD groups
        profiles = Profile.objects.find_by_ad_groups(ad_groups) if ad_groups else []
        profile_ids = [p.id for p in profiles] if profiles else None

        # Get cumulative permissions
        cumulative_permissions = None
        if profile_ids:
            try:
                profile_service = ProfileService()
                cumulative_permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)  # type: ignore[arg-type]
            except Exception as e:  # noqa: BLE001 — graceful-degradation: ProfileService failure sets permissions to None
                # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
                correlation_id = get_correlation_id()
                logger.error(
                    "failed_to_get_cumulative_permissions",
                    user_id=user.id,
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=correlation_id,
                    exc_info=True,
                )
                cumulative_permissions = None

        # Check if user is auditor
        # Story 30.12 AC4: Use explicit == 1 comparison (not truthiness) for Oracle IntegerField
        is_auditor = False
        if profiles:
            is_auditor = any(p.is_auditor == 1 for p in profiles if hasattr(p, 'is_auditor'))

        # Build navigation tabs, injecting 'audit' for auditors (Story 6.5)
        navigation_tabs = list(get_user_navigation_permissions(profile_name))  # Copy to avoid mutating global
        if is_auditor and 'audit' not in navigation_tabs:
            navigation_tabs.append('audit')

        # Build user profile data
        profile_data = {
            'id': user.id,
            'username': getattr(user, 'username', ''),
            'display_name': getattr(user, 'display_name', None),
            'profile': profile_name,
            'profile_ids': profile_ids,
            'cumulative_permissions': cumulative_permissions,
            'is_auditor': is_auditor,
            'navigation_tabs': navigation_tabs,
            'is_business_profile': is_business_profile(profile_name),
            'email': getattr(user, 'email', None),
        }

        serializer = UserProfileSerializer(profile_data)
        return Response({'data': serializer.data})


class RefreshTokenView(APIView):
    """
    POST /auth/refresh - Exchange refresh token for access token.
    """
    permission_classes = [AllowAny]
    throttle_classes = [TokenRefreshThrottle]

    def post(self, request: Request) -> Response:
        """
        Exchange refresh token (httpOnly cookie) for a new access token.
        """
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            raise UnauthorizedError(
                code="NO_REFRESH_TOKEN",
                message="Refresh token manquant",
                details={}
            )

        payload = verify_token(refresh_token, expected_type="refresh")
        if not payload:
            raise UnauthorizedError(
                code="INVALID_TOKEN",
                message="Refresh token invalide ou expire",
                details={}
            )

        # Generate new access token (preserve ad_groups for RBAC, Story 2.12)
        token_data = {
            "sub": payload.sub,
            "username": payload.username,
            "profile": payload.profile,
            "ad_groups": payload.ad_groups or [],
        }
        new_access_token = create_access_token(token_data)

        # Audit refresh
        try:
            entity_id = int(payload.sub)
        except (ValueError, TypeError):
            correlation_id = get_correlation_id()
            logger.error(
                "invalid_user_id_in_refresh_token",
                user_id=payload.sub,
                correlation_id=correlation_id
            )
            raise UnauthorizedError(
                code="INVALID_TOKEN",
                message="Token payload invalide",
                details={}
            )

        AuditService.create_entry(
            user_id=payload.sub,
            action_type=AuditActionType.USER_REFRESH,
            entity_type=AuditEntityType.USER,
            entity_id=entity_id,
            details={"username": payload.username}
        )

        serializer = TokenRefreshResponseSerializer({
            "access_token": new_access_token,
            "token_type": "bearer"
        })
        return Response({'data': serializer.data})


class LogoutView(APIView):
    """
    POST /auth/logout - Clear refresh token cookie.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PublicEndpointThrottle]

    def post(self, request: Request) -> Response:
        """
        Clear the refresh token cookie.
        """
        # Audit logout if we can identify the user
        refresh_token = request.COOKIES.get("refresh_token")
        if refresh_token:
            payload = verify_token(refresh_token, expected_type="refresh")
            if payload:
                try:
                    entity_id = int(payload.sub)
                    AuditService.create_entry(
                        user_id=payload.sub,
                        action_type=AuditActionType.USER_LOGOUT,
                        entity_type=AuditEntityType.USER,
                        entity_id=entity_id,
                        details={"username": payload.username}
                    )
                except (ValueError, TypeError):
                    # Log warning but don't fail logout
                    correlation_id = get_correlation_id()
                    logger.warning(
                        "logout_audit_failed",
                        user_id=payload.sub,
                        reason="invalid_user_id",
                        correlation_id=correlation_id
                    )

        response = Response(
            {'data': {'message': 'Deconnexion reussie'}},
            status=status.HTTP_200_OK
        )
        response.delete_cookie(key='refresh_token', path='/api/v1/auth')
        return response
