from __future__ import annotations

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_serializer

from catalog.models import Action
from core.utils import ensure_utc_isoformat
from executions.models import Execution, ExecutionStep, ExecutionTarget, ScheduledExecution, RecurringPattern


class ExecutionTargetSerializer(serializers.Serializer):
    """Serializer for ExecutionTarget (Story 25.1)."""
    target_type = serializers.CharField(read_only=True)
    target_id = serializers.CharField(read_only=True)
    target_name = serializers.CharField(read_only=True)
    target_metadata = serializers.DictField(read_only=True, allow_null=True)

    def to_representation(self, obj: ExecutionTarget) -> dict:
        return {
            "target_type": obj.target_type,
            "target_id": obj.target_id,
            "target_name": obj.target_name,
            "target_metadata": obj.get_target_metadata() or {},
        }


@extend_schema_serializer(
    exclude_fields=[],
    examples=[]
)
class ExecutionSerializer(serializers.Serializer):
    """
    Serializer matching frontend ExecutionResponse (see frontend/src/types/api.ts).

    Champs dépréciés (ADR-007, Story 57.12) :
    - approved_by, approved_at, approval_comment : conservés en sortie pour rétrocompatibilité API,
      mais la source de vérité est désormais ExecutionStep.approved_* depuis Story 57.1.
      Ne plus utiliser ces champs pour de nouvelles intégrations.
    """
    id = serializers.IntegerField(read_only=True, help_text="Identifiant unique de l'exécution")
    action_id = serializers.IntegerField(help_text="ID de l'action exécutée")
    action_name = serializers.CharField(read_only=True, help_text="Nom de l'action")
    user_id = serializers.IntegerField(help_text="ID de l'utilisateur initiateur")
    user_display_name = serializers.CharField(read_only=True, allow_null=True)
    environment = serializers.CharField(help_text="Environnement d'exécution")
    parameters = serializers.DictField(read_only=True, allow_null=True, help_text="Paramètres d'exécution")
    status = serializers.CharField(help_text="Statut (submitted, running, completed, failed, cancelled)")
    servicenow_change_id = serializers.CharField(read_only=True, allow_null=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    approved_by = serializers.IntegerField(read_only=True, allow_null=True)
    approved_at = serializers.DateTimeField(read_only=True, allow_null=True)
    approval_comment = serializers.CharField(read_only=True, allow_null=True)
    parent_execution_id = serializers.IntegerField(read_only=True, allow_null=True)
    # Distinguish workflow child (parent is workflow) vs remediation (parent is action)
    parent_item_type = serializers.CharField(read_only=True, allow_null=True)
    error_message = serializers.CharField(read_only=True, allow_null=True)
    engine = serializers.CharField(read_only=True, allow_null=True)
    platform = serializers.CharField(read_only=True, allow_null=True)
    item_type = serializers.CharField(read_only=True, allow_null=True)
    integration_id = serializers.IntegerField(read_only=True, allow_null=True)
    integration_name = serializers.CharField(read_only=True, allow_null=True)
    integration_icon = serializers.CharField(read_only=True, allow_null=True)

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
            "parameters": obj.get_parameters(),
            "status": obj.status,
            "servicenow_change_id": obj.servicenow_change_id,
            "started_at": ensure_utc_isoformat(obj.started_at),
            "completed_at": ensure_utc_isoformat(obj.completed_at),
            "created_at": ensure_utc_isoformat(obj.created_at),
            # DEPRECATED ADR-007 (Story 57.12) — conservés pour rétrocompatibilité API.
            # Source de vérité : ExecutionStep.approved_by/at/approval_comment
            "approved_by": obj.approved_by_id,
            "approved_at": ensure_utc_isoformat(obj.approved_at),
            "approval_comment": obj.approval_comment,
            "parent_execution_id": obj.parent_execution_id,
            "parent_item_type": (
                obj.parent_execution
                and getattr(obj.parent_execution, "action", None)
                and getattr(obj.parent_execution.action, "item_type", None)
            ) if obj.parent_execution_id else None,
            # Story 18.6: Integration error message
            "error_message": obj.error_message,
            # Enrichment (Story 9.9)
            "engine": getattr(action, "engine", None) if action else None,
            "platform": getattr(action, "platform", None) if action else None,
            "item_type": getattr(action, "item_type", None) if action else None,
            "integration_id": getattr(integration, "id", None) if integration else None,
            "integration_name": getattr(integration, "name", None) if integration else None,
            "integration_icon": getattr(integration, "icon", None) if integration else None,
            # Story 25.1: ExecutionTarget list
            "targets": ExecutionTargetSerializer(obj.targets.all(), many=True).data,
        }


class ExecutionStepSerializer(serializers.Serializer):
    """Serializer matching frontend ExecutionStepResponse."""
    id = serializers.IntegerField(read_only=True)
    execution_id = serializers.IntegerField(read_only=True)
    step_order = serializers.IntegerField(read_only=True)
    step_name = serializers.CharField(read_only=True)
    step_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    output = serializers.DictField(read_only=True, allow_null=True)
    platform_job_id = serializers.CharField(read_only=True, allow_null=True)
    error_message = serializers.CharField(read_only=True, allow_null=True)

    def to_representation(self, obj: ExecutionStep) -> dict:
        return {
            "id": obj.id,
            "execution_id": obj.execution_id,
            "step_order": obj.step_order,
            "step_name": obj.step_name,
            "step_type": obj.step_type,
            "status": obj.status,
            "started_at": ensure_utc_isoformat(obj.started_at),
            "completed_at": ensure_utc_isoformat(obj.completed_at),
            "output": obj.get_output(),
            "platform_job_id": obj.platform_job_id,
            "error_message": obj.error_message,
            "approved_by_id": obj.approved_by_id,
            "approved_at": ensure_utc_isoformat(obj.approved_at),
            "approval_comment": obj.approval_comment,
        }


class RecurringPatternSerializer(serializers.Serializer):
    """Serializer matching frontend RecurringPatternResponse."""
    pattern_type = serializers.CharField(read_only=True, help_text="Type de récurrence (daily, weekly, cron)")
    pattern_config = serializers.DictField(read_only=True, help_text="Configuration du pattern")
    next_execution_date = serializers.DateTimeField(read_only=True, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)

    def to_representation(self, obj: RecurringPattern) -> dict:
        return {
            "pattern_type": obj.pattern_type,
            "pattern_config": obj.get_pattern_config(),
            "next_execution_date": ensure_utc_isoformat(obj.next_execution_date),
            "is_active": bool(obj.is_active),
        }


class ScheduledExecutionSerializer(serializers.Serializer):
    """
    Serializer matching frontend ScheduledExecutionResponse.
    Used for POST /scheduled-executions responses.
    """
    scheduled_execution_id = serializers.IntegerField(read_only=True)
    action_id = serializers.IntegerField(read_only=True)
    action_name = serializers.CharField(read_only=True, allow_null=True)
    environment = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    scheduled_at = serializers.DateTimeField(read_only=True)
    parameters = serializers.DictField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    correlation_id = serializers.CharField(read_only=True, allow_null=True)
    recurring_pattern = RecurringPatternSerializer(read_only=True, allow_null=True)

    def to_representation(self, obj: ScheduledExecution) -> dict:
        action: Action | None = getattr(obj, "action", None)
        recurring_pattern = getattr(obj, "recurringpattern", None)

        data = {
            "scheduled_execution_id": obj.id,
            "action_id": obj.action_id,
            "action_name": action.name if action else None,
            "environment": obj.environment,
            "status": obj.status,
            "scheduled_at": ensure_utc_isoformat(obj.scheduled_at),
            "parameters": obj.get_parameters(),
            "created_at": ensure_utc_isoformat(obj.created_at),
            "correlation_id": getattr(obj, "correlation_id", None),
        }

        if recurring_pattern is not None:
            data["recurring_pattern"] = RecurringPatternSerializer(recurring_pattern).data

        return data


class ScheduledExecutionListItemSerializer(serializers.Serializer):
    """Serializer matching frontend ScheduledExecutionListItem."""
    scheduled_execution_id = serializers.IntegerField(read_only=True)
    action_id = serializers.IntegerField(read_only=True)
    action_name = serializers.CharField(read_only=True, allow_null=True)
    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.CharField(read_only=True)
    environment = serializers.CharField(read_only=True)
    scheduled_at = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    parameters = serializers.DictField(read_only=True, allow_null=True)
    correlation_id = serializers.CharField(read_only=True, allow_null=True)
    execution_id = serializers.IntegerField(read_only=True, allow_null=True)
    engine = serializers.CharField(read_only=True, allow_null=True)
    platform = serializers.CharField(read_only=True, allow_null=True)
    recurring_pattern = RecurringPatternSerializer(read_only=True, allow_null=True)

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
            "scheduled_at": ensure_utc_isoformat(obj.scheduled_at),
            "status": obj.status,
            "created_at": ensure_utc_isoformat(obj.created_at),
            "parameters": obj.get_parameters(),
            "correlation_id": getattr(obj, "correlation_id", None),
            "execution_id": getattr(obj, "execution_id", None),
            # Story 57.17: ID de l'exécution source ayant créé cette planification via un step workflow
            "source_execution_id": getattr(obj, 'source_execution_id', None),
            # Story 13.6 AC3: Plateforme et Technologie pour le popover détail
            "engine": getattr(action, "engine", None) if action else None,
            "platform": getattr(action, "platform", None) if action else None,
        }

        if recurring_pattern is not None:
            data["recurring_pattern"] = RecurringPatternSerializer(recurring_pattern).data

        return data


# Story 30.2: Remediation endpoint serializers (MEDIUM-2 fix)


class RemediationMatchingRuleSerializer(serializers.Serializer):
    """Schema for matching_rule in remediation suggestions."""

    error_pattern = serializers.CharField()
    environments = serializers.ListField(child=serializers.CharField())
    risk_level = serializers.CharField()
    auto_trigger = serializers.BooleanField()


class RemediationSuggestionSerializer(serializers.Serializer):
    """Response schema for GET /executions/{id}/remediation."""

    action_id = serializers.IntegerField()
    action_name = serializers.CharField()
    action_description = serializers.CharField()
    matching_rule = RemediationMatchingRuleSerializer()


class RemediationActionSerializer(serializers.Serializer):
    """Schema for remediation_actions in remediation context."""

    id = serializers.IntegerField()
    action_id = serializers.IntegerField()
    action_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    created_at = serializers.CharField(allow_null=True)
    completed_at = serializers.CharField(allow_null=True)
    error_message = serializers.CharField(allow_null=True)


class RemediationContextSerializer(serializers.Serializer):
    """Response schema for GET /executions/{id}/remediation-context."""

    has_remediation = serializers.BooleanField()
    successful_remediation = serializers.BooleanField()
    remediation_actions = RemediationActionSerializer(many=True)

