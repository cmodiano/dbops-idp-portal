"""
Views for authentication endpoints.
Story M.7 - Full SAML and JWT auth implementation.
Story M.8 - Task 9: Structured logging with structlog.
"""

from typing import cast

import structlog

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from idp_auth.models import User, APIKey
from idp_auth.serializers import (
    APIKeyCreateSerializer,
    APIKeyListSerializer,
    ServiceLoginRequestSerializer,
    TokenRefreshResponseSerializer,
    UserProfileSerializer,
)
from idp_auth.ldap_service import LDAPService, LDAPUnavailableError
from idp_auth.services import AuthService
from idp_auth.saml_utils import create_saml_auth
from idp_auth.jwt_utils import create_access_token, create_refresh_token, verify_token
from profiles.services import ProfileService
from profiles.models import Profile
from core.rbac import get_user_navigation_permissions, is_business_profile
from core.exceptions import ForbiddenError, UnauthorizedError, NotFoundError, ServiceUnavailableError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.throttling import AuthEndpointThrottle, TokenRefreshThrottle, PublicEndpointThrottle, ApiKeyTokenThrottle, ServiceLoginThrottle
from core.utils import ensure_utc_isoformat
from catalog.models import Action

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
    throttle_classes = [AuthEndpointThrottle]

    def get(self, request: Request) -> HttpResponse:
        """Initiate SAML login flow."""
        # Dev bypass mode (for local development without IdP)
        if settings.AUTH_DEV_BYPASS:
            # SEC-7: Guard — log CRITICAL if dev bypass is active with DEBUG=False (production)
            if not settings.DEBUG:
                logger.critical(
                    "SECURITY ALERT: AUTH_DEV_BYPASS is enabled in production mode "
                    "(DEBUG=False). This creates a critical security vulnerability."
                )
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
            samesite="Lax",
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            path="/api/v1/auth",
        )
        return response


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


class UserFavoritesView(APIView):
    """
    GET /users/me/favorites - List current user's favorites.
    Matches frontend expectations (FavoriteEntry: { action_id, created_at }).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        favorites = AuthService().list_favorites(request.user.id)  # type: ignore[arg-type]
        data = [
            {
                "action_id": fav.action_id,
                "created_at": ensure_utc_isoformat(fav.created_at),
            }
            for fav in favorites
        ]
        return Response({"data": data})


class UserFavoriteItemView(APIView):
    """
    POST /users/me/favorites/{action_id} - Add favorite (idempotent).
    DELETE /users/me/favorites/{action_id} - Remove favorite (idempotent).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, action_id: int) -> Response:
        try:
            AuthService().add_favorite(request.user.id, action_id)  # type: ignore[arg-type]
        except Action.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="Action non trouvée",
                details={"action_id": action_id},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, action_id: int) -> Response:
        # Idempotent: removing a non-existing favorite is still 204
        AuthService().remove_favorite(request.user.id, action_id)  # type: ignore[arg-type]
        return Response(status=status.HTTP_204_NO_CONTENT)


class ServiceLoginView(APIView):
    """
    POST /auth/service-login - Authentification compte de service via LDAP (username+password → JWT).
    Story 49.2.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ServiceLoginThrottle]

    @extend_schema(
        tags=['auth'],
        summary='Authentification compte de service via LDAP',
        description=(
            "Authentifie un compte de service (username/password) contre l'Active Directory via LDAP. "
            'Retourne un JWT access token et positionne un cookie refresh_token httpOnly. '
            'Rate limit : 5 requêtes/minute par IP.'
        ),
        request=ServiceLoginRequestSerializer,
        responses={
            200: OpenApiResponse(description='JWT retourné dans data.access_token'),
            400: OpenApiResponse(description='Validation — username ou password manquant'),
            401: OpenApiResponse(description='INVALID_CREDENTIALS — credentials invalides'),
            403: OpenApiResponse(description='NO_PROFILE — aucun profil AD associé'),
            503: OpenApiResponse(description='LDAP_UNAVAILABLE — service LDAP inaccessible'),
        },
    )
    def post(self, request: Request) -> Response:
        correlation_id = get_correlation_id()
        log = logger.bind(correlation_id=correlation_id)

        # Step 1: Validate request body
        serializer = ServiceLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # Step 2: LDAP authentication
        ldap_service = LDAPService()
        try:
            success, ad_groups, display_name = ldap_service.authenticate(username, password)
        except LDAPUnavailableError as exc:
            log.error('service_login_ldap_unavailable', error=str(exc))
            AuditService.create_entry(
                user_id='unknown',
                action_type=AuditActionType.SERVICE_LOGIN,
                entity_type=AuditEntityType.USER,
                entity_id=0,
                details={'success': False, 'reason': 'ldap_unavailable', 'username': username},
            )
            raise ServiceUnavailableError(
                code='LDAP_UNAVAILABLE',
                message="Service d'authentification LDAP indisponible",
                details={},
            )

        # Step 3: Check credentials
        if not success:
            log.warning('service_login_invalid_credentials', ldap_username=username)
            AuditService.create_entry(
                user_id='unknown',
                action_type=AuditActionType.SERVICE_LOGIN,
                entity_type=AuditEntityType.USER,
                entity_id=0,
                details={'success': False, 'reason': 'invalid_credentials', 'username': username},
            )
            raise UnauthorizedError(
                code='INVALID_CREDENTIALS',
                message='Credentials invalides',
                details={},
            )

        # Step 4: Resolve profile from AD groups
        profiles = Profile.objects.find_by_ad_groups(ad_groups)
        if not profiles:
            log.warning('service_login_no_profile', ldap_username=username, ad_groups=ad_groups)
            AuditService.create_entry(
                user_id='unknown',
                action_type=AuditActionType.SERVICE_LOGIN,
                entity_type=AuditEntityType.USER,
                entity_id=0,
                details={'success': False, 'reason': 'no_profile', 'username': username, 'ad_groups': ad_groups},
            )
            raise ForbiddenError(
                code='NO_PROFILE',
                message='Aucun profil associé à votre compte. Contactez un administrateur.',
                details={'ad_groups': ad_groups},
            )

        # Step 5: JIT create/update user
        profile_for_db = profiles[0].name.lower()
        auth_service = AuthService()
        user = auth_service.create_or_update_user(
            username=username,
            display_name=display_name,
            profile=profile_for_db,
            saml_subject=None,
        )

        # Step 6: Build token data (same format as SAML)
        token_data = {
            'sub': str(user.id),
            'username': user.username,
            'profile': user.profile,
            'ad_groups': ad_groups,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        # Step 7: Audit success
        log.info('service_login_success', ldap_username=username, profile=profile_for_db)
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.SERVICE_LOGIN,
            entity_type=AuditEntityType.USER,
            entity_id=user.id,
            details={'success': True, 'username': username, 'profile': profile_for_db, 'ad_groups': ad_groups},
        )

        # Step 8: Build response with refresh cookie
        response = Response({
            'data': {
                'access_token': access_token,
                'token_type': 'Bearer',
                'expires_in': expires_in,
            }
        })
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=settings.APP_ENV != 'development',
            samesite='Lax',
            max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS * 3600,
            path='/api/v1/auth',
        )
        return response


class APIKeyTokenView(APIView):
    """
    POST /auth/token - Échanger une API key contre un JWT access token.
    Permet la consommation programmatique de l'API (scripts CI/CD).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ApiKeyTokenThrottle]

    @extend_schema(
        tags=['auth'],
        summary='Échanger API key contre JWT',
        description=(
            'Échange une API key (header X-API-Key) contre un token JWT. '
            'Utilisez ce token dans le bouton Authorize de Swagger UI pour tester les endpoints protégés. '
            'Rate limit : 10 requêtes/minute.'
        ),
        parameters=[
            OpenApiParameter(
                name='X-API-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description='API key (créée via portail ou commande create_api_key)',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Token JWT retourné dans data.access_token'),
            401: OpenApiResponse(description='MISSING_API_KEY ou INVALID_API_KEY'),
        },
        auth=[{'apiKeyAuth': []}],  # type: ignore[list-item]
    )
    def post(self, request: Request) -> Response:
        raw_key = request.META.get('HTTP_X_API_KEY', '').strip()
        if not raw_key:
            raise UnauthorizedError(
                code='MISSING_API_KEY',
                message='Header X-API-Key manquant',
                details={}
            )

        api_key = APIKey.objects.verify_key(raw_key)
        correlation_id = get_correlation_id()

        if api_key is None:
            logger.warning(
                'api_key_token_exchange_failed',
                reason='invalid_or_expired_key',
                correlation_id=correlation_id,
            )
            AuditService.create_entry(
                user_id='unknown',
                action_type=AuditActionType.API_KEY_TOKEN_EXCHANGE,
                entity_type=AuditEntityType.USER,
                entity_id=0,
                details={'success': False, 'reason': 'invalid_or_expired_key'}
            )
            raise UnauthorizedError(
                code='INVALID_API_KEY',
                message='API key invalide, expirée ou révoquée',
                details={}
            )

        user = api_key.user
        token_data = {
            'sub': str(user.id),
            'username': user.username,
            'profile': user.profile,
            'ad_groups': [user.profile],
        }
        access_token = create_access_token(token_data)
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        logger.info(
            'api_key_token_exchange_success',
            key_name=api_key.name,
            user_id=user.id,
            correlation_id=correlation_id,
        )
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.API_KEY_TOKEN_EXCHANGE,
            entity_type=AuditEntityType.USER,
            entity_id=user.id,
            details={'success': True, 'key_name': api_key.name, 'scope': api_key.scope}
        )

        return Response({
            'data': {
                'access_token': access_token,
                'token_type': 'Bearer',
                'expires_in': expires_in,
            }
        })


class APIKeysView(APIView):
    """
    POST /auth/api-keys - Create API key for authenticated user (raw_key returned once).
    GET /auth/api-keys - List current user's active API keys (without raw_key).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user_id = cast(int, request.user.id)
        queryset = APIKey.objects.filter(
            user_id=user_id,
            is_active=True,
        ).order_by('-created_at')
        serializer = APIKeyListSerializer(queryset, many=True)
        return Response({'data': serializer.data})

    def post(self, request: Request) -> Response:
        # Story 44.7 AC7: enforce business cap of 5 active keys per user.
        user_id = cast(int, request.user.id)
        active_keys_count = APIKey.objects.filter(
            user_id=user_id,
            is_active=True,
        ).count()
        if active_keys_count >= 5:
            return Response(
                {
                    "error": {
                        "code": "API_KEY_LIMIT_REACHED",
                        "message": "Limite de 5 clés API actives atteinte",
                        "details": {"max_active_keys": 5},
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_key, raw_key = APIKey.objects.create_key(
            user=cast(User, request.user),
            name=serializer.validated_data['name'],
            scope=serializer.validated_data.get('scope'),
        )

        return Response(
            {
                'data': {
                    'id': api_key.id,
                    'name': api_key.name,
                    'scope': api_key.scope,
                    'created_at': api_key.created_at.isoformat(),
                    'raw_key': raw_key,
                }
            },
            status=status.HTTP_201_CREATED,
        )


class APIKeyDetailView(APIView):
    """
    DELETE /auth/api-keys/{id} - Revoke current user's API key (soft delete).
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, pk: int) -> Response:
        try:
            api_key = APIKey.objects.get(pk=pk)
        except APIKey.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="API key introuvable",
                details={"api_key_id": pk},
            )

        if api_key.user_id != cast(int, request.user.id):
            raise ForbiddenError(
                code="FORBIDDEN",
                message="Vous ne pouvez révoquer que vos propres clés API",
                details={"api_key_id": pk},
            )

        if api_key.is_active:
            api_key.is_active = False
            api_key.save(update_fields=['is_active', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)
