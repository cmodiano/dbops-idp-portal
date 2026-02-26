"""
CatalogService for business logic related to actions and workflows.
Handles complex operations like status transitions, tag management, and validation.
Story M.8 - Task 9: Structured logging with structlog.
"""
# Responsabilité : Logique métier du catalogue d'actions (transitions de statut, gestion des
# workflows, dépendances entre étapes, tags, RBAC catalog) — volume justifié par la richesse
# inhérente du domaine métier (Story 35.4 AC3).

from __future__ import annotations

import structlog
from typing import cast, Any
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import QuerySet
from catalog.models import Action, ActionStatus, Tag, ActionTag, ActionItemType, normalize_tag_name
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.exceptions import ConflictError, BadRequestError
from idp_auth.models import User

logger = structlog.get_logger(__name__)


class InvalidTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""
    pass


# Valid transitions mapping: {current_status: {transition: new_status}}
_VALID_TRANSITIONS = {
    ActionStatus.DRAFT: {
        'publish': ActionStatus.PUBLISHED,
    },
    ActionStatus.PUBLISHED: {
        'disable': ActionStatus.DISABLED,
    },
    ActionStatus.DISABLED: {
        'enable': ActionStatus.PUBLISHED,
    },
}


def _validate_workflow_can_be_published(workflow_action: Action, context: str = "publier") -> None:
    """
    Ensure all referenced actions in a workflow are published (not disabled).
    Prevents publishing a workflow whose step actions are disabled (avoids runtime errors).
    Raises BadRequestError with details if any referenced action is missing or not published.
    context: verb for messages (e.g. "publier", "réactiver").
    """
    from executions.utils import extract_workflow_referenced_action_ids

    ref_ids = extract_workflow_referenced_action_ids(workflow_action)
    if not ref_ids:
        return

    int_ref_ids = [int(r) for r in ref_ids]
    found_actions: dict[int, Action] = Action.objects.in_bulk(int_ref_ids)
    missing: list[int] = []
    not_published: list[dict[str, Any]] = []
    for ref_id in int_ref_ids:
        ref_action = found_actions.get(ref_id)
        if ref_action is None:
            missing.append(ref_id)
            continue
        if ref_action.status != ActionStatus.PUBLISHED:
            not_published.append({
                "referenced_action_id": ref_id,
                "action_name": ref_action.name,
                "status": ref_action.status,
            })

    if missing:
        if len(missing) == 1:
            msg = (
                f"Impossible de {context} le workflow : l'action référencée (id {missing[0]}) "
                "n'existe pas ou n'est plus disponible."
            )
        else:
            ids_str = ", ".join(str(i) for i in missing)
            msg = f"Impossible de {context} le workflow : les actions référencées ({ids_str}) n'existent pas."
        raise BadRequestError(
            code="REFERENCED_ACTION_NOT_FOUND",
            message=msg,
            details={
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "missing_referenced_action_ids": missing,
            },
        )

    if not_published:
        first = not_published[0]
        if len(not_published) == 1:
            msg = (
                f"Impossible de {context} le workflow : l'action référencée « {first['action_name']} » "
                f"n'est pas publiée (statut: {first['status']}). Réactivez-la ou retirez-la du workflow."
            )
        else:
            parts = [f"« {p['action_name']} » (statut: {p['status']})" for p in not_published]
            msg = (
                f"Impossible de {context} le workflow : les actions référencées ne sont pas toutes publiées : "
                f"{', '.join(parts)}. Réactivez-les ou retirez-les du workflow."
            )
        raise BadRequestError(
            code="REFERENCED_ACTION_NOT_PUBLISHED",
            message=msg,
            details={
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "not_published": not_published,
            },
        )


def _validate_transition(current_status: str, transition: str) -> str:
    """
    Validate status transition and return new status.
    
    Args:
        current_status: Current status value
        transition: Transition name (publish, disable, enable)
    
    Returns:
        New status value
    
    Raises:
        InvalidTransitionError: If transition is invalid
    """
    transitions = _VALID_TRANSITIONS.get(current_status) or {}  # type: ignore[call-overload]
    if transition not in transitions:
        raise InvalidTransitionError(
            f"Transition '{transition}' invalide pour le statut '{current_status}'. "
            f"Transitions autorisées: {list(transitions.keys())}"
        )
    return cast(str, transitions[transition])


class CatalogService:
    """
    Service for catalog business logic.
    Handles complex operations that require transactions, validations, and audit.
    """
    
    @transaction.atomic
    def create_action(self, action_data: dict[str, Any], created_by_user: User) -> Action:
        """
        Create a new action with tags and audit.

        Args:
            action_data: Dict with action fields (name, description, engine, etc.)
            created_by_user: User instance creating the action

        Returns:
            Action instance
        """
        correlation_id = get_correlation_id()

        # Validation: initial status must be draft or published
        status = action_data.get('status', ActionStatus.DRAFT)
        if status not in [ActionStatus.DRAFT, ActionStatus.PUBLISHED]:
            raise ValueError("Statut initial doit être draft ou published")

        # Story 29.4: Resolve integration_id to Integration FK
        # Story 30.8 ERR-3: Raise ValidationError instead of silent pass
        integration = None
        integration_id = action_data.get('integration_id')
        if integration_id:
            from integrations.models import Integration
            try:
                integration = Integration.objects.get(id=integration_id)
            except Integration.DoesNotExist:
                logger.warning(
                    "integration_not_found",
                    integration_id=integration_id,
                    user_id=created_by_user.id,
                    correlation_id=correlation_id,
                )
                raise ValueError(f"Integration {integration_id} not found")

        # Create the action
        action = Action.objects.create(
            name=action_data['name'],
            description=action_data.get('description'),
            category=action_data.get('category'),
            engine=action_data.get('engine'),
            platform=action_data.get('platform'),
            status=status,
            item_type=action_data.get('item_type', ActionItemType.ACTION),
            created_by=created_by_user,
            documentation_md=action_data.get('documentation_md'),
            default_impact_level=action_data.get('default_impact_level'),
            integration=integration,
        )

        # Log action creation
        logger.info(
            "action_created",
            action_id=action.id,
            action_name=action.name,
            user_id=created_by_user.id,
            status=status,
            correlation_id=correlation_id
        )
        
        # Set JSON fields (OracleJSONField handles serialization automatically)
        # Normalize empty strings to None - OracleJSONField rejects "" as invalid JSON
        def _json_value(val: Any) -> Any:
            if val is None or (isinstance(val, str) and not val.strip()):
                return None
            return val

        if 'parameters_schema' in action_data:
            action.parameters_schema = _json_value(action_data['parameters_schema'])
        if 'impact_rules' in action_data:
            action.impact_rules = _json_value(action_data['impact_rules'])
        if 'execution_steps' in action_data:
            action.execution_steps = _json_value(action_data['execution_steps'])
        if 'change_type_config' in action_data:
            ctc = _json_value(action_data['change_type_config'])
            if ctc is not None:
                from catalog.validators import validate_change_type_config
                validate_change_type_config(ctc)
            action.change_type_config = ctc
        if 'gate_config' in action_data:
            gc = _json_value(action_data['gate_config'])
            if gc is not None:
                from catalog.validators import validate_gate_config
                validate_gate_config(gc)
            action.gate_config = gc
        if 'remediation_rules' in action_data:
            action.remediation_rules = _json_value(action_data['remediation_rules'])

        # Workflow: cannot create as published if any referenced action is disabled or missing
        if status == ActionStatus.PUBLISHED and action.item_type == ActionItemType.WORKFLOW and action.execution_steps:
            _validate_workflow_can_be_published(action)

        action.save()
        
        # Add tags if provided
        if 'tags' in action_data and action_data['tags']:
            self._sync_tags(action, action_data['tags'])
        
        # Audit
        AuditService.create_entry(
            user_id=str(created_by_user.id),
            action_type=AuditActionType.ACTION_CREATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={'name': action.name, 'status': action.status},
            correlation_id=correlation_id
        )

        return action  # type: ignore[no-any-return]
    
    def _sync_tags(self, action: Action, tag_names: list[str]) -> None:
        """
        Synchronize tags for an action.

        Args:
            action: Action instance
            tag_names: List of tag name strings
        """
        # Remove existing tags
        ActionTag.objects.filter(action=action).delete()
        
        # Create or retrieve tags and associate them
        for tag_name in tag_names:
            normalized = normalize_tag_name(tag_name)
            if not normalized:
                continue

            tag, created = Tag.objects.get_or_create(name=normalized)
            ActionTag.objects.create(action=action, tag=tag)
    
    def list_all(
        self,
        status: str | None = None,
        tags_filter: list[str] | None = None,
        item_type: str | None = None,
        page: int = 1,
        page_size: int = 25
    ) -> tuple[list[Action], dict[str, Any]]:
        """
        List all actions with pagination and filters.

        Args:
            status: Optional status filter
            tags_filter: Optional list of tag names (AND logic)
            item_type: Optional item type filter (action or workflow)
            page: Page number (1-based)
            page_size: Number of items per page

        Returns:
            Tuple of (list of Action instances, PaginationInfo dict)
        """
        queryset = Action.objects.all()
        
        if status:
            queryset = queryset.filter(status=status)
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        if tags_filter:
            # Code Review 30.1: Log filter application for observability
            logger.debug(
                "catalog_list_all_applying_tags_filter",
                tags_filter=tags_filter,
                current_queryset_count=queryset.count(),
            )
            queryset = queryset.search_by_tags(tags_filter)
            logger.debug(
                "catalog_list_all_after_tags_filter",
                result_count=queryset.count(),
            )
        
        # Prefetch tags to avoid N+1
        queryset = queryset.with_tags().with_creator()
        
        # Order by created_at DESC
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        pagination_info = {
            'page': page,
            'page_size': page_size,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
        }
        
        return list(page_obj), pagination_info
    
    def get_by_id(self, action_id: int) -> Action | None:
        """
        Get action by ID with prefetched relations.

        Args:
            action_id: ID of the action

        Returns:
            Action instance or None
        """
        try:
            return Action.objects.with_tags().with_creator().get(id=action_id)  # type: ignore[no-any-return]
        except Action.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_action(self, action_id: int, action_update_data: dict[str, Any], user: User) -> Action | None:
        """
        Update action metadata (allowed for all statuses).

        Args:
            action_id: ID of the action to update
            action_update_data: Dict with fields to update
            user: User instance performing the update

        Returns:
            Updated Action instance or None if not found
        """
        try:
            # Story 30.7 (RACE-2): select_for_update() serializes concurrent updates
            action = Action.objects.select_for_update().get(id=action_id)
        except Action.DoesNotExist:
            return None

        # Update fields
        if 'name' in action_update_data:
            action.name = action_update_data['name']
        if 'description' in action_update_data:
            action.description = action_update_data.get('description')
        if 'engine' in action_update_data:
            action.engine = action_update_data['engine']
        if 'platform' in action_update_data:
            action.platform = action_update_data['platform']
        if 'documentation_md' in action_update_data:
            action.documentation_md = action_update_data.get('documentation_md')
        if 'default_impact_level' in action_update_data:
            action.default_impact_level = action_update_data.get('default_impact_level')
        # Story 29.4 Code Review Fix MEDIUM-1: Update integration if provided
        # Story 30.8 ERR-3: Raise ValueError instead of silent pass
        if 'integration_id' in action_update_data:
            integration_id = action_update_data.get('integration_id')
            if integration_id:
                from integrations.models import Integration
                try:
                    action.integration = Integration.objects.get(id=integration_id)
                except Integration.DoesNotExist:
                    # Fix MEDIUM-1: Add correlation_id for consistency
                    correlation_id = get_correlation_id()
                    logger.warning(
                        "integration_not_found",
                        integration_id=integration_id,
                        user_id=user.id,
                        correlation_id=correlation_id,
                    )
                    raise ValueError(f"Integration {integration_id} not found")
            else:
                action.integration = None

        # Update JSON fields (OracleJSONField handles serialization automatically)
        if 'parameters_schema' in action_update_data:
            action.parameters_schema = action_update_data['parameters_schema']
        if 'impact_rules' in action_update_data:
            action.impact_rules = action_update_data['impact_rules']
        if 'remediation_rules' in action_update_data:
            action.remediation_rules = action_update_data['remediation_rules']
        # Story 31.6: gate_config (validated by serializer)
        if 'gate_config' in action_update_data:
            action.gate_config = action_update_data['gate_config']

        action.save()
        
        # Update tags if provided
        if 'tags' in action_update_data:
            self._sync_tags(action, action_update_data['tags'])
        
        # Audit
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.ACTION_UPDATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={'name': action.name}
        )

        return action  # type: ignore[no-any-return]

    @transaction.atomic
    def update_status(self, action_id: int, transition: str, user: User) -> Action | None:
        """
        Update action status via a valid transition.

        Story 30.7 (RACE-2): Uses select_for_update() to serialize concurrent
        status transitions on the same action.

        Args:
            action_id: ID of the action
            transition: Transition name (publish, disable, enable)
            user: User instance performing the transition

        Returns:
            Updated Action instance or None if not found

        Raises:
            InvalidTransitionError: If transition is invalid
        """
        try:
            # Story 30.7 (RACE-2): select_for_update() serializes concurrent transitions
            action = Action.objects.select_for_update().get(id=action_id)
        except Action.DoesNotExist:
            return None
        
        # Validate transition
        new_status = _validate_transition(action.status, transition)

        # Workflow: cannot publish or enable if any referenced action is disabled or missing
        if action.item_type == ActionItemType.WORKFLOW and transition in ('publish', 'enable'):
            _validate_workflow_can_be_published(action, context="réactiver" if transition == "enable" else "publier")
        
        # Update status
        old_status = action.status
        action.status = new_status
        action.save()
        
        # Map transition to audit action type
        audit_action_map = {
            'publish': AuditActionType.ACTION_PUBLISHED,
            'disable': AuditActionType.ACTION_DISABLED,
            'enable': AuditActionType.ACTION_ENABLED,
        }
        
        # Audit
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=audit_action_map[transition],
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            details={
                'previous_status': old_status,
                'new_status': new_status,
                'transition': transition,
            }
        )

        return action  # type: ignore[no-any-return]

    def count_executions(self, action_id: int) -> int:
        """Count total executions for an action."""
        from executions.models import Execution
        return Execution.objects.filter(action_id=action_id).count()

    @transaction.atomic
    def delete_action(self, action_id: int, user: User | None = None) -> bool:
        """
        Hard-delete an action — only allowed if execution_count == 0 (Story 18.1, AC1).

        Story 30.7 (RACE-2): Uses select_for_update() to serialize concurrent deletes.

        Raises:
            ConflictError: If action has any executions (past or current).
        """
        try:
            # Story 30.7 (RACE-2): select_for_update() serializes concurrent deletes
            action = Action.objects.select_for_update().get(id=action_id)
        except Action.DoesNotExist:
            return False

        execution_count = self.count_executions(action_id)
        if execution_count > 0:
            raise ConflictError(
                code="EXECUTION_EXISTS",
                message="Impossible de supprimer une action ayant des exécutions passées",
                details={"execution_count": execution_count},
            )

        action_name = action.name
        action_status = action.status
        action.delete()

        if user:
            correlation_id = get_correlation_id()
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.ACTION_DELETED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action_id,
                details={'name': action_name, 'status': action_status},
                correlation_id=correlation_id,
            )

        return True

    @transaction.atomic
    def deactivate_action(
        self, action_id: int, user: User, deletion_reason: str | None = None
    ) -> dict[str, Any] | None:
        """
        Soft-delete (deactivate) an action (Story 18.1, AC2).
        Story 30.7 (RACE-2): Uses select_for_update() to serialize concurrent deactivations.
        """
        try:
            # Story 30.7 (RACE-2): select_for_update() serializes concurrent deactivations
            action = Action.objects.select_for_update().get(id=action_id)
        except Action.DoesNotExist:
            return None

        if action.status == ActionStatus.DISABLED:
            raise ConflictError(
                code="ALREADY_DISABLED",
                message="Cette action est déjà désactivée",
                details={"action_id": action_id},
            )

        # Find workflows referencing this action (AC3)
        affected_workflows = self._find_workflows_referencing_action(action_id)

        # Perform deactivation — timestamp fixe pour cohérence avec la cascade (SOC1)
        now = timezone.now()
        action.status = ActionStatus.DISABLED
        action.deleted_at = now
        action.deleted_by = user
        action.deletion_reason = deletion_reason
        action.save()

        correlation_id = get_correlation_id()
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.ACTION_DEACTIVATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action_id,
            details={
                'name': action.name,
                'deletion_reason': deletion_reason,
            },
            correlation_id=correlation_id,
        )

        # Cascade deactivation to workflows (AC3)
        # NEW-BE-9: Préparer + bulk_update (N+1 → 1) + audits individuels (SOC1)
        # now est déjà défini ci-dessus (timestamp partagé action + cascade)
        deactivated_workflows = []
        for wf in affected_workflows:
            wf.status = ActionStatus.DISABLED
            wf.deleted_at = now
            wf.deleted_by = user
            wf.deletion_reason = f"Cascade: action '{action.name}' désactivée"
            wf.updated_at = now
            deactivated_workflows.append({'id': wf.id, 'name': wf.name})

        if affected_workflows:
            Action.objects.bulk_update(
                affected_workflows,
                ['status', 'deleted_at', 'deleted_by', 'deletion_reason', 'updated_at']
            )

        for wf in affected_workflows:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.ACTION_DEACTIVATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=wf.id,
                details={
                    'name': wf.name,
                    'cascade_from_action_id': action_id,
                    'cascade_from_action_name': action.name,
                },
                correlation_id=correlation_id,
            )

        return {
            'action': action,
            'deactivated_workflows': deactivated_workflows,
        }

    @transaction.atomic
    def reactivate_action(self, action_id: int, user: User) -> Action | None:
        """
        Reactivate a disabled action (Story 18.1, AC5).
        Resets status to 'published', clears soft-delete fields.
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None

        if action.status != ActionStatus.DISABLED:
            raise ConflictError(
                code="NOT_DISABLED",
                message="Seule une action désactivée peut être réactivée",
                details={"current_status": action.status},
            )

        # Workflow: cannot reactivate if any referenced action is disabled or missing
        if action.item_type == ActionItemType.WORKFLOW:
            _validate_workflow_can_be_published(action, context="réactiver")

        action.status = ActionStatus.PUBLISHED
        action.deleted_at = None
        action.deleted_by = None
        action.deletion_reason = None
        action.save()

        correlation_id = get_correlation_id()
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.ACTION_REACTIVATED,
            entity_type=AuditEntityType.ACTION,
            entity_id=action_id,
            details={'name': action.name},
            correlation_id=correlation_id,
        )

        return action  # type: ignore[no-any-return]

    def get_workflows_referencing_action(self, action_id: int) -> list[dict[str, Any]]:
        """Return list of workflow dicts referencing the given action (Story 18.1, AC3)."""
        workflows = self._find_workflows_referencing_action(action_id)
        return [{'id': w.id, 'name': w.name, 'status': w.status} for w in workflows]

    def _find_workflows_referencing_action(self, action_id: int) -> list[Action]:
        """Find workflows whose execution_steps reference the given action_id.

        Optimized: uses DB-side text filter on execution_steps (OracleJSONField stored as CLOB)
        to pre-filter candidates, then validates in Python for exact match accuracy.
        This avoids loading ALL workflows into memory.

        Performance trade-off: execution_steps__contains=str(action_id) may return false positives
        (e.g., action_id=42 matches "421" or "step_42" in JSON). Python validation filters these out.
        In worst case (many false positives), this still outperforms loading all workflows.
        For tighter filtering, consider raw SQL with JSON_EXISTS (Oracle 19c+).
        """
        # DB-side pre-filter: execution_steps CLOB contains the action_id string
        # This may include false positives, which are filtered out below
        candidates = Action.objects.filter(
            item_type=ActionItemType.WORKFLOW,
            status__in=[ActionStatus.DRAFT, ActionStatus.PUBLISHED],
            execution_steps__contains=str(action_id),
        )
        result = []
        for wf in candidates:
            steps = wf.execution_steps
            if not steps or not isinstance(steps, list):
                continue
            for step in steps:
                if isinstance(step, dict) and step.get('referenced_action_id') == action_id:
                    result.append(wf)
                    break
        return result
    
    def add_tags(self, action_id: int, tag_names: list[str]) -> Action | None:
        """
        Add tags to an action.

        Args:
            action_id: ID of the action
            tag_names: List of tag names to add
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None
        
        for tag_name in tag_names:
            normalized = normalize_tag_name(tag_name)
            if not normalized:
                continue
            tag, created = Tag.objects.get_or_create(name=normalized)
            ActionTag.objects.get_or_create(action=action, tag=tag)

        return action  # type: ignore[no-any-return]

    def remove_tags(self, action_id: int, tag_names: list[str]) -> Action | None:
        """
        Remove tags from an action.

        Args:
            action_id: ID of the action
            tag_names: List of tag names to remove
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None
        
        for tag_name in tag_names:
            normalized = normalize_tag_name(tag_name)
            try:
                tag = Tag.objects.get(name=normalized)
                ActionTag.objects.filter(action=action, tag=tag).delete()
            except Tag.DoesNotExist:
                pass

        return action  # type: ignore[no-any-return]

    def sync_tags(self, action_id: int, tag_names: list[str]) -> Action | None:
        """
        Synchronize tags for an action (replace all existing tags).

        Args:
            action_id: ID of the action
            tag_names: List of tag names to set
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None

        self._sync_tags(action, tag_names)
        return action  # type: ignore[no-any-return]

    def search_by_tags(self, tag_names: list[str], status: str | None = None) -> QuerySet[Action]:
        """
        Search actions by tags with AND logic.

        Args:
            tag_names: List of tag names (action must have all)
            status: Optional status filter

        Returns:
            QuerySet of actions matching all tags
        """
        queryset = Action.objects.search_by_tags(tag_names)
        if status:
            queryset = queryset.filter(status=status)
        return queryset.with_tags().with_creator()  # type: ignore[no-any-return]
    
    @transaction.atomic
    def update_execution_steps(
        self,
        action_id: int,
        steps: list[dict[str, Any]],
        change_type_config: dict[str, Any] | None = None,
        user: User | None = None
    ) -> Action | None:
        """
        Update execution steps and change type config for an action.
        Only allowed for actions in draft or disabled status.

        Story 16.2: Validates workflow steps with branches and retry configuration.

        Args:
            action_id: ID of the action
            steps: List of execution step dicts
            change_type_config: Optional change type config dict
            user: User instance (for audit)

        Returns:
            Updated Action instance or None if not found

        Raises:
            ValueError: If action is not in draft status
            serializers.ValidationError: If workflow steps validation fails
        """
        from catalog.validation import validate_workflow_steps

        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None

        # Check status: only draft or disabled actions can have execution steps updated
        if action.status not in [ActionStatus.DRAFT, ActionStatus.DISABLED]:
            raise ValueError("Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée")

        # Update execution_steps if provided
        if steps is not None:
            # Story 16.2: Validate workflow steps if item_type is workflow
            if action.item_type == ActionItemType.WORKFLOW:
                steps = validate_workflow_steps(steps, action_id=action.id)

            # Story 25.2: Validate gate_conditions in execution steps
            from catalog.validators import validate_gate_conditions
            for step in steps:
                if isinstance(step, dict) and 'gate_conditions' in step:
                    validate_gate_conditions(step['gate_conditions'])

            action.execution_steps = steps

        # Update change_type_config if provided (Story 25.4: validated)
        if change_type_config is not None:
            from catalog.validators import validate_change_type_config
            validate_change_type_config(change_type_config)
            action.change_type_config = change_type_config

        action.save()

        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.ACTION_UPDATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action.id,
                details={'updated_fields': ['execution_steps', 'change_type_config']}
            )

        return action  # type: ignore[no-any-return]
