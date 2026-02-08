"""
ExecutionService for business logic related to executions.
Handles complex operations like atomic execution creation with steps.
Story M.8 - Task 9: Structured logging with structlog.
"""

import json
import structlog

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
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class ExecutionService:
    """
    Service for execution business logic.
    Handles complex operations like atomic execution creation with steps.
    """
    
    @transaction.atomic
    def create_execution(self, user: User, action: Action, environment: str,
                       parameters: dict | None = None, parent_execution_id: int | None = None,
                       correlation_id: str | None = None,
                       source: str | None = None, ip_address: str | None = None,
                       targets: list[str] | None = None,
                       delegated_referenced_action_ids: list[int] | None = None):
        """
        Create an execution atomically.

        Args:
            user: User instance creating the execution
            action: Action instance to execute
            environment: Target environment
            parameters: Optional execution parameters dict
            parent_execution_id: Optional parent execution ID (for remediation)
            correlation_id: Optional correlation ID for tracing
            source: Optional source identifier ('api' or 'ui') for audit (Story 13.5)
            ip_address: Optional IP address of the client for audit (Story 13.5)
            targets: Optional list of target names for audit (Story 13.5)
            delegated_referenced_action_ids: Story 4.11 - when set, merge workflow delegation
                into the single audit entry (avoids duplicate EXECUTION_SUBMITTED).

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

        # Build audit details (Story 13.5: include source, ip_address, targets)
        audit_details = {
            'action_id': action.id,
            'action_name': action.name,
            'environment': environment,
        }
        # Story 4.12 (AC6): include workflow_step_parameters when provided
        if isinstance(parameters, dict) and isinstance(parameters.get("workflow_step_parameters"), dict):
            audit_details["workflow_step_parameters"] = parameters.get("workflow_step_parameters")
        if source:
            audit_details['source'] = source
        if ip_address:
            audit_details['ip_address'] = ip_address
        if targets:
            audit_details['targets'] = targets
        # Story 4.11: single audit entry with delegation info (avoids duplicate)
        if delegated_referenced_action_ids is not None:
            audit_details['delegated'] = True
            audit_details['workflow_action_id'] = action.id
            audit_details['workflow_action_name'] = action.name
            audit_details['referenced_action_ids'] = delegated_referenced_action_ids
            audit_details['validation_result'] = 'success'

        # Audit
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details=audit_details,
            ip_address=ip_address,
            correlation_id=correlation_id
        )

        return execution
    
    @transaction.atomic
    def create_execution_with_steps(self, user: User, action: Action, environment: str,
                                   parameters: dict | None = None, steps_data: list[dict] | None = None,
                                   parent_execution_id: int | None = None, correlation_id: str | None = None,
                                   source: str | None = None, ip_address: str | None = None,
                                   targets: list[str] | None = None):
        """
        Create an execution with steps atomically.
        
        Args:
            user: User instance creating the execution
            action: Action instance to execute
            environment: Target environment
            parameters: Optional execution parameters dict
            steps_data: Optional list of step data dicts
            parent_execution_id: Optional parent execution ID (for remediation)
            correlation_id: Optional correlation ID for tracing
            source: Optional source ('api' or 'ui') for audit (Story 13.5)
            ip_address: Optional client IP for audit (Story 13.5)
            targets: Optional target names for audit (Story 13.5)
        
        Returns:
            Execution instance with steps created
        """
        # Create the execution (pass audit fields for SOC1 traceability)
        execution = self.create_execution(
            user, action, environment, parameters, parent_execution_id, correlation_id,
            source=source, ip_address=ip_address, targets=targets,
        )
        
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
            ExecutionStatus.SUBMITTED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.PENDING_APPROVAL, ExecutionStatus.INTEGRATION_ERROR],
            ExecutionStatus.PENDING_APPROVAL: [ExecutionStatus.SUBMITTED, ExecutionStatus.REJECTED],
            ExecutionStatus.RUNNING: [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
            ExecutionStatus.COMPLETED: [],
            ExecutionStatus.FAILED: [],
            ExecutionStatus.CANCELLED: [],
            ExecutionStatus.REJECTED: [],
            ExecutionStatus.INTEGRATION_ERROR: [],  # Terminal state (Story 18.6)
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
        
        # Map status to audit action type enum
        status_to_audit_type = {
            ExecutionStatus.SUBMITTED: AuditActionType.EXECUTION_SUBMITTED,
            ExecutionStatus.INTEGRATION_ERROR: AuditActionType.EXECUTION_INTEGRATION_ERROR,
            ExecutionStatus.RUNNING: AuditActionType.EXECUTION_RUNNING,
            ExecutionStatus.COMPLETED: AuditActionType.EXECUTION_COMPLETED,
            ExecutionStatus.FAILED: AuditActionType.EXECUTION_FAILED,
            ExecutionStatus.CANCELLED: AuditActionType.EXECUTION_CANCELLED,
            ExecutionStatus.PENDING_APPROVAL: AuditActionType.EXECUTION_PENDING_APPROVAL,
            ExecutionStatus.REJECTED: AuditActionType.EXECUTION_REJECTED,
        }
        audit_action_type = status_to_audit_type.get(new_status)
        if not audit_action_type:
            logger.warning(
                "unknown_execution_status_for_audit",
                status=new_status,
                correlation_id=get_correlation_id()
            )
            audit_action_type = AuditActionType.EXECUTION_SUBMITTED  # Fallback
        
        # Audit
        AuditService.create_entry(
            user_id=user_id,
            action_type=audit_action_type,
            entity_type=AuditEntityType.EXECUTION,
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
            limit: Optional limit (must be > 0)
            offset: Offset for pagination (must be >= 0)
        
        Returns:
            QuerySet of executions
        
        Raises:
            ValueError: If limit or offset are invalid
        """
        # Validate pagination parameters
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be > 0")
        
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

    def get_action_stats(self, action_id: int, days: int = 30):
        """
        Get execution statistics for a single action (Story 20.2, AC5).

        Args:
            action_id: Action ID to filter executions
            days: Number of days to look back

        Returns:
            Dict with keys: total_executions, incidents_count, success_rate, avg_execution_time_ms.
            Always returns a dict (never None) - empty stats have zeros/None values.
        """
        # CRITICAL-3: Validate that action exists
        try:
            Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            logger.warning(
                "get_action_stats_invalid_action_id",
                action_id=action_id,
                correlation_id=get_correlation_id()
            )
            raise ValueError(f"Action {action_id} does not exist")
        
        date_from = timezone.now() - timedelta(days=days)
        queryset = Execution.objects.filter(
            action_id=action_id,
            created_at__gte=date_from
        )
        
        # MEDIUM-1: Single aggregation query instead of multiple queries
        stats = queryset.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=ExecutionStatus.COMPLETED)),
            failed=Count('id', filter=Q(status=ExecutionStatus.FAILED))
        )
        
        total = stats['total']
        completed = stats['completed']
        failed = stats['failed']
        
        # MEDIUM-3: Always return dict (never None)
        # Success rate = COMPLETED / (COMPLETED + FAILED) * 100
        # Only calculated if there are finished executions (completed or failed)
        finished_count = completed + failed
        success_rate = (
            round((completed / finished_count * 100), 2) if finished_count > 0 else None
        )
        
        # CRITICAL-2: Calculate avg_execution_time_ms from started_at and completed_at
        # Only for COMPLETED executions with both timestamps
        completed_executions = queryset.filter(
            status=ExecutionStatus.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False
        )
        durations = []
        for exec in completed_executions:
            try:
                delta = (exec.completed_at - exec.started_at).total_seconds() * 1000
                if delta >= 0:
                    durations.append(delta)
            except (TypeError, AttributeError) as e:
                # Story 17.6: Specific catch for invalid timestamp data
                logger.debug(
                    "execution_duration_calculation_skipped",
                    execution_id=exec.id,
                    started_at=exec.started_at,
                    completed_at=exec.completed_at,
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=get_correlation_id(),
                )
                continue
        
        avg_time_ms = round(sum(durations) / len(durations), 2) if durations else None
        
        # MEDIUM-4: Add structured logging
        logger.info(
            "get_action_stats_called",
            action_id=action_id,
            days=days,
            total_executions=total,
            completed=completed,
            failed=failed,
            success_rate=success_rate,
            avg_execution_time_ms=avg_time_ms,
            correlation_id=get_correlation_id()
        )
        
        return {
            "total_executions": total,
            "incidents_count": failed,
            "success_rate": success_rate,
            "avg_execution_time_ms": avg_time_ms,
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
                action_type=AuditActionType.SCHEDULED_EXECUTION_RECURRING_CREATED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
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
                action_type=AuditActionType.SCHEDULED_EXECUTION_CREATED,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
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
        
        # Map status to audit action type enum
        status_to_audit_type = {
            ScheduledExecutionStatus.EXECUTED: AuditActionType.SCHEDULED_EXECUTION_EXECUTED,
            ScheduledExecutionStatus.CANCELLED: AuditActionType.SCHEDULED_EXECUTION_CANCELLED,
        }
        audit_action_type = status_to_audit_type.get(new_status)
        if audit_action_type:
            AuditService.create_entry(
                user_id=user_id,
                action_type=audit_action_type,
                entity_type=AuditEntityType.SCHEDULED_EXECUTION,
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
