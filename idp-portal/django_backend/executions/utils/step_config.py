"""Utility to match an ExecutionStep to its workflow step definition."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from executions.models import ExecutionStep


def find_step_config(execution_steps: list, step: ExecutionStep) -> dict | None:
    """Match an ExecutionStep to its config definition from action.execution_steps.

    Uses config_step_id (robust UUID-based matching) with fallback to step_name
    for backward compatibility with older ExecutionStep records.

    Args:
        execution_steps: list of step dicts from action.execution_steps
        step: the ExecutionStep to match

    Returns:
        The matching step config dict, or None if not found
    """
    for s in execution_steps:
        if isinstance(s, dict):
            if step.config_step_id and s.get('step_id') == step.config_step_id:
                return s
            if not step.config_step_id and (
                s.get('name') == step.step_name or s.get('step_id') == step.step_name
            ):
                return s
    return None
