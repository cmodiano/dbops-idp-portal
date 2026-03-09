"""
Tests for utils/json_helpers.py
"""

import json
from utils.json_helpers import (
    serialize_json,
    deserialize_json,
    validate_json_schema,
    safe_deserialize_json,
    safe_serialize_json
)


class TestJSONHelpers:
    """Tests for JSON helper functions."""
    
    def test_serialize_json_simple_dict(self):
        """Test serializing a simple dict."""
        data = {'key': 'value', 'number': 42}
        result = serialize_json(data)
        assert result == '{"key": "value", "number": 42}'
        assert isinstance(result, str)
    
    def test_serialize_json_nested_dict(self):
        """Test serializing nested objects."""
        data = {
            'level1': {
                'level2': {
                    'level3': 'deep_value',
                    'array': [1, 2, 3]
                }
            }
        }
        result = serialize_json(data)
        parsed = json.loads(result)
        assert parsed['level1']['level2']['level3'] == 'deep_value'
        assert parsed['level1']['level2']['array'] == [1, 2, 3]
    
    def test_serialize_json_array(self):
        """Test serializing arrays."""
        data = [{'id': 1}, {'id': 2}, {'id': 3}]
        result = serialize_json(data)
        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]['id'] == 1
    
    def test_serialize_json_none(self):
        """Test serializing None."""
        result = serialize_json(None)
        assert result is None
    
    def test_deserialize_json_simple(self):
        """Test deserializing a simple JSON string."""
        json_str = '{"key": "value", "number": 42}'
        result = deserialize_json(json_str)
        assert result == {'key': 'value', 'number': 42}
    
    def test_deserialize_json_nested(self):
        """Test deserializing nested JSON."""
        json_str = '{"level1": {"level2": {"level3": "deep_value"}}}'
        result = deserialize_json(json_str)
        assert result['level1']['level2']['level3'] == 'deep_value'
    
    def test_deserialize_json_array(self):
        """Test deserializing JSON array."""
        json_str = '[{"id": 1}, {"id": 2}]'
        result = deserialize_json(json_str)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]['id'] == 1
    
    def test_deserialize_json_invalid(self):
        """Test deserializing invalid JSON returns default."""
        invalid_json = '{"invalid": json}'
        result = deserialize_json(invalid_json, default={})
        assert result == {}
    
    def test_deserialize_json_none(self):
        """Test deserializing None."""
        result = deserialize_json(None)
        assert result is None
    
    def test_validate_json_schema_basic(self):
        """Test basic JSON Schema validation."""
        schema = {'type': 'object'}
        data = {'key': 'value'}
        is_valid, error = validate_json_schema(data, schema)
        assert is_valid is True
        assert error is None
    
    def test_validate_json_schema_required_fields(self):
        """Test validation with required fields."""
        schema = {
            'type': 'object',
            'required': ['name', 'id']
        }
        data = {'name': 'test'}  # Missing 'id'
        is_valid, error = validate_json_schema(data, schema)
        assert is_valid is False
        assert 'required' in error.lower()
    
    def test_validate_json_schema_properties(self):
        """Test validation with properties."""
        schema = {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'count': {'type': 'number'}
            }
        }
        data = {'name': 'test', 'count': 42}
        is_valid, error = validate_json_schema(data, schema)
        assert is_valid is True
    
    def test_safe_deserialize_json(self):
        """Test safe deserialize returns None on error."""
        invalid_json = 'invalid'
        result = safe_deserialize_json(invalid_json)
        assert result is None
    
    def test_safe_serialize_json(self):
        """Test safe serialize handles errors."""
        # This should work
        result = safe_serialize_json({'key': 'value'})
        assert result is not None

        # This might fail but should return None instead of raising
        # Note: Most Python objects can be serialized, so this test is limited
        result = safe_serialize_json({'key': 'value'})
        assert result is not None


# ---------------------------------------------------------------------------
# Story 55.3 — Branches non couvertes (sous-tâches 3.1 à 3.9)
# ---------------------------------------------------------------------------

class TestValidateJsonSchemaTypeBranches:
    """Tests des branches type manquantes dans validate_json_schema."""

    # 3.1 — type "array"
    def test_array_schema_valid_list(self):
        is_valid, error = validate_json_schema([1, 2, 3], {'type': 'array'})
        assert is_valid is True
        assert error is None

    def test_array_schema_invalid_not_list(self):
        is_valid, error = validate_json_schema("not a list", {'type': 'array'})
        assert is_valid is False
        assert error is not None

    # 3.2 — type "string"
    def test_string_schema_valid_str(self):
        is_valid, error = validate_json_schema("hello", {'type': 'string'})
        assert is_valid is True
        assert error is None

    def test_string_schema_invalid_not_str(self):
        is_valid, error = validate_json_schema(42, {'type': 'string'})
        assert is_valid is False
        assert error is not None

    # 3.3 — type "number"
    def test_number_schema_valid_int(self):
        is_valid, error = validate_json_schema(42, {'type': 'number'})
        assert is_valid is True
        assert error is None

    def test_number_schema_valid_float(self):
        is_valid, error = validate_json_schema(3.14, {'type': 'number'})
        assert is_valid is True
        assert error is None

    def test_number_schema_invalid_str(self):
        is_valid, error = validate_json_schema("42", {'type': 'number'})
        assert is_valid is False
        assert error is not None

    # 3.4 — type "boolean"
    def test_boolean_schema_valid_bool(self):
        is_valid, error = validate_json_schema(True, {'type': 'boolean'})
        assert is_valid is True
        assert error is None

    def test_boolean_schema_invalid_int(self):
        """int n'est pas bool (même si Python considère bool comme sous-classe de int)."""
        # Note: bool est une sous-classe de int en Python, donc isinstance(True, int) == True
        # mais isinstance(1, bool) == False
        is_valid, error = validate_json_schema(1, {'type': 'boolean'})
        assert is_valid is False
        assert error is not None

    # 3.5 — sans type mais avec properties : data non-dict → False
    def test_no_type_with_properties_non_dict_returns_invalid(self):
        schema = {'properties': {'name': {'type': 'string'}}}
        is_valid, error = validate_json_schema("not a dict", schema)
        assert is_valid is False
        assert "JSON object" in error

    # 3.6 — data non-dict avec schema sans type objet/properties → True (early return)
    def test_non_dict_data_with_schema_no_object_type_returns_true(self):
        schema = {'type': 'array'}  # type array, data est liste
        is_valid, error = validate_json_schema([1, 2], schema)
        assert is_valid is True
        assert error is None

    # 3.7 — propriété invalide nested
    def test_nested_property_invalid_type_returns_property_error(self):
        schema = {
            'type': 'object',
            'properties': {
                'count': {'type': 'number'},
            }
        }
        data = {'count': 'not-a-number'}
        is_valid, error = validate_json_schema(data, schema)
        assert is_valid is False
        assert "Property 'count'" in error

    # 3.8 — safe_serialize_json chemin erreur
    def test_safe_serialize_json_returns_none_on_error(self):
        """Quand serialize_json lève TypeError, safe_serialize_json retourne None."""
        from unittest.mock import patch
        with patch('utils.json_helpers.serialize_json', side_effect=TypeError("boom")):
            result = safe_serialize_json({'key': 'value'})
        assert result is None

    # 3.9b — bool non accepté comme "number" (JSON Schema: boolean ≠ number, Story 66.25 review)
    def test_number_schema_rejects_boolean_true(self):
        """True/False ne doivent pas passer la validation de type 'number' (bool sous-classe de int)."""
        is_valid, error = validate_json_schema(True, {'type': 'number'})
        assert is_valid is False
        assert error is not None

    def test_number_schema_rejects_boolean_false(self):
        """False ne doit pas passer la validation de type 'number'."""
        is_valid, error = validate_json_schema(False, {'type': 'number'})
        assert is_valid is False
        assert error is not None

    # 3.9 — serialize_json avec entity_id fourni
    def test_serialize_json_error_log_includes_entity_id(self):
        """serialize_json avec entity_id → le log inclut entity_id comme kwarg structlog (JSON-MED-01)."""
        import pytest
        from structlog.testing import capture_logs
        with capture_logs() as cap_logs:
            with pytest.raises(TypeError, match="Cannot serialize"):
                serialize_json(object(), field_name="test_field", entity_id=42)
        assert len(cap_logs) >= 1
        log_entry = cap_logs[0]
        # JSON-MED-01: event est un nom structuré, entity_id est un kwarg
        assert log_entry.get("event") == "json_serialize_error", f"event inattendu: {log_entry.get('event')}"
        assert log_entry.get("entity_id") == 42, f"entity_id '42' absent du log: {log_entry}"
        assert log_entry.get("field_name") == "test_field"
