"""
DRF Serializers for catalog app.
Maps Django models to JSON responses.
"""
# Responsabilité : Sérialisation/désérialisation DRF du catalogue (10+ serializers, validations
# croisées plateforme/intégration, règles métier au niveau API) — volume justifié par la richesse
# du modèle Action et les contraintes de validation inter-champs (Story 35.4 AC3).

from __future__ import annotations

from typing import Any
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from catalog import models
from catalog.models import (
    Action, Tag, ActionStatus, ActionItemType, BusinessRulePolicy
)
from reference.models import RefEngine, RefCategory
from integrations.models import Integration, IntegrationTypeCatalogue, IntegrationRole
# Story 62.4: Dynamic inventory column validation via DIP factory
# No circular import: inventory does not import from catalog
from inventory.services import InventoryService, InventoryServiceError as _InventoryServiceError

# Story 31.9: Alias mapping for legacy platform codes → catalogue codes
# Canonical source — also used by business_rule_views.py
_PLATFORM_ALIAS: dict[str, str] = {
    'terraform': 'terraform_cloud',
    'tower': 'aap',
}


VALID_INVENTORY_TYPES = ('servers', 'instances', 'databases')

VALID_INVENTORY_VALUE_COLUMNS: dict[str, tuple[str, ...]] = {
    'servers':   ('name', 'id', 'environment', 'engine_type'),
    'instances': ('name', 'id', 'server_ref', 'db_ref'),
    'databases': ('name', 'id'),
}

# Story 62.4: DIP factory — overridable in tests (same pattern as inventory/views.py Story 33.4)
_catalog_inventory_service_factory = InventoryService


def _get_allowed_inventory_columns(inventory_type: str) -> tuple[str, ...]:
    """
    Story 62.4: Get allowed inventory_value_column values dynamically from
    the active inventory integration config.

    Falls back to VALID_INVENTORY_VALUE_COLUMNS if:
    - No active inventory_db integration is configured (mapper is None)
    - Integration is in flat_table mode (not multi_table)
    - InventoryServiceError is raised by the service

    Args:
        inventory_type: One of 'servers', 'instances', 'databases'

    Returns:
        Tuple of allowed column concept names (id always first when dynamic)
    """
    try:
        service = _catalog_inventory_service_factory()
        mapper = service._get_inventory_mapper()
        if mapper and mapper.is_multi_table:
            entity_config = mapper.get_entity_config(inventory_type)
            if entity_config:
                # Build column list: 'id' first, then remaining concepts from config
                columns = ['id'] + [
                    k for k in entity_config.get('columns', {}).keys() if k != 'id'
                ]
                return tuple(columns)
    except _InventoryServiceError:
        pass  # Fallback below

    # Fallback: use hardcoded list (backward compat — no inventory integration configured)
    return VALID_INVENTORY_VALUE_COLUMNS.get(inventory_type, ('id', 'name'))


def _validate_platform_integration_consistency(
    platform: str | None,
    integration: Integration | None,
    integration_id: int | None = None
) -> None:
    """
    Story 29.4: Validate platform ↔ integration.type consistency (DRY helper).

    Raises:
        serializers.ValidationError: If platform and integration are inconsistent.
    """
    # Skip validation if either field is missing
    if not platform or not integration:
        return

    # Get integration type catalogue entry
    try:
        integration_type_cat = IntegrationTypeCatalogue.objects.get(code=integration.type)
    except IntegrationTypeCatalogue.DoesNotExist:
        # If type not in catalogue, skip validation (backward compatibility)
        return

    # Only validate if integration is a platform (not a service)
    if integration_type_cat.integration_role != IntegrationRole.PLATFORM:
        raise serializers.ValidationError({
            'integration_id': (
                f"Integration '{integration.name}' is a service (type '{integration.type}'), "
                f"but action.platform is set. Use integration for platforms only "
                f"(AAP, GitHub Actions, etc.)."
            )
        })

    # Story 31.9: Normalize platform code for matching (lower, spaces→underscores, alias)
    normalized_platform = platform.lower().replace(' ', '_')
    normalized_platform = _PLATFORM_ALIAS.get(normalized_platform, normalized_platform)

    # Check if normalized platform matches integration.type
    if normalized_platform != integration.type:
        raise serializers.ValidationError({
            'platform': (
                f"Platform '{platform}' is inconsistent with integration type '{integration.type}'. "
                f"Expected platform '{integration_type_cat.name}' for integration '{integration.name}'."
            )
        })


def validate_parameters_schema_inventory(value: Any) -> Any:
    """
    Story 23.5 + 37.4: Validate inventory parameters in parameters_schema.

    If a parameter property has source='inventory':
    - inventory_type must be one of 'servers', 'instances', 'databases'.
    - inventory_value_column (optional) must be an allowed column for the inventory_type.
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
        # Story 37.4 / 62.4 — validate optional inventory_value_column (dynamic from mapper)
        inventory_value_column = prop.get('inventory_value_column')
        if inventory_value_column is not None:
            allowed = _get_allowed_inventory_columns(inventory_type)
            if inventory_value_column not in allowed:
                raise serializers.ValidationError(
                    f"Parameter '{param_name}': inventory_value_column must be one of: "
                    f"{', '.join(allowed)} for inventory_type '{inventory_type}'"
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
    
    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
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


class ActionFieldValidationMixin:
    """
    Story 34.1 (SOLID-BE-11): DRY mixin pour la validation des champs engine/platform/category.

    Contient la version STRICTE de validate_category (None passé tel quel, blank → ValidationError).
    ActionCreateSerializer conserve un override pour accepter blank string → None.
    """

    def validate_engine(self, value: str | None) -> str | None:
        """Validate engine against REF_ENGINES table."""
        if value is None:
            return value
        if not RefEngine.objects.filter(code=value, is_active=1).exists():
            active_engines = list(RefEngine.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid engine '{value}'. Must be one of: {', '.join(active_engines)}"
            )
        return value

    def validate_platform(self, value: str | None) -> str | None:
        """Story 31.9: Validate platform against IntegrationTypeCatalogue (role=platform)."""
        if value is None:
            return value
        normalized = value.lower().replace(' ', '_')
        normalized = _PLATFORM_ALIAS.get(normalized, normalized)
        if not IntegrationTypeCatalogue.objects.filter(
            code=normalized, is_active=True, integration_role=IntegrationRole.PLATFORM
        ).exists():
            active_codes = list(
                IntegrationTypeCatalogue.objects.filter(
                    is_active=True, integration_role=IntegrationRole.PLATFORM
                ).values_list('code', flat=True)
            )
            raise serializers.ValidationError(
                f"Invalid platform '{value}'. Must be one of: {', '.join(active_codes)}"
            )
        return value

    def validate_category(self, value: str | None) -> str | None:
        """Validate category against REF_CATEGORIES table (Story 2.30). Version stricte."""
        if value is None:
            return value
        if not RefCategory.objects.filter(code=value, is_active=1).exists():
            active_categories = list(RefCategory.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Must be one of: {', '.join(active_categories)}"
            )
        return value


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
class ActionSerializer(ActionFieldValidationMixin, serializers.ModelSerializer):
    """
    Read-only serializer for Action model.
    Used for list/detail read operations (GET) — matches ActionResponse/ActionDetail.

    Write operations (create/update) use ActionCreateSerializer and CatalogService.
    Do NOT call .save() on this serializer — use ActionCreateSerializer instead.

    Story 34.3 - SOLID-BE-6: create() and update() overrides raising NotImplementedError
    removed (LSP violation). ModelSerializer's default methods are inherited instead.
    """

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
    # Story 31.8: Notification channels configuration (email, teams, page)
    notification_config = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Configuration des notifications : canaux (email, teams, page) et conditions de déclenchement"
    )
    remediation_rules = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Règles de remédiation automatique en cas d'erreur"
    )
    # Story 28.1: Business rule policies evaluated on step output
    business_rule_policies = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Politiques de règles métier évaluées sur la sortie d'étape (ex. revue si modification Terraform)"
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
    # Story 29.4: integration_id for platform ↔ integration.type consistency validation
    integration_id = serializers.IntegerField(
        source='integration.id', read_only=True, allow_null=True
    )
    # Story 28.4: FK to predefined business rule policy
    business_rule_policy_id = serializers.PrimaryKeyRelatedField(
        queryset=BusinessRulePolicy.objects.all(),
        source='business_rule_policy',
        required=False, allow_null=True,
    )
    business_rule_policy_name = serializers.SerializerMethodField()

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_business_rule_policy_name(self, obj: Action) -> str | None:
        """Story 28.4: Get predefined policy name if FK is set."""
        if obj.business_rule_policy_id:
            policy = obj.business_rule_policy
            return policy.name if policy else None
        return None

    def validate_parameters_schema(self, value: Any) -> Any:
        """Story 23.5 + 37.4: Validate inventory_type and inventory_value_column in parameters_schema."""
        return validate_parameters_schema_inventory(value)

    def validate_notification_config(self, value: Any) -> Any:
        """Story 31.8: Validate notification_config schema."""
        if value is not None:
            from catalog.validators import validate_notification_config
            validate_notification_config(value)
        return value

    def validate_business_rule_policies(self, value: Any) -> Any:
        """Story 28.1: Validate business_rule_policies schema."""
        if value is not None:
            from catalog.validators import validate_business_rule_policies
            validate_business_rule_policies(value)
        return value

    def validate_output_schema_id(self, value: Any) -> Any:
        """Story 63.9: Validate that output_schema_id references an existing OutputSchema."""
        if value is not None:
            from output_schemas.models import OutputSchema  # noqa: PLC0415
            if not OutputSchema.objects.filter(id=value).exists():
                raise serializers.ValidationError(f"OutputSchema id={value} introuvable.")
        return value

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Story 29.4: Validate platform ↔ integration.type consistency when both provided.
        Story 28.4: Validate XOR between business_rule_policy_id and business_rule_policies.
        """
        platform = data.get('platform')
        # Get integration from instance (read-only field, set via model)
        integration = getattr(self.instance, 'integration', None) if self.instance else None

        # Use DRY helper for validation
        _validate_platform_integration_consistency(platform, integration)

        # Story 28.4: XOR validation
        has_policy_fk = data.get('business_rule_policy') is not None
        has_policy_inline = data.get('business_rule_policies') is not None
        if has_policy_fk and has_policy_inline:
            raise serializers.ValidationError(
                'Spécifiez soit business_rule_policy_id soit business_rule_policies, pas les deux.'
            )

        return data

    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'category', 'engine', 'platform',
            'parameters_schema', 'impact_rules', 'default_impact_level',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'documentation_md', 'remediation_rules',
            'execution_steps', 'notification_config', 'workflow_steps',
            # Story 28.1: business_rule_policies
            'business_rule_policies',
            # Story 28.4: FK to predefined business rule policy
            'business_rule_policy_id', 'business_rule_policy_name',
            # Story 13.2, AC3: requires_target field
            'requires_target',
            # Story 29.4: integration_id for platform consistency validation
            'integration_id',
            # Story 64.13: CaC drift tracking (read-only)
            'last_synced_at', 'last_synced_hash',
            # Story 63.9: FK vers OutputSchema déclaré par l'admin
            'output_schema_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'integration_id', 'business_rule_policy_name',
                            'last_synced_at', 'last_synced_hash']
    
    # Story 17.4: Removed redundant get_parameters_schema, get_impact_rules, etc.
    # OracleJSONField handles deserialization automatically - no need for SerializerMethodField

    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {
        'order': {'type': 'integer'}, 'name': {'type': 'string'},
        'referenced_action_id': {'type': 'integer'}, 'action_name': {'type': 'string'},
        'step_id': {'type': 'string'},
        # Story 67.1: multi-target routing (replaces singular on_success_step_id / on_error_step_id)
        'on_success_step_ids': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
        'on_error_step_ids': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
        # Story 67.3: join_policy for convergence steps (optional)
        'join_policy': {'type': 'string', 'enum': ['all_success', 'one_success', 'all_done'], 'nullable': True},
        'retry_enabled': {'type': 'boolean'},
        'retry_max_attempts': {'type': 'integer'}, 'retry_interval_seconds': {'type': 'integer'},
        'retry_backoff_multiplier': {'type': 'number'},
        # Story 57.15: step_type and schedule_config
        # Story 67.1: parallel_group removed from enum
        'step_type': {'type': 'string',
                      'enum': ['platform', 'schedule_execution', 'gate', 'service_call',
                               'evaluation', 'http_request'],
                      'default': 'platform'},
        'schedule_config': {'type': 'object', 'nullable': True},
    }}, 'nullable': True})
    def get_workflow_steps(self, obj: Action) -> list[dict[str, Any]] | None:
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

        # Story 18.3: Batch-fetch action names for platform steps
        # Story 57.13: Include gate, service_call, evaluation, http_request (no referenced_action_id)
        action_ids = {
            step['referenced_action_id']
            for step in execution_steps
            if isinstance(step, dict)
            and step.get('referenced_action_id') is not None
        }
        action_names = {}
        if action_ids:
            action_names = dict(
                Action.objects.filter(id__in=action_ids).values_list('id', 'name')
            )

        # Convert execution_steps to workflow_steps format
        # Story 16.2: Include step_id, branches (on_success/on_error), and retry config
        # Story 57.13: Include all step types (platform, gate, service_call, evaluation, http_request)
        # Align order default with extract_workflow_step_map (idx+1) so workflow_step_parameters
        # keys match between frontend (workflow_steps) and backend validation.
        workflow_steps = []
        for idx, step in enumerate(execution_steps):
            if not isinstance(step, dict):
                continue
            step_type = step.get('step_type') or 'platform'
            ref_id = step.get('referenced_action_id')
            workflow_step = {
                'order': step.get('order', idx + 1),
                'name': step.get('name'),
                'step_type': step_type,
                'referenced_action_id': ref_id,
                'action_name': action_names.get(ref_id) if ref_id else None,
            }

            # Story 57.15: Expose schedule_config for platform
            if 'schedule_config' in step:
                workflow_step['schedule_config'] = step['schedule_config']

            # Story 57.13: Type-specific fields
            # Story 58.4: approver_profile_ids for gate type=approval
            if step_type == 'gate':
                workflow_step['gate_type'] = step.get('gate_type')
                workflow_step['on_timeout'] = step.get('on_timeout')
                workflow_step['context_from'] = step.get('context_from')
                workflow_step['approver_profile_ids'] = step.get('approver_profile_ids')
                workflow_step['timeout'] = step.get('timeout')
            elif step_type == 'service_call':
                workflow_step['integration_type'] = step.get('integration_type')
                workflow_step['operation'] = step.get('operation')
                workflow_step['input_mapping'] = step.get('input_mapping')
                workflow_step['output_mapping'] = step.get('output_mapping')
            elif step_type == 'evaluation':
                workflow_step['policy_id'] = step.get('policy_id')
                workflow_step['input_mapping'] = step.get('input_mapping')
            elif step_type == 'http_request':
                workflow_step['url'] = step.get('url')
                workflow_step['method'] = step.get('method')
                workflow_step['headers'] = step.get('headers')
                workflow_step['request_timeout'] = step.get('request_timeout')
                workflow_step['input_mapping'] = step.get('input_mapping')
                workflow_step['output_mapping'] = step.get('output_mapping')
            if step.get('condition'):
                workflow_step['condition'] = step['condition']

            # Story 16.2 / Story 67.1: Branch and retry fields
            if 'step_id' in step:
                workflow_step['step_id'] = step['step_id']

            # Story 67.1: Expose on_success_step_ids / on_error_step_ids (arrays).
            # Convert singular on_success_step_id if present in DB (retrocompat).
            success_ids = step.get('on_success_step_ids')
            if success_ids is None and 'on_success_step_id' in step:
                v = step['on_success_step_id']
                success_ids = [v] if v else []
            if success_ids is not None or 'on_success_step_ids' in step or 'on_success_step_id' in step:
                workflow_step['on_success_step_ids'] = success_ids if success_ids is not None else []

            error_ids = step.get('on_error_step_ids')
            if error_ids is None and 'on_error_step_id' in step:
                v = step['on_error_step_id']
                error_ids = [v] if v else []
            if error_ids is not None or 'on_error_step_ids' in step or 'on_error_step_id' in step:
                workflow_step['on_error_step_ids'] = error_ids if error_ids is not None else []

            # Story 67.3: join_policy (optional) — all_success | one_success | all_done
            join_policy = step.get('join_policy')
            if join_policy is not None:
                workflow_step['join_policy'] = join_policy

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
    def get_tags(self, obj: Action) -> list[str]:
        """Get tag names from ActionTag relations."""
        # Use prefetched tags if available
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        # Fallback: query if not prefetched
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
    def get_created_by(self, obj: Action) -> int | None:
        """Get created_by user ID."""
        return obj.created_by.id if obj.created_by else None

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert incoming JSON to model fields (for write operations)."""
        # Handle JSON fields - convert dict to JSON string for CLOB storage
        validated_data = super().to_internal_value(data)
        
        # Store JSON fields as-is (will be converted by model setters)
        json_fields = ['parameters_schema', 'impact_rules', 'execution_steps',
                      'notification_config',
                      'remediation_rules', 'business_rule_policies']
        for field in json_fields:
            if field in data:
                validated_data[field] = data[field]  # Keep as dict, model will serialize

        return validated_data  # type: ignore[no-any-return]

class ActionCreateSerializer(ActionFieldValidationMixin, serializers.Serializer):
    """Serializer for POST /admin/actions (ActionCreate model)."""

    name = serializers.CharField(max_length=255, min_length=1)
    description = serializers.CharField(max_length=4000, required=False, allow_null=True)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    # Story 2.30: Category code (optional, validated against REF_CATEGORIES)
    category = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    engine = serializers.CharField(max_length=50, required=False, allow_null=True)
    platform = serializers.CharField(max_length=50, required=False, allow_null=True)
    # Story 29.4: integration_id for platform ↔ integration.type consistency validation
    integration_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_category(self, value: str | None) -> str | None:
        """Validate category against REF_CATEGORIES table (Story 2.30). Blank string → None.

        Override du mixin (version stricte) : accepte blank string et le convertit en None.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if not RefCategory.objects.filter(code=value, is_active=1).exists():
            active_categories = list(RefCategory.objects.active().values_list('code', flat=True))
            raise serializers.ValidationError(
                f"Invalid category '{value}'. Must be one of: {', '.join(active_categories)}"
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
    # Story 31.8: Notification channels configuration
    notification_config = serializers.JSONField(required=False, allow_null=True)

    def validate_notification_config(self, value: Any) -> Any:
        """Story 31.8: Validate notification_config schema."""
        if value is not None:
            from catalog.validators import validate_notification_config
            validate_notification_config(value)
        return value

    def validate_parameters_schema(self, value: Any) -> Any:
        """Story 23.5: Validate inventory_type in parameters_schema."""
        return validate_parameters_schema_inventory(value)

    def validate_name(self, value: str) -> str:
        """Strip whitespace and validate not empty."""
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate engine/platform required for action type.
        Story 29.4: Validate platform ↔ integration.type consistency when both provided.
        """
        item_type = data.get('item_type', ActionItemType.ACTION)
        if item_type == ActionItemType.ACTION:
            if not data.get('engine'):
                raise serializers.ValidationError("engine is required for action type")
            if not data.get('platform'):
                raise serializers.ValidationError("platform is required for action type")

        # Story 29.4: Validate platform ↔ integration.type consistency
        platform = data.get('platform')
        integration_id = data.get('integration_id')

        if platform and integration_id:
            try:
                integration = Integration.objects.get(id=integration_id)
            except Integration.DoesNotExist:
                raise serializers.ValidationError(
                    {'integration_id': 'Integration not found'}
                )

            # Use DRY helper for validation
            _validate_platform_integration_consistency(platform, integration, integration_id)

        return data


class ActionListSerializer(serializers.ModelSerializer):
    """Serializer for GET /admin/actions (simplified list with execution_count)."""

    tags = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    # Story 31.8: notification_config exposed in list view
    notification_config = serializers.JSONField(read_only=True, allow_null=True)

    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'category', 'engine', 'platform',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'execution_count',
            # Story 31.8: notification configuration
            'notification_config',
            # Story 18.1: soft-delete fields for admin list
            'deleted_at', 'deleted_by', 'deletion_reason',
            # Story 64.13: CaC drift tracking (read-only)
            'last_synced_at', 'last_synced_hash',
            # Story 63.9: FK OutputSchema (lecture seule dans la liste)
            'output_schema_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by',
                            'last_synced_at', 'last_synced_hash', 'output_schema_id']

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_tags(self, obj: Action) -> list[str]:
        """Get tag names from ActionTag relations."""
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
    def get_execution_count(self, obj: Action) -> int:
        """Get execution count from Execution model (computed field)."""
        if hasattr(obj, 'execution_count'):
            return obj.execution_count  # type: ignore[no-any-return]
        from executions.models import Execution
        return Execution.objects.filter(action_id=obj.id).count()


class ActionMutexSerializer(serializers.ModelSerializer):
    """
    Story 25.5: Serializer for ActionMutex model.
    Used for GET /api/v1/admin/actions/{id}/mutex/ responses.
    """
    action_id = serializers.IntegerField(source='action.id', read_only=True)
    action_name = serializers.CharField(source='action.name', read_only=True)
    incompatible_with_id = serializers.IntegerField(source='incompatible_with.id', read_only=True)
    incompatible_with_name = serializers.CharField(source='incompatible_with.name', read_only=True)
    
    class Meta:
        model = models.ActionMutex
        fields = [
            'id', 'action_id', 'action_name',
            'incompatible_with_id', 'incompatible_with_name',
            'same_target', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ActionMutexCreateSerializer(serializers.ModelSerializer):
    """
    Story 25.5: Serializer for creating ActionMutex rules.
    Used for POST /api/v1/admin/actions/{id}/mutex/ requests.
    """
    class Meta:
        model = models.ActionMutex
        fields = ['incompatible_with_id', 'same_target', 'description']
    
    incompatible_with_id = serializers.IntegerField(required=True)
    same_target = serializers.BooleanField(required=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500
    )

    def validate_incompatible_with_id(self, value: int) -> int:
        """Validate incompatible_with_id exists and is published."""
        try:
            action = Action.objects.get(id=value)
            if action.status == ActionStatus.DISABLED:
                raise serializers.ValidationError(
                    f"Action {value} est désactivée et ne peut pas être utilisée dans une règle mutex"
                )
            return value
        except Action.DoesNotExist:
            raise serializers.ValidationError(f"Action {value} n'existe pas")

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Cross-field validation:
        - Prevent action_id == incompatible_with_id (self-reference)
        - Check for duplicate rules (idempotence)
        - Validate primary action is not disabled (Code Review Fix HIGH-1)
        """
        # action_id is passed via context from the view
        action_id = self.context.get('action_id')
        incompatible_with_id = data.get('incompatible_with_id')
        
        if action_id == incompatible_with_id:
            raise serializers.ValidationError({
                'incompatible_with_id': "Une action ne peut pas être incompatible avec elle-même"
            })
        
        # Code Review Fix HIGH-1: Validate primary action is not disabled
        try:
            primary_action = Action.objects.get(id=action_id)
            if primary_action.status == ActionStatus.DISABLED:
                raise serializers.ValidationError(
                    f"L'action principale {action_id} est désactivée et ne peut pas avoir de règles mutex"
                )
        except Action.DoesNotExist:
            raise serializers.ValidationError(f"L'action principale {action_id} n'existe pas")
        
        # Check for duplicate rule
        from catalog.models import ActionMutex
        existing = ActionMutex.objects.filter(
            action_id=int(action_id),  # type: ignore[arg-type]
            incompatible_with_id=incompatible_with_id
        ).first()
        
        if existing:
            raise serializers.ValidationError({
                'incompatible_with_id': f"Une règle mutex existe déjà entre ces deux actions (ID: {existing.id})"
            })

        return data


class BusinessRulePolicyListSerializer(serializers.ModelSerializer):
    """Story 28.4: List serializer for BusinessRulePolicy (AC#4)."""
    step_type = serializers.SerializerMethodField()

    class Meta:
        model = BusinessRulePolicy
        fields = ['id', 'name', 'description', 'is_active', 'step_type', 'created_at', 'updated_at']

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_step_type(self, obj: BusinessRulePolicy) -> str | None:
        return obj.step_type


class BusinessRulePolicySerializer(serializers.ModelSerializer):
    """Story 28.4: Detail serializer for BusinessRulePolicy (AC#4)."""
    step_type = serializers.SerializerMethodField()
    policy_json = serializers.JSONField()
    actions_count = serializers.SerializerMethodField()

    class Meta:
        model = BusinessRulePolicy
        fields = [
            'id', 'name', 'description', 'policy_json', 'is_active',
            'step_type', 'actions_count', 'created_at', 'updated_at', 'created_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_step_type(self, obj: BusinessRulePolicy) -> str | None:
        return obj.step_type

    @extend_schema_field(OpenApiTypes.INT)
    def get_actions_count(self, obj: BusinessRulePolicy) -> int:
        return obj.actions.count()

    def validate_policy_json(self, value: Any) -> Any:
        """Validate policy_json using existing validator."""
        if value is not None:
            from catalog.validators import validate_business_rule_policies
            validate_business_rule_policies(value)
        return value
