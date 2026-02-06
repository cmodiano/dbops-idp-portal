"""
Serializers for inventory API.
Story 13.1 - Target serializers for API responses.
No DB model - works with dicts from external sources.
"""

from rest_framework import serializers
from inventory.models import TargetEnvironment, TargetType


class TargetSerializer(serializers.Serializer):
    """
    Serializer for target response.
    Works with dicts from external sources (API or DBOPS_INVENTORY).
    """
    name = serializers.CharField(help_text="Target name")
    environment = serializers.ChoiceField(
        choices=TargetEnvironment.CHOICES,
        help_text="Target environment (dev, staging, prod)"
    )
    target_type = serializers.ChoiceField(
        choices=TargetType.CHOICES,
        help_text="Target type (server, database, group, etc.)"
    )
    metadata = serializers.JSONField(
        allow_null=True,
        required=False,
        help_text="Additional target metadata (JSON)"
    )


class TargetFilterParamsSerializer(serializers.Serializer):
    """
    Serializer for target list filter parameters.
    """
    environment = serializers.ChoiceField(
        choices=TargetEnvironment.CHOICES,
        required=False,
        help_text="Filter by environment"
    )
    search = serializers.CharField(
        required=False,
        help_text="Search by name"
    )
    target_type = serializers.ChoiceField(
        choices=TargetType.CHOICES,
        required=False,
        help_text="Filter by target type"
    )
    page = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
        help_text="Page number"
    )
    page_size = serializers.IntegerField(
        required=False,
        default=25,
        min_value=1,
        max_value=5000,
        help_text="Items per page (max 5000 for dropdown/select use)"
    )
