"""
JSON helpers for CLOB field serialization/deserialization.
Centralized utilities for handling JSON data stored in Oracle CLOB fields.
"""

import json
import structlog
from typing import Any

logger = structlog.get_logger(__name__)


def serialize_json(value: Any, field_name: str = "field", entity_id: int | None = None) -> str | None:
    """
    Serialize a Python object to JSON string for CLOB storage.
    
    Args:
        value: Python object to serialize (dict, list, etc.)
        field_name: Name of the field (for logging)
        entity_id: Optional entity ID (for logging)
    
    Returns:
        JSON string or None if value is None
    
    Raises:
        TypeError: If value cannot be serialized to JSON
    """
    if value is None:
        return None
    
    try:
        # ensure_ascii=False: preserves accented chars (French) for Oracle CLOB UTF-8 storage
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        # JSON-MED-01: structlog structured format instead of f-string
        logger.error("json_serialize_error", field_name=field_name, entity_id=entity_id, error=str(e))
        raise TypeError(f"Cannot serialize {field_name} to JSON: {e}") from e


def deserialize_json(json_string: str | None, field_name: str = "field", 
                    entity_id: int | None = None, default: Any = None) -> Any:
    """
    Deserialize a JSON string from CLOB to Python object.
    
    Args:
        json_string: JSON string to deserialize
        field_name: Name of the field (for logging)
        entity_id: Optional entity ID (for logging)
        default: Default value to return if deserialization fails (default: None)
    
    Returns:
        Deserialized Python object (dict, list, etc.) or default if json_string is None/empty or deserialization fails
    """
    if not json_string:
        return default
    
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        # JSON-MED-01: structlog structured format instead of f-string
        logger.warning("json_deserialize_error", field_name=field_name, entity_id=entity_id, error=str(e))
        return default


# JSON-LOW-01: Helpers extracted from validate_json_schema() to reduce nesting (Story 66.25)

def _validate_type(value: Any, schema_type: str) -> bool:
    """Vérifie qu'une valeur correspond au type JSON Schema attendu.

    Args:
        value: Value to check.
        schema_type: Expected JSON Schema type string.

    Returns:
        True if value matches the expected type, False otherwise.
    """
    # JSON Schema: boolean is a distinct type from number.
    # Python's bool is a subclass of int, so isinstance(True, int) == True.
    # We must reject booleans explicitly when checking "number" type.
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    type_checks: dict[str, type] = {
        "object": dict,
        "array": list,
        "string": str,
    }
    expected = type_checks.get(schema_type)
    if expected is None:
        return True  # Unknown type — no validation
    return isinstance(value, expected)


def _validate_properties(data: dict, properties: dict, required: list) -> list[str]:
    """Itère les propriétés d'un objet JSON et retourne une liste d'erreurs.

    Args:
        data: Object dict to validate.
        properties: Schema properties dict.
        required: List of required field names.

    Returns:
        List of error strings (empty if valid).
    """
    errors: list[str] = []
    for field in required:
        if field not in data:
            errors.append(f"Required field '{field}' is missing")
    for prop_name, prop_schema in properties.items():
        if prop_name in data:
            prop_valid, prop_error = validate_json_schema(data[prop_name], prop_schema)
            if not prop_valid:
                errors.append(f"Property '{prop_name}': {prop_error}")
    return errors


def validate_json_schema(data: Any, schema: dict) -> tuple[bool, str | None]:
    """
    Validate JSON data against a JSON Schema.

    Note: This is a basic implementation. For full JSON Schema validation,
    consider using the 'jsonschema' library.

    Args:
        data: Data to validate (dict for root/object, or primitive for property values)
        schema: JSON Schema dict (basic validation only)

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if data is valid, False otherwise
        - error_message: Error message if invalid, None if valid
    """
    expected_type = schema.get("type")
    has_properties = "properties" in schema and isinstance(schema["properties"], dict)

    # Object schemas (explicit or implicit via properties) require a dict
    if expected_type == "object" or (expected_type is None and has_properties):
        if not isinstance(data, dict):
            return False, "Data must be a JSON object"

    # Type validation for non-object explicit types
    if expected_type and expected_type != "object" and not _validate_type(data, expected_type):
        return False, f"Expected type '{expected_type}', got {type(data).__name__}"

    # Properties/required validation only applies to dicts
    if not isinstance(data, dict):
        return True, None

    errors = _validate_properties(
        data,
        schema.get("properties", {}) if has_properties else {},
        schema.get("required", []) if isinstance(schema.get("required"), list) else [],
    )
    if errors:
        return False, errors[0]
    return True, None


def safe_deserialize_json(json_string: str | None, field_name: str = "field",
                         entity_id: int | None = None) -> Any:
    """
    Safely deserialize JSON with consistent error handling.
    Returns None on error instead of raising exception.
    
    Args:
        json_string: JSON string to deserialize
        field_name: Name of the field (for logging)
        entity_id: Optional entity ID (for logging)
    
    Returns:
        Deserialized Python object or None if deserialization fails
    """
    return deserialize_json(json_string, field_name, entity_id, default=None)


def safe_serialize_json(value: Any, field_name: str = "field",
                        entity_id: int | None = None) -> str | None:
    """
    Safely serialize value to JSON with consistent error handling.
    Returns None on error instead of raising exception.
    
    Args:
        value: Python object to serialize
        field_name: Name of the field (for logging)
        entity_id: Optional entity ID (for logging)
    
    Returns:
        JSON string or None if serialization fails
    """
    try:
        return serialize_json(value, field_name, entity_id)
    except (TypeError, ValueError):
        return None
