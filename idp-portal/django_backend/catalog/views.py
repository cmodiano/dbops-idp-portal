"""
DRF ViewSets for catalog app.
Implements admin, catalog, and tags endpoints.
"""

from __future__ import annotations

from typing import Any
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.serializers import ValidationError as DRFValidationError, Serializer
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from django.db import IntegrityError
from django.db.models import Count, Q, OuterRef, Subquery, IntegerField, Value, QuerySet
from django.db.models.functions import Coalesce
from cachetools import TTLCache
from core.utils import ensure_utc_isoformat
from catalog.models import Action, Tag, ActionStatus, ActionItemType, BusinessRulePolicy
from catalog.serializers import (
    ActionSerializer, ActionCreateSerializer, ActionListSerializer,
    ActionTagsUpdateSerializer, StatusUpdateSerializer, TagSerializer,
    BusinessRulePolicySerializer, BusinessRulePolicyListSerializer,
)
from catalog.services import CatalogService, InvalidTransitionError
from catalog.rbac_service import CatalogRBACService
from core.pagination import CustomPageNumberPagination
from core.permissions import DBOPSProfilePermission, OptionalUserPermission
from core.exceptions import NotFoundError, BadRequestError, InvalidStateError
from executions.models import Execution
from core.middleware import get_correlation_id
import structlog

logger = structlog.get_logger(__name__)


def _annotate_execution_count(queryset: QuerySet[Action]) -> QuerySet[Action]:
    """
    Annotate actions with execution_count without GROUP BY on CLOB columns (Oracle limitation).
    Uses a correlated subquery instead of Count() over a join.
    """
    subq = (
        Execution.objects.filter(action_id=OuterRef('pk'))
        .values('action_id')
        .annotate(c=Count('*'))
        .values('c')
    )
    return queryset.annotate(
        execution_count=Coalesce(Subquery(subq, output_field=IntegerField()), Value(0))
    )


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
    """
    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
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
        include_disabled = self.request.query_params.get('include_disabled', 'false').lower() == 'true'
        if self.action == 'list' and not include_disabled:
            # Default: exclude disabled actions (AC4)
            status_filter = self.request.query_params.get('status')
            if not status_filter:
                queryset = queryset.filter(status__in=[ActionStatus.DRAFT, ActionStatus.PUBLISHED])

        # Filters
        status_filter = self.request.query_params.get('status')
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
        try:
            action = CatalogService().create_action(
                action_data=serializer.validated_data,
                created_by_user=request.user  # type: ignore[arg-type]
            )
        except IntegrityError as e:
            err_msg = str(e).upper()
            if 'UK_ACTIONS_CATALOG_NAME' in err_msg or ('UNIQUE' in err_msg and 'NAME' in err_msg):
                raise DRFValidationError({'name': ['Une action avec ce nom existe déjà.']})
            raise
        # Reload with relations
        action = CatalogService().get_by_id(action.id)  # type: ignore[assignment]
        response_serializer = ActionSerializer(action)

        # MEDIUM-1 fix: Invalidate cache after write
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

        try:
            action = CatalogService().update_action(
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
        action = CatalogService().get_by_id(action.id)
        response_serializer = ActionSerializer(action)

        # MEDIUM-1 fix: Invalidate cache after write
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
        
        updated_action = CatalogService().sync_tags(action.id, tag_names or [])
        
        if updated_action is None:
            raise NotFoundError(
                code="NOT_FOUND",
                message=f"Action {action.id} introuvable",
                details={"action_id": action.id}
            )
        
        # Reload with relations
        updated_action = CatalogService().get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # MEDIUM-1 fix: Invalidate cache after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request: Request, pk: int | None = None) -> Response:
        """PATCH /admin/actions/{id}/status - Update action status."""
        action = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            updated_action = CatalogService().update_status(
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
        updated_action = CatalogService().get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # MEDIUM-1 fix: Invalidate cache after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

    @action(detail=True, methods=['put'], url_path='execution-steps')
    def update_execution_steps(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/execution-steps - Update execution steps."""
        action = self.get_object()
        
        steps = request.data.get('steps')
        change_type_config = request.data.get('change_type_config')
        
        try:
            updated_action = CatalogService().update_execution_steps(
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
        updated_action = CatalogService().get_by_id(updated_action.id)
        response_serializer = ActionSerializer(updated_action)

        # MEDIUM-1 fix: Invalidate cache after write
        _catalog_cache.clear()
        _tags_cache.clear()

        return Response({"data": response_serializer.data})

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
        action = CatalogService().get_by_id(action.id)
        response_serializer = ActionSerializer(action)

        return Response({"data": response_serializer.data})

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
        service = CatalogService()
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

    @action(detail=True, methods=['put'], url_path='deactivate')
    def deactivate(self, request: Request, pk: int | None = None) -> Response:
        """PUT /admin/actions/{id}/deactivate — Soft delete with cascade. Story 18.1 AC2/AC3."""
        instance = self.get_object()
        service = CatalogService()
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
        service = CatalogService()
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
            # Code Review Fix HIGH-3: Allow NULL description instead of forcing empty string
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
        # Story 25.5 Code Review Fix: Remove without strict same_target filter to handle inconsistencies
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


@extend_schema_view(
    list=extend_schema(tags=['catalog'], summary='Lister les règles métier'),
    create=extend_schema(tags=['catalog'], summary='Créer une règle métier'),
    retrieve=extend_schema(tags=['catalog'], summary='Détail d\'une règle métier'),
    partial_update=extend_schema(tags=['catalog'], summary='Modifier une règle métier'),
    destroy=extend_schema(tags=['catalog'], summary='Supprimer une règle métier'),
)
class BusinessRulePolicyViewSet(viewsets.ModelViewSet):
    """
    Story 28.4: CRUD ViewSet for BusinessRulePolicy (AC#4).
    GET/POST/PATCH/DELETE /api/v1/admin/business-rule-policies/
    """
    queryset = BusinessRulePolicy.objects.all()
    serializer_class = BusinessRulePolicySerializer
    permission_classes = [IsAuthenticated, DBOPSProfilePermission]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == 'list':
            return BusinessRulePolicyListSerializer
        return BusinessRulePolicySerializer

    def get_queryset(self) -> QuerySet[BusinessRulePolicy]:
        queryset = BusinessRulePolicy.objects.all()

        # Filter by is_active
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Filter by step_type (extracted from policy_json) or by platform (mapped to step_type)
        step_type_filter = self.request.query_params.get('step_type')
        platform_param = self.request.query_params.get('platform')
        if platform_param and not step_type_filter:
            # Map platform code (REF_PLATFORMS / integration) to step_type for filtering
            _PLATFORM_TO_STEP_TYPE = {
                'AAP': 'aap',
                'Tower': 'aap',
                'Terraform': 'terraform_cloud',
                'Terraform Cloud': 'terraform_cloud',
                'Azure DevOps': 'azure_devops',
            }
            step_type_filter = _PLATFORM_TO_STEP_TYPE.get(
                platform_param, platform_param.lower().replace(' ', '_')
            )
        if step_type_filter:
            # Filter in Python since step_type is computed from JSON
            # HIGH-1: Potential N+1 queries — load all policies before filtering
            all_policies = list(queryset)
            ids = [
                p.id for p in all_policies
                if p.step_type == step_type_filter
            ]
            queryset = queryset.filter(id__in=ids) if ids else queryset.none()

        return queryset

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BusinessRulePolicyListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = BusinessRulePolicyListSerializer(queryset, many=True)
        return Response({"data": serializer.data})

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = BusinessRulePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save(created_by=request.user)

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_CREATED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=policy.id,
            details={'name': policy.name},
            correlation_id=get_correlation_id(),
        )
        response_serializer = BusinessRulePolicySerializer(policy)
        return Response({"data": response_serializer.data}, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = BusinessRulePolicySerializer(instance)
        return Response({"data": serializer.data})

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        partial = kwargs.get('partial', True)
        serializer = BusinessRulePolicySerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_UPDATED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=policy.id,
            details={'name': policy.name},
            correlation_id=get_correlation_id(),
        )
        response_serializer = BusinessRulePolicySerializer(policy)
        return Response({"data": response_serializer.data})

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()

        # Audit trail
        from core.models import AuditLog, AuditActionType, AuditEntityType
        AuditLog.objects.create_entry(
            user_id=str(request.user.id),
            action_type=AuditActionType.POLICY_DELETED,
            entity_type=AuditEntityType.BUSINESS_RULE_POLICY,
            entity_id=instance.id,
            details={'name': instance.name},
            correlation_id=get_correlation_id(),
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Story 3.1 AC10: in-memory cache for catalog, TTL 5 min (300s)
# Story 30.6: Cache stores complete response dict {"data": [...], "pagination": {...}}
# Story 30.7 (RACE-3): Per-worker cache (not shared between Gunicorn workers).
# See docs/architecture/caching-strategy.md for rationale and limitations.
_catalog_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1000, ttl=300)

# Story 17.17: in-memory cache for catalog tags, TTL 5 min (300s)
# Story 30.7 (RACE-3): Per-worker cache — see docs/architecture/caching-strategy.md
_tags_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=200, ttl=300)


def _get_cache_key(
    user_id: int | None,
    tags_filter: list[str] | None,
    q: str | None = None,
    engine: str | None = None,
    environment: str | None = None,
    impact: str | None = None,
    category: str | None = None,
    page: str | None = None,
    page_size: str | None = None,
) -> str:
    """Generate cache key for catalog query."""
    user_part = f"user_{user_id}" if user_id else "anon"
    tags_part = ",".join(sorted(tags_filter)) if tags_filter else "all"
    q_part = q.strip() if q and q.strip() else ""
    engine_part = engine or ""
    env_part = environment or ""
    impact_part = impact or ""
    category_part = category or ""
    page_part = page or "1"
    limit_part = page_size or "20"
    return f"{user_part}_{tags_part}_q{q_part}_e{engine_part}_env{env_part}_i{impact_part}_cat{category_part}:page_{page_part}:limit_{limit_part}"


@extend_schema_view(
    list=extend_schema(
        tags=['catalog'], summary='Catalogue des actions (public)',
        description='Retourne la liste paginée des actions publiées avec filtrage RBAC.',
        parameters=[
            OpenApiParameter('tags', str, description='Filtrage par tags (séparés par virgules)'),
            OpenApiParameter('category', str, description='Filtrage par catégorie'),
            OpenApiParameter('search', str, description='Recherche par nom ou description'),
            OpenApiParameter('favorites_only', bool, description='Afficher uniquement les favoris'),
        ],
    ),
    retrieve=extend_schema(tags=['catalog'], summary='Détail d\'une action du catalogue'),
)
class CatalogActionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for catalog actions (read-only, public with RBAC filtering).
    """
    queryset = Action.objects.filter(status=ActionStatus.PUBLISHED)
    serializer_class = ActionSerializer
    permission_classes = [OptionalUserPermission]
    pagination_class = CustomPageNumberPagination  # HIGH-5 fix: Add pagination

    def _get_rbac_service(self) -> CatalogRBACService:
        """Get or create cached RBAC service instance (HIGH-1 fix: Story 26.3 review)."""
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
            queryset = queryset.search_by_tags(tag_names)

        category = self.request.query_params.get('category')
        if category and category.lower() not in ('tout', 'all', 'mes-actions'):
            # Category maps to tag
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
            # HIGH-4 fix: Filter by environment in impact_rules using icontains
            # impact_rules is stored as JSON string in TextField (CLOB)
            # Match environment pattern in the JSON (e.g., "DEV", "PROD")
            queryset = queryset.filter(impact_rules__icontains=environment)
        
        impact = self.request.query_params.get('impact')
        if impact:
            queryset = queryset.filter(default_impact_level=impact)
        
        # RBAC filtering (if user authenticated)
        rbac_service = self._get_rbac_service()
        cumulative_permissions = rbac_service.get_permissions(self.request.user)  # type: ignore[arg-type]
        if cumulative_permissions:
            # Convert queryset to list for filtering
            actions_list = list(queryset)
            filtered_actions = rbac_service.filter_actions(actions_list, cumulative_permissions)
            # Get IDs of filtered actions and filter queryset
            filtered_ids = [a.id if hasattr(a, 'id') else a.get('id') for a in filtered_actions]
            queryset = queryset.filter(id__in=filtered_ids)

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
        # MEDIUM-8 fix: Removed dead code - queryset already filters by PUBLISHED status
        # get_object() will raise 404 if action is not in queryset (i.e., not published)
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
                        "correlation_id": get_correlation_id()  # HIGH-2 fix: Story 26.3 review
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
        # MEDIUM-8 fix: Removed dead code - queryset already filters by PUBLISHED
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
                        "correlation_id": get_correlation_id()  # HIGH-2 fix: Story 26.3 review
                    }
                )
        
        from executions.services import ExecutionService
        execution_service = ExecutionService()
        try:
            stats = execution_service.get_action_stats(action.id, days=30)
        except ValueError as e:
            # CRITICAL-3: Handle invalid action_id (should not happen since get_object() validated it)
            raise NotFoundError(
                code="NOT_FOUND",
                message=str(e),
                details={"action_id": action.id}
            )
        return Response({"data": stats})


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

        # Get tags with action_count for visible actions only
        from catalog.models import ActionTag
        visible_action_ids = actions_queryset.values_list('id', flat=True)

        # Annotate tags with action_count from visible actions
        queryset = Tag.objects.filter(
            actiontag__action_id__in=visible_action_ids
        ).annotate(
            action_count=Count('actiontag', filter=Q(actiontag__action_id__in=visible_action_ids))
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
