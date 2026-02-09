"""
DRF Serializers for catalog app.
Maps Django models to JSON responses.
"""

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from catalog.models import (
    Action, Tag, ActionTag,
    ActionStatus, ActionEngine, ActionPlatform, ActionItemType
)
from reference.models import RefEngine, RefPlatform, RefCategory


VALID_INVENTORY_TYPES = ('servers', 'instances', 'databases')


def validate_parameters_schema_inventory(value):
    """
    Story 23.5: Validate inventory_type in parameters_schema properties.

    If a parameter property has source='inventory', inventory_type must be one of
    'servers', 'instances', or 'databases'.
    """
    if not value or not isinstance(value, dict):
        return value

    properties = value.get('properties')
    if not properties or not isinstance(properties, dict):
        return value

    for param_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        source = prop.get('source')
        if source != 'inventory':
            continue
        inventory_type = prop.get('inventory_type')
        if not inventory_type:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type is required when source is 'inventory'"
            )
        if inventory_type not in VALID_INVENTORY_TYPES:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type must be one of: "
                f"{', '.join(VALID_INVENTORY_TYPES)}"
            )

    return value


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


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Action Example',
            value={
                'id': 42,
                'name': 'Oracle Patch Application',
                'description': 'Applique un patch Oracle sur une base de données',
                'item_type': 'action',
                'engine': 'oracle',
                'platform': 'linux',
                'category': 'patching',
                'status': 'active',
                'requires_target': True,
                'parameters_schema': {'type': 'object', 'properties': {'patch_id': {'type': 'string'}}},
                'tags': ['oracle', 'patching'],
            }
        )
    ]
)
class ActionSerializer(serializers.ModelSerializer):
    """Base Action serializer (read/write) matching ActionResponse/ActionDetail."""

    # CLOB/JSON fields - OracleJSONField handles serialization automatically (Story 17.4)
    # Story 22.20 (AC4): Schémas explicites pour JSONField complexes
    parameters_schema = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Schéma JSON des paramètres d'entrée de l'action (format JSON Schema)"
    )
    impact_rules = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Règles d'évaluation d'impact (conditions + niveau d'impact)"
    )
    execution_steps = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Étapes d'exécution pour workflows (array d'objets avec order, referenced_action_id, etc.)"
    )
    change_type_config = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Configuration du type de changement pour l'audit SOC1"
    )
    remediation_rules = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Règles de remédiation automatique en cas d'erreur"
    )
    # Story 5.7: workflow_steps for workflows (converted from execution_steps)
    workflow_steps = serializers.SerializerMethodField()
    
    # Relations
    tags = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    
    # Enums
    status = serializers.ChoiceField(choices=ActionStatus.choices)
    engine = serializers.CharField(max_length=50, allow_null=True, required=False)
    platform = serializers.CharField(max_length=50, allow_null=True, required=False)
    # Story 2.30: Category code (optional, validated against REF_CATEGORIES)
    category = serializers.CharField(max_length=50, allow_null=True, required=False)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    
    def validate_engine(self, value):
        """Validate engine against REF_ENGINES table."""
        if value is None:
            return value
        # Check if engine exists in REF_ENGINES
        if not RefEngine.objects.filter(code=value, is_active=1).exists():
            active_engines = list(RefEngine.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid engine '{value}'. Must be one of: {', '.join(active_engines)}"
            )
        return value
    
    def validate_platform(self, value):
        """Validate platform against REF_PLATFORMS table."""
        if value is None:
            return value
        # Check if platform exists in REF_PLATFORMS
        if not RefPlatform.objects.filter(code=value, is_active=1).exists():
            active_platforms = list(RefPlatform.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid platform '{value}'. Must be one of: {', '.join(active_platforms)}"
            )
        return value

    def validate_category(self, value):
        """Validate category against REF_CATEGORIES table (Story 2.30)."""
        if value is None:
            return value
        if not RefCategory.objects.filter(code=value, is_active=1).exists():
            active_categories = list(RefCategory.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Must be one of: {', '.join(active_categories)}"
            )
        return value

    def validate_parameters_schema(self, value):
        """Story 23.5: Validate inventory_type in parameters_schema."""
        return validate_parameters_schema_inventory(value)

    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'category', 'engine', 'platform',
            'parameters_schema', 'impact_rules', 'default_impact_level',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'documentation_md', 'remediation_rules',
            'execution_steps', 'change_type_config', 'workflow_steps',
            # Story 13.2, AC3: requires_target field
            'requires_target'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']
    
    # Story 17.4: Removed redundant get_parameters_schema, get_impact_rules, etc.
    # OracleJSONField handles deserialization automatically - no need for SerializerMethodField

    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {
        'order': {'type': 'integer'}, 'name': {'type': 'string'},
        'referenced_action_id': {'type': 'integer'}, 'action_name': {'type': 'string'},
        'step_id': {'type': 'string'}, 'on_success_step_id': {'type': 'string'},
        'on_error_step_id': {'type': 'string'}, 'retry_enabled': {'type': 'boolean'},
        'retry_max_attempts': {'type': 'integer'}, 'retry_interval_seconds': {'type': 'integer'},
        'retry_backoff_multiplier': {'type': 'number'},
    }}, 'nullable': True})
    def get_workflow_steps(self, obj):
        """
        Convert execution_steps to workflow_steps format for workflows.
        Story 16.2: Include branch conditional and retry fields.
        Story 18.3: Include action_name resolved from referenced_action.
        """
        if obj.item_type != ActionItemType.WORKFLOW:
            return None

        execution_steps = obj.execution_steps
        if not execution_steps:
            return None

        # Story 18.3: Batch-fetch action names to avoid N+1 queries
        action_ids = {
            step['referenced_action_id']
            for step in execution_steps
            if isinstance(step, dict) and 'referenced_action_id' in step
        }
        action_names = {}
        if action_ids:
            action_names = dict(
                Action.objects.filter(id__in=action_ids).values_list('id', 'name')
            )

        # Convert execution_steps to workflow_steps format
        # Story 16.2: Include step_id, branches (on_success/on_error), and retry config
        workflow_steps = []
        for step in execution_steps:
            if isinstance(step, dict) and 'referenced_action_id' in step:
                ref_id = step['referenced_action_id']
                workflow_step = {
                    'order': step.get('order', 0),
                    'name': step.get('name'),
                    'referenced_action_id': ref_id,
                    'action_name': action_names.get(ref_id),
                }

                # Story 16.2: Add optional branch and retry fields
                if 'step_id' in step:
                    workflow_step['step_id'] = step['step_id']
                if 'on_success_step_id' in step:
                    workflow_step['on_success_step_id'] = step['on_success_step_id']
                if 'on_error_step_id' in step:
                    workflow_step['on_error_step_id'] = step['on_error_step_id']
                if 'retry_enabled' in step:
                    workflow_step['retry_enabled'] = step['retry_enabled']
                if 'retry_max_attempts' in step:
                    workflow_step['retry_max_attempts'] = step['retry_max_attempts']
                if 'retry_interval_seconds' in step:
                    workflow_step['retry_interval_seconds'] = step['retry_interval_seconds']
                if 'retry_backoff_multiplier' in step:
                    workflow_step['retry_backoff_multiplier'] = step['retry_backoff_multiplier']

                workflow_steps.append(workflow_step)

        # Sort by order to ensure consistent ordering
        workflow_steps.sort(key=lambda x: x['order'])

        return workflow_steps if workflow_steps else None
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}, 'example': ['oracle', 'patching']})
    def get_tags(self, obj):
        """Get tag names from ActionTag relations."""
        # Use prefetched tags if available
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        # Fallback: query if not prefetched
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
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
    # Story 2.30: Category code (optional, validated against REF_CATEGORIES)
    category = serializers.CharField(max_length=50, required=False, allow_null=True)
    engine = serializers.CharField(max_length=50, required=False, allow_null=True)
    platform = serializers.CharField(max_length=50, required=False, allow_null=True)

    def validate_category(self, value):
        """Validate category against REF_CATEGORIES table (Story 2.30)."""
        if value is None:
            return value
        if not RefCategory.objects.filter(code=value, is_active=1).exists():
            active_categories = list(RefCategory.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Must be one of: {', '.join(active_categories)}"
            )
        return value

    def validate_engine(self, value):
        """Validate engine against REF_ENGINES table."""
        if value is None:
            return value
        # Check if engine exists in REF_ENGINES
        if not RefEngine.objects.filter(code=value, is_active=1).exists():
            active_engines = list(RefEngine.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid engine '{value}'. Must be one of: {', '.join(active_engines)}"
            )
        return value
    
    def validate_platform(self, value):
        """Validate platform against REF_PLATFORMS table."""
        if value is None:
            return value
        # Check if platform exists in REF_PLATFORMS
        if not RefPlatform.objects.filter(code=value, is_active=1).exists():
            active_platforms = list(RefPlatform.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid platform '{value}'. Must be one of: {', '.join(active_platforms)}"
            )
        return value
    parameters_schema = serializers.DictField(required=False, allow_null=True)
    impact_rules = serializers.DictField(required=False, allow_null=True)
    default_impact_level = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'critical'],
        required=False,
        allow_null=True
    )
    documentation_md = serializers.CharField(max_length=100_000, required=False, allow_null=True)

    def validate_parameters_schema(self, value):
        """Story 23.5: Validate inventory_type in parameters_schema."""
        return validate_parameters_schema_inventory(value)

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
            'id', 'name', 'description', 'item_type', 'category', 'engine', 'platform',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'execution_count',
            # Story 18.1: soft-delete fields for admin list
            'deleted_at', 'deleted_by', 'deletion_reason',
        ]

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_tags(self, obj):
        """Get tag names from ActionTag relations."""
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
    def get_execution_count(self, obj):
        """Get execution count from Execution model (computed field)."""
        if hasattr(obj, 'execution_count'):
            return obj.execution_count
        from executions.models import Execution
        return Execution.objects.filter(action_id=obj.id).count()
