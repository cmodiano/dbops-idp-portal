"""Validation des contraintes de mutex inter-actions."""
from __future__ import annotations

from executions.utils import validate_action_mutex


class MutexValidator:
    """Point d'entrée uniforme pour la validation mutex."""

    @staticmethod
    def validate(action, target_ids: list, correlation_id: str, user_id: str) -> None:
        """
        Validate action mutex rules before creating execution.

        Raises:
            BadRequestError: If mutex constraint is violated.
        """
        validate_action_mutex(
            action=action,
            target_ids=target_ids,
            correlation_id=correlation_id,
            user_id=user_id,
        )
