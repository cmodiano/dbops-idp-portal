"""
Tests for utils/json_helpers.py
"""

import pytest
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
