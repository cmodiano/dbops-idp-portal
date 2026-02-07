from __future__ import annotations

from rest_framework import serializers

from catalog.models import Action
from executions.models import Execution, ExecutionStep, ScheduledExecution, RecurringPattern


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
            # Story 18.6: Integration error message
            "error_message": obj.error_message,
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


class RecurringPatternSerializer(serializers.Serializer):
    """Serializer matching frontend RecurringPatternResponse."""

    def to_representation(self, obj: RecurringPattern) -> dict:
        return {
            "pattern_type": obj.pattern_type,
            "pattern_config": obj.get_pattern_config() if hasattr(obj, "get_pattern_config") else None,
            "next_execution_date": obj.next_execution_date.isoformat() if obj.next_execution_date else None,
            "is_active": bool(obj.is_active),
        }


class ScheduledExecutionSerializer(serializers.Serializer):
    """
    Serializer matching frontend ScheduledExecutionResponse.
    Used for POST /scheduled-executions responses.
    """

    def to_representation(self, obj: ScheduledExecution) -> dict:
        action: Action | None = getattr(obj, "action", None)
        recurring_pattern = getattr(obj, "recurringpattern", None)

        data = {
            "scheduled_execution_id": obj.id,
            "action_id": obj.action_id,
            "action_name": action.name if action else None,
            "environment": obj.environment,
            "status": obj.status,
            "scheduled_at": obj.scheduled_at.isoformat() if obj.scheduled_at else None,
            "parameters": obj.get_parameters() if hasattr(obj, "get_parameters") else None,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "correlation_id": getattr(obj, "correlation_id", None),
        }

        if recurring_pattern is not None:
            data["recurring_pattern"] = RecurringPatternSerializer(recurring_pattern).data

        return data


class ScheduledExecutionListItemSerializer(serializers.Serializer):
    """Serializer matching frontend ScheduledExecutionListItem."""

    def to_representation(self, obj: ScheduledExecution) -> dict:
        action: Action | None = getattr(obj, "action", None)
        user = getattr(obj, "user", None)
        recurring_pattern = getattr(obj, "recurringpattern", None)

        data = {
            "scheduled_execution_id": obj.id,
            "action_id": obj.action_id,
            "action_name": action.name if action else None,
            "user_id": obj.user_id,
            "user_name": getattr(user, "display_name", None) or getattr(user, "username", None) or "",
            "environment": obj.environment,
            "scheduled_at": obj.scheduled_at.isoformat() if obj.scheduled_at else None,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
            "parameters": obj.get_parameters() if hasattr(obj, "get_parameters") else None,
            "correlation_id": getattr(obj, "correlation_id", None),
            "execution_id": getattr(obj, "execution_id", None),
            # Story 13.6 AC3: Plateforme et Technologie pour le popover détail
            "engine": getattr(action, "engine", None) if action else None,
            "platform": getattr(action, "platform", None) if action else None,
        }

        if recurring_pattern is not None:
            data["recurring_pattern"] = RecurringPatternSerializer(recurring_pattern).data

        return data

