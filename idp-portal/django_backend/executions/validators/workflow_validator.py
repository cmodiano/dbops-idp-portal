"""Validation des workflows et de leurs paramètres par étape."""
from __future__ import annotations

from core.exceptions import BadRequestError
from executions.utils import (
    _extract_workflow_referenced_action_ids,
    _extract_workflow_step_map,
    _validate_workflow_step_parameters,
    _validate_workflow_referenced_actions,
)


class WorkflowValidator:
    """Validation des workflows : actions référencées et paramètres par étape."""

    @staticmethod
    def validate_referenced_actions(
        workflow_action,
        correlation_id: str,
        user_id,
        ip_address: str,
    ) -> list[int] | None:
        """
        Validate workflow referenced actions (Story 4.11).

        Returns:
            List of delegated referenced action IDs, or None.
        """
        return _validate_workflow_referenced_actions(
            workflow_action=workflow_action,
            correlation_id=correlation_id,
            user_id=user_id,
            ip_address=ip_address,
        )

    @staticmethod
    def validate_step_parameters(
        workflow_action,
        workflow_step_parameters,
    ) -> dict:
        """
        Validate and normalize workflow_step_parameters (Story 4.12).

        Returns:
            Normalized workflow step parameters dict.

        Raises:
            BadRequestError: If parameters are invalid.
        """
        return _validate_workflow_step_parameters(
            workflow_action=workflow_action,
            workflow_step_parameters=workflow_step_parameters,
        )

    @staticmethod
    def reject_step_parameters_for_non_workflow(action, workflow_step_parameters) -> None:
        """Reject workflow_step_parameters on non-workflow actions (Story 4.12)."""
        if workflow_step_parameters is not None:
            raise BadRequestError(
                code="INVALID_WORKFLOW_STEP_PARAMETERS",
                message="workflow_step_parameters n'est autorisé que pour les workflows",
                details={"action_id": action.id, "item_type": action.item_type},
            )
