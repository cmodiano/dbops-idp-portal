"""
Serializers for integrations endpoints.
Matches FastAPI IntegrationCreate, IntegrationUpdate, IntegrationResponse models.
"""

from rest_framework import serializers
from integrations.models import Integration, AuthFlow, IntegrationType


def validate_url(value):
    """Validate URL format (must start with http:// or https://)."""
    if value and not value.startswith(('http://', 'https://')):
        raise serializers.ValidationError(
            "URL must start with http:// or https://"
        )
    return value


class IntegrationSerializer(serializers.ModelSerializer):
    """
    Serializer for integration read operations (GET /admin/integrations/{id}).
    Matches FastAPI IntegrationResponse model.
    """
    config = serializers.SerializerMethodField()
    auth_flow = serializers.CharField(required=False, allow_null=True)
    
    class Meta:
        model = Integration
        fields = [
            'id', 'type', 'name', 'base_url', 'credential_ref', 'icon',
            'auth_flow', 'token_url', 'config', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_config(self, obj):
        """Deserialize config CLOB to dict."""
        return obj.get_config()


class IntegrationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating integrations (POST /admin/integrations).
    Matches FastAPI IntegrationCreate model.
    """
    type = serializers.ChoiceField(
        choices=IntegrationType.choices,
        required=True,
        help_text="Integration type (enum: aap, servicenow, terraform, etc.)"
    )
    name = serializers.CharField(
        max_length=255,
        min_length=1,
        required=True,
        help_text="Unique integration name (1-255 chars, required)"
    )
    base_url = serializers.CharField(
        max_length=2000,
        required=True,
        help_text="Base URL of the remote platform (valid URL format, required)"
    )
    credential_ref = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional Vault path or logical name for credentials"
    )
    icon = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional icon identifier (preset name, URL, or uploaded icon path)"
    )
    auth_flow = serializers.ChoiceField(
        choices=AuthFlow.choices,
        required=False,
        allow_null=True,
        help_text="Optional authentication flow (token, basic, basic_then_token, pat)"
    )
    token_url = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Optional URL for token acquisition (validated http(s))"
    )
    config = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Optional JSON flow steps + credentials per step (validated against JSON Schema)"
    )
    
    def validate_type(self, value):
        """Validate type is a valid IntegrationType enum value."""
        if value not in [choice[0] for choice in IntegrationType.choices]:
            raise serializers.ValidationError(
                f"type must be one of: {', '.join([c[0] for c in IntegrationType.choices])}"
            )
        return value
    
    def validate_name(self, value):
        """Strip whitespace and validate not empty."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped
    
    def validate_base_url(self, value):
        """Validate base_url is a valid URL format."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("base_url cannot be empty or whitespace only")
        return validate_url(stripped)
    
    def validate_token_url(self, value):
        """Validate token_url is a valid http(s) URL when provided."""
        if not value:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return validate_url(stripped)


class IntegrationUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating integrations (PUT /admin/integrations/{id}).
    Matches FastAPI IntegrationUpdate model.
    All fields optional for partial update.
    """
    type = serializers.ChoiceField(
        choices=IntegrationType.choices,
        required=False,
        allow_null=True
    )
    name = serializers.CharField(
        max_length=255,
        min_length=1,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    base_url = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    credential_ref = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    icon = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    auth_flow = serializers.ChoiceField(
        choices=AuthFlow.choices,
        required=False,
        allow_null=True
    )
    token_url = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    config = serializers.DictField(
        required=False,
        allow_null=True
    )
    
    def validate_type(self, value):
        """Validate type is a valid IntegrationType enum value."""
        if value is None:
            return None
        if value not in [choice[0] for choice in IntegrationType.choices]:
            raise serializers.ValidationError(
                f"type must be one of: {', '.join([c[0] for c in IntegrationType.choices])}"
            )
        return value
    
    def validate_name(self, value):
        """Strip whitespace and validate not empty."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped
    
    def validate_base_url(self, value):
        """Validate base_url is a valid URL format."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("base_url cannot be empty or whitespace only")
        return validate_url(stripped)
    
    def validate_token_url(self, value):
        """Validate token_url is a valid http(s) URL when provided."""
        if not value:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return validate_url(stripped)


class IntegrationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for integration list (GET /admin/integrations).
    Excludes config for performance.
    """
    auth_flow = serializers.CharField(required=False, allow_null=True)
    
    class Meta:
        model = Integration
        fields = [
            'id', 'type', 'name', 'base_url', 'credential_ref', 'icon',
            'auth_flow', 'token_url', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
