"""
ViewSet public des tags du catalogue.

Responsabilité unique : lecture des tags (liste brute + compteur RBAC pour /catalog/tags/).
Permissions : [OptionalUserPermission].
"""
from __future__ import annotations

from typing import Any

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models import Count

from catalog.models import Action, Tag, ActionStatus
from catalog.serializers import TagSerializer
from catalog.rbac_service import CatalogRBACService
from catalog.views._shared import _tags_cache
from core.permissions import OptionalUserPermission
from core.utils import ensure_utc_isoformat


@extend_schema_view(
    list=extend_schema(tags=['catalog'], summary='Lister tous les tags'),
)
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for tags (read-only, public).
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [OptionalUserPermission]

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /tags - List all tags."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"data": serializer.data})

    @action(detail=False, methods=['get'], url_path='catalog')
    def list_catalog_tags(self, request: Request) -> Response:
        """GET /catalog/tags - List tags with action_count and RBAC filtering."""
        # Story 17.17: Cache tags endpoint (5min TTL, same as actions)
        user_id = request.user.id if request.user and request.user.is_authenticated else None
        category = request.query_params.get('category')
        tags_cache_key = f"tags_user_{user_id}_cat_{category or 'all'}"

        if tags_cache_key in _tags_cache:
            return Response({"data": _tags_cache[tags_cache_key]})

        # HIGH-3 fix: Implement action_count and RBAC filtering

        # Get base queryset of published actions (filtered by RBAC if user authenticated)
        actions_queryset = Action.objects.filter(status=ActionStatus.PUBLISHED)

        # Optional category filter (Story 8.7): restrict to actions tagged with the category tag
        if category and category.lower() not in ('tout', 'all', 'mes-actions'):
            from catalog.models import normalize_tag_name
            category_tag = normalize_tag_name(category)
            if category_tag:
                actions_queryset = actions_queryset.filter(actiontag__tag__name=category_tag).distinct()

        # Apply RBAC filtering if user is authenticated
        rbac_service = CatalogRBACService()
        cumulative_permissions = rbac_service.get_permissions(request.user)  # type: ignore[arg-type]
        if cumulative_permissions and cumulative_permissions.get('actions_type') != 'all':
            # Get allowed action IDs based on RBAC
            action_ids = set(cumulative_permissions.get('action_ids', []) or [])
            tag_patterns = set(cumulative_permissions.get('tag_patterns', []) or [])

            if tag_patterns:
                # Filter by tag patterns - get actions that have matching tags
                from catalog.models import ActionTag
                matching_action_ids = ActionTag.objects.filter(
                    tag__name__in=tag_patterns,
                    action__status=ActionStatus.PUBLISHED
                ).values_list('action_id', flat=True)
                action_ids = action_ids.union(set(matching_action_ids))

            actions_queryset = actions_queryset.filter(id__in=action_ids)

        # Get tags with action_count for visible actions only.
        # The pre-filter restricts the JOIN to visible actions — Count('actiontag') counts
        # only those rows, so no need for a redundant filter=Q(...) that would generate a
        # duplicate correlated subquery in SQL.
        visible_action_ids = actions_queryset.values_list('id', flat=True)
        queryset = Tag.objects.filter(
            actiontag__action_id__in=visible_action_ids
        ).annotate(
            action_count=Count('actiontag')
        ).filter(action_count__gt=0).order_by('name')

        # Build response data with action_count
        data = []
        for tag in queryset:
            data.append({
                'id': tag.id,
                'name': tag.name,
                'action_count': tag.action_count,
                'created_at': ensure_utc_isoformat(tag.created_at)
            })

        # Cache result
        _tags_cache[tags_cache_key] = data

        return Response({"data": data})
