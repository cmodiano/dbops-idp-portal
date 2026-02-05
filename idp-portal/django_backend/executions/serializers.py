from __future__ import annotations

from rest_framework import serializers

from catalog.models import Action
from executions.models import Execution, ExecutionStep


class ExecutionSerializer(serializers.Serializer):
    """
    Serializer matching frontend ExecutionResponse (see frontend/src/types/api.ts).
    """

    def to_representation(self, obj: Execution) -> dict:
        action: Action | None = getattr(obj, "action", None)
        user = getattr(obj, "user", None)
        integration = getattr(action, "integration", None) if action else None

        return {
            "id": obj.id,
            "action_id": obj.action_id,
            "action_name": action.name if action else None,
            "user_id": obj.user_id,
            "user_display_name": getattr(user, "display_name", None) if user else None,
            "environment": obj.environment,
            "parameters": obj.get_parameters() if hasattr(obj, "get_parameters") else None,
            "status": obj.status,
            "servicenow_change_id": obj.servicenow_change_id,
            "started_at": obj.started_at.isoformat() if obj.started_at else None,
            "completed_at": obj.completed_at.isoformat() if obj.completed_at else None,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "approved_by": obj.approved_by_id,
            "approved_at": obj.approved_at.isoformat() if obj.approved_at else None,
            "approval_comment": obj.approval_comment,
            "parent_execution_id": obj.parent_execution_id,
            # Enrichment (Story 9.9)
            "engine": getattr(action, "engine", None) if action else None,
            "platform": getattr(action, "platform", None) if action else None,
            "item_type": getattr(action, "item_type", None) if action else None,
            "integration_id": getattr(integration, "id", None) if integration else None,
            "integration_name": getattr(integration, "name", None) if integration else None,
            "integration_icon": getattr(integration, "icon", None) if integration else None,
        }


class ExecutionStepSerializer(serializers.Serializer):
    """Serializer matching frontend ExecutionStepResponse."""

    def to_representation(self, obj: ExecutionStep) -> dict:
        return {
            "id": obj.id,
            "execution_id": obj.execution_id,
            "step_order": obj.step_order,
            "step_name": obj.step_name,
            "step_type": obj.step_type,
            "status": obj.status,
            "started_at": obj.started_at.isoformat() if obj.started_at else None,
            "completed_at": obj.completed_at.isoformat() if obj.completed_at else None,
            "output": obj.get_output() if hasattr(obj, "get_output") else None,
            "platform_job_id": obj.platform_job_id,
            "error_message": obj.error_message,
        }

