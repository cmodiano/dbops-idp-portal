"""
Tests for executions.infra.work_queue — Story 78.9 AC3.

Verifies the WorkQueue façade correctly delegates to RunnableStepService
for enqueue, claim, release, and reclaim_expired operations.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from executions.infra.work_queue import WorkQueue
from executions.models import RunnableStep
from tests.factories import ExecutionStepFactory


@pytest.mark.django_db(transaction=True)
class TestEnqueue:
    """AC3: enqueue creates a RunnableStep."""

    def test_enqueue_creates_runnable_step(self):
        step = ExecutionStepFactory()
        result = WorkQueue.enqueue(step)
        assert result is not None
        assert RunnableStep.objects.filter(execution_step=step).exists()

    def test_enqueue_idempotent(self):
        step = ExecutionStepFactory()
        first = WorkQueue.enqueue(step)
        second = WorkQueue.enqueue(step)
        assert first is not None
        assert second is None
        assert RunnableStep.objects.filter(execution_step=step).count() == 1

    def test_enqueue_with_priority(self):
        step = ExecutionStepFactory()
        result = WorkQueue.enqueue(step, priority=5)
        assert result.priority == 5


@pytest.mark.django_db(transaction=True)
class TestClaim:
    """AC3: claim returns steps with lease."""

    def test_claim_returns_enqueued_steps(self):
        step = ExecutionStepFactory()
        WorkQueue.enqueue(step)
        batch = WorkQueue.claim(batch_size=1)
        assert len(batch) == 1
        assert batch[0].execution_step_id == step.id

    def test_claim_empty_queue(self):
        batch = WorkQueue.claim(batch_size=5)
        assert batch == []

    def test_claimed_step_not_reclaimed(self):
        step = ExecutionStepFactory()
        WorkQueue.enqueue(step)
        batch1 = WorkQueue.claim(batch_size=1)
        batch2 = WorkQueue.claim(batch_size=1)
        assert len(batch1) == 1
        assert len(batch2) == 0


@pytest.mark.django_db(transaction=True)
class TestReclaimExpired:
    """AC3: reclaim_expired recovers expired leases."""

    def test_reclaim_expired_leases(self):
        step = ExecutionStepFactory()
        WorkQueue.enqueue(step)
        # Claim the step
        WorkQueue.claim(batch_size=1)
        # Expire the lease manually
        RunnableStep.objects.filter(execution_step=step).update(
            claimed_until=timezone.now() - timedelta(seconds=1),
        )
        reclaimed = WorkQueue.reclaim_expired()
        assert reclaimed == 1
        # Now it should be claimable again
        batch = WorkQueue.claim(batch_size=1)
        assert len(batch) == 1


@pytest.mark.django_db(transaction=True)
class TestRelease:
    """AC3: release deletes a step from the queue."""

    def test_release_removes_step(self):
        step = ExecutionStepFactory()
        WorkQueue.enqueue(step)
        runnable = RunnableStep.objects.get(execution_step=step)
        result = WorkQueue.release(runnable.execution_step_id)
        assert result is True
        assert not RunnableStep.objects.filter(execution_step=step).exists()
