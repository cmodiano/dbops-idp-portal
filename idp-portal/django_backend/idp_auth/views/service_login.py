"""
Views for service account LDAP login endpoint.
Extracted from idp_auth/views.py — Story 54.7 (MAINT-BE-2).
"""

import structlog

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse

from idp_auth.serializers import ServiceLoginRequestSerializer
from idp_auth.ldap_service import LDAPService, LDAPUnavailableError
from idp_auth.services import AuthService
from idp_auth.jwt_utils import create_access_token, create_refresh_token
from profiles.models import Profile
from core.exceptions import ForbiddenError, UnauthorizedError, ServiceUnavailableError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.throttling import ServiceLoginThrottle

logger = structlog.get_logger(__name__)


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
            429: OpenApiResponse(
                description='429 Too Many Requests — RATE_LIMIT_EXCEEDED — trop de tentatives, réessayez plus tard',
            ),
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
        # Note: email intentionnellement absent — les comptes de service s'authentifient
        # via LDAP et n'ont pas de claim email SAML. Ils sont distincts des utilisateurs
        # SAML interactifs. email=None (valeur par défaut) est transmis à update_or_create,
        # ce qui écraserait un email existant si le même username existait en SAML.
        # Par convention, les usernames service-account et SAML ne se chevauchent pas.
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
