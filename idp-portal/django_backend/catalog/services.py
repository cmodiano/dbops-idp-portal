"""
CatalogService for business logic related to actions and workflows.
Handles complex operations like status transitions, tag management, and validation.
"""

import logging
from django.db import transaction
from django.db.models import Q, Prefetch
from django.core.paginator import Paginator
from catalog.models import Action, ActionStatus, Tag, ActionTag, ActionItemType
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType

logger = logging.getLogger(__name__)


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
    transitions = _VALID_TRANSITIONS.get(current_status, {})
    if transition not in transitions:
        raise InvalidTransitionError(
            f"Transition '{transition}' invalide pour le statut '{current_status}'. "
            f"Transitions autorisées: {list(transitions.keys())}"
        )
    return transitions[transition]


class CatalogService:
    """
    Service for catalog business logic.
    Handles complex operations that require transactions, validations, and audit.
    """
    
    @transaction.atomic
    def create_action(self, action_data, created_by_user):
        """
        Create a new action with tags and audit.
        
        Args:
            action_data: Dict with action fields (name, description, engine, etc.)
            created_by_user: User instance creating the action
        
        Returns:
            Action instance
        """
        # Validation: initial status must be draft or published
        status = action_data.get('status', ActionStatus.DRAFT)
        if status not in [ActionStatus.DRAFT, ActionStatus.PUBLISHED]:
            raise ValueError("Statut initial doit être draft ou published")
        
        # Create the action
        action = Action.objects.create(
            name=action_data['name'],
            description=action_data.get('description'),
            engine=action_data.get('engine'),
            platform=action_data.get('platform'),
            status=status,
            item_type=action_data.get('item_type', ActionItemType.ACTION),
            created_by=created_by_user,
            documentation_md=action_data.get('documentation_md'),
            default_impact_level=action_data.get('default_impact_level'),
        )
        
        # Set JSON fields using helper methods
        if 'parameters_schema' in action_data:
            action.set_parameters_schema(action_data['parameters_schema'])
        if 'impact_rules' in action_data:
            action.set_impact_rules(action_data['impact_rules'])
        if 'execution_steps' in action_data:
            action.set_execution_steps(action_data['execution_steps'])
        if 'change_type_config' in action_data:
            action.set_change_type_config(action_data['change_type_config'])
        if 'remediation_rules' in action_data:
            action.set_remediation_rules(action_data['remediation_rules'])
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
            details={'name': action.name, 'status': action.status}
        )
        
        return action
    
    def _sync_tags(self, action, tag_names):
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
            # Normalize tag name (lowercase, no spaces)
            normalized = tag_name.lower().strip().replace(' ', '_')
            if not normalized:
                continue
            
            tag, created = Tag.objects.get_or_create(name=normalized)
            ActionTag.objects.create(action=action, tag=tag)
    
    def list_all(self, status=None, tags_filter=None, item_type=None, 
                 page=1, page_size=25):
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
            queryset = Action.objects.search_by_tags(tags_filter)
        
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
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
        }
        
        return list(page_obj), pagination_info
    
    def get_by_id(self, action_id: int):
        """
        Get action by ID with prefetched relations.
        
        Args:
            action_id: ID of the action
        
        Returns:
            Action instance or None
        """
        try:
            return Action.objects.with_tags().with_creator().get(id=action_id)
        except Action.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_action(self, action_id: int, action_update_data, user):
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
            action = Action.objects.get(id=action_id)
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
        
        # Update JSON fields
        if 'parameters_schema' in action_update_data:
            action.set_parameters_schema(action_update_data['parameters_schema'])
        if 'impact_rules' in action_update_data:
            action.set_impact_rules(action_update_data['impact_rules'])
        if 'remediation_rules' in action_update_data:
            action.set_remediation_rules(action_update_data['remediation_rules'])
        
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
        
        return action
    
    @transaction.atomic
    def update_status(self, action_id: int, transition: str, user):
        """
        Update action status via a valid transition.
        
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
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None
        
        # Validate transition
        new_status = _validate_transition(action.status, transition)
        
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
        
        return action
    
    @transaction.atomic
    def delete_action(self, action_id: int, user=None):
        """
        Delete an action after checking dependencies.
        
        Args:
            action_id: ID of the action to delete
            user: Optional user instance for audit
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If action has dependencies (executions in progress)
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return False
        
        # Check for dependencies: executions in progress
        from executions.models import Execution, ExecutionStatus
        running_executions = Execution.objects.filter(
            action_id=action_id,
            status__in=[ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING, ExecutionStatus.PENDING_APPROVAL]
        ).exists()
        
        if running_executions:
            raise ValueError("Impossible de supprimer une action avec des exécutions en cours")
        
        # Store action details for audit before deletion
        action_name = action.name
        action_status = action.status
        
        # Delete the action
        action.delete()
        
        # Audit
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.ACTION_DELETED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action_id,
                details={
                    'name': action_name,
                    'status': action_status,
                }
            )
        
        return True
    
    def add_tags(self, action_id: int, tag_names: list[str]):
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
            normalized = tag_name.lower().strip().replace(' ', '_')
            if not normalized:
                continue
            tag, created = Tag.objects.get_or_create(name=normalized)
            ActionTag.objects.get_or_create(action=action, tag=tag)
        
        return action
    
    def remove_tags(self, action_id: int, tag_names: list[str]):
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
            normalized = tag_name.lower().strip().replace(' ', '_')
            try:
                tag = Tag.objects.get(name=normalized)
                ActionTag.objects.filter(action=action, tag=tag).delete()
            except Tag.DoesNotExist:
                pass
        
        return action
    
    def sync_tags(self, action_id: int, tag_names: list[str]):
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
        return action
    
    def search_by_tags(self, tag_names: list[str], status=None):
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
        return queryset.with_tags().with_creator()
    
    @transaction.atomic
    def update_execution_steps(self, action_id: int, steps: list[dict], 
                               change_type_config: dict | None = None, user=None):
        """
        Update execution steps and change type config for an action.
        Only allowed for actions in draft status.
        
        Args:
            action_id: ID of the action
            steps: List of execution step dicts
            change_type_config: Optional change type config dict
            user: User instance (for audit)
        
        Returns:
            Updated Action instance or None if not found
        
        Raises:
            ValueError: If action is not in draft status
        """
        try:
            action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            return None
        
        # Check status: only draft actions can have execution steps updated
        if action.status != ActionStatus.DRAFT:
            raise ValueError("Les étapes ne peuvent être modifiées que pour une action en brouillon")
        
        # Update execution_steps if provided
        if steps is not None:
            action.set_execution_steps(steps)
        
        # Update change_type_config if provided
        if change_type_config is not None:
            action.set_change_type_config(change_type_config)
        
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
        
        return action
