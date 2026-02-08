"""
Custom Django model fields for Oracle database compatibility.

Story 17.4: OracleJSONField - Custom field for storing JSON in Oracle CLOB
with automatic serialization/deserialization and optional validation.

Usage:
    from core.fields import OracleJSONField

    class MyModel(models.Model):
        json_data = OracleJSONField(null=True, blank=True, db_column='JSON_DATA')

    # Transparent access
    obj.json_data = {"key": "value"}  # Auto-serialized to JSON string
    obj.save()
    data = obj.json_data  # Auto-deserialized to dict

Args:
    validator (callable, optional): Function that takes dict/list and raises
        ValidationError if invalid.
"""

import json
import logging

from django.db import models
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class OracleJSONField(models.TextField):
    """Custom Django field for storing JSON in Oracle CLOB with automatic serialization."""

    def __init__(self, *args, validator=None, **kwargs):
        self.validator = validator
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.validator is not None:
            kwargs['validator'] = self.validator
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        """
        Deserialize JSON from Oracle CLOB after SELECT.

        Treats empty/whitespace string as None (DB may contain "" from legacy data).
        Returns None on deserialization error (permissive mode) to avoid breaking
        queries when DB contains corrupted data. Logs warning for debugging.
        """
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to deserialize JSON field: %s", e)
            return None

    def get_prep_value(self, value):
        """
        Serialize dict/list to JSON string before INSERT/UPDATE.

        If value is already a string, validates it's valid JSON before returning.
        Treats empty string as None (common when frontend sends "" for optional JSON).
        Raises ValidationError for non-serializable values (strict mode).
        """
        if value is None:
            return None
        if isinstance(value, str):
            if not value.strip():
                # Empty or whitespace-only string → treat as None
                return None
            # Validate that string is valid JSON before allowing it through
            try:
                json.loads(value)
                return value
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON string provided: %s", e)
                raise ValidationError(f"Invalid JSON string: {e}")
        if self.validator:
            self.validator(value)
        try:
            return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error("Failed to serialize value to JSON: %s", e)
            raise ValidationError(f"Cannot serialize value to JSON: {e}")

    def to_python(self, value):
        """Convert value to Python dict/list for forms/validation."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            if self.validator:
                self.validator(value)
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError) as e:
                raise ValidationError(f"Invalid JSON: {e}")
            if self.validator:
                self.validator(parsed)
            return parsed
        raise ValidationError(f"Unsupported type for JSON field: {type(value)}")
