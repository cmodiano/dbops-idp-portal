"""
Validators for catalog app.
Story 25.2: gate_conditions validation for execution steps.
Story 25.4: change_type_config validation (allowed, requires_maintenance_window, requires_approval).
Story 28.1: business_rule_policies validation for step output policies.
"""

import structlog
import re

from rest_framework.exceptions import ValidationError

logger = structlog.get_logger(__name__)


VALID_GATE_CONDITION_TYPES = (
    'maintenance_window',
    'time_window',
    'approval_granted',
    'target_state',
)

VALID_ON_TIMEOUT_VALUES = ('FAIL', 'SKIP')


def validate_gate_conditions(gate_conditions: list) -> None:
    """
    Validate gate_conditions from an execution step definition.

    Rules:
    1. gate_conditions must be a list
    2. Each condition must have a 'type' field with a valid value
    3. If timeout_hours is present, it must be a number > 0
    4. If on_timeout is present, it must be 'FAIL' or 'SKIP'

    Args:
        gate_conditions: List of gate condition dicts

    Raises:
        ValidationError: If any validation rule fails
    """
    if not isinstance(gate_conditions, list):
        raise ValidationError(
            "gate_conditions must be a list"
        )

    errors = []
    for idx, condition in enumerate(gate_conditions):
        if not isinstance(condition, dict):
            errors.append(
                f"Gate condition at index {idx}: must be an object"
            )
            continue

        # Validate required 'type' field
        condition_type = condition.get('type')
        if not condition_type:
            errors.append(
                f"Gate condition at index {idx}: 'type' field is required"
            )
        elif not isinstance(condition_type, str):
            errors.append(
                f"Gate condition at index {idx}: 'type' must be a string"
            )
        elif condition_type not in VALID_GATE_CONDITION_TYPES:
            errors.append(
                f"Gate condition at index {idx}: 'type' must be one of: "
                f"{', '.join(VALID_GATE_CONDITION_TYPES)}"
            )

        # Validate optional 'timeout_hours'
        if 'timeout_hours' in condition:
            timeout = condition['timeout_hours']
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                errors.append(
                    f"Gate condition at index {idx}: 'timeout_hours' must be a positive number"
                )

        # Validate optional 'on_timeout'
        if 'on_timeout' in condition:
            on_timeout = condition['on_timeout']
            if on_timeout not in VALID_ON_TIMEOUT_VALUES:
                errors.append(
                    f"Gate condition at index {idx}: 'on_timeout' must be one of: "
                    f"{', '.join(VALID_ON_TIMEOUT_VALUES)}"
                )

    if errors:
        raise ValidationError(errors)


def validate_change_type_config(change_type_config: dict | None) -> None:
    """
    Validate change_type_config per-environment structure (Story 25.4).

    Per-env keys: change_type, template_id, required, change_model_code,
    requires_maintenance_window, requires_approval, allowed.

    Rules:
    - Each env value must be a dict
    - allowed: must be bool if present (default: true if absent)
    - requires_maintenance_window, requires_approval: must be bool if present
    - If required=true for an env, change_model_code must be non-empty and alphanumeric (max 50)

    Raises:
        ValidationError: If any validation rule fails
    """
    if change_type_config is None:
        return
    if not isinstance(change_type_config, dict):
        # Defensive: prevent persisting invalid JSON that would later crash execution validation.
        raise ValidationError(
            "change_type_config doit être un objet JSON (mapping d'environnements vers configuration)"
        )

    for env_key, env_value in change_type_config.items():
        # Skip non-dict values (legacy flat format e.g. {'type': 'standard'})
        if not isinstance(env_value, dict):
            continue

        # required: bool if present
        if 'required' in env_value:
            val = env_value['required']
            if not isinstance(val, bool):
                raise ValidationError(
                    f"change_type_config.{env_key}.required: doit être un booléen (true/false)"
                )

        # allowed: bool if present
        if 'allowed' in env_value:
            val = env_value['allowed']
            if not isinstance(val, bool):
                raise ValidationError(
                    f"change_type_config.{env_key}.allowed: doit être un booléen (true/false)"
                )

        # change_type, template_id: strings if present (Story 25.4 AC2)
        for field, max_len in (('change_type', 50), ('template_id', 100)):
            if field in env_value:
                val = env_value[field]
                if val is None:
                    continue
                if not isinstance(val, str):
                    raise ValidationError(
                        f"change_type_config.{env_key}.{field}: doit être une chaîne"
                    )
                if len(val.strip()) > max_len:
                    raise ValidationError(
                        f"change_type_config.{env_key}.{field}: max {max_len} caractères"
                    )

        # requires_maintenance_window, requires_approval: bool if present
        for field in ('requires_maintenance_window', 'requires_approval'):
            if field in env_value:
                val = env_value[field]
                if not isinstance(val, bool):
                    raise ValidationError(
                        f"change_type_config.{env_key}.{field}: doit être un booléen (true/false)"
                    )

        # required=true → change_model_code required, alphanumeric, max 50
        if env_value.get('required') is True:
            code = env_value.get('change_model_code')
            if not code or not str(code).strip():
                raise ValidationError(
                    f"change_type_config.{env_key}: change_model_code obligatoire quand required=true"
                )
            code_str = str(code).strip()
            if not re.fullmatch(r'[A-Za-z0-9]+', code_str):
                raise ValidationError(
                    f"change_type_config.{env_key}: change_model_code doit être alphanumérique"
                )
            if len(code_str) > 50:
                raise ValidationError(
                    f"change_type_config.{env_key}: change_model_code max 50 caractères"
                )


def validate_gate_config(gate_config: dict | None) -> None:
    """
    Validate gate_config JSON structure (Story 31.6).

    Structure: {"servicenow_change": {"integration_id": <int>}}

    Rules:
    - gate_config must be a dict (or None)
    - servicenow_change.integration_id must reference an existing integration of type 'servicenow'

    Raises:
        ValidationError: If validation fails
    """
    if gate_config is None:
        return
    if not isinstance(gate_config, dict):
        raise ValidationError("gate_config doit être un objet JSON")

    sn_change = gate_config.get('servicenow_change')
    if sn_change is None:
        return
    if not isinstance(sn_change, dict):
        raise ValidationError("gate_config.servicenow_change doit être un objet")

    integration_id = sn_change.get('integration_id')
    if integration_id is None:
        return

    if not isinstance(integration_id, int):
        raise ValidationError("gate_config.servicenow_change.integration_id doit être un entier")

    from integrations.models import Integration
    try:
        integration = Integration.objects.get(id=integration_id)
    except Integration.DoesNotExist:
        raise ValidationError(
            f"gate_config.servicenow_change.integration_id: intégration {integration_id} introuvable"
        )

    if integration.type != 'servicenow':
        raise ValidationError(
            f"gate_config.servicenow_change.integration_id: l'intégration {integration_id} "
            f"est de type '{integration.type}', attendu 'servicenow'"
        )


# Story 31.8: Valid notification channel types and conditions
# Story 57.8: on_approval_required — when a workflow step is waiting for approval
VALID_CHANNEL_TYPES = ('email', 'teams', 'page_dba')
VALID_CONDITIONS = ('on_failure', 'on_success', 'always', 'on_approval_required')


def validate_notification_config(notification_config: dict | None) -> None:
    """
    Validate notification_config JSON structure (Story 31.8).

    Structure:
        {
            "channels": [{"type": "email"|"teams"|"page_dba", "enabled": bool, "conditions": [...], ...}],
            "page_individual_enabled": bool
        }

    Raises:
        ValidationError: If validation fails
    """
    if notification_config is None:
        return
    if not isinstance(notification_config, dict):
        raise ValidationError("notification_config doit être un objet JSON")

    channels = notification_config.get("channels", [])
    if not isinstance(channels, list):
        raise ValidationError("notification_config.channels doit être une liste")

    for i, channel in enumerate(channels):
        if not isinstance(channel, dict):
            raise ValidationError(f"notification_config.channels[{i}] doit être un objet")

        ch_type = channel.get("type")
        if ch_type not in VALID_CHANNEL_TYPES:
            raise ValidationError(
                f"notification_config.channels[{i}].type invalide : '{ch_type}'. "
                f"Valeurs acceptées : {', '.join(VALID_CHANNEL_TYPES)}"
            )

        if "enabled" in channel and not isinstance(channel["enabled"], bool):
            raise ValidationError(
                f"notification_config.channels[{i}].enabled doit être un booléen"
            )

        conditions = channel.get("conditions", [])
        if not isinstance(conditions, list):
            raise ValidationError(
                f"notification_config.channels[{i}].conditions doit être une liste"
            )
        for cond in conditions:
            if cond not in VALID_CONDITIONS:
                raise ValidationError(
                    f"notification_config.channels[{i}].conditions contient "
                    f"une valeur invalide : '{cond}'. "
                    f"Valeurs acceptées : {', '.join(VALID_CONDITIONS)}"
                )

        # Validate webhook_url_ref for Teams: direct URLs must use HTTPS (SSRF mitigation)
        if ch_type == "teams":
            webhook_url_ref = channel.get("webhook_url_ref", "")
            if webhook_url_ref and not webhook_url_ref.startswith("vault:"):
                if not webhook_url_ref.startswith("https://"):
                    raise ValidationError(
                        f"notification_config.channels[{i}].webhook_url_ref : "
                        f"les URLs directes doivent commencer par 'https://'. "
                        f"Pour les secrets, utilisez le format 'vault:secret/...'"
                    )

    page_individual = notification_config.get("page_individual_enabled")
    if page_individual is not None and not isinstance(page_individual, bool):
        raise ValidationError("notification_config.page_individual_enabled doit être un booléen")


# Story 28.1: Valid policy types for business_rule_policies
VALID_POLICY_TYPES = ('review_if_modified',)


# Story 57.15: Valid schedule sources and offset pattern
VALID_SCHEDULE_SOURCES = ('parameter', 'fixed_offset', 'recurring')
VALID_OFFSET_PATTERN = re.compile(r'^\+\d+[dhwm]$')


def validate_schedule_config(schedule_config: dict) -> None:
    """
    Valide la configuration schedule_config d'un step schedule_execution.
    Story 57.15 AC #9.
    """
    if not isinstance(schedule_config, dict):
        raise ValidationError("schedule_config doit être un objet")

    source = schedule_config.get('schedule_source')
    if source not in VALID_SCHEDULE_SOURCES:
        raise ValidationError(
            f"schedule_source invalide: {source!r}. Valeurs attendues: {VALID_SCHEDULE_SOURCES}"
        )

    if source == 'parameter':
        if not schedule_config.get('schedule_parameter_name'):
            raise ValidationError(
                "schedule_parameter_name requis quand schedule_source='parameter'"
            )
    elif source == 'fixed_offset':
        offset = schedule_config.get('fixed_offset')
        if not offset or not VALID_OFFSET_PATTERN.match(offset):
            raise ValidationError(
                f"fixed_offset invalide: {offset!r}. Format attendu: +Nd, +Nh, +Nw, +Nm"
            )
    elif source == 'recurring':
        pattern = schedule_config.get('recurring_pattern', {})
        if not pattern.get('pattern_type'):
            raise ValidationError(
                "recurring_pattern.pattern_type requis quand schedule_source='recurring'"
            )


def validate_business_rule_policies(value: dict | None) -> None:
    """
    Validate business_rule_policies JSON schema (Story 28.1).

    Structure: {"on_step_output": [{when: {step_type, output_key?}, policy: {type, ...}}]}

    Args:
        value: business_rule_policies dict or None

    Raises:
        ValidationError: if schema is invalid
    """
    if value is None or value == {}:
        return

    if not isinstance(value, dict):
        raise ValidationError("business_rule_policies must be a JSON object")

    if "on_step_output" not in value:
        raise ValidationError("business_rule_policies must contain 'on_step_output' key")

    on_step_output = value["on_step_output"]
    if not isinstance(on_step_output, list):
        raise ValidationError("on_step_output must be an array")

    for idx, rule in enumerate(on_step_output):
        if not isinstance(rule, dict):
            raise ValidationError(f"on_step_output[{idx}] must be an object")

        # Validate 'when'
        if "when" not in rule:
            raise ValidationError(f"on_step_output[{idx}] must contain 'when' key")

        when = rule["when"]
        if not isinstance(when, dict):
            raise ValidationError(f"on_step_output[{idx}].when must be an object")

        if "step_type" not in when:
            raise ValidationError(f"on_step_output[{idx}].when must contain 'step_type'")

        if not isinstance(when["step_type"], str) or not when["step_type"].strip():
            raise ValidationError(
                f"on_step_output[{idx}].when.step_type must be a non-empty string"
            )

        if "output_key" in when:
            if not isinstance(when["output_key"], str):
                raise ValidationError(
                    f"on_step_output[{idx}].when.output_key must be a string"
                )

        # Validate 'policy'
        if "policy" not in rule:
            raise ValidationError(f"on_step_output[{idx}] must contain 'policy' key")

        policy = rule["policy"]
        if not isinstance(policy, dict):
            raise ValidationError(f"on_step_output[{idx}].policy must be an object")

        if "type" not in policy:
            raise ValidationError(f"on_step_output[{idx}].policy must contain 'type'")

        policy_type = policy["type"]
        if policy_type not in VALID_POLICY_TYPES:
            raise ValidationError(
                f"on_step_output[{idx}].policy.type must be one of: "
                f"{', '.join(VALID_POLICY_TYPES)} (got: {policy_type})"
            )

        # Validate policy-specific fields
        if policy_type == "review_if_modified":
            _validate_review_if_modified_policy(policy, idx)

    logger.debug(
        "business_rule_policies validation passed",
        extra={"num_rules": len(on_step_output)},
    )


def _validate_review_if_modified_policy(policy: dict, idx: int) -> None:
    """Validate review_if_modified policy fields."""
    if "require_review_if_modified" not in policy:
        raise ValidationError(
            f"on_step_output[{idx}].policy.require_review_if_modified "
            f"is required for type 'review_if_modified'"
        )

    require_review = policy["require_review_if_modified"]
    if not isinstance(require_review, list):
        raise ValidationError(
            f"on_step_output[{idx}].policy.require_review_if_modified must be an array"
        )

    for criteria_idx, criteria in enumerate(require_review):
        prefix = f"on_step_output[{idx}].policy.require_review_if_modified[{criteria_idx}]"

        if not isinstance(criteria, dict):
            raise ValidationError(f"{prefix} must be an object")

        if "resource_type" not in criteria and "attribute_paths" not in criteria:
            raise ValidationError(
                f"{prefix} must contain 'resource_type' or 'attribute_paths'"
            )

        if "resource_type" in criteria and not isinstance(criteria["resource_type"], str):
            raise ValidationError(f"{prefix}.resource_type must be a string")

        if "attribute_paths" in criteria:
            attr_paths = criteria["attribute_paths"]
            if not isinstance(attr_paths, list):
                raise ValidationError(f"{prefix}.attribute_paths must be an array")
            for ap_idx, ap in enumerate(attr_paths):
                if not isinstance(ap, str):
                    raise ValidationError(
                        f"{prefix}.attribute_paths[{ap_idx}] must be a string"
                    )

    if "auto_approve_if_none_match" in policy:
        if not isinstance(policy["auto_approve_if_none_match"], bool):
            raise ValidationError(
                f"on_step_output[{idx}].policy.auto_approve_if_none_match must be a boolean"
            )
