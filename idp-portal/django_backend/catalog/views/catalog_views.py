"""
ViewSet public du catalogue d'actions.

Responsabilité unique : lecture publique du catalogue avec filtrage RBAC et cache.
Permissions : [OptionalUserPermission].
"""
from __future__ import annotations

from typing import Any

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from django.db.models import Q, QuerySet

from catalog.models import Action, ActionStatus
from catalog.serializers import ActionSerializer
from catalog.rbac_service import CatalogRBACService
from catalog.views._shared import _catalog_cache, _annotate_execution_count, _get_cache_key
from core.pagination import CustomPageNumberPagination
from core.permissions import OptionalUserPermission
from core.exceptions import NotFoundError
from core.middleware import get_correlation_id


@extend_schema_view(
    list=extend_schema(
        tags=['catalog'], summary='Catalogue des actions (public)',
        description='Retourne la liste paginée des actions publiées avec filtrage RBAC.',
        parameters=[
            OpenApiParameter('tags', str, description='Filtrage par tags (séparés par virgules)'),
            OpenApiParameter('category', str, description='Filtrage par catégorie'),
            OpenApiParameter('q', str, description='Recherche par nom ou description'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
            OpenApiParameter('impact', str, description='Filtrage par niveau d\'impact'),
            OpenApiParameter('favorites_only', bool, description='Afficher uniquement les favoris'),
            OpenApiParameter('page', int, description='Numéro de page (pagination)'),
            OpenApiParameter('limit', str, description='Taille de page (alias: page_size)'),
        ],
    ),
    retrieve=extend_schema(tags=['catalog'], summary='Détail d\'une action du catalogue'),
)
class CatalogActionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for catalog actions (read-only, public with RBAC filtering).

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    """
    queryset = Action.objects.filter(status=ActionStatus.PUBLISHED)
    serializer_class = ActionSerializer
    permission_classes = [OptionalUserPermission]
    pagination_class = CustomPageNumberPagination

    # Lazy default (None) because ExecutionService is in executions app — circular import risk.
    # Override in tests: view._execution_service_class = MockExecutionService
    _execution_service_class = None

    def get_execution_service(self) -> Any:
        """Return an ExecutionService instance (overridable in tests)."""
        from executions.services import ExecutionService  # noqa: PLC0415
        cls = self._execution_service_class or ExecutionService
        return cls()

    def _get_rbac_service(self) -> CatalogRBACService:
        """Get or create RBAC service instance (lazy init to avoid redundant instantiation per request)."""
        if not hasattr(self, '_rbac_service'):
            self._rbac_service = CatalogRBACService()
        return self._rbac_service

    def get_queryset(self) -> QuerySet[Action]:
        """Filter queryset based on query parameters and RBAC."""
        queryset = Action.objects.filter(status=ActionStatus.PUBLISHED).with_tags().with_creator()

        # Filters
        tags_filter = self.request.query_params.get('tags')
        if tags_filter:
            tag_names = [t.strip() for t in tags_filter.split(',')]
            # Story 34.1 NEW-1: chaîne sur queryset courant (pas de recréation Action.objects.search_by_tags)
            queryset = queryset.search_by_tags(tag_names)

        category = self.request.query_params.get('category')
        if category and category.lower() not in ('tout', 'all', 'mes-actions'):
            # Category maps to tag. Chaîne sur queryset courant → AND logique avec tags si les deux sont fournis.
            # Story 34.1 NEW-1: queryset.search_by_tags (chaîne) intentionnel — pas Action.objects.search_by_tags (recréation)
            from catalog.models import normalize_tag_name
            tag_name = normalize_tag_name(category)
            if tag_name:
                queryset = queryset.search_by_tags([tag_name])

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | Q(description__icontains=q)
            )

        engine = self.request.query_params.get('engine')
        if engine:
            queryset = queryset.filter(engine=engine)

        environment = self.request.query_params.get('environment')
        if environment:
            # Filter by environment in impact_rules (stored as JSON string in CLOB TextField)
            # Uses icontains to match environment value within the serialized JSON (e.g., "DEV", "PROD")
            queryset = queryset.filter(impact_rules__icontains=environment)

        impact = self.request.query_params.get('impact')
        if impact:
            queryset = queryset.filter(default_impact_level=impact)

        # RBAC filtering (if user authenticated)
        # BE-CAT-012: Filter directly in DB to avoid list(queryset) memory spike for large catalogs.
        rbac_service = self._get_rbac_service()
        cumulative_permissions = rbac_service.get_permissions(self.request.user)  # type: ignore[arg-type]
        if cumulative_permissions:
            actions_type = cumulative_permissions.get('actions_type', 'all')
            if actions_type != 'all':
                action_ids = set(cumulative_permissions.get('action_ids', []) or [])
                tag_patterns = set(cumulative_permissions.get('tag_patterns', []) or [])
                if tag_patterns:
                    from catalog.models import ActionTag  # noqa: PLC0415
                    tag_action_ids = set(
                        ActionTag.objects.filter(
                            tag__name__in=tag_patterns,
                            action__status=ActionStatus.PUBLISHED,
                        ).values_list('action_id', flat=True)
                    )
                    action_ids = action_ids | tag_action_ids
                queryset = queryset.filter(id__in=action_ids)

        return queryset.order_by('name')  # type: ignore[no-any-return]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /catalog/actions - List published actions with cache."""
        # Build cache key
        user_id = request.user.id if request.user and request.user.is_authenticated else None
        tags_filter = None
        tags_param = request.query_params.get('tags')
        if tags_param:
            tags_filter = [t.strip() for t in tags_param.split(',')]
        category = request.query_params.get('category')
        if category and category.lower() not in ('tout', 'all', 'mes-actions'):
            from catalog.models import normalize_tag_name
            tag_name = normalize_tag_name(category)
            if tag_name:
                tags_filter = tags_filter or []
                if tag_name not in tags_filter:
                    tags_filter.append(tag_name)

        page_param = request.query_params.get('page', '1')
        page_size_param = request.query_params.get('limit', request.query_params.get('page_size', '20'))

        cache_key = _get_cache_key(
            user_id=user_id,
            tags_filter=tags_filter,
            q=request.query_params.get('q'),
            engine=request.query_params.get('engine'),
            environment=request.query_params.get('environment'),
            impact=request.query_params.get('impact'),
            category=request.query_params.get('category'),
            page=page_param,
            page_size=page_size_param,
        )

        # Check cache: cache stores complete response dict with data+pagination
        if cache_key in _catalog_cache:
            return Response(_catalog_cache[cache_key])

        queryset = self.filter_queryset(self.get_queryset())

        # Annotate execution_count
        queryset = _annotate_execution_count(queryset)

        # Paginate before serializing and caching
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            _catalog_cache[cache_key] = response.data
            return response

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        total = len(data)
        response_data = {
            "data": data,
            "pagination": {
                "page": 1,
                "page_size": total,
                "total": total,
                "total_pages": 1,
            },
        }

        # Cache complete response
        _catalog_cache[cache_key] = response_data

        return Response(response_data)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /catalog/actions/{id} - Get published action details."""
        # get_object() raises 404 if the action is not in the queryset (i.e., not published)
        instance = self.get_object()

        # RBAC check (if user authenticated)
        rbac_service = self._get_rbac_service()
        cumulative_permissions = rbac_service.get_permissions(self.request.user)  # type: ignore[arg-type]
        if cumulative_permissions:
            if not rbac_service.check_action(instance, cumulative_permissions):
                raise NotFoundError(
                    code="NOT_FOUND",
                    message="Action non trouvée",
                    details={
                        "action_id": instance.id,
                        "correlation_id": get_correlation_id()
                    }
                )

        serializer = self.get_serializer(instance)
        response_data = serializer.data

        # Add can_execute and allowed_environments (if user authenticated)
        if cumulative_permissions:
            allowed_environments = cumulative_permissions.get('environments', [])
            response_data['can_execute'] = len(allowed_environments) > 0
            response_data['allowed_environments'] = allowed_environments
        else:
            response_data['can_execute'] = False
            response_data['allowed_environments'] = []

        return Response({"data": response_data})

    @action(detail=True, methods=['get'], url_path='stats')
    def get_stats(self, request: Request, pk: int | None = None) -> Response:
        """GET /catalog/actions/{id}/stats - Get execution stats."""
        action = self.get_object()

        # RBAC check if user is authenticated
        rbac_service = self._get_rbac_service()
        cumulative_permissions = rbac_service.get_permissions(self.request.user)  # type: ignore[arg-type]
        if cumulative_permissions:
            if not rbac_service.check_action(action, cumulative_permissions):
                raise NotFoundError(
                    code="NOT_FOUND",
                    message="Action non trouvée",
                    details={
                        "action_id": action.id,
                        "correlation_id": get_correlation_id()
                    }
                )

        execution_service = self.get_execution_service()
        try:
            stats = execution_service.get_action_stats(action.id, days=30)
        except ValueError as e:
            # Defensive: get_object() already validated action_id, but guard against service errors
            raise NotFoundError(
                code="NOT_FOUND",
                message=str(e),
                details={"action_id": action.id}
            )
        return Response({"data": stats})
