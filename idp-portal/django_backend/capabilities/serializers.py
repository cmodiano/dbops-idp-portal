# capabilities/serializers.py
# Serializers DRF pour documentation OpenAPI uniquement.
# Les views construisent les dicts directement.
from rest_framework import serializers


class PlatformCapabilitySerializer(serializers.Serializer):
    code = serializers.CharField()
    display_name = serializers.CharField()
    aliases = serializers.ListField(child=serializers.CharField())
    icon = serializers.CharField()
    connector_type = serializers.CharField()
    action_platform_code = serializers.CharField()
    supports_health_check = serializers.BooleanField()
    action_config_schema = serializers.DictField(default=dict)
    runtime_config_schema = serializers.DictField(default=dict)
    health_check_policy = serializers.DictField(default=dict)


class ServiceOperationSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    input_schema = serializers.DictField(default=dict)
    output_schema = serializers.DictField(default=dict)
    ui_hints = serializers.DictField(default=dict)


class ServiceCapabilitySerializer(serializers.Serializer):
    code = serializers.CharField()
    display_name = serializers.CharField()
    credential_mode = serializers.ChoiceField(choices=['integration', 'credential_free'])
    operations = ServiceOperationSerializer(many=True)
    supports_health_check = serializers.BooleanField()
    supports_service_call = serializers.BooleanField()


class GateVariantSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    config_schema = serializers.DictField(default=dict)


class StepTypeSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    category = serializers.CharField()
    config_schema = serializers.DictField(default=dict)
    constraints = serializers.DictField(default=dict)
    variants = GateVariantSerializer(many=True, required=False)


class IntegrationsCapabilityResponseSerializer(serializers.Serializer):
    platforms = PlatformCapabilitySerializer(many=True)
    services = ServiceCapabilitySerializer(many=True)


class WorkflowStepsCapabilityResponseSerializer(serializers.Serializer):
    step_types = StepTypeSerializer(many=True)


class IntegrationsCapabilityDataSerializer(serializers.Serializer):
    data = IntegrationsCapabilityResponseSerializer()  # type: ignore[assignment]


class WorkflowStepsCapabilityDataSerializer(serializers.Serializer):
    data = WorkflowStepsCapabilityResponseSerializer()  # type: ignore[assignment]
