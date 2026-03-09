"""
Views for API key CRUD and token exchange endpoints.
Extracted from idp_auth/views.py — Story 54.7 (MAINT-BE-2).
"""

from typing import cast

import structlog

from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from idp_auth.models import User, APIKey
from idp_auth.serializers import APIKeyCreateSerializer, APIKeyListSerializer
from profiles.models import Profile
from idp_auth.jwt_utils import create_access_token
from core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.throttling import ApiKeyTokenThrottle

logger = structlog.get_logger(__name__)


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

        # SEC-3 FIX: Resolve real AD groups from Profile DB instead of hardcoding [user.profile].
        # API key users have no LDAP session, so we resolve profiles by name match.
        resolved_profiles = list(Profile.objects.find_by_ad_groups([user.profile]))
        ad_groups = [p.ad_group for p in resolved_profiles if p.ad_group]
        if not ad_groups:
            # Fallback: no Profile found (or all resolved profiles have empty ad_group).
            # This can occur if Profile table is out of sync with user.profile field.
            if user.profile:
                ad_groups = [user.profile]
            logger.warning(
                'api_key_token_no_profile_found',
                user_profile=user.profile,
                user_id=user.id,
                correlation_id=correlation_id,
            )

        token_data = {
            'sub': str(user.id),
            'username': user.username,
            'profile': user.profile,
            'ad_groups': ad_groups,
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

        # NEW-FIND-01 fix: wrap create_key + audit in atomic block so both succeed or both roll back
        # (consistent with AUTH-MED-02 pattern from services.py)
        with transaction.atomic():
            api_key, raw_key = APIKey.objects.create_key(
                user=cast(User, request.user),
                name=serializer.validated_data['name'],
                scope=serializer.validated_data.get('scope'),
            )

            # Audit: API key creation is a security-critical operation (SOC1 — AUTH-HIGH-01)
            correlation_id = get_correlation_id()
            logger.info(
                'api_key_created',
                key_name=api_key.name,
                user_id=user_id,
                scope=api_key.scope,
                correlation_id=correlation_id,
            )
            AuditService.create_entry(
                user_id=str(user_id),
                action_type=AuditActionType.API_KEY_CREATED,
                entity_type=AuditEntityType.USER,
                entity_id=user_id,
                details={
                    'key_name': api_key.name,
                    'scope': api_key.scope,
                    'api_key_id': api_key.id,
                    'correlation_id': correlation_id,
                }
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

        # NEW-FIND-01 fix: wrap soft-delete + audit in atomic block so both succeed or both roll back
        # (consistent with AUTH-MED-02 pattern from services.py)
        # Audit unconditionally (idempotent revoke still needs a trace for already-inactive keys)
        with transaction.atomic():
            if api_key.is_active:
                api_key.is_active = False
                api_key.save(update_fields=['is_active', 'updated_at'])

            # Audit: API key revocation is a security-critical operation (SOC1 — AUTH-HIGH-02)
            correlation_id = get_correlation_id()
            requester_id = cast(int, request.user.id)
            logger.info(
                'api_key_revoked',
                key_name=api_key.name,
                key_id=pk,
                user_id=api_key.user_id,
                correlation_id=correlation_id,
            )
            AuditService.create_entry(
                user_id=str(requester_id),
                action_type=AuditActionType.API_KEY_REVOKED,
                entity_type=AuditEntityType.USER,
                entity_id=requester_id,
                details={
                    'key_name': api_key.name,
                    'scope': api_key.scope,
                    'api_key_id': api_key.id,
                    'correlation_id': correlation_id,
                }
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
