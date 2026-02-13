"""
Integration config validation against JSON Schema.
"""

import json
import threading
from pathlib import Path

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from core.exceptions import InvalidStateError

# Path to schema file (relative to backend root)
# Try multiple possible paths for flexibility
_SCHEMA_PATHS = [
    Path(__file__).resolve().parent.parent.parent / 'backend' / 'app' / 'schemas' / 'integration_config_schema.json',
    Path(__file__).resolve().parent.parent.parent.parent / 'backend' / 'app' / 'schemas' / 'integration_config_schema.json',
]
_SCHEMA_PATH = None
for path in _SCHEMA_PATHS:
    if path.exists():
        _SCHEMA_PATH = path
        break
if _SCHEMA_PATH is None:
    # Fallback: use first path even if doesn't exist (will be handled in _load_schema)
    _SCHEMA_PATH = _SCHEMA_PATHS[0]
_SCHEMA_CACHE: dict | None = None
_SCHEMA_LOCK = threading.Lock()


def _load_schema() -> dict:
    """Load integration config JSON Schema (draft-07). Thread-safe."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    with _SCHEMA_LOCK:
        if _SCHEMA_CACHE is None:
            if _SCHEMA_PATH.exists():
                with open(_SCHEMA_PATH, encoding="utf-8") as f:
                    _SCHEMA_CACHE = json.load(f)
            else:
                # Fallback: return empty schema if file not found
                _SCHEMA_CACHE = {}
    return _SCHEMA_CACHE


def validate_integration_config(config: dict) -> None:
    """
    Validate config against JSON Schema.
    
    Args:
        config: Non-empty config dict (auth_flow, etc.).
    
    Raises:
        InvalidStateError: code INVALID_CONFIG, 400, with field and error details.
    """
    if not JSONSCHEMA_AVAILABLE:
        # Basic validation if jsonschema not available
        if not isinstance(config, dict):
            raise InvalidStateError(
                code="INVALID_CONFIG",
                message="Config must be a JSON object",
                details={"field": "root", "error": "Config must be a JSON object"}
            )
        return
    
    schema = _load_schema()
    if not schema:
        # Schema file not found - skip validation
        return
    
    try:
        jsonschema.validate(instance=config, schema=schema)
    except jsonschema.ValidationError as e:
        field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        raise InvalidStateError(
            code="INVALID_CONFIG",
            message=f"Config invalide: {e.message}",
            details={
                "field": field_path,
                "error": e.message,
                "schema_path": list(e.schema_path),
            },
        ) from e
    except jsonschema.SchemaError as e:
        raise InvalidStateError(
            code="INVALID_SCHEMA",
            message="Le schema de config d'integration est invalide",
            details={"error": str(e)},
        ) from e
