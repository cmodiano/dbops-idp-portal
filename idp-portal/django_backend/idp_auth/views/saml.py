"""
Views for SAML authentication endpoints.
Extracted from idp_auth/views.py — Story 54.7 (MAINT-BE-2).
"""

import structlog

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny

from idp_auth.dev_bypass import is_dev_bypass_allowed
from idp_auth.models import User
from idp_auth.services import AuthService
from idp_auth.saml_utils import create_saml_auth
from idp_auth.jwt_utils import create_access_token, create_refresh_token
from idp_auth.views.helpers import _extract_ad_groups
from profiles.models import Profile
from core.exceptions import ForbiddenError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.throttling import AuthEndpointThrottle

logger = structlog.get_logger(__name__)


class SAMLLoginView(APIView):
    """
    GET /auth/saml/login - Initiate SP-initiated SAML flow.
    Redirects browser to IdP SSO URL.
    When AUTH_DEV_BYPASS is true, skips IdP and redirects to frontend with dev JWT.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthEndpointThrottle]

    def get(self, request: Request) -> HttpResponse:
        """Initiate SAML login flow."""
        # SEC-6: Reject dev bypass when DEBUG=False (production)
        if getattr(settings, "AUTH_DEV_BYPASS", False) and not getattr(settings, "DEBUG", False):
            logger.critical(
                "SECURITY ALERT: AUTH_DEV_BYPASS is enabled in production mode "
                "(DEBUG=False). Dev bypass is disabled. Use SAML IdP for authentication."
            )
            raise ForbiddenError(
                code="DEV_BYPASS_FORBIDDEN",
                message="Dev bypass authentication is not allowed in production.",
                details={},
            )
        # Dev bypass mode (for local development without IdP)
        # Centralized guard: only allow when DEBUG=True (is_dev_bypass_allowed)
        if is_dev_bypass_allowed():
            # Resolve real dev-user id so GET /auth/me finds the user (no user with id=0 in DB)
            dev_user, _ = User.objects.get_or_create(
                username="dev-user",
                defaults={
                    "display_name": "Dev User",
                    "profile": "dbops",
                },
            )
            token_data = {
                "sub": str(dev_user.id),
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
            # KNOWN LIMITATION (SEC-11): Token in URL fragment is acceptable for dev bypass only.
            # Production SAML flow uses standard session-based authentication.
            # Fragment is NOT sent to the server (unlike query params) but is visible
            # in browser history and JavaScript logs.
            # Future: migrate to OAuth2 authorization code flow for enhanced security.
            redirect_url = f"{cors_origin}/auth/callback#access_token={access_token}"

            response = redirect(redirect_url)
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=settings.APP_ENV != "development",
                samesite="Lax",
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
    parser_classes = [FormParser, MultiPartParser]
    permission_classes = [AllowAny]
    throttle_classes = [AuthEndpointThrottle]

    def post(self, request: Request) -> HttpResponse:
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
        raw_profile = attributes.get("profile", [settings.DEFAULT_SAML_PROFILE])[0] if attributes.get("profile") else settings.DEFAULT_SAML_PROFILE
        saml_subject = name_id
        raw_email = (
            (attributes.get("mail") or [None])[0]
            or (attributes.get("email") or [None])[0]
            or (attributes.get("emailAddress") or [None])[0]
            or (attributes.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress") or [None])[0]
            or None
        )
        email = raw_email or None  # normalize empty string to None

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
            email=email,
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
            samesite="Lax",
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            path="/api/v1/auth",
        )
        return response
