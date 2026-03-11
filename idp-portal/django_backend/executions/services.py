"""
ExecutionService for business logic related to executions.
Handles complex operations like atomic execution creation with steps.
Story M.8 - Task 9: Structured logging with structlog.
"""

import structlog

from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Avg, ExpressionWrapper, F, Q, Count, QuerySet
from django.db.models import DurationField
from django.utils import timezone
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
    ExecutionTarget, TargetType
)
from catalog.models import Action
from idp_auth.models import User
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.utils import sanitize_audit_changes
from executions.dtos import ExecutionRequest
from integrations.models import IntegrationStatus

logger = structlog.get_logger(__name__)


# Story 43.2: Clés sensibles à exclure des paramètres d'audit (case-insensitive)
_SENSITIVE_PARAM_KEYS = frozenset({
    'password', 'secret', 'api_key', 'token', 'private_key',
    'credential', '_env_config'
})


def _sanitize_list(lst: list) -> list:
    """Récursivement assainit les éléments d'une liste (dicts, listes imbriquées, primitives)."""
    out: list = []
    for item in lst:
        if isinstance(item, dict):
            sanitized_item = _sanitize_parameters(item)
            if sanitized_item is not None:
                out.append(sanitized_item)
        elif isinstance(item, list):
            out.append(_sanitize_list(item))
        else:
            out.append(item)
    return out


def _sanitize_parameters(parameters: dict | None) -> dict | None:
    """
    Retourne une copie des paramètres sans les clés sensibles.
    Filtrage récursif sur les valeurs dict imbriquées et les listes de dicts.
    Les dicts imbriqués entièrement sensibles sont exclus (pas incluse comme None).
    Retourne None si parameters est None ou si le résultat est vide.
    """
    if not parameters:
        return None
    sanitized: dict = {}
    for k, v in parameters.items():
        if k.lower() in _SENSITIVE_PARAM_KEYS:
            continue
        if isinstance(v, dict):
            sanitized_v = _sanitize_parameters(v)
            if sanitized_v is not None:
                sanitized[k] = sanitized_v
            # dict imbriqué entièrement sensible → clé exclue (pas incluse comme None)
        elif isinstance(v, list):
            out: list = []
            for item in v:
                if isinstance(item, dict):
                    sanitized_item = _sanitize_parameters(item)
                    if sanitized_item is not None:
                        out.append(sanitized_item)
                elif isinstance(item, list):
                    out.append(_sanitize_list(item))
                else:
                    out.append(item)
            sanitized[k] = out
        else:
            sanitized[k] = v
    return sanitized if sanitized else None


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

    def create_execution(self, request: ExecutionRequest) -> Execution:
        """
        Create an execution atomically.

        Story 24.4 (AC4): Validates integration status BEFORE the atomic block
        so audit entries survive even when execution is blocked.

        Args:
            request: ExecutionRequest DTO encapsulating all execution parameters.

        Returns:
            Execution instance

        Raises:
            BadRequestError: If action's integration is INVALID (Story 24.4 AC4)
        """
        # Story 24.4 (AC4): Validate integration status BEFORE atomic block
        self._check_integration_status(
            action=request.action,
            user_id=str(request.user.id),
            correlation_id=request.correlation_id,
        )

        return self._create_execution_atomic(request)

    @transaction.atomic
    def _create_execution_atomic(self, request: ExecutionRequest) -> Execution:
        """Internal atomic execution creation (after integration validation).

        Legacy PENDING_APPROVAL status is no longer set. When requires_approval is true,
        the execution is created as SUBMITTED and an ExecutionStep WAITING gate is created
        so the approval goes through the step-based gate mechanism (ADR-007).
        """
        requires_approval = bool(
            (request.parameters or {}).get("_env_config", {}).get("requires_approval", False)
        )
        initial_status = ExecutionStatus.SUBMITTED

        execution = Execution.objects.create(
            action=request.action,
            user=request.user,
            environment=request.environment,
            status=initial_status,
            parent_execution_id=request.parent_execution_id,
            correlation_id=request.correlation_id,
        )

        # ADR-007: Create an approval gate step instead of PENDING_APPROVAL status
        if requires_approval:
            from executions.models import ExecutionStepType  # noqa: PLC0415
            step = ExecutionStep.objects.create(
                execution=execution,
                step_order=0,
                step_name='Approval Gate',
                config_step_id='auto-approval-gate',
                step_type=ExecutionStepType.GATE,
                status=ExecutionStepStatus.WAITING,
            )
            step.set_output({
                'gate_conditions': [{'type': 'approval_granted'}],
                'gate_status': [{'type': 'approval_granted', 'satisfied': False}],
            })
            step.save()

        # Set parameters if provided
        if request.parameters:
            execution.set_parameters(request.parameters)
            execution.save()

        # Story 25.1: Create ExecutionTarget records for each validated target
        if request.validated_targets:
            for target_data in request.validated_targets:
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
                target_count=len(request.validated_targets),
                correlation_id=request.correlation_id,
            )

        # Build audit details (Story 13.5: include source, ip_address, targets)
        audit_details = {
            'action_id': request.action.id,
            'action_name': request.action.name,
            'environment': request.environment,
        }
        # Story 4.12 (AC6): include workflow_step_parameters when provided (sanitized)
        raw_wsp = request.parameters.get("workflow_step_parameters") if isinstance(request.parameters, dict) else None
        sanitized_wsp = _sanitize_parameters(raw_wsp) if isinstance(raw_wsp, dict) else None
        if sanitized_wsp:
            audit_details["workflow_step_parameters"] = sanitized_wsp
        # Story 43.2: inclure les paramètres d'exécution nettoyés dans audit_details
        sanitized_params = _sanitize_parameters(request.parameters)
        if sanitized_params:
            sanitized_params.pop("workflow_step_parameters", None)
            if sanitized_params:
                audit_details["parameters"] = sanitized_params
        if request.source:
            audit_details['source'] = request.source
        if request.ip_address:
            audit_details['ip_address'] = request.ip_address
        if request.targets:
            audit_details['targets'] = request.targets
        # Story 4.11: single audit entry with delegation info (avoids duplicate)
        if request.delegated_referenced_action_ids is not None:
            audit_details['delegated'] = True
            audit_details['workflow_action_id'] = request.action.id
            audit_details['workflow_action_name'] = request.action.name
            audit_details['referenced_action_ids'] = request.delegated_referenced_action_ids
            audit_details['validation_result'] = 'success'

        # Audit: always SUBMITTED now (approval is step-based, not status-based)
        audit_action = AuditActionType.EXECUTION_SUBMITTED
        AuditService.create_entry(
            user_id=str(request.user.id),
            action_type=audit_action,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details=audit_details,
            ip_address=request.ip_address,
            correlation_id=request.correlation_id
        )

        return execution

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
        # Story 24.4 (AC4): Validate integration status BEFORE the atomic block
        # so audit entries survive even when execution is blocked.
        self._check_integration_status(
            action=action,
            user_id=str(user.id),
            correlation_id=correlation_id,
        )

        exec_req = ExecutionRequest(
            user=user,
            action=action,
            environment=environment,
            parameters=parameters,
            parent_execution_id=parent_execution_id,
            correlation_id=correlation_id,
            source=source,
            ip_address=ip_address,
            targets=targets,
        )

        with transaction.atomic():
            execution = self._create_execution_atomic(exec_req)

            # Create steps if provided
            if steps_data:
                for step_data in steps_data:
                    ExecutionStep.objects.create(
                        execution=execution,
                        step_order=step_data.get('step_order', 0),
                        step_name=step_data.get('step_name', 'Step'),
                        config_step_id=step_data.get('config_step_id'),
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
        Runtime dispatch via RuntimeRegistry (Story 34.4 — SOLID-BE-7).
        Used after creation (when no approval gate) and after DBA approval via step gate.
        """
        # Late import to avoid circular dependency:
        # runtime_registry → adapter modules → executions.models → executions.services
        # Moving to top-level would create an import cycle at module load time.
        from executions.runtime_registry import runtime_registry  # noqa: PLC0415
        action = execution.action
        if not action:
            return
        runtime = runtime_registry.get(action.item_type)
        if runtime is None:
            logger.debug(
                "no_runtime_registered_for_item_type",
                item_type=action.item_type,
                execution_id=execution.id,
            )
            return
        runtime(execution, correlation_id=correlation_id)

    @staticmethod
    def _validate_transition(old_status: str, new_status: str) -> None:
        """
        Validate that a status transition is allowed by the state machine.

        Raises ValueError with an explicit message if the transition is invalid.

        State machine: valid transitions for execution status.

        ADR-007: PENDING_APPROVAL is no longer used at the Execution level.
        Approvals are handled via ExecutionStep WAITING gates.
        The PENDING_APPROVAL enum value is kept for DB CHECK constraint compatibility.

        Valid transitions by state (with business rationale):
        ┌─────────────────────┬────────────────────────────────────────────────────────┐
        │ From State          │ To State → Business Rationale                          │
        ├─────────────────────┼────────────────────────────────────────────────────────┤
        │ SUBMITTED           │ → RUNNING: Normal execution start                      │
        │                     │ → CANCELLED: User cancels before start                 │
        │                     │ → FAILED: Approval gate rejected (ADR-007)             │
        │                     │ → INTEGRATION_ERROR: Platform integration failed       │
        ├─────────────────────┼────────────────────────────────────────────────────────┤
        │ RUNNING             │ → COMPLETED: Execution succeeded                       │
        │                     │ → FAILED: Execution failed                             │
        │                     │ → CANCELLED: User cancels during execution             │
        ├─────────────────────┼────────────────────────────────────────────────────────┤
        │ COMPLETED           │ (terminal state - no transitions)                      │
        │ FAILED              │ (terminal state - no transitions)                      │
        │ CANCELLED           │ (terminal state - no transitions)                      │
        │ REJECTED            │ (terminal state - no transitions)                      │
        │ INTEGRATION_ERROR   │ (terminal state - Story 18.6)                          │
        └─────────────────────┴────────────────────────────────────────────────────────┘
        """
        # PENDING_APPROVAL transitions removed (ADR-007): approval is now step-based.
        # PENDING_APPROVAL status is kept in the enum for DB CHECK constraint compatibility
        # but is no longer reachable. Any attempt to transition to/from it will raise ValueError.
        valid_transitions = {
            ExecutionStatus.SUBMITTED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED, ExecutionStatus.FAILED, ExecutionStatus.INTEGRATION_ERROR],
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

    @staticmethod
    def _apply_status_change(execution: 'Execution', new_status: str) -> None:
        """
        Apply status change to execution with idempotent timestamp updates and save.

        Updates started_at only when transitioning to RUNNING and not already set.
        Updates completed_at only when transitioning to a terminal state and not already set.
        """
        execution.status = new_status

        # Update timestamps (idempotent - preserve original timestamps)
        if new_status == ExecutionStatus.RUNNING and not execution.started_at:
            execution.started_at = timezone.now()
        elif new_status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED, ExecutionStatus.REJECTED, ExecutionStatus.INTEGRATION_ERROR]:
            if not execution.completed_at:
                execution.completed_at = timezone.now()

        execution.save()

    @staticmethod
    def _create_status_audit_entry(execution: 'Execution', old_status: str, new_status: str, user_id: str) -> None:
        """Create an audit trail entry for the status change."""
        status_to_audit_type = {
            ExecutionStatus.SUBMITTED: AuditActionType.EXECUTION_SUBMITTED,
            ExecutionStatus.INTEGRATION_ERROR: AuditActionType.EXECUTION_INTEGRATION_ERROR,
            ExecutionStatus.RUNNING: AuditActionType.EXECUTION_RUNNING,
            ExecutionStatus.COMPLETED: AuditActionType.EXECUTION_COMPLETED,
            ExecutionStatus.FAILED: AuditActionType.EXECUTION_FAILED,
            ExecutionStatus.CANCELLED: AuditActionType.EXECUTION_CANCELLED,
            # PENDING_APPROVAL audit mapping removed (ADR-007): approval is step-based.
            ExecutionStatus.REJECTED: AuditActionType.EXECUTION_REJECTED,
        }
        audit_action_type = status_to_audit_type.get(new_status)  # type: ignore[call-overload]
        if not audit_action_type:
            logger.warning(
                "unknown_execution_status_for_audit",
                execution_id=execution.id,
                status=new_status,
                correlation_id=get_correlation_id()
            )
            raise ValueError(
                f"Unknown execution status for audit: {new_status}"
            )

        changes = sanitize_audit_changes({'status': {'old': old_status, 'new': new_status}})
        AuditService.create_entry(
            user_id=user_id,
            action_type=audit_action_type,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'action_id': execution.action_id,
                'action_name': execution.action.name if execution.action else None,
                'changes': changes,
            },
            correlation_id=execution.correlation_id or get_correlation_id(),
        )

    @staticmethod
    def _schedule_notification(execution: 'Execution', new_status: str) -> None:
        """
        Schedule non-blocking notifications on terminal states (COMPLETED, FAILED).

        Story 31.8: Uses transaction.on_commit() to avoid holding the DB connection
        open during potentially slow HTTP calls (httpx.post timeout=10s per destination).
        """
        if new_status not in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            return

        try:
            from services.notification_service import NotificationService
            from django.db import transaction as _tx
            event = "on_success" if new_status == ExecutionStatus.COMPLETED else "on_failure"
            params: dict = execution.get_parameters() or {}
            page_me = bool(params.get('__page_me', False))
            page_me_user_id = params.get('__page_me_user_id')
            page_me_user_name = params.get('__page_me_user_name')
            _correlation_id = execution.correlation_id or get_correlation_id()
            _execution_id_snap = execution.id

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
                except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: notification dispatch failure must not break execution
                    logger.error(
                        "notification_dispatch_failed",
                        execution_id=_execution_id_snap,
                        error=str(exc),
                        correlation_id=_correlation_id,
                        exc_info=True,
                    )

            _tx.on_commit(_send_notifications)
        except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: notification setup failure must not break execution
            logger.error(
                "notification_setup_failed",
                execution_id=execution.id,
                error=str(exc),
                correlation_id=get_correlation_id(),
                exc_info=True,
            )

    @transaction.atomic
    def update_status(self, execution_id: int, new_status: str, user_id: str) -> Execution | None:
        """
        Update execution status with transition validation, audit, and notifications.

        Orchestrates the status update by delegating to single-responsibility methods:
        _validate_transition, _apply_status_change, _create_status_audit_entry,
        and _schedule_notification.

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
            execution = Execution.objects.select_for_update().select_related('action').get(id=execution_id)
        except Execution.DoesNotExist:
            return None

        old_status = execution.status

        self._validate_transition(old_status, new_status)
        self._apply_status_change(execution, new_status)
        self._create_status_audit_entry(execution, old_status, new_status, user_id)
        self._schedule_notification(execution, new_status)

        # V113: Emit durable workflow event for UI catch-up
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        WorkflowEventService.emit_execution_status_changed(execution, old_status, new_status)

        # V113: Clear runnable steps on terminal status (cancellation, failure)
        if new_status in (
            ExecutionStatus.CANCELLED, ExecutionStatus.FAILED,
            ExecutionStatus.REJECTED, ExecutionStatus.INTEGRATION_ERROR,
        ):
            from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
            RunnableStepService.delete_for_execution(execution.id)

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
        # Only for COMPLETED executions with both timestamps — aggregated DB-side
        completed_executions = queryset.filter(
            status=ExecutionStatus.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False
        )
        avg_duration = completed_executions.aggregate(
            avg_duration=Avg(ExpressionWrapper(
                F('completed_at') - F('started_at'),
                output_field=DurationField()
            ))
        )['avg_duration']
        avg_time_ms = round(avg_duration.total_seconds() * 1000, 2) if avg_duration else None

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
        # Note: create_step doesn't receive config_step_id; callers should set it if needed
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
from executions.scheduling_service import SchedulingService  # noqa: F401, E402
