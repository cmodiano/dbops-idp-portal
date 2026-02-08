"""
Serializers for reference API.
Story 13.7 - Reference data serializers.
Story 2.30 - Category reference serializer.
"""

import re
from rest_framework import serializers
from reference.models import RefEngine, RefPlatform, RefCategory


class RefEngineSerializer(serializers.ModelSerializer):
    """Serializer for RefEngine model."""

    class Meta:
        model = RefEngine
        fields = ['id', 'code', 'label', 'display_order', 'is_active']


class RefPlatformSerializer(serializers.ModelSerializer):
    """Serializer for RefPlatform model."""

    class Meta:
        model = RefPlatform
        fields = ['id', 'code', 'label', 'display_order', 'is_active']


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

    def validate_code(self, value):
        if not re.match(r'^[a-z0-9_-]+$', value):
            raise serializers.ValidationError(
                "Le code doit contenir uniquement des lettres minuscules, chiffres, tirets et underscores."
            )
        return value

    def validate_label(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Le libellé ne peut pas être vide.")
        return value.strip()

    def validate_display_order(self, value):
        if value < 0:
            raise serializers.ValidationError("L'ordre d'affichage doit être >= 0.")
        return value
