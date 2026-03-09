"""Utilitaires de broadcast WebSocket pour les exécutions — Story 58.3."""
from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from executions.models import ExecutionStep

logger = structlog.get_logger(__name__)


def broadcast_step_update(execution_id: int, step: "ExecutionStep") -> None:
    """Broadcast step_update à tous les clients WS connectés au groupe execution_{id}.

    Envoie un message de type ``step_update`` sur le groupe ``execution_{execution_id}``
    via Django Channels.  Protégé contre l'absence de channels (tests sans Redis) et
    contre toute exception de transport afin de ne jamais interrompre le flux métier.

    Story 58.3 — AC #2 : le frontend reçoit le step WAITING dès sa création.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        step_type = step.step_type
        # step_type peut être un enum ExecutionStepType ou une str selon le contexte
        if hasattr(step_type, "value"):
            step_type = step_type.value

        async_to_sync(channel_layer.group_send)(
            f"execution_{execution_id}",
            {
                "type": "step_update",
                "data": {
                    "id": step.id,
                    "execution_id": execution_id,
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "step_type": step_type,
                    "status": step.status,
                    "started_at": (
                        step.started_at.isoformat() if step.started_at else None
                    ),
                    "completed_at": (
                        step.completed_at.isoformat() if step.completed_at else None
                    ),
                    "output": step.get_output() if hasattr(step, "get_output") else None,
                    "platform_job_id": step.platform_job_id,
                    "error_message": step.error_message,
                },
            },
        )
    except ImportError:
        # channels non disponible (tests sans Redis, environnement sans channels)
        pass
    except Exception:  # noqa: BLE001
        logger.warning(
            "broadcast_step_update_error",
            execution_id=execution_id,
            step_id=step.id,
        )
