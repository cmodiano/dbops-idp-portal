"""
SchedulingService for business logic related to scheduled executions.

Handles creation, listing, cancellation, and status updates of scheduled executions
and recurring patterns.

Story 34.3 - SOLID-BE-4: Extracted from executions/services.py (SRP).
ExecutionService (Execution entity) and SchedulingService (ScheduledExecution entity)
had no shared state — split into separate modules following Single Responsibility Principle.
"""

import json

from datetime import datetime

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from executions.models import (
    RecurringPattern,
    ScheduledExecution, ScheduledExecutionStatus,
)
from catalog.models import Action
from idp_auth.models import User
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id
from core.pagination import MAX_PAGE_SIZE
from core.utils import ensure_utc_isoformat, sanitize_audit_changes
from executions.utils import calculate_next_execution_date


class SchedulingService:
    """
    Service for scheduled execution business logic.
    Handles creation, listing, and updates of scheduled executions and recurring patterns.
    """
    
    @transaction.atomic
    def create_scheduled_execution(self, user: User, action: Action, environment: str,
                                  parameters: dict | None = None, scheduled_at: datetime | None = None,
                                  recurring_pattern_data: dict | None = None) -> ScheduledExecution:
        """
        Create a scheduled execution, optionally with a recurring pattern.
        
        Args:
            user: User instance
            action: Action instance
            environment: Target environment
            parameters: Optional execution parameters dict
            scheduled_at: Optional scheduled datetime (for one-time executions)
            recurring_pattern_data: Optional dict with pattern_type, pattern_config, next_execution_date
        
        Returns:
            ScheduledExecution instance
        """
        scheduled_execution = ScheduledExecution.objects.create(
            action=action,
            user=user,
            environment=environment,
            scheduled_at=scheduled_at,
            status=ScheduledExecutionStatus.PENDING,
        )
        
        # Set parameters if provided
        if parameters:
            scheduled_execution.set_parameters(parameters)
            scheduled_execution.save()
        
        # Create recurring pattern if provided
        correlation_id = get_correlation_id()
        if recurring_pattern_data:
            RecurringPattern.objects.create(
                scheduled_execution=scheduled_execution,
                pattern_type=recurring_pattern_data['pattern_type'],
                pattern_config=json.dumps(recurring_pattern_data.get('pattern_config')) if recurring_pattern_data.get('pattern_config') else None,
                next_execution_date=recurring_pattern_data['next_execution_date'],
                is_active=recurring_pattern_data.get('is_active', 1),
            )
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.SCHEDULED_EXECUTION_RECURRING_CREATED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
                entity_id=scheduled_execution.id,
                details={
                    'action_id': action.id,
                    'action_name': action.name,
                    'environment': environment,
                    'pattern_type': recurring_pattern_data['pattern_type'],
                },
                correlation_id=correlation_id,
            )
        else:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.SCHEDULED_EXECUTION_CREATED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
                entity_id=scheduled_execution.id,
                details={
                    'action_id': action.id,
                    'action_name': action.name,
                    'environment': environment,
                    'scheduled_at': ensure_utc_isoformat(scheduled_at),
                },
                correlation_id=correlation_id,
            )
        
        return scheduled_execution
    
    def list_all(self, status: str | None = None, user_id: int | None = None,
                action_id: int | None = None, scheduled_from: datetime | None = None,
                scheduled_to: datetime | None = None, page: int = 1, page_size: int = 25) -> tuple[list[ScheduledExecution], int]:
        """
        List all scheduled executions with filters and pagination.
        
        Args:
            status: Filter by status
            user_id: Filter by user ID
            action_id: Filter by action ID
            scheduled_from: Filter by scheduled_at >= scheduled_from
            scheduled_to: Filter by scheduled_at <= scheduled_to
            page: Page number (1-based)
            page_size: Number of items per page
        
        Returns:
            Tuple of (list of scheduled executions, total count)
        """
        queryset = ScheduledExecution.objects.select_related('action', 'user').prefetch_related('recurringpattern')
        
        if status:
            queryset = queryset.filter(status=status)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action_id:
            queryset = queryset.filter(action_id=action_id)
        if scheduled_from:
            queryset = queryset.filter(
                Q(scheduled_at__gte=scheduled_from) | Q(recurringpattern__next_execution_date__gte=scheduled_from)
            )
        if scheduled_to:
            queryset = queryset.filter(
                Q(scheduled_at__lte=scheduled_to) | Q(recurringpattern__next_execution_date__lte=scheduled_to)
            )
        
        queryset = queryset.order_by('scheduled_at', 'recurringpattern__next_execution_date').distinct()

        # MED-01: Cap page_size to prevent unbounded queries
        page_size = min(page_size, MAX_PAGE_SIZE)

        # Pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        results = list(queryset[start_index:end_index])
        
        return results, total_count
    
    def get_by_id(self, scheduled_execution_id: int) -> ScheduledExecution | None:
        """
        Get scheduled execution by ID with recurring pattern preloaded.
        
        Args:
            scheduled_execution_id: ID of the scheduled execution
        
        Returns:
            ScheduledExecution instance or None
        """
        try:
            return ScheduledExecution.objects.select_related('action', 'user').prefetch_related('recurringpattern').get(id=scheduled_execution_id)
        except ScheduledExecution.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_status(self, scheduled_execution_id: int, new_status: str, user_id: str) -> ScheduledExecution | None:
        """
        Update scheduled execution status.
        For recurring patterns, recalculates next_execution_date if needed.
        
        Args:
            scheduled_execution_id: ID of the scheduled execution
            new_status: New status value
            user_id: ID of user making the change
        
        Returns:
            Updated ScheduledExecution instance or None
        """
        try:
            scheduled_execution = ScheduledExecution.objects.select_related('recurringpattern').get(id=scheduled_execution_id)
        except ScheduledExecution.DoesNotExist:
            return None
        
        old_status = scheduled_execution.status
        scheduled_execution.status = new_status
        scheduled_execution.updated_at = timezone.now()
        scheduled_execution.save()
        
        # If it's a recurring pattern and status changed to EXECUTED, update next_execution_date
        # MED-03: Use try/except instead of hasattr() — Django OneToOne raises DoesNotExist,
        # not AttributeError, so hasattr() is unreliable for optional reverse relations.
        pattern = None
        try:
            pattern = scheduled_execution.recurringpattern
        except RecurringPattern.DoesNotExist:
            pass
        if pattern is not None and new_status == ScheduledExecutionStatus.EXECUTED:
            if pattern.is_active == 1:
                pattern_config = pattern.get_pattern_config() or {}
                pattern.next_execution_date = calculate_next_execution_date(
                    pattern.pattern_type, pattern_config, timezone.now()
                )
                pattern.updated_at = timezone.now()
                pattern.save()
        
        # Map status to audit action type enum
        status_to_audit_type = {
            ScheduledExecutionStatus.EXECUTED: AuditActionType.SCHEDULED_EXECUTION_EXECUTED,
            ScheduledExecutionStatus.CANCELLED: AuditActionType.SCHEDULED_EXECUTION_CANCELLED,
        }
        audit_action_type = status_to_audit_type.get(new_status)  # type: ignore[call-overload]
        if audit_action_type:
            changes = sanitize_audit_changes({'status': {'old': old_status, 'new': new_status}})
            AuditService.create_entry(
                user_id=user_id,
                action_type=audit_action_type,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
                entity_id=scheduled_execution.id,
                details={
                    'action_id': scheduled_execution.action_id,
                    'action_name': scheduled_execution.action.name if scheduled_execution.action else None,
                    'changes': changes,
                }
            )
        
        return scheduled_execution
    
    def list_pending(self, before_datetime: datetime | None = None) -> QuerySet:
        """
        List scheduled executions pending for external scheduler.
        Includes one-time (scheduled_at <= before) and active recurring (next_execution_date <= before).
        
        Args:
            before_datetime: Datetime threshold (defaults to now)
        
        Returns:
            QuerySet of pending scheduled executions
        """
        if before_datetime is None:
            before_datetime = timezone.now()
        
        return ScheduledExecution.objects.list_pending(before_datetime)
    
    @transaction.atomic
    def cancel_scheduled_execution(self, scheduled_execution_id: int, user_id: str) -> ScheduledExecution | None:
        """
        Cancel a scheduled execution.
        
        Args:
            scheduled_execution_id: ID of the scheduled execution
            user_id: ID of user cancelling
        
        Returns:
            Updated ScheduledExecution instance or None
        """
        try:
            scheduled_execution = ScheduledExecution.objects.select_related('recurringpattern').get(id=scheduled_execution_id)
        except ScheduledExecution.DoesNotExist:
            return None
        
        scheduled_execution.status = ScheduledExecutionStatus.CANCELLED
        scheduled_execution.updated_at = timezone.now()
        scheduled_execution.save()
        
        # If it's a recurring pattern, deactivate it
        if hasattr(scheduled_execution, 'recurringpattern'):
            pattern = scheduled_execution.recurringpattern
            pattern.is_active = 0
            pattern.updated_at = timezone.now()
            pattern.save()
            AuditService.create_entry(
                user_id=user_id,
                action_type=AuditActionType.SCHEDULED_EXECUTION_RECURRING_DISABLED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
                entity_id=scheduled_execution.id,
                details={
                    'action_id': scheduled_execution.action_id,
                    'action_name': scheduled_execution.action.name if scheduled_execution.action else None,
                    'environment': scheduled_execution.environment,
                }
            )
        else:
            AuditService.create_entry(
                user_id=user_id,
                action_type=AuditActionType.SCHEDULED_EXECUTION_CANCELLED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
                entity_id=scheduled_execution.id,
                details={
                    'action_id': scheduled_execution.action_id,
                    'action_name': scheduled_execution.action.name if scheduled_execution.action else None,
                    'environment': scheduled_execution.environment,
                }
            )
        
        return scheduled_execution
