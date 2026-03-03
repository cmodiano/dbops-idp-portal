"""
Views for integrations CRUD endpoints.
"""

import structlog
from typing import Any

from asgiref.sync import async_to_sync
from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiResponse, OpenApiParameter
from integrations.serializers import (
    IntegrationSerializer, IntegrationCreateSerializer,
    IntegrationUpdateSerializer, IntegrationListSerializer
)
from integrations.services import IntegrationService
from integrations.validation_service import IntegrationValidationService
from core.permissions import DBOPSProfilePermission
from core.exceptions import NotFoundError, InvalidStateError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['integrations'],
        summary='Lister les intégrations',
        parameters=[
            OpenApiParameter('type', str, description='Filtre par type d\'intégration'),
        ],
    ),
    retrieve=extend_schema(tags=['integrations'], summary='Détail d\'une intégration'),
    create=extend_schema(tags=['integrations'], summary='Créer une intégration'),
    update=extend_schema(tags=['integrations'], summary='Modifier une intégration'),
    partial_update=extend_schema(tags=['integrations'], summary='Modifier partiellement une intégration'),
    destroy=extend_schema(tags=['integrations'], summary='Supprimer une intégration'),
)
class IntegrationViewSet(viewsets.ViewSet):
    """
    ViewSet for integrations CRUD operations.
    """
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
    
    def list(self, request):
        """
        GET /admin/integrations - List all integrations.
        GET /admin/integrations/?type=... - List integrations filtered by type.
        """
        service = IntegrationService()
        integration_type = request.query_params.get('type')
        integrations = service.list_all(integration_type=integration_type)
        serializer = IntegrationListSerializer(integrations, many=True)
        return Response({'data': serializer.data})
    
    def retrieve(self, request, pk=None):
        """
        GET /admin/integrations/{id} - Get integration by ID.
        """
        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk}
            )
        
        service = IntegrationService()
        integration = service.get_by_id(integration_id)
        
        if integration is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id}
            )
        
        serializer = IntegrationSerializer(integration)
        return Response({'data': serializer.data})
    
    def create(self, request):
        """
        POST /admin/integrations - Create integration.
        Returns 201 Created.
        """
        serializer = IntegrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = IntegrationService()
        
        try:
            integration = service.create_integration(
                serializer.validated_data,
                user=request.user
            )
        except ValueError as e:
            error_msg = str(e)
            if "existe déjà" in error_msg:
                raise InvalidStateError(
                    code="DUPLICATE_NAME",
                    message=error_msg,
                    details={"name": serializer.validated_data.get('name')}
                )
            raise InvalidStateError(
                code="VALIDATION_ERROR",
                message=error_msg,
                details={}
            )
        except InvalidStateError:
            # Re-raise InvalidStateError (e.g., INVALID_CONFIG from JSON Schema validation)
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: unexpected error wrapped in InvalidStateError for API response
            logger.exception(
                "create_integration_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise InvalidStateError(
                code="VALIDATION_ERROR",
                message="Impossible d'enregistrer l'intégration. Réessayez ou contactez l'administrateur.",
                details={}
            )
        
        response_serializer = IntegrationSerializer(integration)
        response_data: dict[str, Any] = {'data': response_serializer.data}
        warnings = getattr(integration, '_warnings', [])
        if warnings:
            response_data['warnings'] = warnings
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        """
        PUT /admin/integrations/{id} - Update integration.
        """
        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk}
            )
        
        serializer = IntegrationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        service = IntegrationService()
        
        try:
            integration = service.update_integration(
                integration_id,
                serializer.validated_data,
                user=request.user
            )
        except ValueError as e:
            error_msg = str(e)
            if "existe déjà" in error_msg:
                raise InvalidStateError(
                    code="DUPLICATE_NAME",
                    message=error_msg,
                    details={"name": serializer.validated_data.get('name')}
                )
            raise InvalidStateError(
                code="VALIDATION_ERROR",
                message=error_msg,
                details={}
            )
        except InvalidStateError:
            # Re-raise InvalidStateError (e.g., INVALID_CONFIG from JSON Schema validation)
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: unexpected error wrapped in InvalidStateError for API response
            logger.exception(
                "update_integration_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise InvalidStateError(
                code="VALIDATION_ERROR",
                message="Impossible d'enregistrer l'intégration. Réessayez ou contactez l'administrateur.",
                details={}
            )
        
        if integration is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id}
            )
        
        response_serializer = IntegrationSerializer(integration)
        response_data: dict[str, Any] = {'data': response_serializer.data}
        warnings = getattr(integration, '_warnings', [])
        if warnings:
            response_data['warnings'] = warnings
        return Response(response_data)

    def destroy(self, request, pk=None):
        """
        DELETE /admin/integrations/{id} - Delete integration and disable linked actions.
        Returns 200 with disabled_actions_count if actions were disabled, 204 otherwise.
        """
        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk}
            )

        service = IntegrationService()

        result = service.delete_integration(integration_id, user=request.user)

        if not result:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id}
            )

        if result['disabled_actions_count'] > 0:
            return Response(
                {'disabled_actions_count': result['disabled_actions_count']},
                status=status.HTTP_200_OK,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=['integrations'],
        summary="Validate a single integration against the type catalogue",
        responses={
            200: inline_serializer(
                name='IntegrationValidationResponse',
                fields={
                    'integration_id': drf_serializers.IntegerField(),
                    'integration_name': drf_serializers.CharField(),
                    'integration_type': drf_serializers.CharField(),
                    'current_status': drf_serializers.CharField(),
                    'validation_details': drf_serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description='Integration not found'),
        },
    )
    @action(detail=True, methods=['get'], url_path='validate')
    def validate(self, request, pk=None):
        """GET /admin/integrations/{id}/validate — Validate integration status."""
        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk},
            )

        service = IntegrationService()
        integration = service.get_by_id(integration_id)

        if integration is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id},
            )

        details = IntegrationValidationService.get_integration_validation_details(integration)
        computed_status = details['status']

        # Update status in DB if changed
        if integration.status != computed_status:
            old_status = integration.status
            integration.status = computed_status
            integration.save(update_fields=['status', 'updated_at'])

            AuditService.create_entry(
                user_id=str(request.user.id) if request.user and hasattr(request.user, 'id') else 'system',
                action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={
                    'previous_status': old_status,
                    'new_status': computed_status,
                    'validation_reason': details['validation_message'],
                },
                correlation_id=get_correlation_id(),
            )

        return Response({"data": {
            'integration_id': integration.id,
            'integration_name': integration.name,
            'integration_type': integration.type,
            'current_status': integration.status,
            'validation_details': {
                'status': details['status'],
                'type_exists': details['type_exists'],
                'type_is_active': details['type_is_active'],
                'catalogue_version': details['catalogue_version'],
                'validation_message': details['validation_message'],
            },
        }})

    @extend_schema(
        tags=['integrations'],
        summary="Liste les templates AAP (job ou workflow) d'une intégration",
        parameters=[
            OpenApiParameter('resource_type', str, description="job_template | workflow_job", default='job_template'),
            OpenApiParameter('search', str, description="Filtre par nom (optionnel)", required=False),
        ],
        responses={
            200: inline_serializer(name='AAPTemplatesResponse', fields={
                'data': drf_serializers.ListField(child=drf_serializers.DictField()),
            }),
            400: OpenApiResponse(description='Invalid resource_type or non-AAP integration'),
            404: OpenApiResponse(description='Integration not found'),
            503: OpenApiResponse(description='AAP API unavailable'),
        },
    )
    @action(detail=True, methods=['get'], url_path='aap-templates')
    def aap_templates(self, request, pk=None):
        """GET /admin/integrations/{id}/aap-templates/ — Liste templates AAP."""
        from adapters.aap_adapter import AAPAdapter
        from adapters.utils import build_auth_headers
        from core.exceptions import ServiceUnavailableError as _ServiceUnavailableError

        # Validate resource_type
        resource_type = request.query_params.get('resource_type', 'job_template')
        if resource_type not in ('job_template', 'workflow_job'):
            return Response(
                {'error': f"resource_type invalide: {resource_type!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        search = request.query_params.get('search') or None

        # Get integration
        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk},
            )

        service = IntegrationService()
        integration = service.get_by_id(integration_id)

        if integration is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id},
            )

        # Verify type AAP (includes tower)
        if integration.type not in ('aap', 'tower'):
            return Response(
                {'error': f"L'intégration {integration_id} n'est pas de type AAP (type={integration.type!r})"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_headers = build_auth_headers(integration, get_correlation_id())
        config = integration.get_config() if hasattr(integration, "get_config") else None
        config = config or {}
        ssl_verify = config.get("ssl_verify", True)
        ca_bundle_path = config.get("ca_bundle_path") or None
        adapter = AAPAdapter(
            base_url=integration.base_url,
            auth_headers=auth_headers,
            ssl_verify=ssl_verify,
            ca_bundle_path=ca_bundle_path,
        )
        try:
            templates = async_to_sync(adapter.list_templates)(
                resource_type=resource_type,
                search=search,
            )
            return Response({'data': templates})
        except _ServiceUnavailableError:
            return Response(
                {'data': [], 'fallback': True, 'error': 'API AAP indisponible'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @extend_schema(
        tags=['integrations'],
        summary="Tester la connexion d'une intégration (health check synchrone)",
        responses={
            200: inline_serializer(name='TestConnectionResponse', fields={
                'data': inline_serializer(name='TestConnectionData', fields={
                    'status': drf_serializers.ChoiceField(choices=['ok', 'error', 'unknown']),
                    'message': drf_serializers.CharField(allow_null=True),
                    'checked_at': drf_serializers.DateTimeField(),
                }),
            }),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Insufficient permissions (DBOPS/DBA profile required)'),
            404: OpenApiResponse(description='Integration not found'),
        },
    )
    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        """POST /admin/integrations/{id}/test-connection/ — Health check synchrone."""
        from integrations.tasks import (
            _resolve_and_check_adapter,
            _resolve_and_check_service,
            _resolve_and_check_vault,
            _sanitize_health_error_message,
            _ADAPTER_TYPE_ALIASES,
            _ADAPTER_TYPES,
            _SERVICE_TYPES,
            _VAULT_TYPE,
        )
        from integrations.health_check import HealthCheckStatus, HealthCheckResult
        from integrations.models import Integration
        from django.utils import timezone

        try:
            integration_id = int(pk)
        except (ValueError, TypeError):
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {pk} introuvable",
                details={"integration_id": pk},
            )

        service = IntegrationService()
        integration = service.get_by_id(integration_id)

        if integration is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id},
            )

        # Dispatch synchrone (même logique que run_integration_health_check)
        itype = integration.type
        normalized_type = _ADAPTER_TYPE_ALIASES.get(itype, itype)
        try:
            if normalized_type in _ADAPTER_TYPES:
                result = _resolve_and_check_adapter(integration)
            elif itype == _VAULT_TYPE:
                result = _resolve_and_check_vault(integration)
            elif itype in _SERVICE_TYPES:
                result = _resolve_and_check_service(integration)
            else:
                result = HealthCheckResult(status=HealthCheckStatus.UNKNOWN, checked_at=timezone.now(), error_message=None)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "test_connection_dispatch_error",
                integration_id=integration_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            result = HealthCheckResult(status=HealthCheckStatus.ERROR, checked_at=timezone.now(), error_message=str(exc))

        # Mise à jour BD (évite signal récursif)
        sanitized_error = _sanitize_health_error_message(result.error_message)
        Integration.objects.filter(id=integration_id).update(
            health_status=result.status.value,
            health_checked_at=result.checked_at,
            health_error_message=sanitized_error,
        )

        # Audit
        AuditService.create_entry(
            user_id=str(request.user.id) if request.user and hasattr(request.user, 'id') else 'system',
            action_type=AuditActionType.INTEGRATION_HEALTH_CHECK_TESTED,
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration_id,
            details={
                'status': result.status.value,
                'checked_at': result.checked_at.isoformat(),
                'error_message': sanitized_error,
            },
            correlation_id=get_correlation_id(),
        )

        return Response({"data": {
            "status": result.status.value,
            "message": sanitized_error,
            "checked_at": result.checked_at.isoformat(),
        }})

    @extend_schema(
        tags=['integrations'],
        summary="Validate all integrations against the type catalogue",
        responses={
            200: inline_serializer(
                name='IntegrationValidateAllResponse',
                fields={
                    'valid': drf_serializers.IntegerField(),
                    'invalid': drf_serializers.IntegerField(),
                    'deprecated': drf_serializers.IntegerField(),
                    'updated': drf_serializers.IntegerField(),
                },
            ),
        },
    )
    @action(detail=False, methods=['post'], url_path='validate-all')
    def validate_all(self, request):
        """POST /admin/integrations/validate-all — Batch validate all integrations."""
        triggered_by = str(request.user.id) if request.user and hasattr(request.user, 'id') else 'system'
        correlation_id = get_correlation_id()
        stats = IntegrationValidationService.validate_all_integrations(
            triggered_by=triggered_by,
            correlation_id=correlation_id,
        )
        return Response({"data": stats})
