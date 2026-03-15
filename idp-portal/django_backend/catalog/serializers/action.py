"""Action serializers and mixins."""
from __future__ import annotations

from typing import Any

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from catalog.models import Action, Tag, ActionStatus, ActionItemType, BusinessRulePolicy
from reference.models import RefEngine, RefCategory
from integrations.models import Integration
from executions.utils import extract_workflow_referenced_action_ids

from catalog.serializers.validators import (
    validate_parameters_schema_inventory,
)
from platforms.registry import platform_registry


def _validate_action_config_schema(platform_code: str, action_config: dict | None) -> None:
    """Valide action_config contre action_config_schema de la plateforme (AC3 Story 82.8).

    Si le schéma est vide ({}) → no-op (aucune contrainte).
    Si le schéma est non vide → validation jsonschema.

    AC5 Story 83-13: normalise le code avant lookup (platform_code peut être 'AAP', 'Azure DevOps', etc.)
    Note Story 83-14: le flux 'Terraform' → lower+replace → 'terraform' → resolve_alias → 'terraform_cloud'
    dépend activement de l'alias 'terraform' défini dans platforms/registry.py.
    """
    if not platform_code:
        return
    try:
        normalized = platform_code.lower().replace(' ', '_')
        resolved = platform_registry.resolve_alias(normalized)
        defn = platform_registry.get(resolved)
    except Exception:
        return  # Plateforme inconnue → laisse les autres validateurs gérer

    schema = defn.action_config_schema
    if not schema:
        return  # Schéma vide → pas de validation

    import jsonschema  # noqa: PLC0415
    try:
        jsonschema.validate(instance=action_config or {}, schema=schema)
    except jsonschema.ValidationError as e:
        raise serializers.ValidationError({'action_config': str(e.message)})
    except jsonschema.SchemaError as e:
        raise serializers.ValidationError({'action_config': f'Invalid platform schema: {e.message}'})


# Step type → fields to copy from config (Audit #5 — 5c)
# Story 63.12: platform steps support input_mapping/output_mapping
_STEP_TYPE_FIELDS: dict[str, tuple[str, ...]] = {
    'gate': ('gate_type', 'on_timeout', 'context_from', 'approver_profile_ids', 'timeout'),
    'platform': ('input_mapping', 'output_mapping'),
    'service_call': ('integration_type', 'operation', 'input_mapping', 'output_mapping'),
    'evaluation': ('policy_id', 'input_mapping'),
    'http_request': ('url', 'method', 'headers', 'request_timeout', 'input_mapping', 'output_mapping'),
}


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


class WorkflowEnrichmentMixin:
    """
    Story 69.1: Mixin exposing `technologies` and `included_actions` derived fields.
    """
    _included_actions_fields: tuple[str, ...] = ('id', 'name', 'engine', 'parameters_schema')
    _cache_db_fields: tuple[str, ...] = ('id', 'name', 'engine', 'parameters_schema')

    def _get_referenced_actions_cache(self, obj: Action) -> tuple[list[int], dict[int, dict]]:
        cache_attr = f'_ref_actions_{obj.id}'
        if not hasattr(self, cache_attr):
            if obj.item_type != 'workflow' or not obj.execution_steps:
                setattr(self, cache_attr, ([], {}))
            else:
                action_ids = extract_workflow_referenced_action_ids(obj)
                if action_ids:
                    actions_map = {
                        a['id']: a
                        for a in Action.objects.filter(id__in=set(action_ids)).values(
                            *self._cache_db_fields
                        )
                    }
                else:
                    actions_map = {}
                setattr(self, cache_attr, (action_ids, actions_map))
        result: tuple[list[int], dict[int, dict]] = getattr(self, cache_attr)
        return result

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}, 'example': ['oracle', 'sqlserver']})
    def get_technologies(self, obj: Action) -> list[str]:
        if obj.item_type != 'workflow' or not obj.execution_steps:
            return [obj.engine] if obj.engine else []
        action_ids, actions_map = self._get_referenced_actions_cache(obj)
        if not action_ids:
            return [obj.engine] if obj.engine else []
        seen = set()
        engines = []
        for aid in action_ids:
            a = actions_map.get(aid)
            if a and a['engine'] and a['engine'] not in seen:
                seen.add(a['engine'])
                engines.append(a['engine'])
        return engines

    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {
        'id': {'type': 'integer'}, 'name': {'type': 'string'},
        'engine': {'type': 'string'}, 'parameters_schema': {'type': 'object', 'nullable': True},
    }}})
    def get_included_actions(self, obj: Action) -> list[dict]:
        if obj.item_type != 'workflow' or not obj.execution_steps:
            return []
        action_ids, actions_map = self._get_referenced_actions_cache(obj)
        if not action_ids:
            return []
        seen = set()
        result = []
        fields = self._included_actions_fields
        for aid in action_ids:
            if aid not in seen and aid in actions_map:
                seen.add(aid)
                result.append({f: actions_map[aid][f] for f in fields})
        return result


class ActionFieldValidationMixin:
    """
    Story 34.1 (SOLID-BE-11): DRY mixin pour la validation des champs engine/platform/category.
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
class ActionSerializer(WorkflowEnrichmentMixin, ActionFieldValidationMixin, serializers.ModelSerializer):
    """
    Read-only serializer for Action model.
    Used for list/detail read operations (GET) — matches ActionResponse/ActionDetail.
    """

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
    notification_config = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Configuration des notifications : canaux (email, teams, page) et conditions de déclenchement"
    )
    remediation_rules = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Règles de remédiation automatique en cas d'erreur"
    )
    business_rule_policies = serializers.JSONField(
        required=False, allow_null=True,
        help_text="Politiques de règles métier évaluées sur la sortie d'étape"
    )
    technologies = serializers.SerializerMethodField()
    included_actions = serializers.SerializerMethodField()
    workflow_steps = serializers.SerializerMethodField()

    tags = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    status = serializers.ChoiceField(choices=ActionStatus.choices)
    engine = serializers.CharField(max_length=50, allow_null=True, required=False)
    platform = serializers.CharField(max_length=50, allow_null=True, required=False)
    category = serializers.CharField(max_length=50, allow_null=True, required=False)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    integration_id = serializers.IntegerField(read_only=True, allow_null=True)
    business_rule_policy_id = serializers.PrimaryKeyRelatedField(
        queryset=BusinessRulePolicy.objects.all(),
        source='business_rule_policy',
        required=False, allow_null=True,
    )
    business_rule_policy_name = serializers.SerializerMethodField()

    @extend_schema_field({'type': 'string', 'nullable': True})
    def get_business_rule_policy_name(self, obj: Action) -> str | None:
        if obj.business_rule_policy_id:
            policy = obj.business_rule_policy
            return policy.name if policy else None
        return None

    def validate_parameters_schema(self, value: Any) -> Any:
        return validate_parameters_schema_inventory(value)

    def validate_notification_config(self, value: Any) -> Any:
        if value is not None:
            from catalog.validators import validate_notification_config
            validate_notification_config(value)
        return value

    def validate_business_rule_policies(self, value: Any) -> Any:
        if value is not None:
            from catalog.validators import validate_business_rule_policies
            validate_business_rule_policies(value)
        return value

    def validate_output_schema_id(self, value: Any) -> Any:
        if value is not None:
            from output_schemas.models import OutputSchema  # noqa: PLC0415
            if not OutputSchema.objects.filter(id=value).exists():
                raise serializers.ValidationError(f"OutputSchema id={value} introuvable.")
        return value

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        platform = data.get('platform')

        # Story 82.8, AC3: validate action_config against platform schema.
        # NOTE: action_config field does not yet exist on the Action model — ne valider que si
        # action_config est explicitement fourni (pas de validation implicite sur None).
        action_config = data.get('action_config') or (
            getattr(self.instance, 'action_config', None) if self.instance else None
        )
        if platform and action_config is not None:
            _validate_action_config_schema(platform, action_config)

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
            'technologies', 'included_actions',
            'business_rule_policies',
            'business_rule_policy_id', 'business_rule_policy_name',
            'requires_target',
            'integration_id',
            'last_synced_at', 'last_synced_hash',
            'output_schema_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'integration_id', 'business_rule_policy_name',
                            'last_synced_at', 'last_synced_hash']

    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {
        'order': {'type': 'integer'}, 'name': {'type': 'string'},
        'referenced_action_id': {'type': 'integer'}, 'action_name': {'type': 'string'},
        'step_id': {'type': 'string'},
        'on_success_step_ids': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
        'on_error_step_ids': {'type': 'array', 'items': {'type': 'string'}, 'nullable': True},
        'join_policy': {'type': 'string', 'enum': ['all_success', 'one_success', 'all_done', 'all_failed', 'one_failed'], 'nullable': True},
        'retry_enabled': {'type': 'boolean'},
        'retry_max_attempts': {'type': 'integer'}, 'retry_interval_seconds': {'type': 'integer'},
        'retry_backoff_multiplier': {'type': 'number'},
        'step_type': {'type': 'string',
                      'enum': ['platform', 'schedule_execution', 'gate', 'service_call',
                               'evaluation', 'http_request'],
                      'default': 'platform'},
        'schedule_config': {'type': 'object', 'nullable': True},
    }}, 'nullable': True})
    def get_workflow_steps(self, obj: Action) -> list[dict[str, Any]] | None:
        if obj.item_type != ActionItemType.WORKFLOW:
            return None
        execution_steps = obj.execution_steps
        if not execution_steps:
            return None
        _, actions_map = self._get_referenced_actions_cache(obj)
        action_names = {aid: a['name'] for aid, a in actions_map.items()}

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
            if 'schedule_config' in step:
                workflow_step['schedule_config'] = step['schedule_config']
            for field in _STEP_TYPE_FIELDS.get(step_type, ()):
                workflow_step[field] = step.get(field)
            if step.get('condition'):
                workflow_step['condition'] = step['condition']
            if 'step_id' in step:
                workflow_step['step_id'] = step['step_id']
            success_ids = step.get('on_success_step_ids')
            if success_ids is not None or 'on_success_step_ids' in step:
                workflow_step['on_success_step_ids'] = success_ids if success_ids is not None else []
            error_ids = step.get('on_error_step_ids')
            if error_ids is not None or 'on_error_step_ids' in step:
                workflow_step['on_error_step_ids'] = error_ids if error_ids is not None else []
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
        workflow_steps.sort(key=lambda x: x['order'])
        return workflow_steps if workflow_steps else None

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}, 'example': ['oracle', 'patching']})
    def get_tags(self, obj: Action) -> list[str]:
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
    def get_created_by(self, obj: Action) -> int | None:
        return obj.created_by.id if obj.created_by else None

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().to_internal_value(data)
        json_fields = ['parameters_schema', 'impact_rules', 'execution_steps',
                      'notification_config', 'remediation_rules', 'business_rule_policies']
        for field in json_fields:
            if field in data:
                validated_data[field] = data[field]
        return validated_data  # type: ignore[no-any-return]


class ActionCreateSerializer(ActionFieldValidationMixin, serializers.Serializer):
    """Serializer for POST /admin/actions (ActionCreate model)."""

    name = serializers.CharField(max_length=255, min_length=1)
    description = serializers.CharField(max_length=4000, required=False, allow_null=True)
    item_type = serializers.ChoiceField(choices=ActionItemType.choices, default=ActionItemType.ACTION)
    category = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    engine = serializers.CharField(max_length=50, required=False, allow_null=True)
    # Story 83-13 AC2: platform n'est plus accepté dans les payloads externes — dérivé automatiquement
    integration_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_category(self, value: str | None) -> str | None:
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
    notification_config = serializers.JSONField(required=False, allow_null=True)

    def validate_notification_config(self, value: Any) -> Any:
        if value is not None:
            from catalog.validators import validate_notification_config
            validate_notification_config(value)
        return value

    def validate_parameters_schema(self, value: Any) -> Any:
        return validate_parameters_schema_inventory(value)

    def validate_name(self, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError("name cannot be empty or whitespace only")
        return stripped

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        is_update = self.context.get('is_update', False)
        instance = self.context.get('instance')

        # Resolve item_type: from request, or from instance (for partial update), or default
        if 'item_type' in data:
            item_type = data['item_type']
        elif is_update and instance is not None:
            item_type = getattr(instance, 'item_type', ActionItemType.ACTION)
        else:
            item_type = ActionItemType.ACTION

        # Story 83-13 AC2/AC3: Dériver platform automatiquement depuis integration_id — jamais accepté du client
        # Note: Action.platform est NOT NULL en BD — utiliser '' quand la plateforme ne peut être dérivée.
        integration_id = data.get('integration_id')
        if is_update and instance is not None and 'integration_id' not in data:
            # PATCH sans changement d'integration_id : dériver depuis l'integration existante
            instance_integration = getattr(instance, 'integration', None)
            if instance_integration:
                try:
                    defn = platform_registry.get(instance_integration.type)
                    data['platform'] = defn.action_platform_code
                except Exception:
                    data['platform'] = getattr(instance, 'platform', None) or ''
            else:
                data['platform'] = ''
        elif integration_id:
            try:
                integration = Integration.objects.get(id=integration_id)
            except Integration.DoesNotExist:
                raise serializers.ValidationError(
                    {'integration_id': 'Integration not found'}
                )
            try:
                defn = platform_registry.get(integration.type)
                data['platform'] = defn.action_platform_code
            except Exception:
                data['platform'] = ''
        else:
            data['platform'] = ''

        if item_type == ActionItemType.ACTION:
            # Effective values: from request data, or existing instance (for partial update)
            if is_update and instance is not None:
                effective_engine = data.get('engine') if 'engine' in data else getattr(instance, 'engine', None)
            else:
                effective_engine = data.get('engine')
            effective_platform = data.get('platform')

            if not effective_engine:
                raise serializers.ValidationError("engine is required for action type")
            if not effective_platform:
                raise serializers.ValidationError("platform is required for action type")

        # Story 82.8, AC3: validate action_config against platform schema.
        # Story 83-13 AC5: platform_code est maintenant le code canonique (ex: 'AAP') — la normalisation
        # dans _validate_action_config_schema sert de garde-fou défensif.
        # NOTE: action_config field does not yet exist on the Action model — ne valider que si
        # action_config est explicitement fourni dans le payload (pas de validation implicite sur None).
        platform = data.get('platform')
        action_config = data.get('action_config') or (
            getattr(self.context.get('instance'), 'action_config', None)
        )
        if platform and action_config is not None:
            _validate_action_config_schema(platform, action_config)

        return data


class ActionListSerializer(WorkflowEnrichmentMixin, serializers.ModelSerializer):
    """Serializer for GET /admin/actions (simplified list with execution_count)."""

    _included_actions_fields: tuple[str, ...] = ('id', 'name', 'engine')
    _cache_db_fields: tuple[str, ...] = ('id', 'name', 'engine')

    tags = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    technologies = serializers.SerializerMethodField()
    included_actions = serializers.SerializerMethodField()
    notification_config = serializers.JSONField(read_only=True, allow_null=True)

    class Meta:
        model = Action
        fields = [
            'id', 'name', 'description', 'item_type', 'category', 'engine', 'platform',
            'status', 'created_by', 'created_at', 'updated_at',
            'tags', 'execution_count',
            'technologies', 'included_actions',
            'notification_config',
            'deleted_at', 'deleted_by', 'deletion_reason',
            'last_synced_at', 'last_synced_hash',
            'output_schema_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by',
                            'last_synced_at', 'last_synced_hash', 'output_schema_id']

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_tags(self, obj: Action) -> list[str]:
        if hasattr(obj, 'actiontag_set'):
            return [at.tag.name for at in obj.actiontag_set.all()]
        return list(obj.actiontag_set.values_list('tag__name', flat=True))

    @extend_schema_field(OpenApiTypes.INT)
    def get_execution_count(self, obj: Action) -> int:
        if hasattr(obj, 'execution_count'):
            return obj.execution_count  # type: ignore[no-any-return]
        from executions.models import Execution
        return Execution.objects.filter(action_id=obj.id).count()
