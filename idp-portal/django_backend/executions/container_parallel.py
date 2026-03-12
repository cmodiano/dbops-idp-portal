"""
Container workflow parallel execution — join policy (Story 67.3, 67.8).

Extracted from container_workflow_runtime for reuse and testability.
"""
from __future__ import annotations

from executions.models import ExecutionStatus


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
