"""
Workflow Runtime Engine - Story 16.3, 16.4, 20.3

Orchestrates execution of workflows with conditional branching (on_success_step_id, on_error_step_id).
Handles success/error paths, loop detection, execution state management,
and retry with exponential backoff (Story 16.4).
Story 20.3: Retry uses Celery apply_async(countdown=...) instead of time.sleep().

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

    # Story 16.4: Patterns indicating permanent (non-retryable) errors
    # M2 FIX: Kept as class constant for now, but should be extracted to
    # executions/constants.py for reusability across modules
    NON_RETRYABLE_PATTERNS = [
        'validation',
        'permission',
        'not found',
        'unauthorized',
        'forbidden',
        'bad request',
        '400', '401', '403', '404',
    ]

    def _is_retryable_error(self, result: StepResult) -> bool:
        """
        Determine if an error is retryable (temporary) or permanent (AC3).

        Permanent errors: validation, permission, 4xx HTTP errors.
        Temporary errors: timeout, connection, 5xx, generic exceptions.

        Args:
            result: StepResult from step execution

        Returns:
            True if error is retryable (temporary), False if permanent
        """
        error_message = result.error_message
        if not error_message:
            return True

        # Check error_type first (more reliable than string matching)
        error_details = result.error_details or {}
        error_type = error_details.get('error_type', '')
        if error_type in ('validation', 'permission'):
            return False

        # Fallback to string pattern matching
        error_lower = error_message.lower()
        for pattern in self.NON_RETRYABLE_PATTERNS:
            if pattern in error_lower:
                return False
        return True

    def _execute_step_with_retry(self, step: Dict[str, Any]) -> StepResult:
        """
        Execute a step with retry logic if retry_enabled is true (Story 16.4, 20.3).

        Story 20.3: Uses Celery apply_async(countdown=...) for non-blocking retry
        instead of time.sleep(). First attempt is synchronous; subsequent retries
        are scheduled as Celery tasks.

        Implements:
        - AC1: Retry with exponential backoff (via Celery countdown)
        - AC2: Stop retrying on success
        - AC3: Stop retrying on permanent errors
        - AC4: Cancel-aware (checks execution status before each attempt)
        - AC5: Audit trail for each attempt

        Args:
            step: Step dict from workflow definition

        Returns:
            StepResult with final outcome after first attempt
        """
        retry_enabled = step.get('retry_enabled', False)

        if not retry_enabled:
            return self._execute_step(step)

        max_attempts = step.get('retry_max_attempts', 3)
        interval_seconds = step.get('retry_interval_seconds', 60)
        step_id = step.get('step_id', 'unknown')

        # AC4: Check if execution was cancelled before first attempt
        from executions.cancellation_cache import is_cancelled
        if is_cancelled(self.execution.id):
            logger.info(
                "workflow_step_retry_cancelled",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                correlation_id=self.correlation_id,
            )
            ExecutionStep.objects.create(
                execution=self.execution,
                step_order=self._step_order_counter + 1,
                step_name=step.get('name', f"Step {step.get('order', 0)}"),
                step_type='platform',
                status=ExecutionStepStatus.FAILED,
                started_at=timezone.now(),
                completed_at=timezone.now(),
                error_message="Execution cancelled during retry",
            )
            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message="Execution cancelled during retry",
            )

        # First attempt: synchronous (attempt=1)
        logger.info(
            "workflow_step_retry_attempt",
            execution_id=self.execution.id,
            step_id=step_id,
            attempt=1,
            max_attempts=max_attempts,
            correlation_id=self.correlation_id,
        )

        result = self._execute_step(step)

        # AC2: Success — stop immediately
        if result.is_success:
            logger.info(
                "workflow_step_retry_success",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                max_attempts=max_attempts,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_SUCCESS,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'result': 'success',
                },
                correlation_id=self.correlation_id,
            )
            return result

        # AC3: Permanent error — stop immediately
        if result.is_error and not self._is_retryable_error(result):
            logger.warning(
                "workflow_step_non_retryable_error",
                execution_id=self.execution.id,
                step_id=step_id,
                attempt=1,
                error=result.error_message,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_ABORTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'reason': 'non_retryable_error',
                    'error': result.error_message,
                },
                correlation_id=self.correlation_id,
            )
            return result

        # Temporary failure — schedule Celery retry if more attempts available
        if max_attempts > 1:
            from executions.tasks import retry_workflow_step

            delay_seconds = interval_seconds  # Delay before attempt 2

            logger.info(
                "workflow_step_retry_scheduling_celery",
                execution_id=self.execution.id,
                step_id=step_id,
                next_attempt=2,
                delay_seconds=delay_seconds,
                correlation_id=self.correlation_id,
            )

            # AC5: Audit trail for failed first attempt
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'attempt': 1,
                    'max_attempts': max_attempts,
                    'result': 'error',
                    'error': result.error_message,
                    'next_wait_seconds': delay_seconds,
                    'retry_method': 'celery',
                },
                correlation_id=self.correlation_id,
            )

            # Schedule async retry via Celery
            retry_workflow_step.apply_async(
                args=[self.execution.id, step, 2],
                countdown=delay_seconds,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=f"Step failed, retry scheduled (attempt 2/{max_attempts} in {delay_seconds}s)",
                error_details={
                    'retry_scheduled': True,
                    'next_attempt': 2,
                    'max_attempts': max_attempts,
                    'delay_seconds': delay_seconds,
                },
            )

        # max_attempts = 1, no retry possible
        logger.error(
            "workflow_step_retry_exhausted",
            execution_id=self.execution.id,
            step_id=step_id,
            max_attempts=1,
            final_error=result.error_message,
            correlation_id=self.correlation_id,
        )
        AuditService.create_entry(
            user_id=str(self.execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=self.execution.id,
            details={
                'step_id': step_id,
                'max_attempts': 1,
                'final_error': result.error_message,
            },
            correlation_id=self.correlation_id,
        )
        return result

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
        Execute a single workflow step, or put it in WAITING if gate_conditions present.

        Story 25.2: If step has gate_conditions, create ExecutionStep in WAITING status
        and return immediately without executing. The Celery Beat task (Story 25.3) will
        evaluate gates and unblock the step later.

        Story 4.12 AC5: Injects workflow_step_parameters[step_order] for this step.

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

        # Story 25.2: Check for gate_conditions — create WAITING step instead of executing
        gate_conditions = step.get('gate_conditions', [])
        if gate_conditions:
            from executions.gate_context import build_waiting_context

            execution_step = ExecutionStep.objects.create(
                execution=self.execution,
                step_order=step_order,
                step_name=step_name,
                step_type='platform',
                status=ExecutionStepStatus.WAITING,
            )

            waiting_context = build_waiting_context(execution_step, gate_conditions)
            execution_step.set_output(waiting_context)
            execution_step.save()

            logger.info(
                "workflow_step_waiting",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                gate_conditions_count=len(gate_conditions),
                correlation_id=self.correlation_id,
            )

            # AC3: Audit trail for WAITING step creation
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_WAITING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'step_order': step_order,
                    'gate_conditions_count': len(gate_conditions),
                    'gate_types': [c.get('type') for c in gate_conditions],
                },
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.WAITING,
                error_message="Step waiting for gate conditions",
                error_details={
                    'step_id': step_id,
                    'step_name': step_name,
                    'waiting': True,
                    'gate_conditions_count': len(gate_conditions),
                },
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
                referenced_action = Action.objects.select_related('integration').get(id=referenced_action_id)
            except Action.DoesNotExist:
                raise ValueError(
                    f"Referenced action {referenced_action_id} not found for step {step_id}"
                )

            # Story 24.4 (AC5): Validate integration status before executing step
            integration = getattr(referenced_action, 'integration', None)
            if integration:
                from integrations.models import IntegrationStatus
                if integration.status == IntegrationStatus.INVALID:
                    error_msg = (
                        f"Workflow step '{step_name}' failed: Integration '{integration.name}' "
                        f"(type: {integration.type}) is invalid and cannot be used. "
                        f"Please update the workflow to use a valid integration before retrying."
                    )
                    logger.error(
                        "workflow_step_blocked_invalid_integration",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        integration_id=integration.id,
                        integration_name=integration.name,
                        integration_type=integration.type,
                        correlation_id=self.correlation_id,
                    )
                    AuditService.create_entry(
                        user_id=str(self.execution.user_id),
                        action_type=AuditActionType.WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION,
                        entity_type=AuditEntityType.EXECUTION,
                        entity_id=self.execution.id,
                        details={
                            'step_id': step_id,
                            'step_name': step_name,
                            'integration_id': integration.id,
                            'integration_name': integration.name,
                            'integration_type': integration.type,
                            'referenced_action_id': referenced_action.id,
                        },
                        correlation_id=self.correlation_id,
                    )
                    raise ValueError(error_msg)

                if integration.status == IntegrationStatus.DEPRECATED:
                    logger.warning(
                        "workflow_step_deprecated_integration",
                        execution_id=self.execution.id,
                        step_id=step_id,
                        integration_id=integration.id,
                        integration_name=integration.name,
                        integration_type=integration.type,
                        correlation_id=self.correlation_id,
                    )
                    AuditService.create_entry(
                        user_id=str(self.execution.user_id),
                        action_type=AuditActionType.EXECUTION_DEPRECATED_INTEGRATION_WARNING,
                        entity_type=AuditEntityType.EXECUTION,
                        entity_id=self.execution.id,
                        details={
                            'step_id': step_id,
                            'step_name': step_name,
                            'integration_id': integration.id,
                            'integration_name': integration.name,
                            'integration_type': integration.type,
                            'referenced_action_id': referenced_action.id,
                        },
                        correlation_id=self.correlation_id,
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

            # H8 FIX: Ensure correlation_id in all logs
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

            # Story 30.15 AC2/AC3: Real adapter call via get_platform_adapter()
            adapter_response = self._call_platform_adapter(
                referenced_action, integration, adapter_payload, execution_step,
            )

            step_output_data = {
                'adapter_ready': True,
                'adapter_payload_prepared': adapter_payload,
                'adapter_response': adapter_response,
                'step_id': step_id,
                'step_name': step_name,
                'outcome': StepOutcome.SUCCESS.value,
                'parameters_used': step_parameters,
                'delegated_from_workflow': True,
                'referenced_action_id': referenced_action.id,
                'referenced_action_name': referenced_action.name,
            }

            # Story 28.2: Evaluate business_rule_policies after step output
            policy_result = self._evaluate_policy_if_needed(
                execution_step, referenced_action, step_output_data,
            )
            if policy_result is not None:
                # PolicyEvaluator decided — step is WAITING or auto-approved
                execution_step.set_output(step_output_data)
                execution_step.save()
                return policy_result

            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()
            execution_step.set_output(step_output_data)
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
            # Story 17.6: Justified broad catch - Step can raise any exception from adapters
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = f"{type(e).__name__}: {str(e)}"
            execution_step.save()

            logger.error(
                "workflow_step_failed",
                execution_id=self.execution.id,
                step_id=step_id,
                step_name=step_name,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=self.correlation_id,
                exc_info=True,
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

    def _call_platform_adapter(
        self,
        referenced_action: Any,
        integration: Any,
        adapter_payload: dict,
        execution_step: ExecutionStep,
    ) -> dict:
        """Call the real platform adapter if integration is configured, else log CRITICAL and return simulated response.

        Story 30.15 AC2/AC3: Replaces simulated adapter call with real adapter infrastructure.
        Falls back to simulated response with CRITICAL audit trail when adapter call is not possible.
        """
        if not integration:
            logger.critical(
                "workflow_step_no_integration_simulated",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                action_id=referenced_action.id,
                action_name=referenced_action.name,
                platform=referenced_action.platform,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_RUNNING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'warning': 'SIMULATED_ADAPTER_RESPONSE',
                    'reason': 'Action has no integration configured',
                    'action_id': referenced_action.id,
                    'platform': referenced_action.platform,
                },
                correlation_id=self.correlation_id,
            )
            return {
                'status': 'success',
                'simulated': True,
                'job_id': f'sim-{self.execution.id}-{execution_step.id}',
                'message': f'SIMULATED: {referenced_action.name} — no integration configured',
                'platform': referenced_action.platform,
            }

        try:
            from adapters import get_platform_adapter
            from adapters.utils import build_auth_headers
            from asgiref.sync import async_to_sync

            auth_headers = build_auth_headers(integration, self.correlation_id)

            # Extract platform-specific kwargs from integration config
            platform_kwargs: dict[str, Any] = {}
            config = integration.get_config() if hasattr(integration, 'get_config') else {}
            if config:
                for key in ('owner', 'repo', 'organization', 'namespace'):
                    if key in config:
                        platform_kwargs[key] = config[key]
                if 'ssl_verify' in config:
                    platform_kwargs['ssl_verify'] = config['ssl_verify']
                if config.get('ca_bundle_path'):
                    platform_kwargs['ca_bundle_path'] = config['ca_bundle_path']

            # Story 31.9: Derive platform_type from integration.type (already normalized)
            # instead of action.platform to avoid mismatch (e.g. "GitHub Actions" → "github actions" ≠ "github_actions")
            platform_type = integration.type

            adapter = get_platform_adapter(
                platform_type=platform_type,
                base_url=integration.base_url,
                auth_headers=auth_headers,
                **platform_kwargs,
            )

            # Build trigger kwargs from adapter_payload
            trigger_kwargs: dict[str, Any] = {
                'correlation_id': self.correlation_id,
            }
            params = adapter_payload.get('parameters') or {}
            if params.get('template_id'):
                trigger_kwargs['template_id'] = str(params['template_id'])
            if params.get('resource_type'):
                trigger_kwargs['resource_type'] = params['resource_type']
            if params.get('extra_vars'):
                trigger_kwargs['extra_vars'] = params['extra_vars']

            adapter_result = async_to_sync(adapter.trigger)(**trigger_kwargs)

            # Store platform_job_id on execution_step for webhook correlation
            platform_job_id = adapter_result.get('platform_job_id')
            if platform_job_id:
                execution_step.platform_job_id = str(platform_job_id)

            logger.info(
                "workflow_step_adapter_call_success",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                platform=referenced_action.platform,
                platform_job_id=platform_job_id,
                correlation_id=self.correlation_id,
            )
            return adapter_result

        except Exception as exc:
            # Adapter call failed (unsupported platform, missing params, network error, etc.)
            # Log CRITICAL and fall back to simulated response so the workflow can continue.
            # Real adapter failures are surfaced via the 'simulated' flag in step output.
            logger.critical(
                "workflow_step_adapter_call_failed",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                platform=referenced_action.platform,
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=self.correlation_id,
            )
            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_RUNNING,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'warning': 'SIMULATED_ADAPTER_RESPONSE',
                    'reason': f'Adapter call failed: {type(exc).__name__}: {exc}',
                    'action_id': referenced_action.id,
                    'platform': referenced_action.platform,
                },
                correlation_id=self.correlation_id,
            )
            return {
                'status': 'success',
                'simulated': True,
                'job_id': f'sim-{self.execution.id}-{execution_step.id}',
                'message': f'SIMULATED: adapter call failed for {referenced_action.platform}: {exc}',
                'platform': referenced_action.platform,
            }

    def _evaluate_policy_if_needed(
        self,
        execution_step: ExecutionStep,
        action: Any,
        step_output: dict,
    ) -> Optional[StepResult]:
        """
        Story 28.2: Evaluate business_rule_policies after step output.

        If the action has policies matching this step type, evaluate them.
        Returns a StepResult if the policy requires approval (WAITING) or
        auto-approves with audit trail. Returns None if no policy applies.
        """
        from dataclasses import asdict
        from executions.policy_evaluator import PolicyEvaluator, PolicyEvaluationError

        policies = getattr(action, 'business_rule_policies', None)
        if not policies:
            return None

        rules = policies.get("on_step_output", []) if isinstance(policies, dict) else []
        if not rules:
            return None

        # Check if any rule matches this step type
        step_type = execution_step.step_type
        matching_rule = next(
            (r for r in rules if r.get("when", {}).get("step_type") == step_type),
            None,
        )
        if not matching_rule:
            return None

        try:
            evaluator = PolicyEvaluator()
            policy_decision = evaluator.evaluate_policy(
                execution_step, action, step_output,
            )
        except PolicyEvaluationError as exc:
            # Policy evaluation failed — mark step FAILED
            execution_step.status = ExecutionStepStatus.FAILED
            execution_step.completed_at = timezone.now()
            execution_step.error_message = exc.message
            execution_step.save()

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_EVALUATION_FAILED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'error': exc.message,
                },
                correlation_id=self.correlation_id,
            )

            logger.error(
                "policy_evaluation_error",
                execution_id=self.execution.id,
                step_id=execution_step.id,
                error_message=exc.message,
                correlation_id=self.correlation_id,
            )

            return StepResult(
                outcome=StepOutcome.ERROR,
                error_message=exc.message,
                error_details={'policy_evaluation_failed': True},
            )

        # Store policy decision in step output
        decision_dict = asdict(policy_decision)
        step_output['policy_decision'] = decision_dict

        if policy_decision.require_approval:
            # Require approval — WAITING
            execution_step.status = ExecutionStepStatus.WAITING
            execution_step.save()

            # Add gate_condition for manual approval
            existing_output = execution_step.get_output() or {}
            gate_conditions = existing_output.get('gate_conditions', [])
            gate_conditions.append({
                'type': 'approval_granted',
                'reason': policy_decision.decision_reason,
                'source': 'policy_evaluator',
            })
            step_output['gate_conditions'] = gate_conditions

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'policy_decision': decision_dict,
                },
                correlation_id=self.correlation_id,
            )

            # MED-7 FIX: Removed redundant logging (PolicyEvaluator already logs decision)

            return StepResult(
                outcome=StepOutcome.WAITING,
                error_message="Step waiting for policy approval",
                error_details={
                    'waiting': True,
                    'policy_decision': decision_dict,
                },
            )
        else:
            # Auto-approved — continue normally but record audit
            execution_step.status = ExecutionStepStatus.COMPLETED
            execution_step.completed_at = timezone.now()

            AuditService.create_entry(
                user_id=str(self.execution.user_id),
                action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=self.execution.id,
                details={
                    'step_id': execution_step.id,
                    'step_name': execution_step.step_name,
                    'policy_decision': decision_dict,
                },
                correlation_id=self.correlation_id,
            )

            # MED-7 FIX: Removed redundant logging (PolicyEvaluator already logs decision)

            # Return None — caller will continue with normal COMPLETED flow
            # But we already set status, so return a SUCCESS result
            return StepResult(
                outcome=StepOutcome.SUCCESS,
                output={
                    'policy_decision': decision_dict,
                    'auto_approved': True,
                },
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

            # Execute step (Story 16.4: with retry if retry_enabled)
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
