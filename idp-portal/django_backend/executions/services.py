"""
ExecutionService for business logic related to executions.
Handles complex operations like atomic execution creation with steps.
Story M.8 - Task 9: Structured logging with structlog.
"""

import json
import structlog

from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Q, Count, QuerySet
from django.utils import timezone
from core.utils import ensure_utc_isoformat
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
    ExecutionTarget, TargetType,
    ScheduledExecution, ScheduledExecutionStatus
)
from catalog.models import Action
from idp_auth.models import User
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from executions.utils import calculate_next_execution_date
from integrations.models import IntegrationStatus

logger = structlog.get_logger(__name__)


class ExecutionService:
    """
    Service for execution business logic.
    Handles complex operations like atomic execution creation with steps.
    """

    @staticmethod
    def _check_integration_status(
        action: Action, user_id: str, correlation_id: str | None = None,
    ) -> None:
        """
        Story 24.4 (AC4): Validate integration status before execution.
        Blocks INVALID integrations (with audit), warns for DEPRECATED, allows VALID.
        Called OUTSIDE the atomic transaction so audit entries survive on error.

        Raises:
            BadRequestError: If integration status is INVALID
        """
        integration = getattr(action, 'integration', None)
        if not integration:
            return

        if integration.status == IntegrationStatus.INVALID:
            logger.error(
                "execution_blocked_invalid_integration",
                integration_id=integration.id,
                integration_name=integration.name,
                integration_status=integration.status,
                action_id=action.id,
                user_id=user_id,
                correlation_id=correlation_id,
            )
            AuditService.create_entry(
                user_id=user_id,
                action_type=AuditActionType.EXECUTION_BLOCKED_INVALID_INTEGRATION,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={
                    'integration_id': integration.id,
                    'integration_name': integration.name,
                    'integration_type': integration.type,
                    'integration_status': integration.status,
                    'action_id': action.id,
                    'reason': 'type_not_found_in_catalogue',
                },
                correlation_id=correlation_id,
            )
            raise BadRequestError(
                code="INVALID_INTEGRATION",
                message=f"L'intégration '{integration.name}' (type: '{integration.type}') est invalide et ne peut pas être utilisée. Veuillez contacter un administrateur.",
                details={
                    'integration_id': integration.id,
                    'integration_name': integration.name,
                    'integration_type': integration.type,
                    'integration_status': integration.status,
                    'reason': 'type_not_found_in_catalogue',
                    'action': 'contact_administrator',
                },
            )

        if integration.status == IntegrationStatus.DEPRECATED:
            logger.warning(
                "execution_with_deprecated_integration",
                integration_id=integration.id,
                integration_name=integration.name,
                integration_status=integration.status,
                action_id=action.id,
                user_id=user_id,
                correlation_id=correlation_id,
            )
            AuditService.create_entry(
                user_id=user_id,
                action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={
                    'integration_id': integration.id,
                    'integration_name': integration.name,
                    'integration_type': integration.type,
                    'integration_status': integration.status,
                    'action_id': action.id,
                },
                correlation_id=correlation_id,
            )

    def create_execution(self, user: User, action: Action, environment: str,
                       parameters: dict | None = None, parent_execution_id: int | None = None,
                       correlation_id: str | None = None,
                       source: str | None = None, ip_address: str | None = None,
                       targets: list[str] | None = None,
                       delegated_referenced_action_ids: list[int] | None = None,
                       validated_targets: list[dict] | None = None) -> Execution:
        """
        Create an execution atomically.

        Story 24.4 (AC4): Validates integration status BEFORE the atomic block
        so audit entries survive even when execution is blocked.

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
            validated_targets: Story 25.1 - list of validated target dicts from inventory
                (keys: name, environment, target_type, metadata). Creates ExecutionTarget records.

        Returns:
            Execution instance

        Raises:
            BadRequestError: If action's integration is INVALID (Story 24.4 AC4)
        """
        # Story 24.4 (AC4): Validate integration status BEFORE atomic block
        self._check_integration_status(
            action=action,
            user_id=str(user.id),
            correlation_id=correlation_id,
        )

        return self._create_execution_atomic(
            user=user, action=action, environment=environment,
            parameters=parameters, parent_execution_id=parent_execution_id,
            correlation_id=correlation_id, source=source, ip_address=ip_address,
            targets=targets, delegated_referenced_action_ids=delegated_referenced_action_ids,
            validated_targets=validated_targets,
        )

    @transaction.atomic
    def _create_execution_atomic(self, user: User, action: Action, environment: str,
                       parameters: dict | None = None, parent_execution_id: int | None = None,
                       correlation_id: str | None = None,
                       source: str | None = None, ip_address: str | None = None,
                       targets: list[str] | None = None,
                       delegated_referenced_action_ids: list[int] | None = None,
                       validated_targets: list[dict] | None = None) -> Execution:
        """Internal atomic execution creation (after integration validation).
        Story 25.4 / 7.4: If requires_approval for this environment, create as PENDING_APPROVAL
        so the execution waits for DBA approval before being launched.
        """
        requires_approval = bool(
            (parameters or {}).get("_env_config", {}).get("requires_approval", False)
        )
        initial_status = (
            ExecutionStatus.PENDING_APPROVAL if requires_approval else ExecutionStatus.SUBMITTED
        )

        execution = Execution.objects.create(
            action=action,
            user=user,
            environment=environment,
            status=initial_status,
            parent_execution_id=parent_execution_id,
        )

        # Set parameters if provided
        if parameters:
            execution.set_parameters(parameters)
            execution.save()

        # Story 25.1: Create ExecutionTarget records for each validated target
        if validated_targets:
            for target_data in validated_targets:
                target_type_str = (target_data.get('target_type') or 'other').upper()
                # Map to TargetType enum, default to OTHER
                try:
                    target_type = TargetType(target_type_str)
                except ValueError:
                    target_type = TargetType.OTHER

                metadata = target_data.get('metadata')
                # Build metadata snapshot with environment and any extra attributes
                metadata_snapshot = {}
                if metadata and isinstance(metadata, dict):
                    metadata_snapshot.update(metadata)
                if target_data.get('environment'):
                    metadata_snapshot['environment'] = target_data['environment']
                # Include extra inventory attributes (engine_type, zone, etc.)
                for key in ('engine_type', 'zone', 'technology'):
                    if key in target_data:
                        metadata_snapshot[key] = target_data[key]

                exec_target = ExecutionTarget(
                    execution=execution,
                    target_type=target_type,
                    target_id=target_data.get('name', ''),
                    target_name=target_data.get('name', ''),
                )
                exec_target.set_target_metadata(metadata_snapshot if metadata_snapshot else None)
                exec_target.save()

            logger.info(
                "execution_targets_created",
                execution_id=execution.id,
                target_count=len(validated_targets),
                correlation_id=correlation_id,
            )

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

        # Audit (Story 25.4: PENDING_APPROVAL when requires_approval for env)
        audit_action = (
            AuditActionType.EXECUTION_PENDING_APPROVAL
            if initial_status == ExecutionStatus.PENDING_APPROVAL
            else AuditActionType.EXECUTION_SUBMITTED
        )
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=audit_action,
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
                                   targets: list[str] | None = None) -> Execution:
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
                page: int = 1, page_size: int = 25) -> tuple[list[Execution], int]:
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
    
    def get_by_id(self, execution_id: int) -> Execution | None:
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

    @staticmethod
    def launch_workflow(execution: Execution, correlation_id: str | None = None) -> None:
        """
        Start the workflow runtime for an execution (Story 7.4 / 25.4).
        Used after creation (when not PENDING_APPROVAL) and after DBA approval.
        """
        from django.conf import settings
        action = execution.action
        if not action:
            return
        if action.item_type == "workflow":
            from executions.container_workflow_runtime import ContainerWorkflowRuntime
            ContainerWorkflowRuntime(execution).run()
            logger.info(
                "container_workflow_execution_launched",
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
        elif getattr(settings, "SIMULATE_EXECUTION_DEV", False):
            from executions.simulation_service import SimulationService
            SimulationService.create_simulated_steps(execution)
            SimulationService.start_simulation(execution)
            logger.info(
                "execution_simulation_started",
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
    
    @transaction.atomic
    def update_status(self, execution_id: int, new_status: str, user_id: str) -> Execution | None:
        """
        Update execution status with transition validation.

        Args:
            execution_id: ID of the execution
            new_status: New status value
            user_id: ID of user making the change

        Returns:
            Updated Execution instance or None

        Raises:
            ValueError: If transition is invalid or user_id is invalid
        """
        # Validate user exists (SOC1 audit integrity)
        try:
            User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError(f"Invalid user_id: {user_id}")

        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            return None

        old_status = execution.status

        # State machine: valid transitions for execution status.
        #
        # SECURITY (Story 22.12): PENDING_APPROVAL → SUBMITTED is explicitly FORBIDDEN.
        #   Allowing it would let executions bypass the DBA approval workflow,
        #   violating SOC1 compliance. An execution that requires approval must
        #   go through RUNNING (after DBA approval) or REJECTED (if DBA refuses).
        #
        # TODO (Story 7.4): Approval transitions must use dedicated endpoints:
        #   - PENDING_APPROVAL → RUNNING via POST /api/v1/executions/{id}/approve
        #   - PENDING_APPROVAL → REJECTED via POST /api/v1/executions/{id}/reject
        #   These endpoints are not yet implemented.
        #
        # Valid transitions by state (with business rationale):
        # ┌─────────────────────┬────────────────────────────────────────────────────────┐
        # │ From State          │ To State → Business Rationale                          │
        # ├─────────────────────┼────────────────────────────────────────────────────────┤
        # │ SUBMITTED           │ → RUNNING: Normal execution start                      │
        # │                     │ → CANCELLED: User cancels before start                 │
        # │                     │ → PENDING_APPROVAL: Elevation to approval required     │
        # │                     │ → INTEGRATION_ERROR: Platform integration failed       │
        # ├─────────────────────┼────────────────────────────────────────────────────────┤
        # │ PENDING_APPROVAL    │ → RUNNING: DBA approves (via /approve endpoint)        │
        # │                     │ → REJECTED: DBA rejects (via /reject endpoint)         │
        # ├─────────────────────┼────────────────────────────────────────────────────────┤
        # │ RUNNING             │ → COMPLETED: Execution succeeded                       │
        # │                     │ → FAILED: Execution failed                             │
        # │                     │ → CANCELLED: User cancels during execution             │
        # ├─────────────────────┼────────────────────────────────────────────────────────┤
        # │ COMPLETED           │ (terminal state - no transitions)                      │
        # │ FAILED              │ (terminal state - no transitions)                      │
        # │ CANCELLED           │ (terminal state - no transitions)                      │
        # │ REJECTED            │ (terminal state - no transitions)                      │
        # │ INTEGRATION_ERROR   │ (terminal state - Story 18.6)                          │
        # └─────────────────────┴────────────────────────────────────────────────────────┘
        valid_transitions = {
            ExecutionStatus.SUBMITTED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.PENDING_APPROVAL, ExecutionStatus.INTEGRATION_ERROR],
            ExecutionStatus.PENDING_APPROVAL: [ExecutionStatus.RUNNING, ExecutionStatus.REJECTED],
            ExecutionStatus.RUNNING: [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED],
            ExecutionStatus.COMPLETED: [],
            ExecutionStatus.FAILED: [],
            ExecutionStatus.CANCELLED: [],
            ExecutionStatus.REJECTED: [],
            ExecutionStatus.INTEGRATION_ERROR: [],  # Terminal state (Story 18.6)
        }

        if new_status not in (valid_transitions.get(old_status) or []):  # type: ignore[call-overload]
            valid_list = ", ".join(valid_transitions.get(old_status) or [])  # type: ignore[call-overload]
            raise ValueError(
                f"Invalid transition from {old_status} to {new_status}. "
                f"Valid transitions: {valid_list or 'none (terminal state)'}"
            )

        execution.status = new_status

        # Update timestamps (idempotent - preserve original timestamps)
        if new_status == ExecutionStatus.RUNNING and not execution.started_at:
            execution.started_at = timezone.now()
        elif new_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.REJECTED]:
            if not execution.completed_at:
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
        audit_action_type = status_to_audit_type.get(new_status)  # type: ignore[call-overload]
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

        # Story 31.8: Trigger notifications on terminal states (non-blocking).
        # Use transaction.on_commit() to avoid holding the DB connection open during
        # potentially slow HTTP calls (httpx.post timeout=10s per destination).
        if new_status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            try:
                from services.notification_service import NotificationService
                from django.db import transaction as _tx
                event = "on_success" if new_status == ExecutionStatus.COMPLETED else "on_failure"
                params: dict = execution.get_parameters() or {}
                page_me = bool(params.get('__page_me', False))
                page_me_user_id = params.get('__page_me_user_id')
                page_me_user_name = params.get('__page_me_user_name')
                _correlation_id = get_correlation_id()
                _execution_id_snap = execution_id

                def _send_notifications() -> None:
                    try:
                        notif_service = NotificationService()
                        notif_service.notify_execution_event(
                            execution=execution,
                            action=execution.action,
                            event=event,
                            page_me=page_me,
                            page_me_user_id=page_me_user_id,
                            page_me_user_name=page_me_user_name,
                            correlation_id=_correlation_id,
                        )
                    except Exception as exc:
                        logger.error(
                            "notification_dispatch_failed",
                            execution_id=_execution_id_snap,
                            error=str(exc),
                            correlation_id=_correlation_id,
                        )

                _tx.on_commit(_send_notifications)
            except Exception as exc:
                logger.error(
                    "notification_setup_failed",
                    execution_id=execution_id,
                    error=str(exc),
                    correlation_id=get_correlation_id(),
                )

        return execution
    
    def list_by_user(self, user_id: int, status: str | None = None,
                    environment: str | None = None, action_id: int | None = None,
                    date_from: datetime | None = None, date_to: datetime | None = None,
                    limit: int | None = None, offset: int = 0) -> QuerySet:
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
    
    def get_recent(self, limit: int = 10) -> QuerySet:
        """
        Get recent executions for dashboard.
        
        Args:
            limit: Maximum number of executions to return
        
        Returns:
            QuerySet of recent executions
        """
        return Execution.objects.get_recent(limit)
    
    def get_stats(self, user_id: int | None = None, days: int = 30) -> dict:
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

    def get_action_stats(self, action_id: int, days: int = 30) -> dict:
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
                assert exec.completed_at is not None and exec.started_at is not None
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
                   step_type: str) -> ExecutionStep:
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
    
    def get_steps_by_execution(self, execution_id: int) -> QuerySet:
        """
        Get all steps for an execution.
        
        Args:
            execution_id: ID of the execution
        
        Returns:
            QuerySet of execution steps ordered by step_order
        """
        return ExecutionStep.objects.filter(execution_id=execution_id).order_by('step_order')
    
    def get_step_by_id(self, step_id: int) -> ExecutionStep | None:
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
    def update_step_status(self, step_id: int, new_status: str, output: dict | None = None) -> ExecutionStep | None:
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


# Backward compatibility re-export — SchedulingService moved to executions/scheduling_service.py (Story 34.3)
from executions.scheduling_service import SchedulingService  # noqa: F401
