"""
Tests pour inventory/mapping_validator.py — Story 55.2 (couverture ≥ 90 %).

Couvre :
- MappingValidator.validate_table_name
- MappingValidator.validate_column_name
- MappingValidator.validate_mapper_columns
"""
from __future__ import annotations

import pytest
from inventory.mapping_validator import MappingValidator
from inventory.mapper import InventoryMapper, MapperValidationError


# ---------------------------------------------------------------------------
# Tests unitaires purs (sans DB)
# ---------------------------------------------------------------------------

class TestValidateTableName:
    """Tests pour MappingValidator.validate_table_name."""

    def setup_method(self):
        self.validator = MappingValidator()

    def test_valid_simple_name(self):
        """Nom simple valide → retourne le nom tel quel."""
        result = self.validator.validate_table_name('SERVERS')
        assert result == 'SERVERS'

    def test_valid_schema_dot_table(self):
        """Nom avec préfixe schéma valide."""
        result = self.validator.validate_table_name('SCHEMA.TABLE_NAME')
        assert result == 'SCHEMA.TABLE_NAME'

    def test_valid_lowercase(self):
        """Nom en minuscules valide."""
        result = self.validator.validate_table_name('servers')
        assert result == 'servers'

    def test_valid_with_underscore(self):
        """Nom avec underscore valide."""
        result = self.validator.validate_table_name('my_schema.my_table')
        assert result == 'my_schema.my_table'

    def test_empty_string_raises_value_error(self):
        """Nom vide → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name('')

    def test_none_raises_value_error(self):
        """None → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name(None)

    def test_sql_injection_drop_table_raises_value_error(self):
        """Tentative d'injection SQL → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name('DROP TABLE')

    def test_starts_with_digit_raises_value_error(self):
        """Nom commençant par un chiffre → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name('1invalid')

    def test_space_in_name_raises_value_error(self):
        """Espace dans le nom → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name('a b c')

    def test_special_chars_raises_value_error(self):
        """Caractères spéciaux → ValueError."""
        with pytest.raises(ValueError):
            self.validator.validate_table_name('table-name')


class TestValidateColumnName:
    """Tests pour MappingValidator.validate_column_name."""

    def setup_method(self):
        self.validator = MappingValidator()

    def test_valid_column_name(self):
        """Nom de colonne valide → retourne le nom."""
        result = self.validator.validate_column_name('HOST_NAME')
        assert result == 'HOST_NAME'

    def test_valid_lowercase(self):
        """Nom en minuscules valide."""
        result = self.validator.validate_column_name('hostname')
        assert result == 'hostname'

    def test_valid_underscore_prefix(self):
        """Nom commençant par underscore valide."""
        result = self.validator.validate_column_name('_internal_col')
        assert result == '_internal_col'

    def test_invalid_with_dot_raises(self):
        """Nom avec point → MapperValidationError."""
        with pytest.raises(MapperValidationError):
            self.validator.validate_column_name('table.column')

    def test_invalid_with_space_raises(self):
        """Nom avec espace → MapperValidationError."""
        with pytest.raises(MapperValidationError):
            self.validator.validate_column_name('col name')

    def test_invalid_starts_with_digit_raises(self):
        """Nom commençant par chiffre → MapperValidationError."""
        with pytest.raises(MapperValidationError):
            self.validator.validate_column_name('1col')

    def test_empty_raises(self):
        """Nom vide → MapperValidationError."""
        with pytest.raises(MapperValidationError):
            self.validator.validate_column_name('')


class TestValidateMapperColumns:
    """Tests pour MappingValidator.validate_mapper_columns."""

    def setup_method(self):
        self.validator = MappingValidator()

    def _make_mapper(self, config: dict) -> InventoryMapper:
        return InventoryMapper(config)

    def test_entity_not_found_returns_without_error(self):
        """Entité inexistante → return immédiat, pas d'erreur."""
        mapper = self._make_mapper({'entities': {}})
        # Ne doit pas lever d'exception
        self.validator.validate_mapper_columns(mapper, 'nonexistent')

    def test_valid_entity_with_id_column(self):
        """Entité valide avec id_column → pas d'erreur."""
        mapper = self._make_mapper({
            'entities': {
                'servers': {
                    'table': 'SERVERS',
                    'id_column': 'SERVER_ID',
                    'columns': {
                        'hostname': 'HOST_NAME',
                        'environment': 'ENV',
                    }
                }
            }
        })
        self.validator.validate_mapper_columns(mapper, 'servers')  # pas d'exception

    def test_entity_without_id_column(self):
        """Entité sans id_column → pas de validation id_col, pas d'erreur."""
        mapper = self._make_mapper({
            'entities': {
                'servers': {
                    'table': 'SERVERS',
                    'columns': {
                        'hostname': 'HOST_NAME',
                    }
                }
            }
        })
        self.validator.validate_mapper_columns(mapper, 'servers')  # pas d'exception

    def test_invalid_id_column_raises(self):
        """id_col invalide → MapperValidationError."""
        mapper = self._make_mapper({
            'entities': {
                'servers': {
                    'table': 'SERVERS',
                    'id_column': 'invalid-id',  # tiret invalide
                    'columns': {
                        'hostname': 'HOST_NAME',
                    }
                }
            }
        })
        with pytest.raises(MapperValidationError):
            self.validator.validate_mapper_columns(mapper, 'servers')

    def test_invalid_concept_name_raises(self):
        """Nom de concept invalide (pattern) → MapperValidationError."""
        mapper = self._make_mapper({
            'entities': {
                'servers': {
                    'table': 'SERVERS',
                    'columns': {
                        'invalid-concept': 'HOST_NAME',  # tiret invalide dans concept
                    }
                }
            }
        })
        with pytest.raises(MapperValidationError):
            self.validator.validate_mapper_columns(mapper, 'servers')

    def test_invalid_column_name_raises(self):
        """Nom de colonne invalide → MapperValidationError."""
        mapper = self._make_mapper({
            'entities': {
                'servers': {
                    'table': 'SERVERS',
                    'columns': {
                        'hostname': 'invalid-col',  # tiret invalide dans colonne
                    }
                }
            }
        })
        with pytest.raises(MapperValidationError):
            self.validator.validate_mapper_columns(mapper, 'servers')
