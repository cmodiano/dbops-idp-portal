"""
Views for inventory API.
Story 13.1 - Target API endpoints with RBAC filtering.
No local DB - reads from external sources.
"""

import structlog

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission

from inventory.models import TargetEnvironment, TargetType
from inventory.serializers import TargetSerializer, TargetFilterParamsSerializer
from inventory.services import InventoryService, InventoryServiceError
from profiles.models import Profile
from core.auth_utils import get_user_ad_groups
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class IsAdminOrIntegration(BasePermission):
    """
    Permission check for admin users or integration service accounts.
    Checks if user has admin profile or is_staff flag.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Check Django staff flag (for service accounts)
        if getattr(user, 'is_staff', False):
            return True

        # Check if user has admin profile via AD groups
        ad_groups = get_user_ad_groups(user)
        if not ad_groups:
            return False

        profiles = Profile.objects.find_by_ad_groups(ad_groups)
        return profiles.filter(is_admin=1).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_targets(request):
    """
    List targets with optional filters.
    Applies RBAC filtering based on user's profiles.

    AC4: Returns targets filtered by user permissions (RBAC).
    AC5: Exposes environment per target.

    Query params:
        environment: Filter by environment (dev, staging, prod)
        search: Search by name
        target_type: Filter by target type (server, database, etc.)
        page: Page number (default: 1)
        page_size: Items per page (default: 25, max: 100)
    """
    correlation_id = get_correlation_id()
    inventory_service = InventoryService()

    # Parse and validate query params
    params_serializer = TargetFilterParamsSerializer(data=request.query_params)
    if not params_serializer.is_valid():
        return Response(
            {'detail': params_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    params = params_serializer.validated_data
    environment = params.get('environment')
    search = params.get('search')
    target_type = params.get('target_type')
    page = params.get('page', 1)
    page_size = params.get('page_size', 25)

    # Get user info from JWT (ad_groups with profile fallback)
    user = request.user
    ad_groups = get_user_ad_groups(user)

    if not ad_groups:
        logger.warning(
            "user_has_no_ad_groups",
            user_id=user.id,
            correlation_id=correlation_id,
            message="User has no AD groups - RBAC filtering will return empty results"
        )

    logger.info(
        "listing_targets",
        user_id=user.id,
        environment=environment,
        search=search,
        target_type=target_type,
        page=page,
        page_size=page_size,
        ad_groups_count=len(ad_groups),
        correlation_id=correlation_id
    )

    try:
        # Get targets with RBAC filtering
        targets, total_count, rbac_truncated = inventory_service.list_targets_for_user(
            user_id=user.id,
            ad_groups=ad_groups,
            environment=environment,
            search=search,
            target_type=target_type,
            page=page,
            page_size=page_size
        )
    except InventoryServiceError as e:
        logger.error(
            "inventory_service_error",
            error=str(e),
            user_id=user.id,
            correlation_id=correlation_id
        )
        return Response(
            {'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Serialize response
    serializer = TargetSerializer(targets, many=True)

    return Response({
        'items': serializer.data,
        'total': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0,
        'rbac_truncated': rbac_truncated,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrIntegration])
def list_all_targets(request):
    """
    List all targets without RBAC filtering.
    Requires admin profile or is_staff flag (for service accounts).

    Query params:
        environment: Filter by environment (dev, staging, prod)
        search: Search by name
        target_type: Filter by target type (server, database, etc.)
        page: Page number (default: 1)
        page_size: Items per page (default: 25, max: 100)
    """
    correlation_id = get_correlation_id()
    inventory_service = InventoryService()

    # Parse and validate query params
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(max(1, int(request.query_params.get('page_size', 25))), 100)
    except (ValueError, TypeError):
        return Response(
            {'detail': 'Invalid page or page_size parameter'},
            status=status.HTTP_400_BAD_REQUEST
        )

    environment = request.query_params.get('environment')
    search = request.query_params.get('search')
    target_type = request.query_params.get('target_type')

    # Validate environment if provided
    if environment and environment not in TargetEnvironment.VALUES:
        return Response(
            {'detail': f'Invalid environment. Must be one of: {TargetEnvironment.VALUES}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    logger.info(
        "listing_all_targets",
        user_id=request.user.id,
        environment=environment,
        search=search,
        target_type=target_type,
        page=page,
        page_size=page_size,
        correlation_id=correlation_id
    )

    try:
        # Get targets without RBAC
        targets, total_count = inventory_service.list_targets(
            environment=environment,
            search=search,
            target_type=target_type,
            page=page,
            page_size=page_size
        )
    except InventoryServiceError as e:
        logger.error(
            "inventory_service_error",
            error=str(e),
            correlation_id=correlation_id
        )
        return Response(
            {'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Serialize response
    serializer = TargetSerializer(targets, many=True)

    return Response({
        'items': serializer.data,
        'total': total_count,
        'page': page,
        'page_size': page_size,
        'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
    })
