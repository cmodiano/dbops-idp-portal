"""
Story 24.1: Views for Integration Type Catalogue API endpoints.
Read-only endpoints for discovering available integration types and actions.
"""

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers as drf_serializers

from integrations.catalogue_service import IntegrationCatalogueService
from integrations.serializers import (
    IntegrationTypeWithActionsSerializer,
    IntegrationActionSerializer,
)


# Fix Issue #7: Define error response serializer for 404
class ErrorResponseSerializer(drf_serializers.Serializer):
    """Serializer for error responses."""
    error = drf_serializers.CharField()


@extend_schema_view(
    list=extend_schema(
        tags=['integration-catalogue'],
        summary='Lister les types d\'intégration',
        description='Retourne tous les types d\'intégration actifs avec leurs actions supportées.',
        responses={200: IntegrationTypeWithActionsSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['integration-catalogue'],
        summary='Détail d\'un type d\'intégration',
        description='Retourne un type d\'intégration spécifique avec ses actions.',
        responses={
            200: IntegrationTypeWithActionsSerializer,
            404: ErrorResponseSerializer,  # Fix Issue #7
        },
    ),
)
class IntegrationTypeCatalogueViewSet(viewsets.ViewSet):
    """
    Read-only ViewSet for the integration type catalogue.
    Authenticated users can browse available types and their actions.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """GET /api/v1/integrations/types — List all active types with actions.

        Query Parameters:
            role (optional): Filter by integration_role. Accepts 'platform' or 'service'.
                Returns 400 if an invalid value is provided.
        """
        role = request.query_params.get('role')
        if role is not None and role not in ('platform', 'service'):
            return Response(
                {'error': f"Valeur de filtre 'role' invalide : '{role}'. Valeurs acceptées : 'platform', 'service'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        types = IntegrationCatalogueService.list_all_types(role=role)
        serializer = IntegrationTypeWithActionsSerializer(types, many=True)
        return Response({'data': serializer.data})

    def retrieve(self, request, pk=None):
        """GET /api/v1/integrations/types/{code} — Get type by code."""
        integration_type = IntegrationCatalogueService.get_type_by_code(pk)
        if integration_type is None:
            return Response(
                {'error': f"Type d'intégration '{pk}' introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = IntegrationTypeWithActionsSerializer(integration_type)
        return Response({'data': serializer.data})

    @extend_schema(
        tags=['integration-catalogue'],
        summary='Lister les actions d\'un type d\'intégration',
        description='Retourne les actions supportées par un type d\'intégration.',
        responses={
            200: IntegrationActionSerializer(many=True),
            404: ErrorResponseSerializer,  # Fix Issue #7
        },
    )
    @action(detail=True, methods=['get'], url_path='actions', url_name='actions')
    def actions_list(self, request, pk=None):
        """GET /api/v1/integrations/types/{code}/actions — List actions for a type."""
        integration_type = IntegrationCatalogueService.get_type_by_code(pk)
        if integration_type is None:
            return Response(
                {'error': f"Type d'intégration '{pk}' introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )
        actions = IntegrationCatalogueService.list_actions_by_type(pk)
        serializer = IntegrationActionSerializer(actions, many=True)
        return Response({'data': serializer.data})
