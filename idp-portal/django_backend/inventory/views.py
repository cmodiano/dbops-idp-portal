"""
Views for inventory API.
Story 13.1 - Target API endpoints with RBAC filtering.
Story 23.3 - Multi-table inventory API: /servers, /instances, /databases.
No local DB - reads from external sources.

⚠️  INTERNAL USE ONLY — Ces endpoints sont réservés au frontend (TargetSelector,
ExecutionWizard). Ils ne sont pas exposés dans la documentation API publique.
Cf. Story 44.3 — @extend_schema(exclude=True) sur toutes les vues.
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

# Story 33.4 (DIP): module-level factory, overridable in tests via:
#   import inventory.views as v; v._inventory_service_factory = lambda: MockInventoryService()
_inventory_service_factory = InventoryService

# Story 62.3: inventory entity types and default columns for schema endpoint
INVENTORY_ENTITY_TYPES = ('servers', 'instances', 'databases')
DEFAULT_COLUMNS = ['id', 'name']


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


@extend_schema(exclude=True)
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
    inventory_service = _inventory_service_factory()

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


@extend_schema(exclude=True)
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
    inventory_service = _inventory_service_factory()

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


@extend_schema(exclude=True)
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
    inventory_service = _inventory_service_factory()

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


def _get_rbac_allowed_servers(
    inventory_service: InventoryService,
    user: object,
    environment: str,
) -> set[str]:
    """
    Get the set of server names the user is allowed to access (RBAC).

    Single RBAC query shared by list_servers, list_instances, list_databases
    to avoid duplicate inventory queries and ensure consistent RBAC enforcement.

    Args:
        inventory_service: Shared InventoryService instance (avoids creating multiples per request)
        user: Authenticated user object
        environment: Target environment (required)

    Returns:
        Set of allowed server names for the user in this environment.

    Raises:
        PermissionDenied: If RBAC query fails.
    """
    correlation_id = get_correlation_id()

    ad_groups = get_user_ad_groups(user)
    try:
        allowed_targets, _, _ = inventory_service.list_targets_for_user(
            user_id=user.id,  # type: ignore[attr-defined]
            ad_groups=ad_groups,
            environment=environment,
            page=1,
            page_size=10000,
        )
        return {name for t in allowed_targets if (name := t.get('name'))}
    except InventoryServiceError:
        raise  # Let the view-level handler return 503/500
    except (KeyError, TypeError) as e:
        logger.error(
            "rbac_validation_failed",
            user_id=user.id,  # type: ignore[attr-defined]
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise PermissionDenied("Failed to validate server access")


def _validate_explicit_server_filter(
    allowed_server_names: set[str],
    user: object,
    environment: str,
    server_name: str | None = None,
    server_names: list[str] | None = None,
) -> None:
    """
    Validate that explicitly requested servers are within the user's allowed set.

    Args:
        allowed_server_names: Set from _get_rbac_allowed_servers
        user: Authenticated user object
        environment: Target environment
        server_name: Single server name to validate
        server_names: Multiple server names to validate

    Raises:
        PermissionDenied: If any specified server is not in user's allowed servers.
    """
    correlation_id = get_correlation_id()

    if server_name and server_name not in allowed_server_names:
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
    exclude=True,  # Story 44.3: Usage interne uniquement — non exposé dans la doc publique
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

    inventory_service = _inventory_service_factory()
    try:
        # RBAC: single query to get allowed servers
        allowed_server_names = _get_rbac_allowed_servers(inventory_service, user, environment)

        # Fetch servers from inventory (single query, no duplicate)
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
        OpenApiParameter('engine_type', str, required=False, description="Filter by engine type"),
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
    exclude=True,  # Story 44.3: Usage interne uniquement — non exposé dans la doc publique
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
    engine_type = params.get('engine_type')
    server_name = params.get('server_name')
    server_names = params.get('server_names')

    inventory_service = _inventory_service_factory()
    try:
        # RBAC: always get allowed servers (single query)
        allowed_server_names = _get_rbac_allowed_servers(inventory_service, user, environment)

        # Validate explicit server filter if provided
        if server_name or server_names:
            _validate_explicit_server_filter(
                allowed_server_names, user, environment, server_name, server_names
            )

        # When no explicit server filter, restrict to user's allowed servers
        # This ensures instances are only returned for servers the user can access
        effective_server_names = server_names
        effective_server_name = server_name
        if not server_name and not server_names:
            effective_server_names = sorted(allowed_server_names) if allowed_server_names else None

        if effective_server_names is not None and not effective_server_names:
            # User has no allowed servers → empty result
            instances: list[dict] = []
        else:
            instances = inventory_service.list_instances(
                environment=environment,
                engine_type=engine_type,
                server_name=effective_server_name,
                server_names=effective_server_names,
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
        engine_type=engine_type,
        server_filter={'server_name': server_name, 'server_names': server_names},
        nb_results=len(instances),
        rbac_server_count=len(allowed_server_names),
        correlation_id=correlation_id,
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


@extend_schema(
    summary="List databases from inventory",
    description="Returns databases filtered by environment and optionally by server. Applies RBAC filtering.",
    parameters=[
        OpenApiParameter('environment', str, required=True, description="Target environment (required)"),
        OpenApiParameter('engine_type', str, required=False, description="Filter by engine type"),
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
    exclude=True,  # Story 44.3: Usage interne uniquement — non exposé dans la doc publique
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
    engine_type = params.get('engine_type')
    server_name = params.get('server_name')
    server_names = params.get('server_names')

    inventory_service = _inventory_service_factory()
    try:
        # RBAC: always get allowed servers (single query)
        allowed_server_names = _get_rbac_allowed_servers(inventory_service, user, environment)

        # Validate explicit server filter if provided
        if server_name or server_names:
            _validate_explicit_server_filter(
                allowed_server_names, user, environment, server_name, server_names
            )

        # When no explicit server filter, restrict to user's allowed servers
        # Databases are found via instances → servers, so filtering by allowed servers
        # ensures only databases linked to authorized servers are returned
        effective_server_names = server_names
        effective_server_name = server_name
        if not server_name and not server_names:
            effective_server_names = sorted(allowed_server_names) if allowed_server_names else None

        if effective_server_names is not None and not effective_server_names:
            # User has no allowed servers → empty result
            databases: list[dict] = []
        else:
            databases = inventory_service.list_databases(
                environment=environment,
                engine_type=engine_type,
                server_name=effective_server_name,
                server_names=effective_server_names,
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
        engine_type=engine_type,
        server_filter={'server_name': server_name, 'server_names': server_names},
        nb_results=len(databases),
        rbac_server_count=len(allowed_server_names),
        correlation_id=correlation_id,
    )

    return Response({'data': serializer.data}, status=status.HTTP_200_OK)


# --- Story 62.3: Inventory schema endpoint ---


@extend_schema(exclude=True)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_inventory_schema(request: Request) -> Response:
    """
    Return available column concepts per inventory entity type from config.
    Story 62.3 — Used by ParametersEditor and execution wizard to load dynamic columns.

    Returns:
        200: dict mapping entity type → list of column concept names (id always first)
        401: if not authenticated
    """
    correlation_id = get_correlation_id()
    inventory_service = _inventory_service_factory()
    try:
        mapper = inventory_service._get_inventory_mapper()
    except InventoryServiceError as e:
        logger.error(
            "inventory_schema_fetch_failed",
            error=str(e),
            user_id=request.user.id,
            correlation_id=correlation_id,
        )
        return Response(
            {'detail': str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    schema: dict[str, list[str]] = {}
    for entity_type in INVENTORY_ENTITY_TYPES:
        if mapper and mapper.is_multi_table:
            entity_config = mapper.get_entity_config(entity_type)
            if entity_config:
                # Always place 'id' first, even if present elsewhere in config columns
                columns = ['id'] + [k for k in entity_config.get('columns', {}).keys() if k != 'id']
                schema[entity_type] = columns
            else:
                schema[entity_type] = list(DEFAULT_COLUMNS)
        else:
            schema[entity_type] = list(DEFAULT_COLUMNS)

    logger.info(
        "inventory_schema_fetched",
        user_id=request.user.id,
        entity_counts={k: len(v) for k, v in schema.items()},
        correlation_id=correlation_id,
    )
    return Response(schema, status=status.HTTP_200_OK)
