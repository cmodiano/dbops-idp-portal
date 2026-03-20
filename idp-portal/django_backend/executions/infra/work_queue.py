"""
Façade for the durable work queue (RUNNABLE_STEPS).

Wraps `RunnableStepService` behind a simplified API so callers interact with
a queue abstraction rather than the underlying service directly.

Usage:
    from executions.infra.work_queue import WorkQueue

    WorkQueue.enqueue(execution_step)
    batch = WorkQueue.claim(batch_size=5, lease_seconds=300)
    WorkQueue.release(runnable_step_id)
    reclaimed = WorkQueue.reclaim_expired(threshold_seconds=300)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from executions.models import RunnableStep
from executions.services.runnable_steps import RunnableStepService

__all__ = ["WorkQueue", "RunnableStep"]

if TYPE_CHECKING:
    from executions.models import ExecutionStep


class WorkQueue:
    """Simplified façade over RunnableStepService."""

    @staticmethod
    def enqueue(
        execution_step: "ExecutionStep",
        *,
        priority: int = 0,
    ) -> RunnableStep | None:
        """Add a step to the work queue. Idempotent."""
        return RunnableStepService.enqueue(execution_step, priority=priority)

    @staticmethod
    def claim(
        batch_size: int = 1,
        *,
        worker_id: str = "orchestration-worker",
        step_types: list[str] | None = None,
    ) -> list[RunnableStep]:
        """Claim up to *batch_size* steps with a lease."""
        return RunnableStepService.claim_batch(
            worker_id=worker_id,
            limit=batch_size,
            step_types=step_types,
        )

    @staticmethod
    def release(execution_step_id: int) -> bool:
        """Release (delete) a claimed step from the queue."""
        return RunnableStepService.delete(execution_step_id)

    @staticmethod
    def delete_for_execution(execution_id: int) -> int:
        """Remove all queued steps for a given execution (e.g. on cancel)."""
        return RunnableStepService.delete_for_execution(execution_id)

    @staticmethod
    def reclaim_expired() -> int:
        """Reclaim steps whose lease has expired (crash recovery)."""
        return RunnableStepService.reclaim_expired_leases()
