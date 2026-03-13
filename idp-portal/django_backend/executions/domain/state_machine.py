"""
Centralised state-machine for Execution and ExecutionStep transitions.

Pure-Python module (no Django ORM dependency) — validates transition legality
at the application level, complementing the Oracle CHECK constraints that only
guard allowed *values*, not allowed *transitions*.

Usage:
    from executions.domain.state_machine import assert_execution_transition

    # Validates + returns target; raises InvalidStateTransition if illegal
    new_status = assert_execution_transition(current_status, target_status)
"""

from typing import Dict, FrozenSet, Set

from executions.models import ExecutionStatus, ExecutionStepStatus


class InvalidStateTransition(ValueError):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, current: str, target: str, entity_type: str) -> None:
        self.current = current
        self.target = target
        self.entity_type = entity_type
        super().__init__(
            f"Invalid {entity_type} transition: {current} → {target}"
        )


# ---------------------------------------------------------------------------
# Execution transitions
# ---------------------------------------------------------------------------

EXECUTION_TRANSITIONS: Dict[str, Set[str]] = {
    ExecutionStatus.SUBMITTED: {
        ExecutionStatus.RUNNING,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.INTEGRATION_ERROR,
    },
    ExecutionStatus.RUNNING: {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.INTEGRATION_ERROR: {
        ExecutionStatus.SUBMITTED,  # retry
    },
    ExecutionStatus.PENDING_APPROVAL: set(),  # deprecated, no outgoing
    ExecutionStatus.COMPLETED: set(),  # terminal
    ExecutionStatus.FAILED: set(),  # terminal
    ExecutionStatus.CANCELLED: set(),  # terminal
    ExecutionStatus.REJECTED: set(),  # terminal
}

EXECUTION_TERMINAL_STATES: FrozenSet[str] = frozenset(
    status for status, targets in EXECUTION_TRANSITIONS.items() if not targets
)

# ---------------------------------------------------------------------------
# ExecutionStep transitions
# ---------------------------------------------------------------------------

STEP_TRANSITIONS: Dict[str, Set[str]] = {
    ExecutionStepStatus.PENDING: {
        ExecutionStepStatus.RUNNING,
        ExecutionStepStatus.SKIPPED,
    },
    ExecutionStepStatus.RUNNING: {
        ExecutionStepStatus.COMPLETED,
        ExecutionStepStatus.FAILED,
        ExecutionStepStatus.WAITING,
        ExecutionStepStatus.PENDING,  # crash recovery reset via reconcile
    },
    ExecutionStepStatus.WAITING: {
        ExecutionStepStatus.COMPLETED,  # approve
        ExecutionStepStatus.FAILED,  # reject / timeout
    },
    ExecutionStepStatus.COMPLETED: set(),  # terminal
    ExecutionStepStatus.FAILED: {
        ExecutionStepStatus.PENDING,  # redrive via reconcile
    },
    ExecutionStepStatus.SKIPPED: set(),  # terminal
}

STEP_TERMINAL_STATES: FrozenSet[str] = frozenset(
    status for status, targets in STEP_TRANSITIONS.items() if not targets
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_execution_transition(current: str, target: str) -> bool:
    """Return True if *current → target* is a valid Execution transition."""
    allowed = EXECUTION_TRANSITIONS.get(current)
    if allowed is None:
        return False
    return target in allowed


def validate_step_transition(current: str, target: str) -> bool:
    """Return True if *current → target* is a valid ExecutionStep transition."""
    allowed = STEP_TRANSITIONS.get(current)
    if allowed is None:
        return False
    return target in allowed


def assert_execution_transition(current: str, target: str) -> str:
    """Validate and return *target*, or raise `InvalidStateTransition`."""
    if not validate_execution_transition(current, target):
        raise InvalidStateTransition(current, target, "Execution")
    return target


def assert_step_transition(current: str, target: str) -> str:
    """Validate and return *target*, or raise `InvalidStateTransition`."""
    if not validate_step_transition(current, target):
        raise InvalidStateTransition(current, target, "ExecutionStep")
    return target
