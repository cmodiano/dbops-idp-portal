"""Service for RUNNABLE_STEPS — work queue of steps ready for execution.

V113: Avoids scanning large partitioned EXECUTION_STEPS table for eligible work.
When the workflow engine determines a step is eligible (prerequisites met, gates
satisfied), it inserts a row here. Workers claim rows, then delete after dispatch.

Usage:
    from executions.services.runnable_steps import RunnableStepService
    RunnableStepService.enqueue(step)
    batch = RunnableStepService.claim_batch(worker_id, limit=10)
    RunnableStepService.delete(step_id)
"""
from __future__ import annotations

import structlog
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from executions.models import RunnableStep

if TYPE_CHECKING:
    from executions.models import ExecutionStep

logger = structlog.get_logger(__name__)


LEASE_DURATION_SECONDS = getattr(settings, 'RUNNABLE_STEP_LEASE_SECONDS', 300)


class RunnableStepService:
    """Enqueue, claim, and process runnable steps."""

    @staticmethod
    def enqueue(
        step: "ExecutionStep",
        priority: int = 0,
    ) -> RunnableStep | None:
        """Add a step to the runnable queue. Idempotent: ignores duplicates.

        Args:
            step: ExecutionStep that is ready to run.
            priority: Higher = higher priority. Default 0.

        Returns:
            RunnableStep instance, or None if already enqueued or on error.
        """
        try:
            runnable, created = RunnableStep.objects.get_or_create(
                execution_step=step,
                defaults={
                    "execution_id": step.execution_id,
                    "step_order": step.step_order,
                    "step_type": step.step_type if isinstance(step.step_type, str) else step.step_type.value,
                    "priority": priority,
                },
            )
            if created:
                logger.info(
                    "runnable_step_enqueued",
                    execution_step_id=step.id,
                    execution_id=step.execution_id,
                    priority=priority,
                )
            return runnable if created else None
        except IntegrityError:
            # Expected: race condition on get_or_create (duplicate execution_step_id)
            return None
        except Exception as e:
            logger.error(
                "runnable_step_enqueue_failed",
                execution_step_id=step.id,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def claim_batch(
        worker_id: str,
        limit: int = 10,
        step_types: list[str] | None = None,
    ) -> list[RunnableStep]:
        """Atomically claim a batch of unclaimed runnable steps.

        Uses SELECT FOR UPDATE SKIP LOCKED to allow concurrent workers
        to claim without contention.

        Args:
            worker_id: Identifier of the claiming worker.
            limit: Max steps to claim per batch.
            step_types: Optional filter on step types for type-based routing.

        Returns:
            List of claimed RunnableStep instances.
        """
        now = timezone.now()
        lease_until = now + timedelta(seconds=LEASE_DURATION_SECONDS)
        try:
            with transaction.atomic():
                qs = (
                    RunnableStep.objects
                    .filter(eligible_at__lte=now)
                    .filter(
                        Q(claimed_until__isnull=True) |
                        Q(claimed_until__lt=now)
                    )
                    .exclude(attempt_no__gte=F('max_attempts'))
                    .select_for_update(skip_locked=True)
                    .order_by('-priority', 'eligible_at')
                )
                if step_types:
                    qs = qs.filter(step_type__in=step_types)

                batch = list(qs[:limit])
                if batch:
                    ids = [r.id for r in batch]
                    RunnableStep.objects.filter(id__in=ids).update(
                        claimed_at=now,
                        claimed_by=worker_id,
                        claimed_until=lease_until,
                        attempt_no=F('attempt_no') + 1,
                    )
                    # Refresh instances to reflect the update
                    for r in batch:
                        r.claimed_at = now
                        r.claimed_by = worker_id
                        r.claimed_until = lease_until
                        r.attempt_no = (r.attempt_no or 0) + 1

                    logger.info(
                        "runnable_steps_claimed",
                        worker_id=worker_id,
                        count=len(batch),
                        step_ids=[r.execution_step_id for r in batch],
                    )
                return batch
        except IntegrityError:
            # Expected: rare constraint violation during update
            return []
        except Exception as e:
            logger.error(
                "runnable_steps_claim_failed",
                worker_id=worker_id,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def delete(execution_step_id: int) -> bool:
        """Remove a step from the runnable queue after dispatch.

        Args:
            execution_step_id: ID of the ExecutionStep to dequeue.

        Returns:
            True if deleted, False if not found or on error.
        """
        try:
            deleted, _ = RunnableStep.objects.filter(
                execution_step_id=execution_step_id
            ).delete()
            return deleted > 0
        except IntegrityError:
            # Expected: rare constraint violation during delete
            return False
        except Exception as e:
            logger.error(
                "runnable_step_delete_failed",
                execution_step_id=execution_step_id,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def delete_for_execution(execution_id: int) -> int:
        """Remove all runnable steps for an execution (e.g. on cancellation).

        Returns:
            Number of deleted rows.
        """
        try:
            deleted, _ = RunnableStep.objects.filter(
                execution_id=execution_id
            ).delete()
            return deleted
        except IntegrityError:
            # Expected: rare constraint violation during delete
            return 0
        except Exception as e:
            logger.error(
                "runnable_steps_delete_for_execution_failed",
                execution_id=execution_id,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def reclaim_expired_leases() -> int:
        """Reclaim steps whose lease has expired (worker crash recovery).

        Resets claimed_at, claimed_by, claimed_until but preserves attempt_no
        to track cumulative attempts across crashes.

        Returns:
            Number of rows reclaimed.
        """
        now = timezone.now()
        updated = RunnableStep.objects.filter(
            claimed_until__lt=now
        ).update(
            claimed_at=None,
            claimed_by=None,
            claimed_until=None,
        )
        if updated:
            logger.info("runnable_steps_leases_reclaimed", count=updated)
        return updated

    @staticmethod
    def pending_count(execution_id: int | None = None) -> int:
        """Count available runnable steps (unclaimed or lease expired)."""
        now = timezone.now()
        qs = RunnableStep.objects.filter(
            Q(claimed_until__isnull=True) | Q(claimed_until__lt=now)
        )
        if execution_id:
            qs = qs.filter(execution_id=execution_id)
        return qs.count()
