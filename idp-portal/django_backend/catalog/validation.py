"""
Validation utilities for catalog models.
Story 16.2: Workflow steps validation (branches, retry, cycles).
Story 67.1: Multi-target support — on_success_step_ids / on_error_step_ids (arrays).
            Removes parallel_group validation.
Story 67.3: join_policy validation — all_success | one_success | all_done.
Story 67.8: all_failed | one_failed.
Story 77.7: Reject gate steps inside parallel branches (fan-out) at validation time.
Story 86.5: Validate gate_type against gate_registry at workflow definition time.
"""

from collections import deque
from typing import Any
from rest_framework import serializers

VALID_JOIN_POLICIES = frozenset({'all_success', 'one_success', 'all_done', 'all_failed', 'one_failed'})


def validate_workflow_steps(steps: list[dict[str, Any]], action_id: int | None = None) -> list[dict[str, Any]]:
    """
    Validate workflow steps with branch conditional and retry configuration.

    Story 16.2 AC8: Validates:
    - All on_success_step_ids and on_error_step_ids references point to valid step_id
    - No infinite loops in branch paths (cycle detection)
    - At least one step has an exit point (on_success_step_ids=[] or null)
    - Retry constraints: max_attempts >= 1, interval_seconds >= 1 when retry_enabled=true

    Story 67.1: Uses on_success_step_ids/on_error_step_ids (arrays) for branching.

    Story 86.5: For steps with step_type='gate', validates that gate_type is present
    and is a registered type in gate_registry. Raises ValidationError with the list of
    valid types if the gate_type is missing or unknown.

    Args:
        steps: List of workflow step dicts
        action_id: Optional action ID for error messages

    Returns:
        Validated steps (same list, for chaining)

    Raises:
        serializers.ValidationError: If validation fails
    """
    if not steps:
        return steps

    # Story 86.5: Lazy import at function scope to avoid Django init issues (no top-level import)
    from executions.gates.registry import gate_registry  # noqa: PLC0415

    # Basic shape validation: platform steps must reference an action (Story 57.13)
    # gate, service_call, evaluation, http_request have their own required fields
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise serializers.ValidationError(f"Step {i}: must be an object")
        step_type = step.get('step_type') or 'platform'
        if step_type == 'platform' and step.get('referenced_action_id') is None:
            raise serializers.ValidationError(f"Step {i}: referenced_action_id is required for platform steps")
        if step_type == 'platform' and action_id is not None:
            if step.get('referenced_action_id') == action_id:
                raise serializers.ValidationError(
                    f"Step {i}: referenced_action_id cannot reference the workflow's own action (self-reference → infinite loop)"
                )

    # Detect whether this payload uses branching/retry features (Story 16.2).
    # Story 67.1: only on_success_step_ids / on_error_step_ids (plural) are supported.
    uses_branches_or_retry = any(
        (
            'on_success_step_ids' in (step or {})
            or 'on_error_step_ids' in (step or {})
            or (step or {}).get('retry_enabled') is True
            or 'retry_max_attempts' in (step or {})
            or 'retry_interval_seconds' in (step or {})
            or 'retry_backoff_multiplier' in (step or {})
            # NB: plus de 'parallel_group' ici (Story 67.1)
        )
        for step in steps
    )

    # Extract all step_ids for reference validation and ensure uniqueness when used.
    step_ids: set[str] = set()
    step_id_counts: dict[str, int] = {}
    for i, step in enumerate(steps):
        step_id = step.get('step_id')
        if uses_branches_or_retry and not step_id:
            raise serializers.ValidationError(
                f"Step {i}: step_id is required when using branches/retry fields"
            )
        if step_id:
            if not isinstance(step_id, str) or not step_id.strip():
                raise serializers.ValidationError(f"Step {i}: step_id must be a non-empty string")
            step_id_counts[step_id] = step_id_counts.get(step_id, 0) + 1
            step_ids.add(step_id)

    duplicates = [sid for sid, count in step_id_counts.items() if count > 1]
    if duplicates:
        raise serializers.ValidationError(
            f"Duplicate step_id values are not allowed: {', '.join(sorted(duplicates))}"
        )

    # Track if at least one exit point exists (for branching workflows only).
    has_exit_point = False

    # Validate each step
    for i, step in enumerate(steps):
        step_id = step.get('step_id')
        step_type = step.get('step_type') or 'platform'
        retry_enabled = step.get('retry_enabled', False)
        retry_max_attempts = step.get('retry_max_attempts')
        retry_interval_seconds = step.get('retry_interval_seconds')
        retry_backoff_multiplier = step.get('retry_backoff_multiplier')

        # Apply defaults when retry is enabled (AC1 defaults).
        if retry_enabled:
            if retry_max_attempts is None:
                retry_max_attempts = 3
                step['retry_max_attempts'] = retry_max_attempts
            if retry_interval_seconds is None:
                retry_interval_seconds = 60
                step['retry_interval_seconds'] = retry_interval_seconds
            if retry_backoff_multiplier is None:
                retry_backoff_multiplier = 2.0
                step['retry_backoff_multiplier'] = retry_backoff_multiplier

        # Story 67.1 AC #3: Validate on_success_step_ids references
        if uses_branches_or_retry and 'on_success_step_ids' in step:
            success_ids = step['on_success_step_ids']
            if success_ids is not None:
                if not isinstance(success_ids, list):
                    raise serializers.ValidationError(
                        f"Step {i} (step_id={step_id}): on_success_step_ids must be a list of strings"
                    )
                for sid in success_ids:
                    if not isinstance(sid, str) or not sid.strip():
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): on_success_step_ids must contain non-empty strings"
                        )
                    if sid not in step_ids:
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): on_success_step_ids contains '{sid}' "
                            f"which does not reference a valid step_id in this workflow"
                        )

        # Story 67.1 AC #3: Validate on_error_step_ids references
        if uses_branches_or_retry and 'on_error_step_ids' in step:
            error_ids = step['on_error_step_ids']
            if error_ids is not None:
                if not isinstance(error_ids, list):
                    raise serializers.ValidationError(
                        f"Step {i} (step_id={step_id}): on_error_step_ids must be a list of strings"
                    )
                for sid in error_ids:
                    if not isinstance(sid, str) or not sid.strip():
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): on_error_step_ids must contain non-empty strings"
                        )
                    if sid not in step_ids:
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): on_error_step_ids contains '{sid}' "
                            f"which does not reference a valid step_id in this workflow"
                        )

        # Story 67.1 AC #6: Check for exit points (only meaningful when branching is configured).
        # A step is an exit point if on_success_step_ids is empty/null OR on_error_step_ids is empty/null.
        if uses_branches_or_retry:
            success_ids = step.get('on_success_step_ids')
            error_ids = step.get('on_error_step_ids')
            success_is_exit = 'on_success_step_ids' in step and (success_ids is None or success_ids == [])
            error_is_exit = 'on_error_step_ids' in step and (error_ids is None or error_ids == [])
            if success_is_exit or error_is_exit:
                has_exit_point = True

        # Story 67.3 AC #4: Validate join_policy if present
        join_policy = step.get('join_policy')
        if join_policy is not None and join_policy not in VALID_JOIN_POLICIES:
            raise serializers.ValidationError(
                f"Step '{step_id}': join_policy must be one of "
                f"{sorted(VALID_JOIN_POLICIES)}, got '{join_policy}'"
            )

        # Story 86.5: Validate gate_type for gate steps
        if step_type == 'gate':
            gate_type_val = step.get('gate_type')
            if not gate_type_val or not gate_type_val.strip():
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): gate_type est requis pour les steps de type 'gate'"
                )
            gate_type_val = gate_type_val.strip()
            if not gate_registry.is_registered(gate_type_val):
                valid_types = gate_registry.list_types()
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): gate_type '{gate_type_val}' invalide. "
                    f"Types valides : {', '.join(sorted(valid_types))}"
                )

        # AC4: Validate retry_max_attempts >= 1 if retry_enabled
        if retry_enabled:
            if retry_max_attempts is None or retry_max_attempts < 1:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): retry_max_attempts must be >= 1 when retry_enabled=true"
                )

            # AC5: Validate retry_interval_seconds >= 1 if retry_enabled
            if retry_interval_seconds is None or retry_interval_seconds < 1:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): retry_interval_seconds must be >= 1 when retry_enabled=true"
                )

    # Story 67.1 AC #6: Ensure at least one exit point exists when branches/retry is used.
    if uses_branches_or_retry and not has_exit_point:
        raise serializers.ValidationError(
            "Workflow must have at least one exit point "
            "(step with on_success_step_ids=[] or null, or on_error_step_ids=[] or null)"
        )

    # AC8: Detect cycles in branch paths using DFS
    if uses_branches_or_retry:
        _detect_workflow_cycles(steps)

    # Story 77.7 AC#1-2: Detect gate steps inside parallel branches (fan-out)
    if uses_branches_or_retry:
        _detect_gates_in_parallel_branches(steps, step_ids)

    return steps


def _detect_workflow_cycles(steps: list[dict[str, Any]]) -> None:
    """
    Detect infinite loops in workflow branch paths using DFS.

    Story 16.2 AC8: Ensures no infinite loops exist.
    Story 67.1: Uses on_success_step_ids / on_error_step_ids for edges.

    Args:
        steps: List of workflow step dicts

    Raises:
        serializers.ValidationError: If a cycle is detected
    """
    if not steps:
        return

    # Build adjacency graph: step_id -> set of next_step_ids
    # Story 67.1: use on_success_step_ids / on_error_step_ids for edges
    graph: dict[str, set[str]] = {}
    for step in steps:
        step_id = step.get('step_id')
        if not step_id:
            continue

        neighbors: set[str] = set()
        for target in (step.get('on_success_step_ids') or []):
            if isinstance(target, str) and target:
                neighbors.add(target)
        for target in (step.get('on_error_step_ids') or []):
            if isinstance(target, str) and target:
                neighbors.add(target)

        graph[step_id] = neighbors

    # Iterative DFS cycle detection using an explicit stack (avoids Python recursion limit).
    # Each stack entry: (node, iterator_over_neighbors, current_path_list)
    # rec_stack tracks nodes on the current DFS path for cycle detection.
    visited: set[str] = set()

    for start in graph:
        if start in visited:
            continue

        # Stack entries: (node, neighbors_iter, path_so_far)
        rec_stack: set[str] = set()
        path: list[str] = []
        stack: list[tuple[str, Any]] = [(start, iter(graph.get(start, set())))]
        rec_stack.add(start)
        path.append(start)
        visited.add(start)

        while stack:
            node, neighbors_iter = stack[-1]
            try:
                neighbor = next(neighbors_iter)
                if neighbor in rec_stack:
                    # Cycle detected — build readable path
                    cycle_start = path.index(neighbor)
                    cycle_path = ' -> '.join(path[cycle_start:] + [neighbor])
                    raise serializers.ValidationError(
                        f"Infinite loop detected in workflow branches: {cycle_path}"
                    )
                if neighbor not in visited:
                    visited.add(neighbor)
                    rec_stack.add(neighbor)
                    path.append(neighbor)
                    stack.append((neighbor, iter(graph.get(neighbor, set()))))
            except StopIteration:
                stack.pop()
                rec_stack.discard(node)
                if path and path[-1] == node:
                    path.pop()


def _detect_gates_in_parallel_branches(steps: list[dict], step_ids: set[str]) -> None:
    """
    Story 77.7 AC1-2: Détecte les gate steps dans des branches parallèles (fan-out).

    Algorithme :
    1. Construire le graphe des prédécesseurs (in_degree) pour identifier les join points.
    2. Pour chaque step avec 2+ on_success_step_ids ou 2+ on_error_step_ids (fan-out origin),
       faire un BFS depuis les cibles parallèles (s'arrêter aux join points).
    3. Si un step gate est trouvé dans la traversée → ValidationError.

    Les join points (in_degree >= 2) marquent la convergence des branches et
    sont exclus de la traversée (pas une erreur d'avoir un gate APRÈS le join).
    """
    if not steps:
        return

    # Construire step_map et in_degree
    step_map: dict[str, dict] = {}
    in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
    for step in steps:
        sid = step.get('step_id')
        if sid:
            step_map[sid] = step
        for target in (step.get('on_success_step_ids') or []):
            if target in in_degree:
                in_degree[target] += 1
        for target in (step.get('on_error_step_ids') or []):
            if target in in_degree:
                in_degree[target] += 1

    # Join points = steps avec 2+ prédécesseurs (convergence de branches)
    join_points: set[str] = {sid for sid, deg in in_degree.items() if deg >= 2}

    # Pour chaque fan-out origin : BFS sur les branches parallèles
    for step in steps:
        origin_id = step.get('step_id', '')

        success_ids = step.get('on_success_step_ids') or []
        error_ids = step.get('on_error_step_ids') or []

        for ids_list in (success_ids, error_ids):
            if len(ids_list) < 2:
                continue  # Pas un fan-out (séquentiel ou vide)

            # BFS depuis toutes les cibles simultanées du fan-out
            visited: set[str] = set()
            queue: deque[str] = deque(ids_list)

            while queue:
                current = queue.popleft()
                if current in visited or current in join_points:
                    continue
                visited.add(current)

                current_step = step_map.get(current)
                if not current_step:
                    continue

                if current_step.get('step_type') == 'gate':
                    raise serializers.ValidationError(
                        f"Step '{current}': les gate steps ne sont pas supportés à l'intérieur "
                        f"d'une branche parallèle (fan-out). Déplacez le gate en dehors de la "
                        f"branche parallèle. (Fan-out originant du step '{origin_id}')"
                    )

                # Continuer BFS dans la sous-branche (exclure join_points et déjà visités)
                for next_id in (
                    (current_step.get('on_success_step_ids') or [])
                    + (current_step.get('on_error_step_ids') or [])
                ):
                    if next_id not in visited and next_id not in join_points:
                        queue.append(next_id)


def validate_retry_constraints(step: dict[str, Any]) -> None:
    """
    Validate retry configuration constraints for a single step.

    Story 16.2 AC4, AC5: Validates retry_max_attempts and retry_interval_seconds.

    Args:
        step: Workflow step dict

    Raises:
        serializers.ValidationError: If retry constraints are violated
    """
    retry_enabled = step.get('retry_enabled', False)
    if not retry_enabled:
        return

    retry_max_attempts = step.get('retry_max_attempts')
    retry_interval_seconds = step.get('retry_interval_seconds')

    # AC4: retry_max_attempts >= 1
    if retry_max_attempts is None or retry_max_attempts < 1:
        raise serializers.ValidationError(
            "retry_max_attempts must be >= 1 when retry_enabled=true"
        )

    # AC5: retry_interval_seconds >= 1
    if retry_interval_seconds is None or retry_interval_seconds < 1:
        raise serializers.ValidationError(
            "retry_interval_seconds must be >= 1 when retry_enabled=true"
        )
