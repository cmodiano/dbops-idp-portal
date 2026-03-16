"""
Container workflow routing — next step resolution (Story 67.2, 67.3).

Extracted from container_workflow_runtime for reuse and testability.
"""
from __future__ import annotations

from executions.models import ExecutionStatus


def get_next_step_ids(
    step: dict,
    outcome: ExecutionStatus,
    workflow_steps: list[dict],
) -> list[str]:
    """
    Retourne les step_id cibles selon l'outcome, avec rétrocompat singulier.

    Si aucun champ de routing n'est présent (ancien mode linéaire), retourne
    le step suivant par ordre (rétrocompat workflows sans routing explicite).

    Story 67.2 — AC1, AC2, AC7.
    """
    if outcome == ExecutionStatus.COMPLETED:
        has_routing = 'on_success_step_ids' in step
        if not has_routing:
            return get_linear_next_step_ids(step, workflow_steps)
        ids = step.get('on_success_step_ids')
        return ids or []
    else:  # FAILED, CANCELLED, etc.
        ids = step.get('on_error_step_ids')
        return ids or []


def get_linear_next_step_ids(step: dict, workflow_steps: list[dict]) -> list[str]:
    """
    Retourne le step suivant par ordre (mode linéaire sans routing explicite).

    Rétrocompatibilité pour les workflows créés avant le support multi-cibles.
    """
    current_order = step.get('order', 0)
    next_steps = [
        s for s in workflow_steps
        if s.get('order', 0) > current_order and s.get('step_id')
    ]
    if next_steps:
        next_step = min(next_steps, key=lambda s: s.get('order', 0))
        return [next_step['step_id']]
    return []  # exit point
