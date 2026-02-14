"""
Views for integrations CRUD endpoints.
"""

from typing import Any

from rest_framework import viewsets, status, serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse
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


class IntegrationViewSet(viewsets.ViewSet):
    """
    ViewSet for integrations CRUD operations.
    """
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
    
    def list(self, request):
        """
        GET /admin/integrations - List all integrations.
        """
        service = IntegrationService()
        integrations = service.list_all()
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
        DELETE /admin/integrations/{id} - Delete integration.
        Returns 204 No Content.
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
        
        try:
            deleted = service.delete_integration(integration_id, user=request.user)
        except ValueError as e:
            error_msg = str(e)
            if "actions liées" in error_msg:
                raise InvalidStateError(
                    code="DEPENDENCY_ERROR",
                    message=error_msg,
                    details={"integration_id": integration_id}
                )
            raise InvalidStateError(
                code="VALIDATION_ERROR",
                message=error_msg,
                details={}
            )
        
        if not deleted:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Integration {integration_id} introuvable",
                details={"integration_id": integration_id}
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
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

        return Response({
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
        })

    @extend_schema(
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
        return Response(stats)
