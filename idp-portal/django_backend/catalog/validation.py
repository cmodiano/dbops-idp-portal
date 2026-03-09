"""
Validation utilities for catalog models.
Story 16.2: Workflow steps validation (branches, retry, cycles).
"""

from typing import Any
from rest_framework import serializers


def validate_workflow_steps(steps: list[dict[str, Any]], action_id: int | None = None) -> list[dict[str, Any]]:
    """
    Validate workflow steps with branch conditional and retry configuration.

    Story 16.2 AC8: Validates:
    - All on_success_step_id and on_error_step_id references point to valid step_id
    - No infinite loops in branch paths (cycle detection)
    - At least one step has an exit point (on_success_step_id=null OR on_error_step_id=null)
    - Retry constraints: max_attempts >= 1, interval_seconds >= 1 when retry_enabled=true

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

    # Detect whether this payload uses branching/retry features (Story 16.2).
    # Backward compatibility: older workflows may only have order/name/referenced_action_id.
    # Story 65.1: parallel_group steps also require step_id and cycle detection.
    uses_branches_or_retry = any(
        (
            'on_success_step_id' in (step or {})
            or 'on_error_step_id' in (step or {})
            or (step or {}).get('retry_enabled') is True
            or 'retry_max_attempts' in (step or {})
            or 'retry_interval_seconds' in (step or {})
            or 'retry_backoff_multiplier' in (step or {})
            or (step or {}).get('step_type') == 'parallel_group'
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

    # Build step_id -> step lookup and collect parallel_group member step_ids for routing validation.
    step_id_to_step: dict[str, dict] = {}
    for s in steps:
        sid = s.get('step_id')
        if isinstance(sid, str) and sid:
            step_id_to_step[sid] = s
    member_step_ids: set[str] = set()
    for s in steps:
        if s.get('step_type') == 'parallel_group':
            for ps_id in s.get('parallel_steps') or []:
                if isinstance(ps_id, str) and ps_id.strip():
                    member_step_ids.add(ps_id)

    # Track if at least one exit point exists (for branching workflows only).
    has_exit_point = False

    # Validate each step
    for i, step in enumerate(steps):
        step_id = step.get('step_id')
        on_success = step.get('on_success_step_id')
        on_error = step.get('on_error_step_id')
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

        # AC8: Validate on_success_step_id reference (only when using branching features)
        if uses_branches_or_retry and 'on_success_step_id' in step:
            if on_success is not None and on_success not in step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_success_step_id '{on_success}' "
                    f"does not reference a valid step_id in this workflow"
                )
            if on_success is not None and on_success in member_step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_success_step_id cannot target "
                    f"parallel_group member '{on_success}' (members are not directly routable)"
                )

        # AC8: Validate on_error_step_id reference (only when using branching features)
        if uses_branches_or_retry and 'on_error_step_id' in step:
            if on_error is not None and on_error not in step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_error_step_id '{on_error}' "
                    f"does not reference a valid step_id in this workflow"
                )
            if on_error is not None and on_error in member_step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_error_step_id cannot target "
                    f"parallel_group member '{on_error}' (members are not directly routable)"
                )

        # AC8: Check for exit points (only meaningful when branching is configured).
        # We consider an "exit point" only if a branch field is explicitly present and set to null.
        if uses_branches_or_retry:
            if ('on_success_step_id' in step and on_success is None) or ('on_error_step_id' in step and on_error is None):
                has_exit_point = True

        # Story 65.1: Validate parallel_group step-specific fields (AC #2, #3, #4, #6, #7)
        if step.get('step_type') == 'parallel_group':
            parallel_steps = step.get('parallel_steps')

            # Task 1.2: parallel_steps must be present and a non-empty list
            if parallel_steps is None or not isinstance(parallel_steps, list):
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): parallel_steps is required for parallel_group steps"
                )

            # Element types: every element must be a non-empty string before set()/distinct checks
            if not all(isinstance(x, str) and x for x in parallel_steps):
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): parallel_steps must be a list of non-empty string step_ids"
                )

            # Task 1.2: parallel_steps must contain at least 2 distinct step_ids (AC #3)
            if len(set(parallel_steps)) < 2:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): parallel_steps must contain at least 2 distinct step_ids"
                )

            # Task 1.5: parallel_steps cannot reference the group's own step_id (AC #7)
            if step_id and step_id in parallel_steps:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): parallel_steps cannot contain the step's own step_id"
                )

            # Task 1.3: each step_id in parallel_steps must reference an existing step (AC #4)
            for ps_id in parallel_steps:
                if ps_id not in step_ids:
                    raise serializers.ValidationError(
                        f"Step {i} (step_id={step_id}): parallel_steps contains '{ps_id}' "
                        f"which is not a valid step_id in this workflow"
                    )
                # Reject member step types the runtime cannot handle in _execute_step_for_parallel
                ref_step = step_id_to_step.get(ps_id)
                if ref_step:
                    ref_type = ref_step.get('step_type') or 'platform'
                    if ref_type == 'parallel_group':
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): parallel_steps cannot contain "
                            f"nested parallel_group step '{ps_id}'"
                        )
                    if ref_type == 'gate':
                        raise serializers.ValidationError(
                            f"Step {i} (step_id={step_id}): parallel_steps cannot contain "
                            f"gate step '{ps_id}' (gate steps may wait and are not supported as members)"
                        )

            # Task 1.4: on_all_success_step_id / on_any_error_step_id must reference existing steps (AC #6)
            on_all_success = step.get('on_all_success_step_id')
            on_any_error = step.get('on_any_error_step_id')
            if on_all_success is not None and on_all_success not in step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_all_success_step_id '{on_all_success}' "
                    f"does not reference a valid step_id in this workflow"
                )
            if on_all_success is not None and on_all_success in member_step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_all_success_step_id cannot target "
                    f"parallel_group member '{on_all_success}' (members are not directly routable)"
                )
            if on_any_error is not None and on_any_error not in step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_any_error_step_id '{on_any_error}' "
                    f"does not reference a valid step_id in this workflow"
                )
            if on_any_error is not None and on_any_error in member_step_ids:
                raise serializers.ValidationError(
                    f"Step {i} (step_id={step_id}): on_any_error_step_id cannot target "
                    f"parallel_group member '{on_any_error}' (members are not directly routable)"
                )

            # A parallel_group acts as an exit point when on_all_success or on_any_error is null
            if on_all_success is None or on_any_error is None:
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

    # AC8: Ensure at least one exit point exists when branches/retry is used.
    if uses_branches_or_retry and not has_exit_point:
        raise serializers.ValidationError(
            "Workflow must have at least one exit point "
            "(step with on_success_step_id=null, on_error_step_id=null, "
            "on_all_success_step_id=null, or on_any_error_step_id=null)"
        )

    # AC8: Detect cycles in branch paths using DFS
    if uses_branches_or_retry:
        _detect_workflow_cycles(steps)

    return steps


def _detect_workflow_cycles(steps: list[dict[str, Any]]) -> None:
    """
    Detect infinite loops in workflow branch paths using DFS.

    Story 16.2 AC8: Ensures no infinite loops exist.

    Args:
        steps: List of workflow step dicts

    Raises:
        serializers.ValidationError: If a cycle is detected
    """
    if not steps:
        return

    # Collect all parallel_group member step_ids (excluded from sequential execution)
    member_step_ids: set[str] = set()
    for s in steps:
        if s.get('step_type') == 'parallel_group':
            member_step_ids.update(s.get('parallel_steps') or [])

    # Non-member steps sorted by order (mirrors ContainerWorkflowRuntime._execute_workflow_steps)
    sorted_non_member = sorted(
        [s for s in steps if s.get('step_id') and s.get('step_id') not in member_step_ids],
        key=lambda s: s.get('order', 0),
    )

    # Build adjacency graph: step_id -> [next_step_ids]
    graph: dict[str, list[str]] = {}
    for step in steps:
        step_id = step.get('step_id')
        if not step_id:
            continue

        neighbors: list[str] = []
        step_type = step.get('step_type') or 'platform'

        if step_type == 'parallel_group':
            # Task 2.1: Fan-out edges parallel_group → each parallel_step_id (Story 65.1)
            parallel_steps = step.get('parallel_steps') or []
            neighbors.extend(parallel_steps)
            # Task 2.2: Add edges for on_all_success_step_id and on_any_error_step_id
            on_all_success = step.get('on_all_success_step_id')
            on_any_error = step.get('on_any_error_step_id')
            if on_all_success is not None:
                neighbors.append(on_all_success)
            if on_any_error is not None:
                neighbors.append(on_any_error)
            # Implicit fall-through: when on_all_success absent, runtime continues to next sequential non-member
            if on_all_success is None:
                try:
                    idx = next(i for i, s in enumerate(sorted_non_member) if s.get('step_id') == step_id)
                    if idx + 1 < len(sorted_non_member):
                        next_step_id = sorted_non_member[idx + 1].get('step_id')
                        if next_step_id:
                            neighbors.append(next_step_id)
                except StopIteration:
                    pass
        else:
            on_success = step.get('on_success_step_id') if 'on_success_step_id' in step else None
            on_error = step.get('on_error_step_id') if 'on_error_step_id' in step else None
            if on_success is not None:
                neighbors.append(on_success)
            if on_error is not None:
                neighbors.append(on_error)

        graph[step_id] = neighbors

    # DFS cycle detection with recursion stack
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: list[str]) -> bool:
        """
        DFS traversal with cycle detection.

        Returns:
            True if cycle detected, False otherwise
        """
        if node in rec_stack:
            # Cycle detected - build path for error message
            cycle_start = path.index(node)
            cycle_path = ' -> '.join(path[cycle_start:] + [node])
            raise serializers.ValidationError(
                f"Infinite loop detected in workflow branches: {cycle_path}"
            )

        if node in visited:
            return False

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        # Visit all neighbors
        for neighbor in graph.get(node, []):
            dfs(neighbor, path.copy())

        rec_stack.remove(node)
        return False

    # Run DFS from each unvisited node
    for step_id in graph:
        if step_id not in visited:
            dfs(step_id, [])


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
