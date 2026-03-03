"""
ViewSet admin des actions du catalogue.

Responsabilité unique : CRUD admin des actions (cycle de vie, tags, étapes d'exécution,
mutex, règles métier inline). Permissions : [IsAuthenticated, AdminProfilePermission] (admin users only).
"""
from __future__ import annotations

from typing import Any

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as DRFValidationError, Serializer
from rest_framework.request import Request
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer
from django.db import IntegrityError
from django.db.models import Q, QuerySet

from catalog.models import Action, Tag, ActionStatus, ActionItemType
from catalog.serializers import (
    ActionSerializer, ActionCreateSerializer, ActionListSerializer,
    ActionTagsUpdateSerializer, StatusUpdateSerializer,
    ActionMutexCreateSerializer,
)
from catalog.services import CatalogService, InvalidTransitionError
from catalog.views._shared import _catalog_cache, _tags_cache, _annotate_execution_count
from core.pagination import CustomPageNumberPagination
from core.permissions import AdminProfilePermission
from core.exceptions import NotFoundError, BadRequestError, InvalidStateError
from core.middleware import get_correlation_id
import structlog

logger = structlog.get_logger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['catalog'], summary='Lister les actions (admin)',
        description='Retourne la liste paginée des actions avec filtrage et exécution_count.',
        parameters=[
            OpenApiParameter('include_disabled', bool, description='Inclure les actions désactivées'),
            OpenApiParameter('search', str, description='Recherche par nom ou description'),
            OpenApiParameter('status', str, description='Filtrage par statut (draft, published, disabled)'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('platform', str, description='Filtrage par plateforme'),
            OpenApiParameter('item_type', str, description='Filtrage par type (action, workflow)'),
        ],
    ),
    create=extend_schema(tags=['catalog'], summary='Créer une action', request=ActionCreateSerializer),
    retrieve=extend_schema(tags=['catalog'], summary='Détail d\'une action'),
    update=extend_schema(tags=['catalog'], summary='Modifier une action'),
    destroy=extend_schema(tags=['catalog'], summary='Supprimer une action (soft-delete)'),
)
class ActionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin actions (CRUD operations).

    Story 33.4 (DIP): uses _catalog_service_class + get_catalog_service() so
    tests can override the service class without monkey-patching.
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer

    _catalog_service_class: type[CatalogService] = CatalogService

    def get_catalog_service(self) -> CatalogService:
        """Return a CatalogService instance (overridable in tests)."""
        return self._catalog_service_class()
    permission_classes = [IsAuthenticated, AdminProfilePermission]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[Serializer[Any]]:
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ActionCreateSerializer
        elif self.action == 'list':
            return ActionListSerializer
        return ActionSerializer

    def get_queryset(self) -> QuerySet[Action]:
        """Filter queryset based on query parameters."""
        queryset = Action.objects.with_tags().with_creator()

        # Annotate execution_count for list view
        if self.action == 'list':
            queryset = _annotate_execution_count(queryset)

        # Story 18.1 (AC4/AC5): include_disabled filter — default excludes disabled
        status_filter = self.request.query_params.get('status')
        include_disabled = self.request.query_params.get('include_disabled', 'false').lower() == 'true'
        if self.action == 'list' and not include_disabled:
            # Default: exclude disabled actions (AC4) unless explicit status filter provided
            if not status_filter:
                queryset = queryset.filter(status__in=[ActionStatus.DRAFT, ActionStatus.PUBLISHED])

        # Filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        engine_filter = self.request.query_params.get('engine')
        if engine_filter:
            queryset = queryset.filter(engine=engine_filter)

        item_type_filter = self.request.query_params.get('item_type')
        if item_type_filter:
            queryset = queryset.filter(item_type=item_type_filter)

        return queryset.order_by('-created_at')  # type: ignore[no-any-return]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """POST /admin/actions - Create a new action."""
        serializer = ActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        svc = self.get_catalog_service()
        try:
            action = svc.create_action(
                action_data=serializer.validated_data,
                created_by_user=request.user  # type: ignore[arg-type]
            )
        except IntegrityError as e:
            err_msg = str(e).upper()
            if 'UK_ACTIONS_CATALOG_NAME' in err_msg or ('UNIQUE' in err_msg and 'NAME' in err_msg):
                raise DRFValidationError({'name': ['Une action avec ce nom existe déjà.']})
            raise
        # Reload with relations
        action = svc.get_by_id(action.id)  # type: ignore[assignment]
        response_serializer = ActionSerializer(action)

        # Invalidate catalog and tags caches after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data}, status=status.HTTP_201_CREATED)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /admin/actions - List all actions with pagination."""
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ActionListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ActionListSerializer(queryset, many=True)
        return Response({"data": serializer.data})

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """GET /admin/actions/{id} - Get action details."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({"data": serializer.data})

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """PUT/PATCH /admin/actions/{id} - Update action metadata."""
        instance = self.get_object()
        partial = kwargs.get('partial', False)

        # Story 28.4: Handle business_rule_policy_id in PATCH requests
        if 'business_rule_policy_id' in request.data or 'business_rule_policies' in request.data:
            brp_id = request.data.get('business_rule_policy_id')
            brp_inline = request.data.get('business_rule_policies')

            # XOR validation
            if brp_id is not None and brp_inline is not None:
                raise DRFValidationError({
                    'business_rule_policies': ['Spécifiez soit business_rule_policy_id soit business_rule_policies, pas les deux.']
                })

            if brp_inline is not None:
                from catalog.validators import validate_business_rule_policies
                from django.core.exceptions import ValidationError as DjangoValidationError
                try:
                    validate_business_rule_policies(brp_inline)
                except (DjangoValidationError, ValueError, TypeError, KeyError) as e:
                    raise DRFValidationError({'business_rule_policies': [str(e)]})

            instance.business_rule_policy_id = brp_id
            instance.business_rule_policies = brp_inline
            instance.save()

            _catalog_cache.clear()
            _tags_cache.clear()

            instance.refresh_from_db()
            response_serializer = ActionSerializer(instance)
            return Response({"data": response_serializer.data})

        # Handle other fields via ActionCreateSerializer (includes gate_config via Story 31.6)
        serializer = ActionCreateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        update_data = serializer.validated_data
        svc = self.get_catalog_service()

        try:
            action = svc.update_action(
                action_id=instance.id,
                action_update_data=update_data,
                user=request.user  # type: ignore[arg-type]
            )
        except IntegrityError as e:
            err_msg = str(e).upper()
            if 'UK_ACTIONS_CATALOG_NAME' in err_msg or ('UNIQUE' in err_msg and 'NAME' in err_msg):
                raise DRFValidationError({'name': ['Une action avec ce nom existe déjà.']})
            raise
        if action is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {instance.id} introuvable",
                details={"action_id": instance.id}
            )

        # Reload with relations
        action = svc.get_by_id(action.id)
        response_serializer = ActionSerializer(action)

        # Invalidate catalog and tags caches after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @action(detail=True, methods=['put'], url_path='tags')
    def update_tags(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/tags - Update action tags."""
        action = self.get_object()
        serializer = ActionTagsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Handle tag_ids or tag_names
        tag_names = None
        if serializer.validated_data.get('tag_names'):
            tag_names = serializer.validated_data['tag_names']
        elif serializer.validated_data.get('tag_ids'):
            # Convert tag_ids to tag_names
            tags = Tag.objects.filter(id__in=serializer.validated_data['tag_ids'])
            tag_names = [tag.name for tag in tags]

        svc = self.get_catalog_service()
        updated_action = svc.sync_tags(action.id, tag_names or [])

        if updated_action is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {action.id} introuvable",
                details={"action_id": action.id}
            )

        # Reload with relations
        updated_action = svc.get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # Invalidate catalog and tags caches after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request: Request, pk: int | None = None) -> Response:
        """PATCH /admin/actions/{id}/status - Update action status."""
        action = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        svc = self.get_catalog_service()
        try:
            updated_action = svc.update_status(
                action_id=action.id,
                transition=serializer.validated_data['transition'],
                user=request.user  # type: ignore[arg-type]
            )
        except InvalidTransitionError as e:
            raise InvalidStateError(
                code="INVALID_STATE",
                message=str(e),
                details={
                    "current_status": action.status,
                    "transition": serializer.validated_data['transition']
                }
            )

        if updated_action is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {action.id} introuvable",
                details={"action_id": action.id}
            )

        # Reload with relations
        updated_action = svc.get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # Invalidate catalog and tags caches after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @action(detail=True, methods=['put'], url_path='execution-steps')
    def update_execution_steps(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/execution-steps - Update execution steps."""
        action = self.get_object()

        steps = request.data.get('steps')
        change_type_config = request.data.get('change_type_config')

        svc = self.get_catalog_service()
        try:
            updated_action = svc.update_execution_steps(
                action_id=action.id,
                steps=steps,  # type: ignore[arg-type]
                change_type_config=change_type_config,
                user=self.request.user  # type: ignore[arg-type]
            )
        except ValueError as e:
            raise InvalidStateError(
                code="INVALID_STATE",
                message=str(e),
                details={
                    "status": action.status,
                    "required_status": "draft or disabled"
                }
            )

        if updated_action is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {action.id} introuvable",
                details={"action_id": action.id}
            )

        # Reload with relations
        updated_action = svc.get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # Invalidate catalog and tags caches after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @extend_schema(
        tags=['catalog'],
        summary='Vérifier disponibilité du nom',
        parameters=[
            OpenApiParameter('name', str, description='Nom à vérifier'),
            OpenApiParameter('exclude_id', int, description='ID à exclure (pour édition)'),
        ],
    )
    @action(detail=False, methods=['get'], url_path='name-available')
    def name_available(self, request: Request) -> Response:
        """GET /admin/actions/name-available/?name=...&exclude_id=... - Check if action name is available."""
        name = (request.query_params.get('name') or '').strip()
        if not name:
            return Response({"available": True})
        qs = Action.objects.filter(name__iexact=name)
        exclude_id = request.query_params.get('exclude_id')
        if exclude_id is not None:
            try:
                qs = qs.exclude(id=int(exclude_id))
            except (ValueError, TypeError):
                pass
        return Response({"available": not qs.exists()})

    @action(detail=False, methods=['get'], url_path='eligible-for-workflow')
    def list_eligible_for_workflow(self, request: Request) -> Response:
        """GET /admin/actions/eligible-for-workflow - List published actions eligible for workflows."""
        queryset = Action.objects.filter(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION
        ).with_tags().with_creator()

        serializer = ActionSerializer(queryset, many=True)
        return Response({"data": serializer.data})

    @extend_schema(
        tags=['catalog'],
        summary='Mettre à jour les règles de remédiation',
        request=inline_serializer(
            name='RemediationRulesRequest',
            fields={
                'remediation_rules': serializers.ListField(
                    child=serializers.DictField(),
                    help_text='Liste des règles de remédiation',
                ),
            },
        ),
    )
    @action(detail=True, methods=['put'], url_path='remediation-rules')
    def update_remediation_rules(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/remediation-rules - Update remediation rules."""
        action = self.get_object()

        remediation_rules = request.data.get('remediation_rules')

        if remediation_rules is None:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="remediation_rules est requis",
                details={}
            )

        # Only draft actions can have remediation_rules updated
        if action.status != ActionStatus.DRAFT:
            raise InvalidStateError(
                code="INVALID_STATE",
                message="Les règles de remédiation ne peuvent être modifiées que pour une action en brouillon",
                details={
                    "status": action.status,
                    "required_status": "draft"
                }
            )

        # Update remediation_rules
        action.remediation_rules = remediation_rules
        action.save()

        # Invalidate cache
        _catalog_cache.clear()
        _tags_cache.clear()

        # Reload with relations
        action = self.get_catalog_service().get_by_id(action.id)
        response_serializer = ActionSerializer(action)

        return Response({"data": response_serializer.data})

    @extend_schema(
        tags=['catalog'],
        summary='Définir les politiques de règles métier inline',
        request=inline_serializer(
            name='BusinessRulePoliciesRequest',
            fields={
                'business_rule_policies': serializers.ListField(
                    child=serializers.DictField(),
                    required=False,
                    allow_null=True,
                    help_text='Liste des politiques inline (null pour effacer)',
                ),
            },
        ),
    )
    @action(detail=True, methods=['put'], url_path='business-rule-policies')
    def update_business_rule_policies(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/business-rule-policies/ - Set inline business rule policies (Story 28.1)."""
        instance = self.get_object()
        brp_inline = request.data.get('business_rule_policies')

        # Clear predefined FK when setting inline or clearing
        instance.business_rule_policy_id = None
        if brp_inline is None:
            instance.business_rule_policies = None
        else:
            from catalog.validators import validate_business_rule_policies
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_business_rule_policies(brp_inline)
            except (DjangoValidationError, ValueError, TypeError, KeyError) as e:
                raise DRFValidationError({'business_rule_policies': [str(e)]})
            instance.business_rule_policies = brp_inline

        instance.save()
        _catalog_cache.clear()
        _tags_cache.clear()
        instance.refresh_from_db()
        response_serializer = ActionSerializer(instance)
        return Response({"data": response_serializer.data})

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """DELETE /admin/actions/{id} — Hard delete (only if execution_count=0). Story 18.1 AC1."""
        instance = self.get_object()
        service = self.get_catalog_service()
        # ConflictError is raised if execution_count > 0 (propagated to exception handler → 409)
        deleted = service.delete_action(instance.id, user=request.user)  # type: ignore[arg-type]
        if not deleted:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {instance.id} introuvable",
                details={"action_id": instance.id},
            )
        _catalog_cache.clear()
        _tags_cache.clear()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=['catalog'],
        summary='Désactiver une action (soft-delete)',
        parameters=[
            OpenApiParameter('confirmed', bool, description='Confirmer la désactivation (requis si workflows impactés)'),
        ],
        request=inline_serializer(
            name='DeactivateRequest',
            fields={
                'deletion_reason': serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text='Motif de la désactivation',
                ),
            },
        ),
    )
    @action(detail=True, methods=['put'], url_path='deactivate')
    def deactivate(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/deactivate — Soft delete with cascade. Story 18.1 AC2/AC3."""
        instance = self.get_object()
        service = self.get_catalog_service()
        confirmed = request.query_params.get('confirmed', 'false').lower() == 'true'
        deletion_reason = request.data.get('deletion_reason')

        # If not confirmed, check for affected workflows and ask for confirmation
        if not confirmed:
            affected = service.get_workflows_referencing_action(instance.id)
            if affected:
                return Response({
                    "status": "requires_confirmation",
                    "affected_workflows": affected,
                }, status=status.HTTP_200_OK)

        # ConflictError is raised if already disabled (propagated → 409)
        result = service.deactivate_action(instance.id, user=request.user, deletion_reason=deletion_reason)  # type: ignore[arg-type]
        if result is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {instance.id} introuvable",
                details={"action_id": instance.id},
            )

        _catalog_cache.clear()
        _tags_cache.clear()

        action_obj = result['action']
        reloaded = service.get_by_id(action_obj.id)
        serializer = ActionSerializer(reloaded)
        return Response({
            "data": serializer.data,
            "deactivated_workflows": result['deactivated_workflows'],
        })

    @action(detail=True, methods=['put'], url_path='reactivate')
    def reactivate(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/reactivate — Reactivate a disabled action. Story 18.1 AC5."""
        instance = self.get_object()
        service = self.get_catalog_service()
        # ConflictError is raised if not disabled (propagated → 409)
        reactivated = service.reactivate_action(instance.id, user=request.user)  # type: ignore[arg-type]
        if reactivated is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {instance.id} introuvable",
                details={"action_id": instance.id},
            )

        _catalog_cache.clear()
        _tags_cache.clear()

        reloaded = service.get_by_id(reactivated.id)
        serializer = ActionSerializer(reloaded)
        return Response({"data": serializer.data})

    @extend_schema(
        tags=['catalog'],
        summary='Règles mutex (liste ou création)',
        request=ActionMutexCreateSerializer,
    )
    @action(detail=True, methods=['get', 'post'], url_path='mutex')
    def mutex_rules(self, request: Request, pk: int | None = None) -> Response:
        """
        GET /admin/actions/{id}/mutex/ - List mutex rules for this action.
        POST /admin/actions/{id}/mutex/ - Create a mutex rule.
        Story 25.5, Task 4.1: CRUD operations for mutex rules.
        """
        from catalog.models import ActionMutex
        from catalog.serializers import ActionMutexSerializer, ActionMutexCreateSerializer

        action = self.get_object()

        if request.method == 'GET':
            # List rules where this action is involved (either side)
            rules = ActionMutex.objects.filter(
                Q(action=action) | Q(incompatible_with=action)
            ).select_related('action', 'incompatible_with')

            serializer = ActionMutexSerializer(rules, many=True)
            return Response({"data": serializer.data})

        elif request.method == 'POST':
            # Create mutex rule
            # Pass action_id to serializer context for validation
            serializer = ActionMutexCreateSerializer(  # type: ignore[assignment]
                data=request.data,
                context={'action_id': action.id}
            )
            serializer.is_valid(raise_exception=True)

            # Create the primary rule (A→B)
            # Allow NULL description (no forced empty string)
            mutex_rule = ActionMutex.objects.create(
                action=action,
                incompatible_with_id=serializer.validated_data['incompatible_with_id'],
                same_target=serializer.validated_data['same_target'],
                description=serializer.validated_data.get('description'),
            )

            # Story 25.5, Task 2.3 Option A: Create symmetric rule (B→A) automatically
            # Check if symmetric rule already exists
            symmetric_exists = ActionMutex.objects.filter(
                action_id=serializer.validated_data['incompatible_with_id'],
                incompatible_with=action
            ).exists()

            if not symmetric_exists:
                ActionMutex.objects.create(
                    action_id=serializer.validated_data['incompatible_with_id'],
                    incompatible_with=action,
                    same_target=serializer.validated_data['same_target'],
                    description=serializer.validated_data.get('description'),
                )
                logger.info(
                    "mutex_symmetric_rule_created",
                    action_id=action.id,
                    incompatible_with_id=serializer.validated_data['incompatible_with_id'],
                    same_target=serializer.validated_data['same_target'],
                    correlation_id=get_correlation_id(),
                )

            response_serializer = ActionMutexSerializer(mutex_rule)
            return Response({"data": response_serializer.data}, status=status.HTTP_201_CREATED)

        # Mypy thinks this is unreachable but it handles unexpected HTTP methods
        raise ValueError(f"Unsupported HTTP method: {request.method}")

    @action(detail=True, methods=['delete'], url_path='mutex/(?P<rule_id>[^/.]+)')
    def delete_mutex_rule(self, request: Request, pk: int | None = None, rule_id: str | None = None) -> Response:
        """
        DELETE /admin/actions/{id}/mutex/{rule_id}/ - Delete a mutex rule.
        Story 25.5, Task 4.1: Deletes rule and optionally its symmetric counterpart.
        """
        from catalog.models import ActionMutex

        action = self.get_object()

        # Find the rule
        try:
            mutex_rule = ActionMutex.objects.get(
                id=rule_id,  # type: ignore[misc]
                action=action
            )
        except ActionMutex.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Règle mutex {rule_id} non trouvée pour cette action",
                details={"action_id": action.id, "rule_id": rule_id}
            )

        # Store data for symmetric rule deletion
        incompatible_with_id = mutex_rule.incompatible_with_id

        # Delete the primary rule
        mutex_rule.delete()

        # Task 2.3: Delete symmetric rule if it exists
        # Delete without same_target filter to handle data inconsistencies (symmetric rules may differ)
        symmetric_rules = ActionMutex.objects.filter(
            action_id=incompatible_with_id,
            incompatible_with=action
        )

        # Log warning if multiple symmetric rules found (data inconsistency)
        if symmetric_rules.count() > 1:
            logger.warning(
                "mutex_multiple_symmetric_rules_found",
                action_id=action.id,
                incompatible_with_id=incompatible_with_id,
                count=symmetric_rules.count(),
                correlation_id=get_correlation_id(),
            )

        if symmetric_rules.exists():
            deleted_count = symmetric_rules.delete()[0]
            logger.info(
                "mutex_symmetric_rule_deleted",
                action_id=action.id,
                incompatible_with_id=incompatible_with_id,
                deleted_count=deleted_count,
                correlation_id=get_correlation_id(),
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
