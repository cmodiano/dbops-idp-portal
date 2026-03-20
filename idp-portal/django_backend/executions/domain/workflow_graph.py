"""
Domain workflow graph — logique pure de traversal du graphe workflow.

Aucune dépendance ORM. Seule dépendance externe autorisée :
- executions.models.ExecutionStatus (enum TextChoices — pas de requête ORM)

Story 85.1 — extrait de container_routing.py, container_parallel.py,
et services/workflow_commands.py.
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


def apply_join_policy(
    wave_steps: list[dict],
    results: dict[str, tuple[ExecutionStatus, list[str]]],
    step_lookup_by_id: dict[str, dict],
) -> list[str]:
    """
    Construit la prochaine vague en appliquant join_policy pour les steps convergents.

    Pour chaque step cible candidat :
    - Si 1 seul prédécesseur dans la vague → inclus inconditionnellement
    - Si 2+ prédécesseurs dans la vague → apply join_policy du step cible (défaut all_success)

    Story 67.3 — AC: #1, #5, #6, #7, #8.
    Story 67.8 — all_failed | one_failed.
    """
    target_preds: dict[str, list[tuple[str, ExecutionStatus]]] = {}
    for step in wave_steps:
        sid = step.get('step_id', '')
        if not sid:
            continue
        status, _ = results.get(sid, (ExecutionStatus.FAILED, []))
        all_targets: set[str] = set()
        for t in (step.get('on_success_step_ids') or []):
            if t:
                all_targets.add(t)
        for t in (step.get('on_error_step_ids') or []):
            if t:
                all_targets.add(t)
        for target_id in all_targets:
            target_preds.setdefault(target_id, []).append((sid, status))

    all_next_ids: list[str] = []
    for _, (_, next_ids) in results.items():
        all_next_ids.extend(next_ids)
    candidate_ids = list(dict.fromkeys(all_next_ids))

    result: list[str] = []
    for target_id in candidate_ids:
        preds = target_preds.get(target_id, [])
        if len(preds) <= 1:
            result.append(target_id)
            continue

        target_step = step_lookup_by_id.get(target_id)
        join_policy = (target_step or {}).get('join_policy', 'all_success')
        pred_statuses = [s for _, s in preds]

        if join_policy == 'all_success':
            if all(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                result.append(target_id)
        elif join_policy == 'one_success':
            if any(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                result.append(target_id)
        elif join_policy == 'all_done':
            result.append(target_id)
        elif join_policy == 'all_failed':
            if all(s == ExecutionStatus.FAILED for s in pred_statuses):
                result.append(target_id)
        elif join_policy == 'one_failed':
            if any(s == ExecutionStatus.FAILED for s in pred_statuses):
                result.append(target_id)
        else:
            if all(s == ExecutionStatus.COMPLETED for s in pred_statuses):
                result.append(target_id)

    return result


def find_step_config(all_steps: list, config_step_id: str | None) -> dict | None:
    """Find step config dict by step_id in workflow definition."""
    if not config_step_id:
        return None
    for s in all_steps:
        if isinstance(s, dict) and s.get('step_id') == config_step_id:
            return s
    return None
