"""
Views for reference API.
Story 13.7 - Reference endpoints for engines and platforms.
Story 2.30 - Category endpoints (list + CRUD admin).
"""

import structlog
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from reference.models import RefEngine, RefPlatform, RefCategory
from reference.serializers import (
    RefEngineSerializer, RefPlatformSerializer,
    RefCategorySerializer, RefCategoryWriteSerializer,
)
from core.middleware import get_correlation_id
from core.permissions import DBOPSProfilePermission

logger = structlog.get_logger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_engines(request):
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
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_platforms(request):
    """
    List all active platforms from REF_PLATFORMS table.
    Returns platforms ordered by display_order, code.
    
    Query params:
        active_only: If true (default), return only active platforms (is_active=1)
    """
    correlation_id = get_correlation_id()
    
    # Parse query params
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'
    
    logger.info(
        "listing_platforms",
        active_only=active_only,
        correlation_id=correlation_id
    )
    
    # Query platforms
    queryset = RefPlatform.objects.all()
    if active_only:
        queryset = queryset.active()
    queryset = queryset.ordered()
    
    # Serialize
    serializer = RefPlatformSerializer(queryset, many=True)

    return Response(serializer.data)


# ─── Story 2.30: Category endpoints ────────────────────────────────────────


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_categories(request):
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
        queryset = queryset.active()
    queryset = queryset.ordered()

    serializer = RefCategorySerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, DBOPSProfilePermission])
def create_category(request):
    """Create a new category (DBOPS only). Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("creating_category", correlation_id=correlation_id)

    serializer = RefCategoryWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    category = serializer.save()

    logger.info("category_created", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response(RefCategorySerializer(category).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, DBOPSProfilePermission])
def update_category(request, pk):
    """Update an existing category (DBOPS only). Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("updating_category", category_id=pk, correlation_id=correlation_id)

    try:
        category = RefCategory.objects.get(pk=pk)
    except RefCategory.DoesNotExist:
        return Response(
            {"detail": f"Catégorie {pk} introuvable."},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = RefCategoryWriteSerializer(category, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    category = serializer.save()

    logger.info("category_updated", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response(RefCategorySerializer(category).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, DBOPSProfilePermission])
def delete_category(request, pk):
    """Soft-delete a category (set is_active=0). DBOPS only. Story 2.30, AC5."""
    correlation_id = get_correlation_id()
    logger.info("deleting_category", category_id=pk, correlation_id=correlation_id)

    try:
        category = RefCategory.objects.get(pk=pk)
    except RefCategory.DoesNotExist:
        return Response(
            {"detail": f"Catégorie {pk} introuvable."},
            status=status.HTTP_404_NOT_FOUND
        )

    category.is_active = 0
    category.save(update_fields=['is_active'])

    logger.info("category_deactivated", category_id=category.id, code=category.code, correlation_id=correlation_id)
    return Response(status=status.HTTP_204_NO_CONTENT)
