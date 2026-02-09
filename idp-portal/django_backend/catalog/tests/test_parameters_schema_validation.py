"""
Tests for Story 23.5: validate_parameters_schema_inventory.

Validates that parameters_schema with source='inventory' requires a valid inventory_type.
"""

import pytest
from rest_framework import serializers

from catalog.serializers import validate_parameters_schema_inventory, VALID_INVENTORY_TYPES


class TestValidateParametersSchemaInventory:
    """Unit tests for validate_parameters_schema_inventory function."""

    def test_none_value_passes(self):
        assert validate_parameters_schema_inventory(None) is None

    def test_empty_dict_passes(self):
        assert validate_parameters_schema_inventory({}) == {}

    def test_no_properties_passes(self):
        schema = {"type": "object"}
        assert validate_parameters_schema_inventory(schema) == schema

    def test_empty_properties_passes(self):
        schema = {"type": "object", "properties": {}}
        assert validate_parameters_schema_inventory(schema) == schema

    def test_manual_source_passes(self):
        schema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "source": "manual"}
            },
        }
        assert validate_parameters_schema_inventory(schema) == schema

    def test_no_source_passes(self):
        """Parameters without source field should pass (backward compatibility)."""
        schema = {
            "type": "object",
            "properties": {
                "backup_path": {"type": "string"}
            },
        }
        assert validate_parameters_schema_inventory(schema) == schema

    @pytest.mark.parametrize("inventory_type", VALID_INVENTORY_TYPES)
    def test_valid_inventory_type_passes(self, inventory_type):
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": inventory_type,
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_source_without_inventory_type_fails(self):
        schema = {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "source": "inventory",
                }
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        assert "inventory_type is required" in str(exc_info.value)
        assert "server_name" in str(exc_info.value)

    def test_inventory_source_with_invalid_type_fails(self):
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "unknown",
                }
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        assert "must be one of" in str(exc_info.value)

    def test_multiple_params_mixed_sources(self):
        """Schema with both manual and inventory params should validate correctly."""
        schema = {
            "type": "object",
            "properties": {
                "instance_name": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "instances",
                },
                "backup_path": {
                    "type": "string",
                },
                "db_name": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "databases",
                },
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_multiple_params_one_invalid_fails(self):
        """If any inventory param has invalid type, entire validation fails."""
        schema = {
            "type": "object",
            "properties": {
                "instance_name": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "instances",
                },
                "bad_param": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "invalid",
                },
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        assert "bad_param" in str(exc_info.value)

    def test_non_dict_property_skipped(self):
        """Non-dict property values should be skipped gracefully."""
        schema = {
            "type": "object",
            "properties": {
                "weird": "not_a_dict",
                "valid": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                },
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_type_empty_string_fails(self):
        """Empty string inventory_type should fail."""
        schema = {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "",
                }
            },
        }
        with pytest.raises(serializers.ValidationError):
            validate_parameters_schema_inventory(schema)
