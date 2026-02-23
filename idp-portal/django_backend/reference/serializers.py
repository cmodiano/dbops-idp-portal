"""
Serializers for reference API.
Story 13.7 - Reference data serializers.
Story 2.30 - Category reference serializer.
"""

import re
from rest_framework import serializers
from reference.models import RefEngine, RefCategory
from integrations.models import IntegrationTypeCatalogue


class RefEngineSerializer(serializers.ModelSerializer):
    """Serializer for RefEngine model."""

    normalized_code = serializers.SerializerMethodField()

    class Meta:
        model = RefEngine
        fields = ['id', 'code', 'label', 'display_order', 'is_active', 'normalized_code', 'icon_url']

    def get_normalized_code(self, obj: RefEngine) -> str:
        """Retourne le code normalisé (minuscules + underscores) pour usage dans engine_type."""
        return obj.code.lower().replace(' ', '_')


class RefEngineWriteSerializer(serializers.ModelSerializer):
    """Write serializer for RefEngine admin updates (Story 31.3, AC6)."""

    class Meta:
        model = RefEngine
        fields = ['label', 'display_order', 'is_active', 'icon_url']


class PlatformTypeCatalogueSerializer(serializers.ModelSerializer):
    """Story 31.9: Serializer for IntegrationTypeCatalogue (role=platform).
    Replaces RefPlatformSerializer. Compatible response format."""

    label: serializers.CharField = serializers.CharField(source='name')  # type: ignore[assignment]
    normalized_code: serializers.CharField = serializers.CharField(source='code')

    class Meta:
        model = IntegrationTypeCatalogue
        fields = ['code', 'label', 'is_active', 'normalized_code']


class RefCategorySerializer(serializers.ModelSerializer):
    """Serializer for RefCategory model (Story 2.30)."""

    class Meta:
        model = RefCategory
        fields = ['id', 'code', 'label', 'display_order', 'is_active']


class RefCategoryWriteSerializer(serializers.ModelSerializer):
    """Write serializer for RefCategory with validation (Story 2.30, AC5)."""

    class Meta:
        model = RefCategory
        fields = ['code', 'label', 'display_order', 'is_active']

    def validate_code(self, value: str) -> str:
        if not re.match(r'^[a-z0-9_-]+$', value):
            raise serializers.ValidationError(
                "Le code doit contenir uniquement des lettres minuscules, chiffres, tirets et underscores."
            )
        return value

    def validate_label(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Le libellé ne peut pas être vide.")
        return value.strip()

    def validate_display_order(self, value: int) -> int:
        if value < 0:
            raise serializers.ValidationError("L'ordre d'affichage doit être >= 0.")
        return value
