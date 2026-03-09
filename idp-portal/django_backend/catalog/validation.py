"""
Validation utilities for catalog models.
Story 16.2: Workflow steps validation (branches, retry, cycles).
Story 67.1: Multi-target support — on_success_step_ids / on_error_step_ids (arrays).
            Removes parallel_group validation.
"""

from typing import Any
from rest_framework import serializers


def validate_workflow_steps(steps: list[dict[str, Any]], action_id: int | None = None) -> list[dict[str, Any]]:
    """
    Validate workflow steps with branch conditional and retry configuration.

    Story 16.2 AC8: Validates:
    - All on_success_step_ids and on_error_step_ids references point to valid step_id
    - No infinite loops in branch paths (cycle detection)
    - At least one step has an exit point (on_success_step_ids=[] or null)
    - Retry constraints: max_attempts >= 1, interval_seconds >= 1 when retry_enabled=true

    Story 67.1: Replaces singular on_success_step_id/on_error_step_id with arrays.
                Removes parallel_group validation. Adds retrocompat normalization.

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

    # Basic shape validation: platform steps must reference an action (Story 57.13)
    # gate, service_call, evaluation, http_request have their own required fields
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise serializers.ValidationError(f"Step {i}: must be an object")
        step_type = step.get('step_type') or 'platform'
        if step_type == 'platform' and step.get('referenced_action_id') is None:
            raise serializers.ValidationError(f"Step {i}: referenced_action_id is required for platform steps")

    # Story 67.1 AC #2: Retrocompat normalization — convert singular to plural for each step.
    # This must happen before uses_branches_or_retry detection so that plural fields are present.
    for step in steps:
        if isinstance(step, dict):
            if 'on_success_step_id' in step and 'on_success_step_ids' not in step:
                val = step['on_success_step_id']
                step['on_success_step_ids'] = [val] if val is not None else []
            if 'on_error_step_id' in step and 'on_error_step_ids' not in step:
                val = step['on_error_step_id']
                step['on_error_step_ids'] = [val] if val is not None else []

    # Detect whether this payload uses branching/retry features (Story 16.2).
    # Backward compatibility: older workflows may only have order/name/referenced_action_id.
    # Story 67.1: detect on_success_step_ids / on_error_step_ids (plural); singular kept for retrocompat detection.
    uses_branches_or_retry = any(
        (
            'on_success_step_ids' in (step or {})
            or 'on_error_step_ids' in (step or {})
            or 'on_success_step_id' in (step or {})   # rétrocompat
            or 'on_error_step_id' in (step or {})      # rétrocompat
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
