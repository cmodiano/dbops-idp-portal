"""
Shared types for workflow runtime (Story 16.3, 34.7).

Extracted from workflow_runtime for reuse by workflow_step_executor,
workflow_retry, tasks/retry, and other execution modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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
        outcome: SUCCESS, ERROR, or WAITING (from StepOutcome enum).
            - SUCCESS: step completed successfully
            - ERROR: step failed; error_message and error_details apply
            - WAITING: step blocked by gate_conditions (Story 25.2)
        output: Optional output data from the step
        error_message: Error message if outcome is ERROR (otherwise None)
        error_details: Additional error context if outcome is ERROR (otherwise None)
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
    """
    execution_id: int
    current_step_id: Optional[str] = None
    visited_counts: Dict[str, int] = field(default_factory=dict)
    transition_count: int = 0
    last_step_outcome: Optional[StepOutcome] = None
    last_error: Optional[Dict[str, Any]] = None
    path_trace: List[Dict[str, Any]] = field(default_factory=list)

    def visit_step(self, step_id: str) -> None:
        """Record a visit to a step."""
        self.visited_counts[step_id] = self.visited_counts.get(step_id, 0) + 1
        self.transition_count += 1

    def has_exceeded_max_transitions(self) -> bool:
        """Check if workflow has reached or exceeded maximum transitions (loop detection)."""
        return self.transition_count >= MAX_STEP_TRANSITIONS
