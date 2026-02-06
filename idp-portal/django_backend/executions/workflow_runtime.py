"""
Workflow Runtime Engine - Story 16.3

Orchestrates execution of workflows with conditional branching (on_success_step_id, on_error_step_id).
Handles success/error paths, loop detection, and execution state management.

Architecture:
- WorkflowExecutionState: Runtime state tracking (current step, visited counts, outcomes)
- WorkflowRuntime: Main orchestrator that executes workflow steps following branches
- StepResult: Result of executing a single step (success/error + payload)
"""

import structlog
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from django.db import transaction
from django.utils import timezone

from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
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

    Executes workflow steps following conditional branches (on_success_step_id, on_error_step_id).
    Handles loop detection, state management, and execution updates.
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
        self.correlation_id = get_correlation_id()

        # Track global step_order counter for ExecutionStep creation
        self._step_order_counter = 0

        # Load workflow steps from action
        self.workflow_steps = self._load_workflow_steps()
        self.steps_by_id = {step.get('step_id'): step for step in self.workflow_steps if step.get('step_id')}

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
            List of step dicts with step_id, on_success_step_id, on_error_step_id, etc.
        """
        steps = self.action.get_execution_steps() or []
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

        Backward compatibility (Story 16.3 guardrail):
        - If on_success_step_id/on_error_step_id are absent, use linear order (next step by order)

        Args:
            current_step: Current step dict
            outcome: StepOutcome (SUCCESS or ERROR)

        Returns:
            Next step_id to execute, or None if workflow should terminate
        """
        is_success = outcome == StepOutcome.SUCCESS

        # Branching logic (Story 16.2 fields):
        # Only treat the relevant branch key as "explicit" for the outcome.
        # This avoids a subtle retro-compat bug where having ONLY on_error_step_id would
        # incorrectly terminate a success path (AC1).
        if is_success and 'on_success_step_id' in current_step:
            next_step_id = current_step.get('on_success_step_id')
            logger.debug(
                "workflow_branch_resolution",
                current_step_id=current_step.get('step_id'),
                outcome=outcome.value,
                next_step_id=next_step_id,
                correlation_id=self.correlation_id,
            )
            return next_step_id

        if (not is_success) and 'on_error_step_id' in current_step:
            next_step_id = current_step.get('on_error_step_id')
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

    def _execute_step(self, step: Dict[str, Any]) -> StepResult:
        """
        Execute a single workflow step.

        Story 4.12 AC5: Injects workflow_step_parameters[step_order] for this step.
        When the platform adapter is called (future story), it must receive step_parameters
        as the execution parameters for the referenced action.

        Placeholder implementation for Story 16.3 - actual execution logic
        will be added in future stories (e.g., calling platform adapters).

        For now, creates an ExecutionStep record and marks it COMPLETED.

        Args:
            step: Step dict from workflow definition

        Returns:
            StepResult with outcome
        """
        step_id = step.get('step_id')
        step_name = step.get('name', f"Step {step.get('order', 0)}")

        # Story 4.12 AC5: get parameters for this step (key = workflow step "order" as string)
        step_parameters = self._get_step_parameters(step)

        # Use global counter for step_order to avoid conflicts in loops
        self._step_order_counter += 1
        step_order = self._step_order_counter

        logger.info(
            "workflow_step_executing",
            execution_id=self.execution.id,
            step_id=step_id,
            step_name=step_name,
            step_order=step_order,
            correlation_id=self.correlation_id,
        )

        # Note (AC3): this runtime is strictly sequential in V1.
        # Parallel execution is intentionally NOT supported yet; this is a future enhancement.

        # Create ExecutionStep record
        execution_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_order,
            step_name=step_name,
            step_type='platform',  # Default type for now
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        try:
            # Story 4.12 AC5: Load referenced action and prepare adapter payload
            referenced_action_id = step.get('referenced_action_id')

            if not referenced_action_id:
                raise ValueError(f"Workflow step {step_id} missing referenced_action_id")

            # Load the referenced action (validates it exists and is accessible)
            from catalog.models import Action
            try:
                referenced_action = Action.objects.get(id=referenced_action_id)
            except Action.DoesNotExist:
                raise ValueError(
                    f"Referenced action {referenced_action_id} not found for step {step_id}"
                )

            # Story 4.12 AC5: Prepare complete adapter payload with step_parameters ✓
            adapter_payload = {
                'action_id': referenced_action.id,
                'action_name': referenced_action.name,
                'platform': referenced_action.platform,
                'environment': self.execution.environment,
                'parameters': step_parameters,  # AC5: step params injected!
                'correlation_id': self.correlation_id,
                'execution_id': self.execution.id,
                'execution_step_id': execution_step.id,
            }

            logger.info(
                "workflow_step_adapter_payload_ready",
                execution_id=self.execution.id,
                step_id=step_id,
                referenced_action_id=referenced_action.id,
                referenced_action_name=referenced_action.name,
                platform=referenced_action.platform,
                has_parameters=bool(step_parameters),
                correlation_id=self.correlation_id,
            )

            # TODO (Infrastructure): Platform adapter layer not yet implemented in Django backend.
            # The payload is fully prepared and ready to be passed to the adapter.
            # When adapter infrastructure is available, replace this block with:
            #
            # from platform_adapters import PlatformAdapterFactory
            # adapter = PlatformAdapterFactory.get_adapter(referenced_action.platform)
            # adapter_result = adapter.trigger(adapter_payload)
            # execution_step.status = map_adapter_status(adapter_result.status)
            # execution_step.set_output(adapter_result.to_dict())
            #
            # For now: Simulate successful adapter call with prepared payload
            simulated_adapter_response = {
                'status': 'success',
                'job_id': f'workflow-{self.execution.id}-step-{execution_step.id}',
                'message': f'Simulated execution of {referenced_action.name} (adapter infrastructure pending)',
                'platform': referenced_action.platform,
            }

            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()
            execution_step.set_output(
                {
                    # Story 4.12 AC5: Payload is complete and ready for adapter ✓
                    'adapter_ready': True,
                    'adapter_payload_prepared': adapter_payload,
                    'adapter_response': simulated_adapter_response,
                    'step_id': step_id,
                    'step_name': step_name,
                    'outcome': StepOutcome.SUCCESS.value,
                    # Story 4.12 AC6: Audit trail with parameters used ✓
                    'parameters_used': step_parameters,
                    'delegated_from_workflow': True,
                    'referenced_action_id': referenced_action.id,
                    'referenced_action_name': referenced_action.name,
                }
            )
            execution_step.save()

            logger.info(
                "workflow_step_completed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                referenced_action_id=referenced_action.id,
                adapter_ready=True,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.SUCCESS,
                output={
                    'step_id': step_id,
                    'step_name': step_name,
                    'referenced_action_id': referenced_action.id,
                    'adapter_payload_prepared': True,
                }
            )

        except ValueError as e:
            # Handle validation errors (missing referenced_action_id, action not found)
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = str(e)
            execution_step.save()

            logger.error(
                "workflow_step_validation_failed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                error=str(e),
                error_type='validation',
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=str(e),
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'error_type': 'validation',
                }
            )

        except Exception as e:
            # Handle unexpected step failures
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = str(e)
            execution_step.save()

            logger.error(
                "workflow_step_failed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=str(e),
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'error_type': type(e).__name__,
                }
            )

    @transaction.atomic
    def run(self) -> ExecutionStatus:
        """
        Execute the complete workflow following branches.

        Implements AC1-AC5:
        - AC1: Follow on_success_step_id on success
        - AC2: Follow on_error_step_id on error
        - AC4: Convergence (same next step from success/error paths)
        - AC5: Loop detection (max MAX_STEP_TRANSITIONS transitions)

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

        # Find first step (order = 1 or minimum order)
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

            # Execute step
            result = self._execute_step(current_step)

            # Update state
            self.state.last_step_outcome = result.outcome
            if result.is_error:
                self.state.last_error = {
                    'step_id': self.state.current_step_id,
                    'error_message': result.error_message,
                    'error_details': result.error_details,
                }

            # AC2: If step failed and no error path, workflow fails
            if result.is_error and 'on_error_step_id' not in current_step:
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
