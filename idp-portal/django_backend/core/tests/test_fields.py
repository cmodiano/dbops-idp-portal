"""
Tests for OracleJSONField custom Django field.

Story 17.4: Unit tests for automatic JSON serialization/deserialization
in Oracle CLOB fields.
"""

import json
import logging
import pytest

from django.core.exceptions import ValidationError
from core.fields import OracleJSONField


class TestOracleJSONFieldFromDbValue:
    """Tests for from_db_value() - deserialization after SELECT."""

    def setup_method(self):
        self.field = OracleJSONField()

    def test_none_returns_none(self):
        result = self.field.from_db_value(None, None, None)
        assert result is None

    def test_valid_json_object(self):
        result = self.field.from_db_value('{"key": "value"}', None, None)
        assert result == {"key": "value"}

    def test_valid_json_array(self):
        result = self.field.from_db_value('[1, 2, 3]', None, None)
        assert result == [1, 2, 3]

    def test_valid_json_nested(self):
        data = '{"a": {"b": [1, 2, {"c": true}]}}'
        result = self.field.from_db_value(data, None, None)
        assert result == {"a": {"b": [1, 2, {"c": True}]}}

    def test_empty_json_object(self):
        result = self.field.from_db_value('{}', None, None)
        assert result == {}

    def test_empty_json_array(self):
        result = self.field.from_db_value('[]', None, None)
        assert result == []

    def test_invalid_json_returns_none(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = self.field.from_db_value('invalid json', None, None)
        assert result is None
        assert "Failed to deserialize JSON field" in caplog.text

    def test_dict_already_deserialized(self):
        data = {"key": "value"}
        result = self.field.from_db_value(data, None, None)
        assert result == data

    def test_list_already_deserialized(self):
        data = [1, 2, 3]
        result = self.field.from_db_value(data, None, None)
        assert result == data

    def test_empty_string_returns_none(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = self.field.from_db_value('', None, None)
        assert result is None


class TestOracleJSONFieldGetPrepValue:
    """Tests for get_prep_value() - serialization before INSERT/UPDATE."""

    def setup_method(self):
        self.field = OracleJSONField()

    def test_none_returns_none(self):
        result = self.field.get_prep_value(None)
        assert result is None

    def test_dict_serialized_to_string(self):
        result = self.field.get_prep_value({"key": "value"})
        assert isinstance(result, str)
        assert json.loads(result) == {"key": "value"}

    def test_list_serialized_to_string(self):
        result = self.field.get_prep_value([1, 2, 3])
        assert isinstance(result, str)
        assert json.loads(result) == [1, 2, 3]

    def test_string_returned_as_is(self):
        result = self.field.get_prep_value('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_nested_dict(self):
        data = {"a": {"b": [1, 2, {"c": True}]}}
        result = self.field.get_prep_value(data)
        assert json.loads(result) == data

    def test_empty_dict(self):
        result = self.field.get_prep_value({})
        assert result == '{}'

    def test_empty_list(self):
        result = self.field.get_prep_value([])
        assert result == '[]'

    def test_non_serializable_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Cannot serialize value to JSON"):
            self.field.get_prep_value({"key": set([1, 2])})

    def test_with_validator_called_on_dict(self):
        called_with = []
        def mock_validator(value):
            called_with.append(value)
        field = OracleJSONField(validator=mock_validator)
        field.get_prep_value({"key": "value"})
        assert len(called_with) == 1
        assert called_with[0] == {"key": "value"}

    def test_with_validator_raises_validation_error(self):
        def failing_validator(value):
            raise ValidationError("Invalid schema")
        field = OracleJSONField(validator=failing_validator)
        with pytest.raises(ValidationError, match="Invalid schema"):
            field.get_prep_value({"key": "value"})

    def test_string_bypasses_validator(self):
        """String values bypass validator since they're already serialized."""
        called = []
        def mock_validator(value):
            called.append(True)
        field = OracleJSONField(validator=mock_validator)
        result = field.get_prep_value('{"key": "value"}')
        assert len(called) == 0
        assert result == '{"key": "value"}'


class TestOracleJSONFieldToPython:
    """Tests for to_python() - validation and normalization."""

    def setup_method(self):
        self.field = OracleJSONField()

    def test_none_returns_none(self):
        result = self.field.to_python(None)
        assert result is None

    def test_dict_returns_dict(self):
        data = {"key": "value"}
        result = self.field.to_python(data)
        assert result == data

    def test_list_returns_list(self):
        data = [1, 2, 3]
        result = self.field.to_python(data)
        assert result == data

    def test_valid_json_string_parsed(self):
        result = self.field.to_python('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_array_string_parsed(self):
        result = self.field.to_python('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_invalid_json_string_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Invalid JSON"):
            self.field.to_python("not valid json")

    def test_unsupported_type_raises_validation_error(self):
        with pytest.raises(ValidationError, match="Unsupported type"):
            self.field.to_python(42)

    def test_with_validator_on_dict(self):
        called_with = []
        def mock_validator(value):
            called_with.append(value)
        field = OracleJSONField(validator=mock_validator)
        field.to_python({"key": "value"})
        assert called_with == [{"key": "value"}]

    def test_with_validator_on_string(self):
        called_with = []
        def mock_validator(value):
            called_with.append(value)
        field = OracleJSONField(validator=mock_validator)
        field.to_python('{"key": "value"}')
        assert called_with == [{"key": "value"}]

    def test_with_validator_raises_on_dict(self):
        def failing_validator(value):
            raise ValidationError("Bad data")
        field = OracleJSONField(validator=failing_validator)
        with pytest.raises(ValidationError, match="Bad data"):
            field.to_python({"key": "value"})

    def test_with_validator_raises_on_string(self):
        def failing_validator(value):
            raise ValidationError("Bad data")
        field = OracleJSONField(validator=failing_validator)
        with pytest.raises(ValidationError, match="Bad data"):
            field.to_python('{"key": "value"}')


class TestOracleJSONFieldDeconstruct:
    """Tests for deconstruct() - migration support."""

    def test_deconstruct_without_validator(self):
        field = OracleJSONField()
        name, path, args, kwargs = field.deconstruct()
        assert 'validator' not in kwargs

    def test_deconstruct_with_validator(self):
        def my_validator(value):
            pass
        field = OracleJSONField(validator=my_validator)
        name, path, args, kwargs = field.deconstruct()
        assert kwargs['validator'] is my_validator

    def test_deconstruct_preserves_field_options(self):
        field = OracleJSONField(null=True, blank=True, db_column='MY_COL')
        name, path, args, kwargs = field.deconstruct()
        assert kwargs['null'] is True
        assert kwargs['blank'] is True
        assert kwargs['db_column'] == 'MY_COL'


class TestOracleJSONFieldInit:
    """Tests for __init__() - field initialization."""

    def test_default_validator_is_none(self):
        field = OracleJSONField()
        assert field.validator is None

    def test_custom_validator_stored(self):
        def my_validator(value):
            pass
        field = OracleJSONField(validator=my_validator)
        assert field.validator is my_validator

    def test_field_is_text_field(self):
        field = OracleJSONField()
        assert isinstance(field, OracleJSONField)
        from django.db import models
        assert isinstance(field, models.TextField)


class TestOracleJSONFieldLogging:
    """Tests for logging behavior."""

    def setup_method(self):
        self.field = OracleJSONField()

    def test_from_db_value_logs_warning_on_json_error(self, caplog):
        with caplog.at_level(logging.WARNING):
            result = self.field.from_db_value('invalid json', None, None)
        assert result is None
        assert "Failed to deserialize JSON field" in caplog.text

    def test_get_prep_value_logs_error_on_serialization_failure(self, caplog):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError):
                self.field.get_prep_value({"key": set([1, 2])})  # set is not JSON serializable
        assert "Failed to serialize value to JSON" in caplog.text

    def test_get_prep_value_logs_error_on_invalid_json_string(self, caplog):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError, match="Invalid JSON string"):
                self.field.get_prep_value('not valid json')
        assert "Invalid JSON string provided" in caplog.text


class TestOracleJSONFieldStringValidation:
    """Tests for JSON string validation in get_prep_value."""

    def setup_method(self):
        self.field = OracleJSONField()

    def test_valid_json_string_accepted(self):
        result = self.field.get_prep_value('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_invalid_json_string_rejected(self):
        with pytest.raises(ValidationError, match="Invalid JSON string"):
            self.field.get_prep_value('not valid json')

    def test_empty_json_string_rejected(self):
        with pytest.raises(ValidationError, match="Invalid JSON string"):
            self.field.get_prep_value('')

    def test_partial_json_string_rejected(self):
        with pytest.raises(ValidationError, match="Invalid JSON string"):
            self.field.get_prep_value('{"key": "value"')  # Missing closing brace
