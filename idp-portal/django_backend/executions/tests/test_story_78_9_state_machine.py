"""
Tests for executions.domain.state_machine — Story 78.9 AC1.

Pure-Python state-machine with no DB dependency.
"""

import pytest

from executions.domain.state_machine import (
    EXECUTION_TERMINAL_STATES,
    EXECUTION_TRANSITIONS,
    STEP_TERMINAL_STATES,
    STEP_TRANSITIONS,
    InvalidStateTransition,
    assert_execution_transition,
    assert_step_transition,
    validate_execution_transition,
    validate_step_transition,
)
from executions.models import ExecutionStatus, ExecutionStepStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_valid_execution_pairs():
    """Yield (current, target) for every valid Execution transition."""
    for current, targets in EXECUTION_TRANSITIONS.items():
        for target in targets:
            yield current, target


def _all_valid_step_pairs():
    """Yield (current, target) for every valid Step transition."""
    for current, targets in STEP_TRANSITIONS.items():
        for target in targets:
            yield current, target


def _all_execution_statuses():
    return [s.value for s in ExecutionStatus]


def _all_step_statuses():
    return [s.value for s in ExecutionStepStatus]


# ===================================================================
# Execution transitions
# ===================================================================

class TestExecutionTransitionsMap:
    """Verify the transition map covers every ExecutionStatus value."""

    def test_all_statuses_have_entry(self):
        for status in _all_execution_statuses():
            assert status in EXECUTION_TRANSITIONS, (
                f"{status} missing from EXECUTION_TRANSITIONS"
            )

    def test_terminal_states_have_no_outgoing(self):
        for status in EXECUTION_TERMINAL_STATES:
            assert EXECUTION_TRANSITIONS[status] == set()

    def test_terminal_states_set(self):
        expected = {
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.REJECTED,
            ExecutionStatus.PENDING_APPROVAL,  # deprecated, no outgoing
        }
        assert EXECUTION_TERMINAL_STATES == expected


class TestValidateExecutionTransition:

    @pytest.mark.parametrize("current,target", list(_all_valid_execution_pairs()))
    def test_valid_transitions_accepted(self, current, target):
        assert validate_execution_transition(current, target) is True

    @pytest.mark.parametrize("current", [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.REJECTED,
    ])
    def test_terminal_states_reject_all(self, current):
        for target in _all_execution_statuses():
            assert validate_execution_transition(current, target) is False

    def test_completed_to_running_rejected(self):
        assert validate_execution_transition(
            ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING
        ) is False

    def test_cancelled_to_submitted_rejected(self):
        assert validate_execution_transition(
            ExecutionStatus.CANCELLED, ExecutionStatus.SUBMITTED
        ) is False

    def test_integration_error_to_submitted_accepted(self):
        assert validate_execution_transition(
            ExecutionStatus.INTEGRATION_ERROR, ExecutionStatus.SUBMITTED
        ) is True

    def test_unknown_current_returns_false(self):
        assert validate_execution_transition("BOGUS", ExecutionStatus.RUNNING) is False


class TestAssertExecutionTransition:

    def test_valid_returns_target(self):
        result = assert_execution_transition(
            ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING
        )
        assert result == ExecutionStatus.RUNNING

    def test_invalid_raises(self):
        with pytest.raises(InvalidStateTransition) as exc_info:
            assert_execution_transition(
                ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING
            )
        err = exc_info.value
        assert err.current == ExecutionStatus.COMPLETED
        assert err.target == ExecutionStatus.RUNNING
        assert err.entity_type == "Execution"
        assert "COMPLETED" in str(err)
        assert "RUNNING" in str(err)


# ===================================================================
# Step transitions
# ===================================================================

class TestStepTransitionsMap:

    def test_all_statuses_have_entry(self):
        for status in _all_step_statuses():
            assert status in STEP_TRANSITIONS, (
                f"{status} missing from STEP_TRANSITIONS"
            )

    def test_terminal_states_have_no_outgoing(self):
        for status in STEP_TERMINAL_STATES:
            assert STEP_TRANSITIONS[status] == set()

    def test_terminal_states_set(self):
        expected = {
            ExecutionStepStatus.COMPLETED,
            ExecutionStepStatus.SKIPPED,
        }
        assert STEP_TERMINAL_STATES == expected


class TestValidateStepTransition:

    @pytest.mark.parametrize("current,target", list(_all_valid_step_pairs()))
    def test_valid_transitions_accepted(self, current, target):
        assert validate_step_transition(current, target) is True

    def test_failed_to_pending_accepted(self):
        """FAILED → PENDING is legal (redrive via reconcile)."""
        assert validate_step_transition(
            ExecutionStepStatus.FAILED, ExecutionStepStatus.PENDING
        ) is True

    @pytest.mark.parametrize("current", [
        ExecutionStepStatus.COMPLETED,
        ExecutionStepStatus.SKIPPED,
    ])
    def test_terminal_states_reject_all(self, current):
        for target in _all_step_statuses():
            assert validate_step_transition(current, target) is False

    def test_completed_to_running_rejected(self):
        assert validate_step_transition(
            ExecutionStepStatus.COMPLETED, ExecutionStepStatus.RUNNING
        ) is False


class TestAssertStepTransition:

    def test_valid_returns_target(self):
        result = assert_step_transition(
            ExecutionStepStatus.PENDING, ExecutionStepStatus.RUNNING
        )
        assert result == ExecutionStepStatus.RUNNING

    def test_invalid_raises(self):
        with pytest.raises(InvalidStateTransition) as exc_info:
            assert_step_transition(
                ExecutionStepStatus.COMPLETED, ExecutionStepStatus.RUNNING
            )
        err = exc_info.value
        assert err.current == ExecutionStepStatus.COMPLETED
        assert err.target == ExecutionStepStatus.RUNNING
        assert err.entity_type == "ExecutionStep"


# ===================================================================
# InvalidStateTransition exception
# ===================================================================

class TestInvalidStateTransition:

    def test_includes_current_target_entity(self):
        err = InvalidStateTransition("A", "B", "Widget")
        assert err.current == "A"
        assert err.target == "B"
        assert err.entity_type == "Widget"
        assert "A" in str(err)
        assert "B" in str(err)
        assert "Widget" in str(err)

    def test_is_value_error(self):
        assert issubclass(InvalidStateTransition, ValueError)
