"""
Views for integrations CRUD endpoints.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from integrations.serializers import (
    IntegrationSerializer, IntegrationCreateSerializer,
    IntegrationUpdateSerializer, IntegrationListSerializer
)
from integrations.services import IntegrationService
from core.permissions import DBOPSProfilePermission
from core.exceptions import NotFoundError, InvalidStateError


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
        return Response(
            {'data': response_serializer.data},
            status=status.HTTP_201_CREATED
        )
    
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
        return Response({'data': response_serializer.data})
    
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
