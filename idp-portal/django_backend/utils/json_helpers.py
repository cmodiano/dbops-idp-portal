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
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        entity_info = f" for entity {entity_id}" if entity_id else ""
        logger.error(f"Failed to serialize {field_name}{entity_info}: {e}")
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
        entity_info = f" for entity {entity_id}" if entity_id else ""
        logger.warning(f"Failed to deserialize {field_name}{entity_info}: {e}")
        return default


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
    # When schema expects an object or has properties, data must be a dict
    expected_type = schema.get("type")
    has_properties = "properties" in schema and isinstance(schema["properties"], dict)
    if expected_type == "object" or (expected_type is None and has_properties):
        if not isinstance(data, dict):
            return False, "Data must be a JSON object"

    # Basic type validation
    if expected_type is not None:
        if expected_type == "object" and not isinstance(data, dict):
            return False, f"Expected type 'object', got {type(data).__name__}"
        if expected_type == "array" and not isinstance(data, list):
            return False, f"Expected type 'array', got {type(data).__name__}"
        if expected_type == "string" and not isinstance(data, str):
            return False, f"Expected type 'string', got {type(data).__name__}"
        if expected_type == "number" and not isinstance(data, (int, float)):
            return False, f"Expected type 'number', got {type(data).__name__}"
        if expected_type == "boolean" and not isinstance(data, bool):
            return False, f"Expected type 'boolean', got {type(data).__name__}"

    # Required fields and properties validation only apply to objects
    if not isinstance(data, dict):
        return True, None

    # Required fields validation
    if "required" in schema and isinstance(schema["required"], list):
        for required_field in schema["required"]:
            if required_field not in data:
                return False, f"Required field '{required_field}' is missing"

    # Properties validation (basic)
    if has_properties:
        for prop_name, prop_schema in schema["properties"].items():
            if prop_name in data:
                prop_valid, prop_error = validate_json_schema(data[prop_name], prop_schema)
                if not prop_valid:
                    return False, f"Property '{prop_name}': {prop_error}"

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
