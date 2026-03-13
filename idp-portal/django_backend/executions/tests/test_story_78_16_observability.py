"""
Tests for executions.observability — Story 78.16 AC6.

Verifies:
  - get_runnable_queue_depth() returns correct pending/running/expired counts
  - get_command_backlog() counts only PENDING commands
  - get_outbox_pending() counts only PENDING outbox entries
  - process_runnable_steps task logs structured metric fields via structlog
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from executions.observability import (
    get_command_backlog,
    get_outbox_pending,
    get_runnable_queue_depth,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execution_step():
    """Create a minimal ExecutionStep (via ExecutionStepFactory) for testing."""
    from tests.factories import ExecutionStepFactory  # noqa: PLC0415
    return ExecutionStepFactory()


def _make_runnable_step(execution_step, *, claimed_by=None, claimed_until=None):
    """Create a RunnableStep with specified claim state."""
    from executions.models import RunnableStep  # noqa: PLC0415
    return RunnableStep.objects.create(
        execution_step=execution_step,
        execution=execution_step.execution,
        step_order=execution_step.step_order,
        step_type="platform",
        claimed_by=claimed_by,
        claimed_until=claimed_until,
    )


def _make_workflow_command(execution, *, status="pending"):
    """Create a WorkflowCommand with specified status."""
    from executions.models import WorkflowCommand  # noqa: PLC0415
    return WorkflowCommand.objects.create(
        execution=execution,
        command_type="cancel",
        status=status,
    )


def _make_outbox_entry(execution, *, status="pending"):
    """Create an ExecutionOutbox entry with specified status."""
    from executions.models import ExecutionOutbox  # noqa: PLC0415
    return ExecutionOutbox.objects.create(
        execution=execution,
        event_type="execution_notification",
        idempotency_key=uuid.uuid4().hex,
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests: get_runnable_queue_depth()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetRunnableQueueDepth:
    """AC3 + AC6: get_runnable_queue_depth() returns correct counts."""

    def test_empty_queue_returns_zeros(self):
        result = get_runnable_queue_depth()
        assert result == {"pending": 0, "running": 0, "expired_leases": 0}

    def test_pending_step_unclaimed(self):
        """A step with no claimed_by is counted as pending."""
        step = _make_execution_step()
        _make_runnable_step(step, claimed_by=None, claimed_until=None)

        result = get_runnable_queue_depth()
        assert result["pending"] == 1
        assert result["running"] == 0
        assert result["expired_leases"] == 0

    def test_running_step_with_active_lease(self):
        """A step with claimed_until in the future is counted as running."""
        step = _make_execution_step()
        future = timezone.now() + timedelta(seconds=60)
        _make_runnable_step(step, claimed_by="worker-abc", claimed_until=future)

        result = get_runnable_queue_depth()
        assert result["running"] == 1
        assert result["expired_leases"] == 0

    def test_expired_lease_step(self):
        """A step with claimed_until in the past is counted as expired_leases."""
        step = _make_execution_step()
        past = timezone.now() - timedelta(seconds=10)
        _make_runnable_step(step, claimed_by="worker-dead", claimed_until=past)

        result = get_runnable_queue_depth()
        assert result["expired_leases"] == 1
        assert result["running"] == 0

    def test_mixed_states(self):
        """Multiple steps in different states are counted independently."""
        step1 = _make_execution_step()
        step2 = _make_execution_step()
        step3 = _make_execution_step()
        step4 = _make_execution_step()

        # 2 pending
        _make_runnable_step(step1)
        _make_runnable_step(step2)
        # 1 running
        _make_runnable_step(step3, claimed_by="worker-1", claimed_until=timezone.now() + timedelta(seconds=30))
        # 1 expired
        _make_runnable_step(step4, claimed_by="worker-dead", claimed_until=timezone.now() - timedelta(seconds=5))

        result = get_runnable_queue_depth()
        assert result["pending"] == 2
        assert result["running"] == 1
        assert result["expired_leases"] == 1


# ---------------------------------------------------------------------------
# Tests: get_command_backlog()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetCommandBacklog:
    """AC3 + AC6: get_command_backlog() counts PENDING only."""

    def test_empty_returns_zero(self):
        assert get_command_backlog() == 0

    def test_counts_only_pending(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_workflow_command(execution, status="pending")
        _make_workflow_command(execution, status="pending")
        _make_workflow_command(execution, status="processed")

        assert get_command_backlog() == 2

    def test_processed_commands_ignored(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_workflow_command(execution, status="processed")
        _make_workflow_command(execution, status="failed")

        assert get_command_backlog() == 0

    def test_single_pending_command(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_workflow_command(execution, status="pending")

        assert get_command_backlog() == 1


# ---------------------------------------------------------------------------
# Tests: get_outbox_pending()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetOutboxPending:
    """AC3 + AC6: get_outbox_pending() counts PENDING only."""

    def test_empty_returns_zero(self):
        assert get_outbox_pending() == 0

    def test_counts_only_pending(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_outbox_entry(execution, status="pending")
        _make_outbox_entry(execution, status="pending")
        _make_outbox_entry(execution, status="dispatched")

        assert get_outbox_pending() == 2

    def test_dispatched_entries_ignored(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_outbox_entry(execution, status="dispatched")
        _make_outbox_entry(execution, status="failed")

        assert get_outbox_pending() == 0

    def test_single_pending_entry(self):
        from tests.factories import ExecutionFactory  # noqa: PLC0415
        execution = ExecutionFactory()

        _make_outbox_entry(execution, status="pending")

        assert get_outbox_pending() == 1


# ---------------------------------------------------------------------------
# Tests: process_runnable_steps — structlog fields (AC6.4)
# ---------------------------------------------------------------------------

class TestProcessRunnableStepsMetrics:
    """AC6.4: process_runnable_steps logs runnable_queue_depth via structlog."""

    def test_structlog_called_with_queue_depth_fields(self):
        """Verify that process_runnable_steps calls logger.info with metric fields."""
        mock_depth = {"pending": 3, "running": 1, "expired_leases": 2}

        with patch("executions.tasks.orchestration_worker.get_runnable_queue_depth", return_value=mock_depth) as mock_get_depth, \
             patch("executions.tasks.orchestration_worker.WorkQueue.claim", return_value=[]), \
             patch("executions.tasks.orchestration_worker.logger") as mock_logger:

            from executions.tasks.orchestration_worker import process_runnable_steps
            process_runnable_steps()

            mock_get_depth.assert_called_once()
            mock_logger.info.assert_any_call(
                "process_runnable_steps_metrics",
                runnable_queue_depth=4,
                runnable_pending=3,
                runnable_running=1,
                runnable_expired_leases=2,
            )

    def test_return_dict_includes_queue_depth(self):
        """Verify the task return dict includes runnable_queue_depth."""
        mock_depth = {"pending": 5, "running": 0, "expired_leases": 0}

        with patch("executions.tasks.orchestration_worker.get_runnable_queue_depth", return_value=mock_depth), \
             patch("executions.tasks.orchestration_worker.WorkQueue.claim", return_value=[]), \
             patch("executions.tasks.orchestration_worker.logger"):

            from executions.tasks.orchestration_worker import process_runnable_steps
            result = process_runnable_steps()

            assert result["runnable_queue_depth"] == 5
            assert result["processed"] == 0
