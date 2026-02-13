"""
Validators for catalog app.
Story 25.2: gate_conditions validation for execution steps.
Story 25.4: change_type_config validation (allowed, requires_maintenance_window, requires_approval).
"""

import re

from rest_framework.exceptions import ValidationError


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
