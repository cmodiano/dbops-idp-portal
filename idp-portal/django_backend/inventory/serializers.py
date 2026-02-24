"""
Serializers for inventory API.
Story 13.1 - Target serializers for API responses.
Story 23.3 - Multi-table inventory serializers (servers, instances, databases).
No DB model - works with dicts from external sources.
"""

from __future__ import annotations

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


# --- Story 23.3: Multi-table inventory serializers ---


class ServerSerializer(serializers.Serializer):
    """Serializer for server inventory entity. Story 23.3 AC4."""
    id = serializers.CharField(help_text="Server unique identifier")
    name = serializers.CharField(help_text="Server hostname")
    environment = serializers.CharField(help_text="Server environment")
    engine_type = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Database engine type (oracle, sqlserver, postgres, etc.)"
    )


class InstanceSerializer(serializers.Serializer):
    """Serializer for instance inventory entity. Story 23.3 AC4."""
    id = serializers.CharField(help_text="Instance unique identifier")
    name = serializers.CharField(help_text="Instance name")
    environment = serializers.CharField(help_text="Instance environment")
    server_ref = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Parent server reference"
    )
    db_ref = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Associated database reference"
    )


class DatabaseSerializer(serializers.Serializer):
    """Serializer for database inventory entity. Story 23.3 AC4."""
    id = serializers.CharField(help_text="Database unique identifier")
    name = serializers.CharField(help_text="Database name")
    environment = serializers.CharField(help_text="Database environment")


class ServerFilterParamsSerializer(serializers.Serializer):
    """Query params validation for servers endpoint. Story 23.3 AC1."""
    environment = serializers.CharField(
        required=True,
        max_length=50,
        help_text="Target environment (required)"
    )
    engine_type = serializers.CharField(
        required=False,
        max_length=20,
        help_text="Filter by engine type (oracle, sqlserver, postgres, etc.)"
    )


class InstanceFilterParamsSerializer(serializers.Serializer):
    """Query params validation for instances endpoint. Story 23.3 AC2."""
    environment = serializers.CharField(
        required=True,
        max_length=50,
        help_text="Target environment (required)"
    )
    engine_type = serializers.CharField(
        required=False,
        max_length=20,
        help_text="Filter by engine type (oracle, sqlserver, postgres, etc.)"
    )
    server_name = serializers.CharField(
        required=False,
        max_length=255,
        help_text="Filter by single server name"
    )
    server_names = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=False,
        help_text="Filter by multiple server names"
    )

    def validate(self, attrs: dict) -> dict:
        """Ensure server_name and server_names are mutually exclusive per AC2."""
        if attrs.get('server_name') and attrs.get('server_names'):
            raise serializers.ValidationError(
                "Cannot specify both server_name and server_names"
            )
        return attrs


class DatabaseFilterParamsSerializer(serializers.Serializer):
    """Query params validation for databases endpoint. Story 23.3 AC3."""
    environment = serializers.CharField(
        required=True,
        max_length=50,
        help_text="Target environment (required)"
    )
    engine_type = serializers.CharField(
        required=False,
        max_length=20,
        help_text="Filter by engine type (oracle, sqlserver, postgres, etc.)"
    )
    server_name = serializers.CharField(
        required=False,
        max_length=255,
        help_text="Filter by single server name"
    )
    server_names = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=False,
        help_text="Filter by multiple server names"
    )

    def validate(self, attrs: dict) -> dict:
        """Ensure server_name and server_names are mutually exclusive per AC3."""
        if attrs.get('server_name') and attrs.get('server_names'):
            raise serializers.ValidationError(
                "Cannot specify both server_name and server_names"
            )
        return attrs


# --- Response wrapper serializers for OpenAPI documentation (AC7) ---


class ServerListResponseSerializer(serializers.Serializer):
    """Wrapper for servers list response. Story 23.3 AC7 - OpenAPI documentation."""
    data = ServerSerializer(many=True, help_text="List of servers")  # type: ignore[assignment]


class InstanceListResponseSerializer(serializers.Serializer):
    """Wrapper for instances list response. Story 23.3 AC7 - OpenAPI documentation."""
    data = InstanceSerializer(many=True, help_text="List of instances")  # type: ignore[assignment]


class DatabaseListResponseSerializer(serializers.Serializer):
    """Wrapper for databases list response. Story 23.3 AC7 - OpenAPI documentation."""
    data = DatabaseSerializer(many=True, help_text="List of databases")  # type: ignore[assignment]
