"""
Gate context builder for ExecutionStep WAITING status.
Story 25.2: Build initial waiting context when an ExecutionStep has gate_conditions.
"""
from typing import Any

import structlog
from django.utils import timezone
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


def build_waiting_context(exec_step: Any, gate_conditions: list) -> dict:
    """
    Build the initial waiting context for an ExecutionStep in WAITING status.

    Args:
        exec_step: ExecutionStep instance
        gate_conditions: List of gate conditions from step definition

    Returns:
        dict: Waiting context to be stored in ExecutionStep.output

    Raises:
        ValueError: If gate_conditions is not a list
    """
    if not isinstance(gate_conditions, list):
        logger.error(  # type: ignore[unreachable]
            "build_waiting_context_invalid_type",
            gate_conditions_type=type(gate_conditions).__name__,
            correlation_id=get_correlation_id(),
        )
        raise ValueError("gate_conditions must be a list")

    gate_status = []
    for condition in gate_conditions:
        gate_status.append({
            'type': condition['type'],
            'satisfied': False,
            'reason': "En attente d'évaluation",
            'next_evaluation_at': None,
        })

    context = {
        'waiting_since': (
            exec_step.created_at.isoformat()
            if exec_step.created_at
            else timezone.now().isoformat()
        ),
        'gate_conditions': gate_conditions,
        'gate_status': gate_status,
    }

    logger.info(
        "waiting_context_built",
        execution_step_id=getattr(exec_step, 'id', None),
        gate_conditions_count=len(gate_conditions),
        correlation_id=get_correlation_id(),
    )

    return context
