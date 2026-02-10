"""
Validators for catalog app.
Story 25.2: gate_conditions validation for execution steps.
"""

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
