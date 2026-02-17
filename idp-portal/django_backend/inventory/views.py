"""
Views for inventory API.
Story 13.1 - Target API endpoints with RBAC filtering.
Story 23.3 - Multi-table inventory API: /servers, /instances, /databases.
No local DB - reads from external sources.
"""

from __future__ import annotations

from typing import Any

import structlog

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from inventory.serializers import (
    TargetSerializer, TargetFilterParamsSerializer,
    ServerSerializer, InstanceSerializer, DatabaseSerializer,
    ServerFilterParamsSerializer, InstanceFilterParamsSerializer,
    DatabaseFilterParamsSerializer,
    ServerListResponseSerializer, InstanceListResponseSerializer,
    DatabaseListResponseSerializer,
)
from core.environment import EnvironmentHelper
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

    def has_permission(self, request: Any, view: Any) -> bool:
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
def list_targets(request: Request) -> Response:
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
        # Get targets with RBAC filtering (Story 22.6: returns total not total_count)
        targets, total, rbac_truncated = inventory_service.list_targets_for_user(
            user_id=user.id,  # type: ignore[arg-type]
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
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 0,
        'rbac_truncated': rbac_truncated,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminOrIntegration])
def list_all_targets(request: Request) -> Response:
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

    # Story 13.7: Validate environment against inventory instead of hardcoded list
    if environment:
        try:
            valid_environments = inventory_service.list_environments()
            if not EnvironmentHelper.is_in(environment, valid_environments):
                return Response(
                    {'detail': f'Invalid environment. Must be one of: {sorted(valid_environments)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except InventoryServiceError:
            # If inventory service fails, allow but log warning
            logger.warning(
                "inventory_validation_failed_list_all",
                environment=environment,
                correlation_id=correlation_id
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
        # Get targets without RBAC (Story 22.6: returns total not total_count)
        targets, total = inventory_service.list_targets(
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
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 0
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_environments(request: Request) -> Response:
    """
    List distinct environments from inventory.
    Story 13.7 - AC2: Source of truth for environments is inventory.
    Returns normalized environment values (dev, staging, prod).

    This endpoint replaces hardcoded environment lists.
    """
    correlation_id = get_correlation_id()
    inventory_service = InventoryService()

    logger.info(
        "listing_environments",
        user_id=request.user.id,
        correlation_id=correlation_id
    )

    try:
        environments = inventory_service.list_environments()
    except InventoryServiceError as e:
        logger.error(
            "inventory_service_error",
            error=str(e),
            user_id=request.user.id,
            correlation_id=correlation_id
        )
        return Response(
            {'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return Response(environments)


# --- Story 23.3: Multi-table inventory API ---


def _validate_server_access(
    user: object,
    environment: str,
    server_name: str | None = None,
    server_names: list[str] | None = None,
) -> list[str]:
    """
    Validate that user has RBAC access to specified server(s).
    Story 23.3 AC5 - RBAC validation for instances/databases endpoints.

    Args:
        user: Authenticated user object
        environment: Target environment (required)
        server_name: Single server name to validate (mutually exclusive with server_names)
        server_names: Multiple server names to validate (mutually exclusive with server_name)

    Returns:
        List of allowed server names for the user in this environment.

    Raises:
        PermissionDenied: If any specified server is not in user's allowed servers.
    """
    correlation_id = get_correlation_id()
    inventory_service = InventoryService()

    ad_groups = get_user_ad_groups(user)
    try:
        allowed_targets, _, _ = inventory_service.list_targets_for_user(
            user_id=user.id,  # type: ignore[attr-defined]
            ad_groups=ad_groups,
            environment=environment,
            page=1,
            page_size=10000,
        )
        # Safely extract server names, handling missing 'name' key
        allowed_server_names = {t.get('name') for t in allowed_targets if t.get('name')}
    except (KeyError, TypeError, InventoryServiceError) as e:
        logger.error(
            "rbac_validation_failed",
            user_id=user.id,  # type: ignore[attr-defined]
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise PermissionDenied("Failed to validate server access")

    if server_name:
        if server_name not in allowed_server_names:
            logger.warning(
                "rbac_server_access_denied",
                user_id=user.id,  # type: ignore[attr-defined]
                environment=environment,
                requested_server=server_name,
                correlation_id=correlation_id,
            )
            raise PermissionDenied(f"Access denied to server: {server_name}")

    if server_names:
        unauthorized = [s for s in server_names if s not in allowed_server_names]
        if unauthorized:
            logger.warning(
                "rbac_servers_access_denied",
                user_id=user.id,  # type: ignore[attr-defined]
                environment=environment,
                unauthorized_servers=unauthorized,
                correlation_id=correlation_id,
            )
            raise PermissionDenied(f"Access denied to server: {unauthorized[0]}")

    return list(s for s in allowed_server_names if s is not None)


@extend_schema(
    summary="List servers from inventory",
    description="Returns servers filtered by environment. Applies RBAC filtering.",
    parameters=[
        OpenApiParameter('environment', str, required=True, description="Target environment (required)"),
        OpenApiParameter('engine_type', str, required=False, description="Filter by engine type"),
    ],
    responses={
        200: ServerListResponseSerializer,
        400: {"description": "Invalid query parameters (environment missing)"},
        500: {"description": "Internal server error"},
    },
    examples=[
        OpenApiExample(
            'Success response',
            value={"data": [{"id": "srv01", "name": "srv01", "environment": "dev", "engine_type": "oracle"}]},
            response_only=True,
        )
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_servers(request: Request) -> Response:
    """List servers with RBAC filtering. Story 23.3 AC1."""
    correlation_id = get_correlation_id()
    user = request.user

    params_serializer = ServerFilterParamsSerializer(data=request.query_params)
    if not params_serializer.is_valid():
        return Response(
            {'detail': str(params_serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    params = params_serializer.validated_data
    environment = params['environment']
    engine_type = params.get('engine_type')

    inventory_service = InventoryService()
    try:
        # RBAC: get allowed servers for this user
        ad_groups = get_user_ad_groups(user)
        allowed_targets, _, _ = inventory_service.list_targets_for_user(
            user_id=user.id,  # type: ignore[arg-type]
            ad_groups=ad_groups,
            environment=environment,
            page=1,
            page_size=10000,  # Increased from 5000 to handle large deployments
        )
        allowed_server_names = {t.get('name') for t in allowed_targets if t.get('name')}

        servers = inventory_service.list_servers(
            environment=environment,
            engine_type=engine_type,
        )

        # Filter by RBAC allowed servers
        servers = [s for s in servers if s.get('name') in allowed_server_names]

    except InventoryServiceError as e:
        logger.error(
            "inventory_api_list_servers_failed",
            user_id=user.id,
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        return Response(
            {'detail': 'Failed to retrieve servers'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = ServerSerializer(servers, many=True)

    logger.info(
        "inventory_api_list_servers",
        user_id=user.id,
        environment=environment,
        engine_type=engine_type,
        nb_results=len(servers),
        correlation_id=correlation_id,
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


@extend_schema(
    summary="List database instances from inventory",
    description="Returns instances filtered by environment and optionally by server. Applies RBAC filtering.",
    parameters=[
        OpenApiParameter('environment', str, required=True, description="Target environment (required)"),
        OpenApiParameter('server_name', str, required=False, description="Filter by single server name"),
        OpenApiParameter('server_names', str, required=False, description="Filter by multiple server names (multi-value)", many=True),
    ],
    responses={
        200: InstanceListResponseSerializer,
        400: {"description": "Invalid query parameters"},
        403: {"description": "Access denied to specified server"},
        500: {"description": "Internal server error"},
    },
    examples=[
        OpenApiExample(
            'Success response',
            value={"data": [{"id": "INST01", "name": "INST01", "environment": "dev", "server_ref": "srv01", "db_ref": "DB01"}]},
            response_only=True,
        )
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_instances(request: Request) -> Response:
    """List instances with optional server filter. Story 23.3 AC2."""
    correlation_id = get_correlation_id()
    user = request.user

    params_serializer = InstanceFilterParamsSerializer(data=request.query_params)
    if not params_serializer.is_valid():
        return Response(
            {'detail': str(params_serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    params = params_serializer.validated_data
    environment = params['environment']
    server_name = params.get('server_name')
    server_names = params.get('server_names')

    # RBAC validation for server filter (logging handled in helper)
    if server_name or server_names:
        try:
            _validate_server_access(user, environment, server_name, server_names)
        except PermissionDenied:
            raise

    inventory_service = InventoryService()
    try:
        instances = inventory_service.list_instances(
            environment=environment,
            server_name=server_name,
            server_names=server_names,
        )
    except InventoryServiceError as e:
        logger.error(
            "inventory_api_list_instances_failed",
            user_id=user.id,
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        return Response(
            {'detail': 'Failed to retrieve instances'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = InstanceSerializer(instances, many=True)

    logger.info(
        "inventory_api_list_instances",
        user_id=user.id,
        environment=environment,
        server_filter={'server_name': server_name, 'server_names': server_names},
        nb_results=len(instances),
        correlation_id=correlation_id,
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


@extend_schema(
    summary="List databases from inventory",
    description="Returns databases filtered by environment and optionally by server. Applies RBAC filtering.",
    parameters=[
        OpenApiParameter('environment', str, required=True, description="Target environment (required)"),
        OpenApiParameter('server_name', str, required=False, description="Filter by single server name"),
        OpenApiParameter('server_names', str, required=False, description="Filter by multiple server names (multi-value)", many=True),
    ],
    responses={
        200: DatabaseListResponseSerializer,
        400: {"description": "Invalid query parameters"},
        403: {"description": "Access denied to specified server"},
        500: {"description": "Internal server error"},
    },
    examples=[
        OpenApiExample(
            'Success response',
            value={"data": [{"id": "DB01", "name": "DB01", "environment": "dev"}]},
            response_only=True,
        )
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_databases(request: Request) -> Response:
    """List databases with optional server filter. Story 23.3 AC3."""
    correlation_id = get_correlation_id()
    user = request.user

    params_serializer = DatabaseFilterParamsSerializer(data=request.query_params)
    if not params_serializer.is_valid():
        return Response(
            {'detail': str(params_serializer.errors)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    params = params_serializer.validated_data
    environment = params['environment']
    server_name = params.get('server_name')
    server_names = params.get('server_names')

    # RBAC validation for server filter (logging handled in helper)
    if server_name or server_names:
        try:
            _validate_server_access(user, environment, server_name, server_names)
        except PermissionDenied:
            raise

    inventory_service = InventoryService()
    try:
        databases = inventory_service.list_databases(
            environment=environment,
            server_name=server_name,
            server_names=server_names,
        )
    except InventoryServiceError as e:
        logger.error(
            "inventory_api_list_databases_failed",
            user_id=user.id,
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        return Response(
            {'detail': 'Failed to retrieve databases'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = DatabaseSerializer(databases, many=True)

    logger.info(
        "inventory_api_list_databases",
        user_id=user.id,
        environment=environment,
        server_filter={'server_name': server_name, 'server_names': server_names},
        nb_results=len(databases),
        correlation_id=correlation_id,
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)
