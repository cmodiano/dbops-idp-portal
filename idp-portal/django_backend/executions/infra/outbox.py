"""Transactional outbox for reliable side-effects — infrastructure layer.

Story 78.7: Side-effects (notifications, websocket broadcast, event emission)
are written in the same DB transaction as the business mutation, then dispatched
asynchronously by a Celery Beat worker with retry and traceability.

Story 85.2: Relocalisation depuis executions.services.outbox vers executions.infra.outbox.
L'outbox est un pattern infrastructure (table DB, écriture transactionnelle).

Usage:
    from executions.infra.outbox import OutboxService
    OutboxService.write_entry(execution_id, event_type, payload, idempotency_key)
"""
from __future__ import annotations

import structlog

from executions.models import ExecutionOutbox

logger = structlog.get_logger(__name__)


# Event type constants
APPROVAL_GRANTED = "approval_granted"
APPROVAL_REJECTED = "approval_rejected"
STEP_BROADCAST = "step_broadcast"
EXECUTION_NOTIFICATION = "execution_notification"
APPROVAL_NOTIFICATION = "approval_notification"


class OutboxService:
    """Write and query outbox entries for reliable side-effect delivery."""

    @staticmethod
    def write_entry(
        execution_id: int,
        event_type: str,
        payload: dict,
        idempotency_key: str,
    ) -> tuple[ExecutionOutbox, bool]:
        """Write an outbox entry atomically (must be called inside transaction.atomic()).

        Uses get_or_create on idempotency_key for idempotence.

        Args:
            execution_id: FK to the execution.
            event_type: One of the event type constants.
            payload: JSON-serializable dict with event data.
            idempotency_key: Unique key to prevent duplicate entries.

        Returns:
            Tuple of (entry, created) — caller knows if it's a duplicate.
        """
        entry, created = ExecutionOutbox.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "execution_id": execution_id,
                "event_type": event_type,
                "payload": payload,
            },
        )
        if created:
            logger.info(
                "outbox_entry_written",
                execution_id=execution_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
            )
        else:
            logger.info(
                "outbox_entry_duplicate",
                idempotency_key=idempotency_key,
            )
        return entry, created

    @staticmethod
    def build_idempotency_key(
        execution_id: int,
        event_type: str,
        discriminator: str,
    ) -> str:
        """Build a deterministic idempotency key.

        Format: {execution_id}:{event_type}:{discriminator}
        Example: 42:approval_granted:step_15
        """
        return f"{execution_id}:{event_type}:{discriminator}"
