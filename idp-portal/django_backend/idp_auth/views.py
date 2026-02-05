"""
Views for authentication endpoints.
Matches FastAPI /auth/* endpoints.
Story M.7 - Full SAML and JWT auth implementation.
Story M.8 - Task 9: Structured logging with structlog.
"""

import structlog

from django.conf import settings
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from idp_auth.serializers import UserProfileSerializer, TokenRefreshResponseSerializer
from idp_auth.services import AuthService
from idp_auth.saml_utils import create_saml_auth
from idp_auth.jwt_utils import create_access_token, create_refresh_token, verify_token
from profiles.services import ProfileService
from profiles.models import Profile
from core.rbac import get_user_navigation_permissions, is_business_profile
from core.exceptions import ForbiddenError, UnauthorizedError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Default profile mapping for SAML attributes
_DEFAULT_PROFILE = "dba_applicatif"
_ALLOWED_PROFILES = {"dba_applicatif", "dba_infrastructure", "dbops"}


def _extract_ad_groups(attributes: dict, raw_profile: str | None) -> list[str]:
    """Extract AD groups from SAML attributes.

    Looks for groups in: groups, memberOf, ad_groups.
    Falls back to raw_profile for backward compatibility.
    """
    raw_groups = (
        attributes.get("groups")
        or attributes.get("memberOf")
        or attributes.get("ad_groups")
        or []
    )
    if isinstance(raw_groups, str):
        ad_groups = [raw_groups.strip()] if raw_groups.strip() else []
    else:
        ad_groups = [g.strip() for g in raw_groups if g and str(g).strip()]

    # Fallback to raw_profile for backward compat
    if not ad_groups and raw_profile:
        ad_groups = [raw_profile]

    return ad_groups


class SAMLLoginView(APIView):
    """
    GET /auth/saml/login - Initiate SP-initiated SAML flow.
    Redirects browser to IdP SSO URL.
    When AUTH_DEV_BYPASS is true, skips IdP and redirects to frontend with dev JWT.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        """Initiate SAML login flow."""
        # Dev bypass mode (for local development without IdP)
        if settings.AUTH_DEV_BYPASS:
            token_data = {
                "sub": "0",
                "username": "dev-user",
                "profile": "dbops",
                "ad_groups": ["dbops"],
            }
            access_token = create_access_token(token_data)
            refresh_token = create_refresh_token(token_data)

            cors_origin = (
                settings.CORS_ALLOWED_ORIGINS[0] 
                if settings.CORS_ALLOWED_ORIGINS and len(settings.CORS_ALLOWED_ORIGINS) > 0 
                else 'http://localhost:5173'
            )
            redirect_url = f"{cors_origin}/auth/callback#access_token={access_token}"

            response = redirect(redirect_url)
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=settings.APP_ENV != "development",
                samesite="lax",
                max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
                path="/api/v1/auth",
            )
            correlation_id = get_correlation_id()
            logger.info(
                "auth_dev_bypass_login",
                redirect_origin=cors_origin,
                correlation_id=correlation_id
            )
            return response

        # Normal SAML flow
        auth = create_saml_auth(request)
        sso_url = auth.login()
        correlation_id = get_correlation_id()
        logger.info(
            "saml_login_redirect",
            sso_url=sso_url,
            correlation_id=correlation_id
        )
        return redirect(sso_url)


class SAMLCallbackView(APIView):
    """
    POST /auth/saml/callback - Receive SAML assertion from IdP.
    Validates assertion, creates/updates user, emits JWT tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Process SAML callback with assertion."""
        post_data = dict(request.POST)

        auth = create_saml_auth(request, post_data=post_data)
        auth.process_response()
        errors = auth.get_errors()

        if errors:
            correlation_id = get_correlation_id()
            logger.error(
                "saml_callback_error",
                errors=errors,
                reason=auth.get_last_error_reason(),
                correlation_id=correlation_id
            )
            raise ForbiddenError(
                code="SAML_VALIDATION_FAILED",
                message=f"SAML validation failed: {errors}",
                details={"errors": errors}
            )

        if not auth.is_authenticated():
            raise ForbiddenError(
                code="SAML_NOT_AUTHENTICATED",
                message="SAML authentication failed",
                details={}
            )

        # Extract attributes from assertion (Story 2.12: groups for multi-profile)
        attributes = auth.get_attributes()
        name_id = auth.get_nameid()

        username = attributes.get("username", [name_id])[0] if attributes.get("username") else name_id
        display_name = attributes.get("displayName", [None])[0] if attributes.get("displayName") else None
        raw_profile = attributes.get("profile", [_DEFAULT_PROFILE])[0] if attributes.get("profile") else _DEFAULT_PROFILE
        saml_subject = name_id

        # Extract AD groups
        ad_groups = _extract_ad_groups(attributes, raw_profile)

        # Resolve profiles by AD groups (AC1, AC3): no profile -> 403 NO_PROFILE
        profiles = Profile.objects.find_by_ad_groups(ad_groups)
        if not profiles:
            correlation_id = get_correlation_id()
            logger.warning(
                "saml_callback_no_profile",
                username=username,
                ad_groups=ad_groups,
                correlation_id=correlation_id
            )
            raise ForbiddenError(
                code="NO_PROFILE",
                message="Aucun profil associé à votre compte.",
                details={"ad_groups": ad_groups}
            )

        # Use first resolved profile name from AD groups for DB storage
        # This is the authoritative profile (Story 2.12: multi-profile support)
        profile_for_db = profiles[0].name.lower()

        correlation_id = get_correlation_id()
        logger.info(
            "saml_callback_success",
            username=username,
            profile=profile_for_db,
            profile_count=len(profiles),
            correlation_id=correlation_id
        )

        # Create or update user in DB
        auth_service = AuthService()
        user = auth_service.create_or_update_user(
            username=username,
            display_name=display_name,
            profile=profile_for_db,
            saml_subject=saml_subject,
        )

        # Audit login
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.USER_LOGIN,
            entity_type=AuditEntityType.USER,
            entity_id=user.id,
            details={"username": username, "ad_groups": ad_groups}
        )

        # Generate JWT tokens (include ad_groups for RBAC cumulative permissions, Story 2.12)
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "profile": user.profile,
            "ad_groups": ad_groups,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Redirect to SPA with access token as URL fragment, set refresh token as httpOnly cookie
        cors_origin = (
            settings.CORS_ALLOWED_ORIGINS[0] 
            if settings.CORS_ALLOWED_ORIGINS and len(settings.CORS_ALLOWED_ORIGINS) > 0 
            else 'http://localhost:5173'
        )
        redirect_url = f"{cors_origin}/auth/callback#access_token={access_token}"

        response = redirect(redirect_url)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.APP_ENV != "development",
            samesite="lax",
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            path="/api/v1/auth",
        )
        return response


class CurrentUserProfileView(APIView):
    """
    GET /auth/me - Return current user profile with navigation permissions.
    Matches FastAPI get_current_user_profile endpoint.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
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
                cumulative_permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)
            except Exception as e:
                # Log error but don't fail the request
                correlation_id = get_correlation_id()
                logger.error(
                    "failed_to_get_cumulative_permissions",
                    user_id=user.id,
                    error=str(e),
                    correlation_id=correlation_id
                )
                cumulative_permissions = None

        # Check if user is auditor
        is_auditor = False
        if profiles:
            is_auditor = any(
                getattr(p, 'is_auditor', False) or (hasattr(p, 'is_auditor') and p.is_auditor == 1)
                for p in profiles
            )

        # Build user profile data
        profile_data = {
            'id': user.id,
            'username': getattr(user, 'username', ''),
            'display_name': getattr(user, 'display_name', None),
            'profile': profile_name,
            'profile_ids': profile_ids,
            'cumulative_permissions': cumulative_permissions,
            'is_auditor': is_auditor,
            'navigation_tabs': get_user_navigation_permissions(profile_name),
            'is_business_profile': is_business_profile(profile_name),
        }

        serializer = UserProfileSerializer(profile_data)
        return Response({'data': serializer.data})


class RefreshTokenView(APIView):
    """
    POST /auth/refresh - Exchange refresh token for access token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
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

    def post(self, request):
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
