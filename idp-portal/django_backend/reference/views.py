"""
Views for reference API.
Story 13.7 - Reference endpoints for engines and platforms.
Story 2.30 - Category endpoints (list + CRUD admin).
"""

import structlog
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, OpenApiParameter
from reference.models import RefEngine, RefCategory
from reference.serializers import (
    RefEngineSerializer, RefEngineWriteSerializer,
    PlatformTypeCatalogueSerializer,
    RefCategorySerializer, RefCategoryWriteSerializer,
)
from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from core.exceptions import NotFoundError
from core.middleware import get_correlation_id
from core.permissions import AdminProfilePermission

logger = structlog.get_logger(__name__)


@extend_schema(
    tags=['reference'],
    summary='Lister les moteurs',
    parameters=[
        OpenApiParameter('active_only', bool, description='Si true (défaut), uniquement les moteurs actifs'),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_engines(request: Request) -> Response:
    """
    List all active engines from REF_ENGINES table.
    Returns engines ordered by display_order, code.
    
    Query params:
        active_only: If true (default), return only active engines (is_active=1)
    """
    correlation_id = get_correlation_id()
    
    # Parse query params
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'
    
    logger.info(
        "listing_engines",
        active_only=active_only,
        correlation_id=correlation_id
    )
    
    # Query engines
    queryset = RefEngine.objects.all()
    if active_only:
        queryset = queryset.active()
    queryset = queryset.ordered()
    
    # Serialize
    serializer = RefEngineSerializer(queryset, many=True)
    
    return Response({"data": serializer.data})


@extend_schema(
    tags=['reference'],
    summary='Lister les plateformes',
    parameters=[
        OpenApiParameter('active_only', bool, description='Si true (défaut), uniquement les plateformes actives'),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_platforms(request: Request) -> Response:
    """
    Story 31.9: List platform types from IntegrationTypeCatalogue (role=platform).
    Replaces the former REF_PLATFORMS source. URL unchanged for backward compatibility.

    Query params:
        active_only: If true (default), return only active platform types
    """
    correlation_id = get_correlation_id()

    active_only = request.query_params.get('active_only', 'true').lower() == 'true'

    logger.info(
        "listing_platforms",
        active_only=active_only,
        correlation_id=correlation_id
    )

    queryset = IntegrationTypeCatalogue.objects.filter(
        integration_role=IntegrationRole.PLATFORM
    )
    if active_only:
        queryset = queryset.filter(is_active=True)
    queryset = queryset.order_by('code')

    serializer = PlatformTypeCatalogueSerializer(queryset, many=True)

    return Response({"data": serializer.data})


# ─── Story 31.3: Engine admin endpoint ─────────────────────────────────────


@extend_schema(
    tags=['reference'],
    summary='Modifier un moteur',
    request=RefEngineWriteSerializer,
    responses={200: RefEngineSerializer},
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, AdminProfilePermission])
def update_engine(request: Request, pk: int) -> Response:
    """
    PATCH /api/v1/admin/engines/{pk}/
    Update engine fields (icon_url, label, display_order, is_active).
    admin only. Story 31.3, AC6.
    """
    correlation_id = get_correlation_id()
    logger.info("updating_engine", engine_id=pk, correlation_id=correlation_id)

    try:
        engine = RefEngine.objects.get(pk=pk)
    except RefEngine.DoesNotExist:
        raise NotFoundError(message="Moteur introuvable.")

    serializer = RefEngineWriteSerializer(engine, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    logger.info("engine_updated", engine_id=pk, correlation_id=correlation_id)
    # REF-MED-01: Aligner sur le pattern {"data": ...} utilisé par update_category et create_category.
    return Response({"data": RefEngineSerializer(engine).data})


# ─── Story 2.30: Category endpoints ────────────────────────────────────────


@extend_schema(
    tags=['reference'],
    summary='Lister les catégories',
    parameters=[
        OpenApiParameter('active_only', bool, description='Si true (défaut), uniquement les catégories actives'),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_categories(request: Request) -> Response:
    """
    List categories from REF_CATEGORIES table.
    Returns categories ordered by display_order, code.

    Query params:
        active_only: If true (default), return only active categories (is_active=1)
    """
    correlation_id = get_correlation_id()
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'

    logger.info("listing_categories", active_only=active_only, correlation_id=correlation_id)

    queryset = RefCategory.objects.all()
    if active_only:
        queryset = queryset.active()  # type: ignore[assignment]
    queryset = queryset.ordered()  # type: ignore[assignment]

    serializer = RefCategorySerializer(queryset, many=True)
    return Response({"data": serializer.data})


@extend_schema(
    tags=['reference'],
    summary='Créer une catégorie',
    request=RefCategoryWriteSerializer,
    responses={201: RefCategorySerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, AdminProfilePermission])
def create_category(request: Request) -> Response:
    """Create a new category (admin only). Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("creating_category", correlation_id=correlation_id)

    serializer = RefCategoryWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    category = serializer.save()

    logger.info("category_created", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response({"data": RefCategorySerializer(category).data}, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['reference'],
    summary='Modifier une catégorie',
    request=RefCategoryWriteSerializer,
    responses={200: RefCategorySerializer},
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, AdminProfilePermission])
def update_category(request: Request, pk: int) -> Response:
    """Update an existing category (admin only). Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("updating_category", category_id=pk, correlation_id=correlation_id)

    try:
        category = RefCategory.objects.get(pk=pk)
    except RefCategory.DoesNotExist:
        raise NotFoundError(message=f"Catégorie {pk} introuvable.")

    serializer = RefCategoryWriteSerializer(category, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    category = serializer.save()

    logger.info("category_updated", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response({"data": RefCategorySerializer(category).data})


@extend_schema(
    tags=['reference'],
    summary='Supprimer une catégorie (soft-delete)',
    responses={204: None},
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, AdminProfilePermission])
def delete_category(request: Request, pk: int) -> Response:
    """Soft-delete a category (set is_active=0). admin only. Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("deleting_category", category_id=pk, correlation_id=correlation_id)

    try:
        category = RefCategory.objects.get(pk=pk)
    except RefCategory.DoesNotExist:
        raise NotFoundError(message=f"Catégorie {pk} introuvable.")

    category.is_active = 0
    category.save(update_fields=['is_active'])

    logger.info("category_deactivated", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response(status=status.HTTP_204_NO_CONTENT)
