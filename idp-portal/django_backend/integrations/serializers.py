"""
Serializers for integrations endpoints.
"""

import json

from rest_framework import serializers
import structlog

from integrations.models import (
    Integration, AuthFlow, IntegrationType, IntegrationRole,
    IntegrationTypeCatalogue, IntegrationAction,
)

logger = structlog.get_logger(__name__)


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
    """
    config = serializers.SerializerMethodField()
    auth_flow = serializers.CharField(required=False, allow_null=True)
    
    class Meta:
        model = Integration
        fields = [
            'id', 'type', 'name', 'base_url', 'credential_ref', 'icon',
            'auth_flow', 'token_url', 'config', 'status',
            'secret_service_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']

    secret_service_id = serializers.PrimaryKeyRelatedField(
        source='secret_service',
        queryset=Integration.objects.filter(type=IntegrationType.VAULT),
        required=False,
        allow_null=True,
    )

    def get_config(self, obj):
        """Deserialize config CLOB to dict."""
        return obj.get_config()


class IntegrationVaultValidationMixin:
    """Story 30.8 ERR-2: Shared cross-field validation for credential_ref and secret_service_id."""

    def _validate_vault_constraints(self, attrs: dict, instance=None) -> dict:
        """
        Validate cross-field constraints for Vault integrations.

        For update serializers, merges provided attrs with existing instance
        data so partial updates are validated correctly.
        """
        if instance:
            integration_type = attrs.get('type', instance.type)
            credential_ref = attrs.get('credential_ref', instance.credential_ref)
            # Fix HIGH-3: Use secret_service.id for FK relation, not secret_service_id attribute
            existing_secret_service_id = instance.secret_service.id if instance.secret_service else None
            secret_service_id = attrs.get('secret_service_id', existing_secret_service_id)
        else:
            integration_type = attrs.get('type', '')
            credential_ref = attrs.get('credential_ref')
            secret_service_id = attrs.get('secret_service_id')

        # Vault integrations should not have credential_ref
        if integration_type == IntegrationType.VAULT and credential_ref:
            raise serializers.ValidationError({
                'credential_ref': (
                    "Les intégrations de type 'vault' n'ont pas besoin de credential_ref. "
                    "L'authentification utilise le secret 0 (variables d'environnement)."
                )
            })

        # Vault integrations should not have secret_service_id
        if integration_type == IntegrationType.VAULT and secret_service_id:
            raise serializers.ValidationError({
                'secret_service_id': (
                    "Les intégrations de type 'vault' ne peuvent pas avoir de service de secrets."
                )
            })

        # secret_service_id must reference a vault integration
        if secret_service_id is not None:
            try:
                vault_integration = Integration.objects.get(id=secret_service_id)
                if vault_integration.type != IntegrationType.VAULT:
                    raise serializers.ValidationError({
                        'secret_service_id': (
                            f"L'intégration référencée (id={secret_service_id}) n'est pas de type 'vault' "
                            f"(type actuel: '{vault_integration.type}')."
                        )
                    })
            except Integration.DoesNotExist:
                raise serializers.ValidationError({
                    'secret_service_id': f"Aucune intégration trouvée avec l'id {secret_service_id}."
                })

        return attrs


class IntegrationCreateSerializer(IntegrationVaultValidationMixin, serializers.Serializer):
    """
    Serializer for creating integrations (POST /admin/integrations).
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
    # Story 27.11: Service de secrets (FK vers intégration Vault)
    secret_service_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID de l'intégration Vault à utiliser pour résoudre les secrets (NULL = Vault par défaut)"
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

    def validate(self, attrs):
        """Cross-field validation for credential_ref and secret_service_id."""
        attrs = super().validate(attrs)
        return self._validate_vault_constraints(attrs)


class IntegrationUpdateSerializer(IntegrationVaultValidationMixin, serializers.Serializer):
    """
    Serializer for updating integrations (PUT /admin/integrations/{id}).
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
    # Story 27.11: Service de secrets (FK vers intégration Vault)
    secret_service_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID de l'intégration Vault à utiliser pour résoudre les secrets (NULL = Vault par défaut)"
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

    def validate(self, attrs):
        """Story 30.8 ERR-2: Cross-field validation for partial updates."""
        attrs = super().validate(attrs)
        # Merge with instance data for partial update validation
        instance = getattr(self, 'instance', None)
        return self._validate_vault_constraints(attrs, instance=instance)


class IntegrationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for integration list (GET /admin/integrations).
    Excludes config for performance.
    """
    auth_flow = serializers.CharField(required=False, allow_null=True)
    secret_service_id: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
        source='secret_service',
        read_only=True,
    )

    class Meta:
        model = Integration
        fields = [
            'id', 'type', 'name', 'base_url', 'credential_ref', 'icon',
            'auth_flow', 'token_url', 'status', 'secret_service_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ============================================================================
# Story 24.1: Integration Type Catalogue Serializers
# ============================================================================


class JSONTextField(serializers.Field):
    """Serialize/deserialize TextField containing JSON."""

    def to_representation(self, value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_internal_value(self, data):
        if isinstance(data, str):
            return data
        return json.dumps(data)


class IntegrationActionSerializer(serializers.ModelSerializer):
    """Serializer for IntegrationAction model."""
    required_params = JSONTextField()
    optional_params = JSONTextField()
    response_format = JSONTextField()

    class Meta:
        model = IntegrationAction
        fields = [
            'id', 'action_code', 'action_label', 'description',
            'required_params', 'optional_params', 'response_format',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class IntegrationTypeCatalogueSerializer(serializers.ModelSerializer):
    """Serializer for IntegrationTypeCatalogue model (without nested actions)."""

    class Meta:
        model = IntegrationTypeCatalogue
        fields = [
            'code', 'name', 'description', 'version',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class IntegrationTypeWithActionsSerializer(serializers.ModelSerializer):
    """Serializer for IntegrationTypeCatalogue with nested actions."""
    actions = IntegrationActionSerializer(many=True, read_only=True)

    class Meta:
        model = IntegrationTypeCatalogue
        fields = [
            'code', 'name', 'description', 'version',
            'is_active', 'integration_role', 'created_at', 'updated_at', 'actions',
        ]
        read_only_fields = ['created_at', 'updated_at']
