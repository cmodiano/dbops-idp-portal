"""
DRF Serializers for catalog app.
Maps Django models to FastAPI-compatible JSON responses.
"""

from rest_framework import serializers
from catalog.models import (
    Action, Tag, ActionTag,
    ActionStatus, ActionEngine, ActionPlatform, ActionItemType
)


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model (GET /tags, GET /catalog/tags)."""
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'created_at']


class ActionTagsUpdateSerializer(serializers.Serializer):
    """Serializer for PUT /admin/actions/{id}/tags."""
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_null=True
    )
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_null=True
    )
    
    def validate(self, data):
        """Ensure either tag_ids or tag_names is provided, but not both."""
        tag_ids = data.get('tag_ids')
        tag_names = data.get('tag_names')
        
        if tag_ids is None and tag_names is None:
            raise serializers.ValidationError("provide either tag_ids or tag_names")
        if tag_ids is not None and tag_names is not None:
            raise serializers.ValidationError("provide either tag_ids or tag_names, not both")
        
        return data


class StatusUpdateSerializer(serializers.Serializer):
    """Serializer for PATCH /admin/actions/{id}/status."""
    transition = serializers.ChoiceField(
        choices=['publish', 'disable', 'enable'],
        required=True
    )


class ActionSerializer(serializers.ModelSerializer):
    """Base Action serializer (read/write) matching ActionResponse/ActionDetail."""
    
    # CLOB/JSON fields - use SerializerMethodField for read, custom handling for write
    parameters_schema = serializers.SerializerMethodField()
    impact_rules = serializers.SerializerMethodField()
    execution_steps = serializers.SerializerMethodField()
    change_type_config = serializers.SerializerMethodField()
    remediation_rules = serializers.SerializerMethodField()
    
    # Relations
    tags = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    
    # Enums
    status = serializers.ChoiceField(choices=ActionStatus.choices)
    engine = serializers.ChoiceField(choices=ActionEngine.choices, allow_null=True)
    platform = serializers.ChoiceField(choices=ActionPlatform.choices, allow_null=True)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    
    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'engine', 'platform',
            'parameters_schema', 'impact_rules', 'default_impact_level',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'documentation_md', 'remediation_rules',
            'execution_steps', 'change_type_config',
            # Story 13.2, AC3: requires_target field
            'requires_target'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    def get_parameters_schema(self, obj):
        """Deserialize JSON from CLOB using model helper."""
        return obj.get_parameters_schema()
    
    def get_impact_rules(self, obj):
        """Deserialize JSON from CLOB using model helper."""
        return obj.get_impact_rules()
    
    def get_execution_steps(self, obj):
        """Deserialize JSON from CLOB using model helper."""
        return obj.get_execution_steps()
    
    def get_change_type_config(self, obj):
        """Deserialize JSON from CLOB using model helper."""
        return obj.get_change_type_config()
    
    def get_remediation_rules(self, obj):
        """Deserialize JSON from CLOB using model helper."""
        return obj.get_remediation_rules()
    
    def get_tags(self, obj):
        """Get tag names from ActionTag relations."""
        # Use prefetched tags if available
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        # Fallback: query if not prefetched
        return list(obj.actiontag_set.values_list('tag__name', flat=True))
    
    def get_created_by(self, obj):
        """Get created_by user ID."""
        return obj.created_by.id if obj.created_by else None
    
    def to_internal_value(self, data):
        """Convert incoming JSON to model fields (for write operations)."""
        # Handle JSON fields - convert dict to JSON string for CLOB storage
        validated_data = super().to_internal_value(data)
        
        # Store JSON fields as-is (will be converted by model setters)
        json_fields = ['parameters_schema', 'impact_rules', 'execution_steps', 
                      'change_type_config', 'remediation_rules']
        for field in json_fields:
            if field in data:
                validated_data[field] = data[field]  # Keep as dict, model will serialize
        
        return validated_data
    
    def create(self, validated_data):
        """Create action - handled by ViewSet using CatalogService."""
        # This serializer is mainly for read operations
        # Create is handled by ActionCreateSerializer
        raise NotImplementedError("Use ActionCreateSerializer for creation")
    
    def update(self, instance, validated_data):
        """Update action - handled by ViewSet using CatalogService."""
        # This serializer is mainly for read operations
        # Update is handled by ViewSet
        raise NotImplementedError("Update handled by ViewSet")


class ActionCreateSerializer(serializers.Serializer):
    """Serializer for POST /admin/actions (ActionCreate model)."""
    
    name = serializers.CharField(max_length=255, min_length=1)
    description = serializers.CharField(max_length=4000, required=False, allow_null=True)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    engine = serializers.ChoiceField(choices=ActionEngine.choices, required=False, allow_null=True)
    platform = serializers.ChoiceField(choices=ActionPlatform.choices, required=False, allow_null=True)
    parameters_schema = serializers.DictField(required=False, allow_null=True)
    impact_rules = serializers.DictField(required=False, allow_null=True)
    default_impact_level = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'critical'],
        required=False,
        allow_null=True
    )
    documentation_md = serializers.CharField(max_length=100_000, required=False, allow_null=True)
    
    def validate_name(self, value):
        """Strip whitespace and validate not empty."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped
    
    def validate(self, data):
        """Validate engine and platform required for action type."""
        item_type = data.get('item_type', ActionItemType.ACTION)
        if item_type == ActionItemType.ACTION:
            if not data.get('engine'):
                raise serializers.ValidationError("engine is required for action type")
            if not data.get('platform'):
                raise serializers.ValidationError("platform is required for action type")
        return data


class ActionListSerializer(serializers.ModelSerializer):
    """Serializer for GET /admin/actions (simplified list with execution_count)."""
    
    tags = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'engine', 'platform',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'execution_count'
        ]
    
    def get_tags(self, obj):
        """Get tag names from ActionTag relations."""
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        return list(obj.actiontag_set.values_list('tag__name', flat=True))
    
    def get_execution_count(self, obj):
        """Get execution count from Execution model (computed field)."""
        # This will be annotated in the ViewSet queryset
        if hasattr(obj, 'execution_count'):
            return obj.execution_count
        # Fallback: count executions if not annotated
        from executions.models import Execution
        return Execution.objects.filter(action_id=obj.id).count()
