"""
Views for reference API.
Story 13.7 - Reference endpoints for engines and platforms.
"""

import structlog
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from reference.models import RefEngine, RefPlatform
from reference.serializers import RefEngineSerializer, RefPlatformSerializer
from core.middleware import get_correlation_id

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
