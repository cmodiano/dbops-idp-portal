"""
Workflow Runtime Engine - Story 16.3, 16.4, 20.3, 34.7

Orchestrateur pur : boucle principale run(), résolution de branche _resolve_next_step(),
délégation à RetryHandler (workflow_retry.py) et StepExecutor (workflow_step_executor.py).

Architecture:
- StepOutcome, StepResult: types partagés (importés par executions/tasks/retry.py)
- WorkflowExecutionState: état runtime (step courant, visites, outcome)
- WorkflowRuntime: orchestrateur < 500 lignes (SRP Story 34.7)
"""

import structlog
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from django.db import transaction
from django.utils import timezone

from executions.models import Execution, ExecutionStatus
from executions.utils.workflow_parsing import get_workflow_entry_step_ids
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Maximum number of step transitions to prevent infinite loops (AC5)
MAX_STEP_TRANSITIONS = 100


class StepOutcome(str, Enum):
    """Outcome of a step execution."""
    SUCCESS = "success"
    ERROR = "error"
    WAITING = "waiting"  # Story 25.2: step blocked by gate_conditions


@dataclass
class StepResult:
    """
    Result of executing a single workflow step.

    Attributes:
        outcome: SUCCESS or ERROR
        output: Optional output data from the step
        error_message: Error message if outcome is ERROR
        error_details: Additional error context
    """
    outcome: StepOutcome
    output: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Check if step succeeded."""
        return self.outcome == StepOutcome.SUCCESS

    @property
    def is_error(self) -> bool:
        """Check if step failed."""
        return self.outcome == StepOutcome.ERROR

    @property
    def is_waiting(self) -> bool:
        """Check if step is waiting for gate conditions (Story 25.2)."""
        return self.outcome == StepOutcome.WAITING


@dataclass
class WorkflowExecutionState:
    """
    Runtime state for workflow execution.

    Tracks current position in workflow graph, visited steps count (for loop detection),
    and last execution outcome for audit/debug.

    Attributes:
        execution_id: ID of the Execution being run
        current_step_id: Current step_id being executed (from workflow JSON)
        visited_counts: Map of step_id -> visit count (for loop detection)
        transition_count: Total number of step transitions (for loop detection)
        last_step_outcome: Outcome of last executed step (success|error)
        last_error: Last error details if any
    """
    execution_id: int
    current_step_id: Optional[str] = None
    visited_counts: Dict[str, int] = field(default_factory=dict)
    transition_count: int = 0
    last_step_outcome: Optional[StepOutcome] = None
    last_error: Optional[Dict[str, Any]] = None
    # Trace of the execution path for audit/debug (AC4)
    path_trace: List[Dict[str, Any]] = field(default_factory=list)

    def visit_step(self, step_id: str) -> None:
        """
        Record a visit to a step.

        Args:
            step_id: The step_id being visited
        """
        self.visited_counts[step_id] = self.visited_counts.get(step_id, 0) + 1
        self.transition_count += 1

    def has_exceeded_max_transitions(self) -> bool:
        """
        Check if workflow has exceeded maximum transitions (loop detection).

        Returns:
            True if transition_count >= MAX_STEP_TRANSITIONS
        """
        return self.transition_count >= MAX_STEP_TRANSITIONS


class WorkflowRuntime:
    """
    Main workflow runtime orchestrator.

    Executes workflow steps following conditional branches (on_success_step_ids, on_error_step_ids).
    Handles loop detection, state management, and execution updates.

    Story 34.7: Delegates retry logic to RetryHandler and step execution to StepExecutor (SRP).
    """

    def __init__(self, execution: Execution):
        """
        Initialize runtime for an execution.

        Args:
            execution: The Execution instance to run (must be a workflow)
        """
        self.execution = execution
        self.action = execution.action
        self.state = WorkflowExecutionState(execution_id=execution.id)
        self.correlation_id: str = get_correlation_id() or ""

        # Track global step_order counter for ExecutionStep creation
        self._step_order_counter = 0

        # Load workflow steps from action
        self.workflow_steps = self._load_workflow_steps()
        self.steps_by_id = {step.get('step_id'): step for step in self.workflow_steps if step.get('step_id')}

        # Story 34.7: DI collaborators (SRP — delegate retry and step execution)
        from executions.workflow_retry import RetryHandler  # noqa: PLC0415
        from executions.workflow_step_executor import StepExecutor  # noqa: PLC0415
        self._retry_handler = RetryHandler(self.execution, self.correlation_id)
        self._step_executor = StepExecutor(self.execution, self.correlation_id)

        logger.info(
            "workflow_runtime_initialized",
            execution_id=self.execution.id,
            action_id=self.action.id,
            action_name=self.action.name,
            step_count=len(self.workflow_steps),
            correlation_id=self.correlation_id,
        )

    def _load_workflow_steps(self) -> List[Dict[str, Any]]:
        """
        Load workflow steps from action's execution_steps.

        Returns:
            List of step dicts with step_id, on_success_step_ids, on_error_step_ids, etc.
        """
        steps = self.action.execution_steps or []
        if not isinstance(steps, list):
            logger.warning(
                "workflow_steps_invalid_format",
                execution_id=self.execution.id,
                action_id=self.action.id,
                correlation_id=self.correlation_id,
            )
            return []
        return steps

    def _get_step_parameters(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get parameters for a workflow step from execution's workflow_step_parameters (Story 4.12 AC5).

        Keys in workflow_step_parameters are string step_order from the workflow definition.
        Each value is { "parameters": { ... } }. Returns the inner "parameters" dict or {}.

        Args:
            step: Step dict from workflow definition (must have "order")

        Returns:
            Dict of parameters to pass to the referenced action for this step
        """
        params = self.execution.get_parameters() or {}
        wsp = params.get("workflow_step_parameters")
        if not isinstance(wsp, dict):
            return {}
        order_key = str(step.get("order", ""))
        step_entry = wsp.get(order_key)
        if not isinstance(step_entry, dict):
            return {}
        return step_entry.get("parameters") or {}

    def _next_step_order(self) -> int:
        """
        Increment and return the global step_order counter.

        Story 34.7: Counter is owned by WorkflowRuntime and passed explicitly to
        StepExecutor (Option A — more explicit, more testable).

        Returns:
            Next step_order value
        """
        self._step_order_counter += 1
        return self._step_order_counter

    # Backward-compat delegation — existing tests patch these methods directly.
    # They delegate to RetryHandler / StepExecutor without changing behaviour.

    def _is_retryable_error(self, result: "StepResult") -> bool:  # noqa: D401
        return self._retry_handler.is_retryable_error(result)

    def _execute_step(self, step: Dict[str, Any]) -> "StepResult":
        step_order = self._next_step_order()
        return self._step_executor.execute(step, step_order, self._get_step_parameters(step))

    def _execute_step_with_retry(self, step: Dict[str, Any]) -> "StepResult":
        # Peek counter (no increment) — used only in cancelled-early path.
        def _peek() -> int:
            return self._step_order_counter + 1

        # execute_fn wraps self._execute_step so test patches are honoured;
        # _execute_step manages the counter via _next_step_order() internally.
        return self._retry_handler.execute_with_retry(
            step, lambda s, _o: self._execute_step(s), _peek
        )

    def _call_platform_adapter(self, referenced_action: Any, integration: Any,
                               adapter_payload: dict, execution_step: Any) -> dict:
        return self._step_executor.call_platform_adapter(
            referenced_action, integration, adapter_payload, execution_step
        )

    def _resolve_next_step(
        self,
        current_step: Dict[str, Any],
        outcome: StepOutcome
    ) -> Optional[str]:
        """
        Resolve next step_id based on current step and outcome.

        Implements AC1, AC2, AC4 (branching logic):
        - If outcome is SUCCESS: follow on_success_step_id
        - If outcome is ERROR: follow on_error_step_id
        - If next step is None/NULL: workflow terminates

        Linear fallback (Story 16.3):
        - If on_success_step_ids/on_error_step_ids are absent, use linear order (next step by order)

        Args:
            current_step: Current step dict
            outcome: StepOutcome (SUCCESS or ERROR)

        Returns:
            Next step_id to execute, or None if workflow should terminate
        """
        is_success = outcome == StepOutcome.SUCCESS

        # Branching logic (Story 16.2, 67.1): on_success_step_ids/on_success_step_id,
        # on_error_step_ids/on_error_step_id (singular for retrocompat).
        if is_success and ('on_success_step_ids' in current_step or 'on_success_step_id' in current_step):
            ids_plural = current_step.get('on_success_step_ids')
            sid_singular = current_step.get('on_success_step_id')
            next_step_id: str | None
            if ids_plural and isinstance(ids_plural, list) and len(ids_plural) > 0:
                next_step_id = str(ids_plural[0])
            elif sid_singular and isinstance(sid_singular, str) and sid_singular.strip():
                next_step_id = sid_singular.strip()
            else:
                next_step_id = None
            logger.debug(
                "workflow_branch_resolution",
                current_step_id=current_step.get('step_id'),
                outcome=outcome.value,
                next_step_id=next_step_id,
                correlation_id=self.correlation_id,
            )
            return next_step_id

        if (not is_success) and ('on_error_step_ids' in current_step or 'on_error_step_id' in current_step):
            ids_plural = current_step.get('on_error_step_ids')
            sid_singular = current_step.get('on_error_step_id')
            if ids_plural and isinstance(ids_plural, list) and len(ids_plural) > 0:
                next_step_id = str(ids_plural[0])
            elif sid_singular and isinstance(sid_singular, str) and sid_singular.strip():
                next_step_id = sid_singular.strip()
            else:
                next_step_id = None
            logger.debug(
                "workflow_branch_resolution",
                current_step_id=current_step.get('step_id'),
                outcome=outcome.value,
                next_step_id=next_step_id,
                correlation_id=self.correlation_id,
            )
            return next_step_id

        # Backward compatibility: linear workflow (no branches defined)
        # Find next step by order
        current_order = current_step.get('order', 0)
        next_steps = [s for s in self.workflow_steps if s.get('order', 0) > current_order]
        if next_steps:
            next_step = min(next_steps, key=lambda s: s.get('order', 0))
            next_step_id = next_step.get('step_id')
            logger.debug(
                "workflow_linear_fallback",
                current_step_id=current_step.get('step_id'),
                current_order=current_order,
                next_step_id=next_step_id,
                correlation_id=self.correlation_id,
            )
            return next_step_id

        # No next step found - end of workflow
        logger.debug(
            "workflow_end_reached",
            current_step_id=current_step.get('step_id'),
            outcome=outcome.value,
            correlation_id=self.correlation_id,
        )
        return None

    @transaction.atomic
    def run(self) -> ExecutionStatus:
        """
        Execute the complete workflow following branches.

        Implements AC1-AC5:
        - AC1: Follow on_success_step_ids on success
        - AC2: Follow on_error_step_ids on error
        - AC4: Convergence (same next step from success/error paths)
        - AC5: Loop detection (max MAX_STEP_TRANSITIONS transitions)

        Story 34.7: Delegates to RetryHandler and StepExecutor (SRP).

        Returns:
            Final ExecutionStatus (COMPLETED or FAILED)
        """
        logger.info(
            "workflow_execution_starting",
            execution_id=self.execution.id,
            action_id=self.action.id,
            action_name=self.action.name,
            correlation_id=self.correlation_id,
        )

        # Update execution status to RUNNING
        self.execution.status = ExecutionStatus.RUNNING
        self.execution.started_at = timezone.now()
        self.execution.save()

        # Find first step: use graph entry points (steps with no incoming edges),
        # not min(order). Fixes workflow starting at wrong step when approval/gate
        # is added at the beginning but has higher order due to array position.
        if not self.workflow_steps:
            logger.error(
                "workflow_empty",
                execution_id=self.execution.id,
                action_id=self.action.id,
                correlation_id=self.correlation_id,
            )
            self.execution.status = ExecutionStatus.FAILED
            self.execution.completed_at = timezone.now()
            self.execution.save()
            return ExecutionStatus.FAILED

        entry_ids = get_workflow_entry_step_ids(self.workflow_steps)
        if entry_ids:
            # Pick entry with minimum order (deterministic when multiple entries)
            entry_steps = [s for s in self.workflow_steps if s.get('step_id') in entry_ids]
            first_step = min(entry_steps, key=lambda s: s.get('order', 0))
        else:
            # Fallback: no entry found (cycle?) — use min order
            first_step = min(self.workflow_steps, key=lambda s: s.get('order', 0))
        self.state.current_step_id = first_step.get('step_id')

        # Main execution loop
        final_status = ExecutionStatus.COMPLETED

        while self.state.current_step_id is not None:
            # AC5: Loop detection
            if self.state.has_exceeded_max_transitions():
                error_msg = "Boucle infinie détectée"
                logger.error(
                    "workflow_infinite_loop_detected",
                    execution_id=self.execution.id,
                    transition_count=self.state.transition_count,
                    max_transitions=MAX_STEP_TRANSITIONS,
                    correlation_id=self.correlation_id,
                )

                self.execution.status = ExecutionStatus.FAILED
                self.execution.completed_at = timezone.now()
                self.execution.save()

                # Audit
                AuditService.create_entry(
                    user_id=str(self.execution.user_id),
                    action_type=AuditActionType.EXECUTION_FAILED,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=self.execution.id,
                    details={
                        'action_id': self.action.id,
                        'action_name': self.action.name,
                        'error': error_msg,
                        'transition_count': self.state.transition_count,
                    },
                    correlation_id=self.correlation_id,
                )

                return ExecutionStatus.FAILED

            # Get current step
            current_step = self.steps_by_id.get(self.state.current_step_id)
            if not current_step:
                logger.error(
                    "workflow_step_not_found",
                    execution_id=self.execution.id,
                    step_id=self.state.current_step_id,
                    correlation_id=self.correlation_id,
                )
                final_status = ExecutionStatus.FAILED
                break

            # Record visit
            self.state.visit_step(self.state.current_step_id)

            # Story 34.7: Delegate via _execute_step_with_retry (backward-compat entry point).
            # This allows test patches on _execute_step / _execute_step_with_retry to work.
            result = self._execute_step_with_retry(current_step)

            # Update state
            self.state.last_step_outcome = result.outcome
            if result.is_error:
                self.state.last_error = {
                    'step_id': self.state.current_step_id,
                    'error_message': result.error_message,
                    'error_details': result.error_details,
                }

            # Story 25.2: If step is WAITING, stop workflow but keep RUNNING status
            # The Celery Beat task (Story 25.3) will resume execution after gates are satisfied
            if result.is_waiting:
                logger.info(
                    "workflow_paused_waiting_gate",
                    execution_id=self.execution.id,
                    step_id=self.state.current_step_id,
                    correlation_id=self.correlation_id,
                )
                # Keep execution in RUNNING status — do NOT set completed_at
                # Story 25.3 will resume from this step
                return ExecutionStatus.RUNNING

            # AC2: If step failed and no error path, workflow fails
            has_error_path = (
                'on_error_step_ids' in current_step or 'on_error_step_id' in current_step
            )
            if result.is_error and not has_error_path:
                # Backward compat: no explicit error path = fail workflow
                logger.warning(
                    "workflow_step_failed_no_error_path",
                    execution_id=self.execution.id,
                    step_id=self.state.current_step_id,
                    error_message=result.error_message,
                    correlation_id=self.correlation_id,
                )
                final_status = ExecutionStatus.FAILED
                break

            # Resolve next step based on outcome
            next_step_id = self._resolve_next_step(current_step, result.outcome)

            # AC4: record the path taken (success/error) and transition info
            self.state.path_trace.append(
                {
                    'step_id': self.state.current_step_id,
                    'outcome': result.outcome.value,
                    'next_step_id': next_step_id,
                }
            )

            # AC1, AC2: If next_step_id is None, workflow terminates
            if next_step_id is None:
                logger.info(
                    "workflow_terminated_naturally",
                    execution_id=self.execution.id,
                    last_outcome=result.outcome.value,
                    correlation_id=self.correlation_id,
                )
                # Workflow ends with last step's outcome
                if result.is_error:
                    final_status = ExecutionStatus.FAILED
                break

            # Move to next step
            self.state.current_step_id = next_step_id

        # Update final execution status
        self.execution.status = final_status
        self.execution.completed_at = timezone.now()
        self.execution.save()

        # Audit
        audit_action_type = (
            AuditActionType.EXECUTION_COMPLETED
            if final_status == ExecutionStatus.COMPLETED
            else AuditActionType.EXECUTION_FAILED
        )

        audit_details = {
            'action_id': self.action.id,
            'action_name': self.action.name,
            'transition_count': self.state.transition_count,
            'final_outcome': self.state.last_step_outcome.value if self.state.last_step_outcome else None,
            # AC4: minimal audit proof of the path taken
            'path_trace': self.state.path_trace,
        }

        if self.state.last_error:
            audit_details['last_error'] = self.state.last_error

        AuditService.create_entry(
            user_id=str(self.execution.user_id),
            action_type=audit_action_type,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=self.execution.id,
            details=audit_details,
            correlation_id=self.correlation_id,
        )

        logger.info(
            "workflow_execution_finished",
            execution_id=self.execution.id,
            final_status=final_status,
            transition_count=self.state.transition_count,
            correlation_id=self.correlation_id,
        )

        return final_status
