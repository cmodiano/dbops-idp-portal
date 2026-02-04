"""
ExecutionService for business logic related to executions.
Handles complex operations like atomic execution creation with steps.
"""

import json
import logging
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
    ScheduledExecution, ScheduledExecutionStatus
)
from catalog.models import Action
from idp_auth.models import User
from core.services import AuditService

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    Service for execution business logic.
    Handles complex operations like atomic execution creation with steps.
    """
    
    @transaction.atomic
    def create_execution(self, user: User, action: Action, environment: str, 
                       parameters: dict | None = None, parent_execution_id: int | None = None):
        """
        Create an execution atomically.
        
        Args:
            user: User instance creating the execution
            action: Action instance to execute
            environment: Target environment
            parameters: Optional execution parameters dict
            parent_execution_id: Optional parent execution ID (for remediation)
        
        Returns:
            Execution instance
        """
        execution = Execution.objects.create(
            action=action,
            user=user,
            environment=environment,
            status=ExecutionStatus.SUBMITTED,
            parent_execution_id=parent_execution_id,
        )
        
        # Set parameters if provided
        if parameters:
            execution.set_parameters(parameters)
            execution.save()
        
        # Audit
        AuditService.create_entry(
            user_id=str(user.id),
            action_type='EXECUTION_SUBMITTED',
            entity_type='execution',
            entity_id=execution.id,
            details={
                'action_id': action.id,
                'action_name': action.name,
                'environment': environment,
            }
        )
        
        return execution
    
    @transaction.atomic
    def create_execution_with_steps(self, user: User, action: Action, environment: str,
                                   parameters: dict | None = None, steps_data: list[dict] | None = None,
                                   parent_execution_id: int | None = None):
        """
        Create an execution with steps atomically.
        
        Args:
            user: User instance creating the execution
            action: Action instance to execute
            environment: Target environment
            parameters: Optional execution parameters dict
            steps_data: Optional list of step data dicts
            parent_execution_id: Optional parent execution ID (for remediation)
        
        Returns:
            Execution instance with steps created
        """
        # Create the execution
        execution = self.create_execution(user, action, environment, parameters, parent_execution_id)
        
        # Create steps if provided
        if steps_data:
            for step_data in steps_data:
                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=step_data.get('step_order', 0),
                    step_name=step_data.get('step_name', 'Step'),
                    step_type=step_data.get('step_type', 'manual'),
                    status=ExecutionStepStatus.PENDING,
                )
        
        return execution
    
    def list_all(self, status: str | None = None, user_id: int | None = None,
                action_id: int | None = None, environment: str | None = None,
                date_from: datetime | None = None, date_to: datetime | None = None,
                page: int = 1, page_size: int = 25):
        """
        List all executions with pagination and filters.
        
        Args:
            status: Filter by status
            user_id: Filter by user ID
            action_id: Filter by action ID
            environment: Filter by environment
            date_from: Filter by created_at >= date_from
            date_to: Filter by created_at <= date_to
            page: Page number (1-based)
            page_size: Number of items per page
        
        Returns:
            Tuple of (list of executions, total count)
        """
        queryset = Execution.objects.select_related('action', 'user').prefetch_related('executionstep_set')
        
        # Apply filters
        if status:
            queryset = queryset.filter(status=status)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action_id:
            queryset = queryset.filter(action_id=action_id)
        if environment:
            queryset = queryset.filter(environment=environment)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Order by created_at DESC
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        results = list(queryset[start_index:end_index])
        
        return results, total_count
    
    def get_by_id(self, execution_id: int):
        """
        Get execution by ID with steps preloaded.
        
        Args:
            execution_id: ID of the execution
        
        Returns:
            Execution instance or None
        """
        try:
            return Execution.objects.select_related('action', 'user').prefetch_related('executionstep_set').get(id=execution_id)
        except Execution.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_status(self, execution_id: int, new_status: str, user_id: str):
        """
        Update execution status with transition validation.
        
        Args:
            execution_id: ID of the execution
            new_status: New status value
            user_id: ID of user making the change
        
        Returns:
            Updated Execution instance or None
        
        Raises:
            ValueError: If transition is invalid
        """
        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            return None
        
        old_status = execution.status
        
        # Validate transition (basic validation - can be enhanced)
        valid_transitions = {
            ExecutionStatus.SUBMITTED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.PENDING_APPROVAL],
            ExecutionStatus.PENDING_APPROVAL: [ExecutionStatus.SUBMITTED, ExecutionStatus.REJECTED],
            ExecutionStatus.RUNNING: [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
            ExecutionStatus.COMPLETED: [],
            ExecutionStatus.FAILED: [],
            ExecutionStatus.CANCELLED: [],
            ExecutionStatus.REJECTED: [],
        }
        
        if new_status not in valid_transitions.get(old_status, []):
            raise ValueError(f"Invalid transition from {old_status} to {new_status}")
        
        execution.status = new_status
        
        # Update timestamps
        if new_status == ExecutionStatus.RUNNING:
            execution.started_at = timezone.now()
        elif new_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.REJECTED]:
            execution.completed_at = timezone.now()
        
        execution.save()
        
        # Audit
        AuditService.create_entry(
            user_id=user_id,
            action_type=f'EXECUTION_{new_status}',
            entity_type='execution',
            entity_id=execution.id,
            details={
                'action_id': execution.action_id,
                'action_name': execution.action.name if execution.action else None,
                'previous_status': old_status,
                'new_status': new_status,
            }
        )
        
        return execution
    
    def list_by_user(self, user_id: int, status: str | None = None,
                    environment: str | None = None, action_id: int | None = None,
                    date_from: datetime | None = None, date_to: datetime | None = None,
                    limit: int | None = None, offset: int = 0):
        """
        List executions for a specific user with filters.
        
        Args:
            user_id: ID of the user
            status: Optional status filter
            environment: Optional environment filter
            action_id: Optional action ID filter
            date_from: Optional date_from filter
            date_to: Optional date_to filter
            limit: Optional limit
            offset: Offset for pagination
        
        Returns:
            QuerySet of executions
        """
        queryset = Execution.objects.list_by_user(user_id).select_related('action', 'user')
        
        if status:
            queryset = queryset.filter(status=status)
        if environment:
            queryset = queryset.filter(environment=environment)
        if action_id:
            queryset = queryset.filter(action_id=action_id)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        if offset:
            queryset = queryset[offset:]
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def get_recent(self, limit: int = 10):
        """
        Get recent executions for dashboard.
        
        Args:
            limit: Maximum number of executions to return
        
        Returns:
            QuerySet of recent executions
        """
        return Execution.objects.get_recent(limit)
    
    def get_stats(self, user_id: int | None = None, days: int = 30):
        """
        Get execution statistics with aggregations.
        
        Args:
            user_id: Optional user ID filter
            days: Number of days to look back
        
        Returns:
            Dict with statistics
        """
        date_from = timezone.now() - timedelta(days=days)
        
        queryset = Execution.objects.filter(created_at__gte=date_from)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        total = queryset.count()
        completed = queryset.filter(status=ExecutionStatus.COMPLETED).count()
        failed = queryset.filter(status=ExecutionStatus.FAILED).count()
        running = queryset.filter(status=ExecutionStatus.RUNNING).count()
        
        # Calculate success rate
        success_rate = (completed / total * 100) if total > 0 else 0
        
        # Group by status
        by_status = queryset.values('status').annotate(count=Count('id'))
        
        # Group by environment
        by_environment = queryset.values('environment').annotate(count=Count('id'))
        
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'running': running,
            'success_rate': round(success_rate, 2),
            'by_status': list(by_status),
            'by_environment': list(by_environment),
        }
    
    # ExecutionStep CRUD methods
    @transaction.atomic
    def create_step(self, execution: Execution, step_order: int, step_name: str,
                   step_type: str):
        """
        Create an execution step.
        
        Args:
            execution: Execution instance
            step_order: Order of the step
            step_name: Name of the step
            step_type: Type of the step
        
        Returns:
            ExecutionStep instance
        """
        step = ExecutionStep.objects.create(
            execution=execution,
            step_order=step_order,
            step_name=step_name,
            step_type=step_type,
            status=ExecutionStepStatus.PENDING,
        )
        return step
    
    def get_steps_by_execution(self, execution_id: int):
        """
        Get all steps for an execution.
        
        Args:
            execution_id: ID of the execution
        
        Returns:
            QuerySet of execution steps ordered by step_order
        """
        return ExecutionStep.objects.filter(execution_id=execution_id).order_by('step_order')
    
    def get_step_by_id(self, step_id: int):
        """
        Get execution step by ID.
        
        Args:
            step_id: ID of the step
        
        Returns:
            ExecutionStep instance or None
        """
        try:
            return ExecutionStep.objects.select_related('execution').get(id=step_id)
        except ExecutionStep.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_step_status(self, step_id: int, new_status: str, output: dict | None = None):
        """
        Update execution step status and output.
        
        Args:
            step_id: ID of the step
            new_status: New status value
            output: Optional output dict
        
        Returns:
            Updated ExecutionStep instance or None
        """
        try:
            step = ExecutionStep.objects.get(id=step_id)
        except ExecutionStep.DoesNotExist:
            return None
        
        step.status = new_status
        
        if output is not None:
            step.set_output(output)
        
        step.save()
        
        return step


class SchedulingService:
    """
    Service for scheduled execution business logic.
    Handles creation, listing, and updates of scheduled executions and recurring patterns.
    """
    
    @transaction.atomic
    def create_scheduled_execution(self, user: User, action: Action, environment: str,
                                  parameters: dict | None = None, scheduled_at: datetime | None = None,
                                  recurring_pattern_data: dict | None = None):
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
        if recurring_pattern_data:
            from executions.models import RecurringPattern
            RecurringPattern.objects.create(
                scheduled_execution=scheduled_execution,
                pattern_type=recurring_pattern_data['pattern_type'],
                pattern_config=json.dumps(recurring_pattern_data.get('pattern_config')) if recurring_pattern_data.get('pattern_config') else None,
                next_execution_date=recurring_pattern_data['next_execution_date'],
                is_active=recurring_pattern_data.get('is_active', 1),
            )
            AuditService.create_entry(
                user_id=str(user.id),
                action_type='SCHEDULED_EXECUTION_RECURRING_CREATED',
                entity_type='scheduled_execution',
                entity_id=scheduled_execution.id,
                details={
                    'action_id': action.id,
                    'action_name': action.name,
                    'environment': environment,
                    'pattern_type': recurring_pattern_data['pattern_type'],
                }
            )
        else:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type='SCHEDULED_EXECUTION_CREATED',
                entity_type='scheduled_execution',
                entity_id=scheduled_execution.id,
                details={
                    'action_id': action.id,
                    'action_name': action.name,
                    'environment': environment,
                    'scheduled_at': scheduled_at.isoformat() if scheduled_at else None,
                }
            )
        
        return scheduled_execution
    
    def list_all(self, status: str | None = None, user_id: int | None = None,
                action_id: int | None = None, scheduled_from: datetime | None = None,
                scheduled_to: datetime | None = None, page: int = 1, page_size: int = 25):
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
        
        queryset = queryset.order_by('scheduled_at', 'recurringpattern__next_execution_date')
        
        # Pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        results = list(queryset[start_index:end_index])
        
        return results, total_count
    
    def get_by_id(self, scheduled_execution_id: int):
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
    def update_status(self, scheduled_execution_id: int, new_status: str, user_id: str):
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
        if hasattr(scheduled_execution, 'recurringpattern') and new_status == ScheduledExecutionStatus.EXECUTED:
            # Recalculate next_execution_date based on pattern_config
            # This is a simplified version - full implementation would parse pattern_config
            # For now, just add 1 day as a placeholder
            pattern = scheduled_execution.recurringpattern
            if pattern.is_active:
                pattern.next_execution_date = timezone.now() + timedelta(days=1)
                pattern.updated_at = timezone.now()
                pattern.save()
        
        AuditService.create_entry(
            user_id=user_id,
            action_type=f'SCHEDULED_EXECUTION_{new_status.upper()}',
            entity_type='scheduled_execution',
            entity_id=scheduled_execution.id,
            details={
                'action_id': scheduled_execution.action_id,
                'action_name': scheduled_execution.action.name if scheduled_execution.action else None,
                'previous_status': old_status,
                'new_status': new_status,
            }
        )
        
        return scheduled_execution
    
    def list_pending(self, before_datetime: datetime | None = None):
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
    def cancel_scheduled_execution(self, scheduled_execution_id: int, user_id: str):
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
                action_type='SCHEDULED_EXECUTION_RECURRING_DISABLED',
                entity_type='scheduled_execution',
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
                action_type='SCHEDULED_EXECUTION_CANCELLED',
                entity_type='scheduled_execution',
                entity_id=scheduled_execution.id,
                details={
                    'action_id': scheduled_execution.action_id,
                    'action_name': scheduled_execution.action.name if scheduled_execution.action else None,
                    'environment': scheduled_execution.environment,
                }
            )
        
        return scheduled_execution
