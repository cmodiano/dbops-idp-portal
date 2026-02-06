"""
Serializers for reference API.
Story 13.7 - Reference data serializers.
"""

from rest_framework import serializers
from reference.models import RefEngine, RefPlatform


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
