"""Integration config validation against JSON Schema (Story 5.4).

Validates config (auth_flow steps) when creating/updating integrations.
Raises InvalidStateError(400) with INVALID_CONFIG on schema violation.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import jsonschema

from app.core.exceptions import InvalidStateError

_SCHEMA_PATH = Path(__file__).resolve().parent / "integration_config_schema.json"
_SCHEMA_CACHE: dict | None = None
_SCHEMA_LOCK = threading.Lock()


def _load_schema() -> dict:
    """Load integration config JSON Schema (draft-07). Thread-safe."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    with _SCHEMA_LOCK:
        if _SCHEMA_CACHE is None:
            with open(_SCHEMA_PATH, encoding="utf-8") as f:
                _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def validate_integration_config(config: dict) -> None:
    """Validate config against JSON Schema (Story 5.4, AC2).

    Args:
        config: Non-empty config dict (auth_flow, etc.).

    Raises:
        InvalidStateError: code INVALID_CONFIG, 400, with field and error details.
    """
    schema = _load_schema()
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
