"""Business rule policy serializers."""
from __future__ import annotations

from typing import Any

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from catalog.models import BusinessRulePolicy


class BusinessRulePolicyListSerializer(serializers.ModelSerializer):
    """Story 28.4: List serializer for BusinessRulePolicy (AC#4)."""
    step_type = serializers.SerializerMethodField()

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_step_type(self, obj: BusinessRulePolicy) -> str | None:
        return obj.step_type

    class Meta:
        model = BusinessRulePolicy
        fields = ['id', 'name', 'description', 'is_active', 'step_type', 'created_at', 'updated_at']


class BusinessRulePolicySerializer(serializers.ModelSerializer):
    """Story 28.4: Detail serializer for BusinessRulePolicy (AC#4)."""
    step_type = serializers.SerializerMethodField()
    policy_json = serializers.JSONField()
    actions_count = serializers.SerializerMethodField()

    class Meta:
        model = BusinessRulePolicy
        fields = [
            'id', 'name', 'description', 'policy_json', 'is_active',
            'step_type', 'actions_count', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_step_type(self, obj: BusinessRulePolicy) -> str | None:
        return obj.step_type

    @extend_schema_field(OpenApiTypes.INT)
    def get_actions_count(self, obj: BusinessRulePolicy) -> int:
        return obj.actions.count()

    def validate_policy_json(self, value: Any) -> Any:
        if value is not None:
            from catalog.validators import validate_business_rule_policies
            validate_business_rule_policies(value)
        return value
