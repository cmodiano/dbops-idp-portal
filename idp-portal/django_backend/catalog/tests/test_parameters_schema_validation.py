"""
Tests for Story 23.5 + 37.4: validate_parameters_schema_inventory.

Validates that parameters_schema with source='inventory' requires a valid inventory_type
and that the optional inventory_value_column is a valid column for that inventory_type.
"""

import pytest
from rest_framework import serializers

from catalog.serializers import (
    validate_parameters_schema_inventory,
    VALID_INVENTORY_TYPES,
    VALID_INVENTORY_VALUE_COLUMNS,
)


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


class TestInventoryValueColumn:
    """Story 37.4: Tests for optional inventory_value_column property."""

    def test_inventory_value_column_valid_name_passes(self):
        """4.1 — servers + inventory_value_column=name → passe."""
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": "name",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_value_column_valid_id_passes(self):
        """4.2 — databases + inventory_value_column=id → passe."""
        schema = {
            "type": "object",
            "properties": {
                "db": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "databases",
                    "inventory_value_column": "id",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_value_column_valid_server_ref_passes(self):
        """4.3 — instances + inventory_value_column=server_ref → passe."""
        schema = {
            "type": "object",
            "properties": {
                "inst": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "instances",
                    "inventory_value_column": "server_ref",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_value_column_invalid_fails_with_message(self):
        """4.4 — servers + inventory_value_column=bad_col → exception avec message explicite."""
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": "bad_col",
                }
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        error = str(exc_info.value)
        assert "target" in error
        assert "inventory_value_column" in error
        assert "must be one of" in error
        assert "servers" in error

    def test_inventory_value_column_wrong_type_fails(self):
        """4.5 — databases + inventory_value_column=engine_type (non autorisé) → exception."""
        schema = {
            "type": "object",
            "properties": {
                "db": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "databases",
                    "inventory_value_column": "engine_type",
                }
            },
        }
        with pytest.raises(serializers.ValidationError):
            validate_parameters_schema_inventory(schema)

    def test_inventory_value_column_absent_passes(self):
        """4.6 — schéma sans inventory_value_column → rétrocompatibilité (AC #4)."""
        schema = {
            "type": "object",
            "properties": {
                "srv": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_value_column_none_passes(self):
        """4.7 — inventory_value_column=None explicite → passe (AC #4)."""
        schema = {
            "type": "object",
            "properties": {
                "srv": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": None,
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    @pytest.mark.parametrize(
        "inventory_type,column",
        [
            (itype, col)
            for itype, cols in VALID_INVENTORY_VALUE_COLUMNS.items()
            for col in cols
        ],
    )
    def test_all_valid_columns_per_type(self, inventory_type, column):
        """4.8 — chaque colonne valide par inventory_type → passe."""
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": inventory_type,
                    "inventory_value_column": column,
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_inventory_value_column_persisted_in_schema(self):
        """4.9 — round-trip : la fonction retourne exactement le schéma passé (AC #3)."""
        schema = {
            "type": "object",
            "properties": {
                "instance": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "instances",
                    "inventory_value_column": "server_ref",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result is schema  # même objet, pas de copie

    def test_inventory_value_column_empty_string_fails(self):
        """Edge case — inventory_value_column='' (chaîne vide) → n'est pas None, doit échouer."""
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": "",
                }
            },
        }
        with pytest.raises(serializers.ValidationError):
            validate_parameters_schema_inventory(schema)

    def test_inventory_value_column_invalid_on_second_param_fails(self):
        """Multi-params — premier param valide, second param avec colonne invalide → exception sur le second."""
        schema = {
            "type": "object",
            "properties": {
                "first": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": "name",  # valide
                },
                "second": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "databases",
                    "inventory_value_column": "engine_type",  # invalide pour databases
                },
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        assert "second" in str(exc_info.value)


def test_valid_inventory_value_columns_covers_all_inventory_types():
    """M1 — Invariant : VALID_INVENTORY_VALUE_COLUMNS doit couvrir exactement VALID_INVENTORY_TYPES.

    Sans cet invariant, un nouveau type ajouté dans VALID_INVENTORY_TYPES sans mise à jour
    de VALID_INVENTORY_VALUE_COLUMNS produirait un message d'erreur vide : 'must be one of: '.
    """
    assert set(VALID_INVENTORY_VALUE_COLUMNS.keys()) == set(VALID_INVENTORY_TYPES), (
        "VALID_INVENTORY_VALUE_COLUMNS keys must match VALID_INVENTORY_TYPES exactly. "
        "Update VALID_INVENTORY_VALUE_COLUMNS when adding a new inventory type."
    )
