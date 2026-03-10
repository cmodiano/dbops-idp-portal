"""
Module executions.utils.mutex_validation — Validation des règles mutex inter-actions.

Responsabilité unique : vérifier qu'aucune règle ACTION_MUTEX ne bloque la soumission
d'une nouvelle exécution (conflits globaux ou par cible).

Note : les imports de catalog.models et executions.models sont intentionnellement
lazy (à l'intérieur de la fonction) pour éviter les imports circulaires.
"""
from __future__ import annotations

from typing import Any

import structlog

from django.db.models import Q

from core.exceptions import ConflictError

exec_logger = structlog.get_logger(__name__)


def validate_action_mutex(
    action: Any,
    target_ids: list[str],
    correlation_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """
    Story 25.5: Validate action mutex rules before execution creation.
    Checks for conflicting executions based on ACTION_MUTEX rules.

    Args:
        action: Action being submitted for execution
        target_ids: List of target_id strings (from validated_targets)
        correlation_id: Request correlation ID for logging
        user_id: User ID for audit trail

    Raises:
        ConflictError: If a mutex violation is detected (code="MUTEX_VIOLATION", HTTP 409)

    Implementation notes:
    - Checks BOTH directions (A→B and B→A) for symmetric enforcement
    - Active statuses: RUNNING, SUBMITTED (ADR-007: PENDING_APPROVAL removed)
    - same_target=True: blocks only if targets intersect
    - same_target=False: blocks globally regardless of targets
    """
    from catalog.models import ActionMutex  # noqa: PLC0415
    from executions.models import Execution, ExecutionStatus  # noqa: PLC0415

    # Define active statuses that block new executions
    # ADR-007: PENDING_APPROVAL removed — approval is now step-based (SUBMITTED status)
    ACTIVE_STATUSES = [
        ExecutionStatus.RUNNING,
        ExecutionStatus.SUBMITTED,
    ]

    # Fetch mutex rules where current action is involved (either side)
    # Option B from Dev Notes: check both directions (action=current OR incompatible_with=current)
    mutex_rules = ActionMutex.objects.filter(
        Q(action=action) | Q(incompatible_with=action)
    ).select_related('action', 'incompatible_with')

    if not mutex_rules.exists():
        # No mutex rules defined for this action
        return

    for rule in mutex_rules:
        # Determine which action is the incompatible one
        if rule.action.id == action.id:
            incompatible_action = rule.incompatible_with
        else:
            incompatible_action = rule.action

        # Check for active executions of the incompatible action
        conflicting_executions = Execution.objects.filter(
            action=incompatible_action,
            status__in=ACTIVE_STATUSES,
        )

        if rule.same_target and target_ids:
            # Mode: same_target=True
            # Only block if there's target intersection
            # Join ExecutionTarget to check for overlapping target_ids
            conflicting_executions = conflicting_executions.filter(
                targets__target_id__in=target_ids
            ).distinct()

        # Performance: use exists() instead of count() or fetching all
        if conflicting_executions.exists():
            # Mutex violation detected
            # Fetch one example for detailed error message
            first_conflict = conflicting_executions.select_related('action', 'user').first()

            exec_logger.warning(
                "mutex_violation_detected",
                action_id=action.id,
                action_name=action.name,
                incompatible_action_id=incompatible_action.id,
                incompatible_action_name=incompatible_action.name,
                same_target=rule.same_target,
                target_ids=target_ids,
                conflicting_execution_id=first_conflict.id if first_conflict else None,
                conflicting_status=first_conflict.status if first_conflict else None,
                correlation_id=correlation_id,
                user_id=user_id,
                message="Mutex rule blocks execution - incompatible action is currently running",
            )

            # Raise 409 CONFLICT with structured error
            scope_msg = "sur les mêmes cibles" if rule.same_target else "globalement"
            raise ConflictError(
                code="MUTEX_VIOLATION",
                message=(
                    f"Impossible d'exécuter '{action.name}' : une opération incompatible "
                    f"'{incompatible_action.name}' est déjà en cours {scope_msg}. "
                    f"Veuillez attendre la fin de l'opération en cours avant de relancer."
                ),
                details={
                    "action_id": action.id,
                    "action_name": action.name,
                    "incompatible_action_id": incompatible_action.id,
                    "incompatible_action_name": incompatible_action.name,
                    "same_target": rule.same_target,
                    "conflicting_execution_id": first_conflict.id if first_conflict else None,
                    "conflicting_status": first_conflict.status if first_conflict else None,
                    "mutex_rule_description": rule.description,
                },
            )
