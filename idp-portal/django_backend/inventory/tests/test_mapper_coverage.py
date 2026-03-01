"""
Coverage tests for inventory/mapper.py — targeting missing lines to reach ≥90%.
Story 55-3.

Missing lines targeted:
  129, 157, 184, 189, 208, 235, 281-287, 297, 330-338, 343->347,
  392-393, 406-407, 416-417, 449-457, 486-493
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from inventory.mapper import (
    InventoryMapper,
    MapperValidationError,
    _validate_column_name,
    _validate_table_name,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MULTI_TABLE_CONFIG = {
    "entities": {
        "servers": {
            "table": "DBOPS_SERVERS",
            "id_column": "SERVER_ID",
            "columns": {
                "name": "HOSTNAME",
                "environment": "ENV",
                "engine_type": "ENGINE",
            },
        },
        "instances": {
            "table": "DBOPS_INSTANCES",
            "id_column": "INSTANCE_ID",
            "columns": {
                "name": "INSTANCE_NAME",
                "server_ref": "SERVER_NAME",
            },
        },
    }
}

FLAT_TABLE_CONFIG = {
    "flat_table": {
        "table": "DBOPS_INVENTORY",
        "columns": {
            "name": "NAME",
            "environment": "ENVIRONMENT",
            "type": "TYPE",
        },
    }
}


# ---------------------------------------------------------------------------
# Basic properties — is_multi_table, is_flat_table
# ---------------------------------------------------------------------------

class TestInventoryMapperProperties(TestCase):
    """Cover is_multi_table, is_flat_table, get_entity_config basic paths."""

    def test_multi_table_is_multi_table(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertTrue(mapper.is_multi_table)
        self.assertFalse(mapper.is_flat_table)

    def test_flat_table_is_flat_table(self):
        mapper = InventoryMapper(FLAT_TABLE_CONFIG)
        self.assertTrue(mapper.is_flat_table)
        self.assertFalse(mapper.is_multi_table)

    def test_empty_config_neither(self):
        mapper = InventoryMapper({})
        self.assertFalse(mapper.is_multi_table)
        self.assertFalse(mapper.is_flat_table)

    def test_none_config_neither(self):
        mapper = InventoryMapper(None)
        self.assertFalse(mapper.is_multi_table)
        self.assertFalse(mapper.is_flat_table)

    def test_get_entity_config_found(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        cfg = mapper.get_entity_config("servers")
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["table"], "DBOPS_SERVERS")

    def test_get_entity_config_not_found(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertIsNone(mapper.get_entity_config("nonexistent"))


# ---------------------------------------------------------------------------
# get_table_name — happy paths and schema prefix
# ---------------------------------------------------------------------------

class TestGetTableName(TestCase):
    """Cover get_table_name normal paths and schema prefix."""

    def test_get_table_name_normal(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertEqual(mapper.get_table_name("servers"), "DBOPS_SERVERS")
        self.assertEqual(mapper.get_table_name("instances"), "DBOPS_INSTANCES")

    def test_get_table_name_prepends_schema(self):
        config = {**MULTI_TABLE_CONFIG, "schema": "MYSCHEMA"}
        mapper = InventoryMapper(config)
        self.assertEqual(mapper.get_table_name("servers"), "MYSCHEMA.DBOPS_SERVERS")

    def test_get_table_name_no_double_prefix_when_already_qualified(self):
        config = {
            "schema": "OTHER",
            "entities": {
                "servers": {
                    "table": "MYSCHEMA.SERVERS",
                    "id_column": "ID",
                    "columns": {"name": "NAME"},
                }
            },
        }
        mapper = InventoryMapper(config)
        self.assertEqual(mapper.get_table_name("servers"), "MYSCHEMA.SERVERS")

    def test_get_table_name_entity_not_configured_raises(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        with self.assertRaises(MapperValidationError):
            mapper.get_table_name("nonexistent")


# ---------------------------------------------------------------------------
# get_column — happy paths
# ---------------------------------------------------------------------------

class TestGetColumn(TestCase):
    """Cover get_column happy paths."""

    def test_get_column_name(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertEqual(mapper.get_column("servers", "name"), "HOSTNAME")

    def test_get_column_environment(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertEqual(mapper.get_column("servers", "environment"), "ENV")

    def test_get_column_concept_not_mapped_raises(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        with self.assertRaises(MapperValidationError):
            mapper.get_column("servers", "nonexistent")


# ---------------------------------------------------------------------------
# get_id_column — happy path
# ---------------------------------------------------------------------------

class TestGetIdColumn(TestCase):
    """Cover get_id_column happy path."""

    def test_get_id_column_servers(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertEqual(mapper.get_id_column("servers"), "SERVER_ID")


# ---------------------------------------------------------------------------
# refs_join_on_id — various cases
# ---------------------------------------------------------------------------

class TestRefsJoinOnId(TestCase):
    """Cover refs_join_on_id."""

    def test_false_when_no_ref_join(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertFalse(mapper.refs_join_on_id("instances"))

    def test_true_when_ref_join_id(self):
        config = {
            "entities": {
                "instances": {
                    "table": "I",
                    "id_column": "ID",
                    "columns": {"name": "NAME", "server_ref": "SID"},
                    "ref_join": "id",
                }
            }
        }
        mapper = InventoryMapper(config)
        self.assertTrue(mapper.refs_join_on_id("instances"))

    def test_false_when_non_string_ref_join(self):
        config = {
            "entities": {
                "instances": {
                    "table": "I",
                    "id_column": "ID",
                    "columns": {"name": "NAME"},
                    "ref_join": 42,
                }
            }
        }
        mapper = InventoryMapper(config)
        self.assertFalse(mapper.refs_join_on_id("instances"))


# ---------------------------------------------------------------------------
# build_select_clause — happy path
# ---------------------------------------------------------------------------

class TestBuildSelectClause(TestCase):
    """Cover build_select_clause happy paths."""

    def test_select_includes_id_and_columns(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        select = mapper.build_select_clause("servers")
        self.assertIn("SERVER_ID AS id", select)
        self.assertIn("HOSTNAME AS name", select)
        self.assertIn("ENV AS environment", select)

    def test_select_entity_not_configured_raises(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        with self.assertRaises(MapperValidationError):
            mapper.build_select_clause("nonexistent")


# ---------------------------------------------------------------------------
# build_where_clause — happy paths
# ---------------------------------------------------------------------------

class TestBuildWhereClause(TestCase):
    """Cover build_where_clause happy paths."""

    def test_single_filter(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        where, params = mapper.build_where_clause("servers", {"environment": "prod"})
        self.assertIn("UPPER(ENV)", where)
        self.assertEqual(params["p_environment"], "prod")

    def test_empty_filters_returns_empty(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        where, params = mapper.build_where_clause("servers", {})
        self.assertEqual(where, "")
        self.assertEqual(params, {})

    def test_none_value_skipped(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        where, params = mapper.build_where_clause(
            "servers", {"environment": "prod", "engine_type": None}
        )
        self.assertIn("ENV", where)
        self.assertNotIn("ENGINE", where)


# ---------------------------------------------------------------------------
# validate_config — happy paths and error paths
# ---------------------------------------------------------------------------

class TestValidateConfig(TestCase):
    """Cover validate_config paths."""

    def test_valid_multi_table_no_errors(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        self.assertEqual(mapper.validate_config(), [])

    def test_valid_flat_table_no_errors(self):
        mapper = InventoryMapper(FLAT_TABLE_CONFIG)
        self.assertEqual(mapper.validate_config(), [])

    def test_empty_config_error(self):
        mapper = InventoryMapper({})
        errors = mapper.validate_config()
        self.assertEqual(len(errors), 1)
        self.assertIn("must define", errors[0])

    def test_entity_not_dict_error(self):
        config = {"entities": {"servers": "not_a_dict"}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("must be a dict" in e for e in errors))

    def test_entity_missing_table_error(self):
        config = {"entities": {"servers": {"columns": {"name": "NAME"}}}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("missing 'table'" in e for e in errors))

    def test_entity_missing_columns_error(self):
        config = {"entities": {"servers": {"table": "SERVERS"}}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("no 'columns'" in e for e in errors))

    def test_flat_table_not_dict_error(self):
        config = {"flat_table": "invalid"}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("must be a dict" in e for e in errors))

    def test_flat_table_missing_table_error(self):
        config = {"flat_table": {"columns": {"name": "NAME"}}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("missing 'table'" in e for e in errors))

    def test_flat_table_missing_columns_error(self):
        config = {"flat_table": {"table": "INVENTORY"}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("no 'columns'" in e for e in errors))


# ---------------------------------------------------------------------------
# _validate_table_name and _validate_column_name — valid inputs
# ---------------------------------------------------------------------------

class TestValidateFunctionsValid(TestCase):
    """Cover _validate_table_name and _validate_column_name valid paths."""

    def test_valid_table_names(self):
        for name in ["SERVERS", "MY_TABLE", "SCHEMA.TABLE", "dbo_Servers"]:
            _validate_table_name(name)  # should not raise

    def test_valid_column_names(self):
        for name in ["HOSTNAME", "ENV", "engine_type", "_col", "col1"]:
            _validate_column_name(name)  # should not raise

    @patch("inventory.mapper.get_correlation_id", return_value="test")
    def test_invalid_table_name_raises(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_table_name("DROP TABLE;")

    @patch("inventory.mapper.get_correlation_id", return_value="test")
    def test_empty_table_name_raises(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_table_name("")

    @patch("inventory.mapper.get_correlation_id", return_value="test")
    def test_invalid_column_name_raises(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_column_name("'; DROP TABLE")

    @patch("inventory.mapper.get_correlation_id", return_value="test")
    def test_empty_column_name_raises(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_column_name("")


# ---------------------------------------------------------------------------
# get_table_name — missing table key (line 129)
# ---------------------------------------------------------------------------

class TestGetTableNameMissingTable(TestCase):
    """Line 129: entity exists but has no 'table' key."""

    def test_entity_without_table_raises(self):
        config = {
            "entities": {
                "servers": {
                    "id_column": "ID",
                    "columns": {"name": "NAME"},
                    # 'table' is intentionally absent
                }
            }
        }
        mapper = InventoryMapper(config)
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.get_table_name("servers")
        self.assertIn("missing 'table'", str(ctx.exception))


# ---------------------------------------------------------------------------
# get_column — entity not configured (line 157)
# ---------------------------------------------------------------------------

class TestGetColumnEntityNotConfigured(TestCase):
    """Line 157: get_column raises when entity not in config."""

    def test_get_column_unknown_entity_raises(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.get_column("nonexistent", "name")
        self.assertIn("not configured", str(ctx.exception))


# ---------------------------------------------------------------------------
# get_id_column — entity not configured (line 184) and missing id_column (189)
# ---------------------------------------------------------------------------

class TestGetIdColumnErrors(TestCase):
    """Lines 184, 189: get_id_column error paths."""

    def test_entity_not_configured_raises(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.get_id_column("nonexistent")
        self.assertIn("not configured", str(ctx.exception))

    def test_entity_missing_id_column_raises(self):
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "columns": {"name": "NAME"},
                    # 'id_column' intentionally absent
                }
            }
        }
        mapper = InventoryMapper(config)
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.get_id_column("servers")
        self.assertIn("missing 'id_column'", str(ctx.exception))


# ---------------------------------------------------------------------------
# refs_join_on_id — entity not found (line 208)
# ---------------------------------------------------------------------------

class TestRefsJoinOnIdEntityNotFound(TestCase):
    """Line 208: refs_join_on_id returns False when entity not found."""

    def test_unknown_entity_returns_false(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        result = mapper.refs_join_on_id("nonexistent")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# build_select_clause — empty columns dict (line 235)
# ---------------------------------------------------------------------------

class TestBuildSelectClauseEmptyColumns(TestCase):
    """Line 235: build_select_clause raises when entity has no columns."""

    def test_empty_columns_raises(self):
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "id_column": "ID",
                    "columns": {},  # empty columns
                }
            }
        }
        mapper = InventoryMapper(config)
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.build_select_clause("servers")
        self.assertIn("no columns mapped", str(ctx.exception))


# ---------------------------------------------------------------------------
# build_where_clause — invalid concept name (lines 281-287) and all None (297)
# ---------------------------------------------------------------------------

class TestBuildWhereClauseEdgeCases(TestCase):
    """Lines 281-287: invalid concept triggers security error. Line 297: all None → empty."""

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_invalid_concept_name_raises(self, _mock_corr):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        # Concept name with special characters triggers security check
        with self.assertRaises(MapperValidationError) as ctx:
            mapper.build_where_clause("servers", {"'; DROP TABLE": "value"})
        self.assertIn("Invalid filter concept name", str(ctx.exception))

    def test_all_none_values_returns_empty(self):
        mapper = InventoryMapper(MULTI_TABLE_CONFIG)
        # All values are None — conditions list stays empty → line 297
        where, params = mapper.build_where_clause(
            "servers", {"environment": None, "engine_type": None}
        )
        self.assertEqual(where, "")
        self.assertEqual(params, {})


# ---------------------------------------------------------------------------
# get_available_concepts — invalid config path (lines 330-338) and
#   valid entity with columns (lines 343-347)
# ---------------------------------------------------------------------------

class TestGetAvailableConcepts(TestCase):
    """Lines 330-338 and 343->347: get_available_concepts branches.

    get_available_concepts does `from inventory.services import InventoryService`
    inside the function body, so we must patch the name at its import location:
    `inventory.services.InventoryService`.
    """

    def _make_mock_service(self, mapper):
        mock_service = MagicMock()
        mock_service._get_inventory_mapper.return_value = mapper
        return mock_service

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_invalid_config_falls_back_to_defaults(self, _mock_corr):
        """When mapper.validate_config() returns errors → fallback to defaults (lines 330-338)."""
        invalid_config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "id_column": "ID",
                    "columns": {"name": "'; INVALID"},
                }
            }
        }
        mock_mapper = InventoryMapper(invalid_config)
        mock_service = self._make_mock_service(mock_mapper)

        with patch("inventory.services.InventoryService", return_value=mock_service):
            result = InventoryMapper.get_available_concepts("servers")

        self.assertEqual(result, ["name", "environment", "type"])

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_valid_mapper_returns_columns(self, _mock_corr):
        """When mapper is valid and entity has columns → return column keys (lines 343->347)."""
        valid_config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "id_column": "ID",
                    "columns": {"name": "NAME", "environment": "ENV", "engine_type": "ENGINE"},
                }
            }
        }
        mock_mapper = InventoryMapper(valid_config)
        mock_service = self._make_mock_service(mock_mapper)

        with patch("inventory.services.InventoryService", return_value=mock_service):
            result = InventoryMapper.get_available_concepts("servers")

        self.assertIn("name", result)
        self.assertIn("environment", result)
        self.assertIn("engine_type", result)

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_no_mapper_returns_defaults(self, _mock_corr):
        """When mapper returns None → fallback to defaults."""
        mock_service = self._make_mock_service(None)

        with patch("inventory.services.InventoryService", return_value=mock_service):
            result = InventoryMapper.get_available_concepts("servers")

        self.assertEqual(result, ["name", "environment", "type"])

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_flat_table_mapper_returns_defaults(self, _mock_corr):
        """When mapper is_multi_table=False (flat) → fallback to defaults."""
        flat_config = {
            "flat_table": {
                "table": "INVENTORY",
                "columns": {"name": "NAME"},
            }
        }
        mock_mapper = InventoryMapper(flat_config)
        mock_service = self._make_mock_service(mock_mapper)

        with patch("inventory.services.InventoryService", return_value=mock_service):
            result = InventoryMapper.get_available_concepts("servers")

        self.assertEqual(result, ["name", "environment", "type"])

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_entity_not_found_returns_defaults(self, _mock_corr):
        """When entity 'databases' not in config → fallback to defaults."""
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "id_column": "ID",
                    "columns": {"name": "NAME"},
                }
            }
        }
        mock_mapper = InventoryMapper(config)
        mock_service = self._make_mock_service(mock_mapper)

        with patch("inventory.services.InventoryService", return_value=mock_service):
            result = InventoryMapper.get_available_concepts("databases")

        self.assertEqual(result, ["name", "environment", "type"])


# ---------------------------------------------------------------------------
# validate_config — invalid id_column (lines 392-393)
# ---------------------------------------------------------------------------

class TestValidateConfigIdColumnInvalid(TestCase):
    """Lines 392-393: invalid id_column in entity triggers error in validate_config."""

    def test_invalid_id_column_reported_in_validate(self):
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "id_column": "'; DROP TABLE --",  # invalid
                    "columns": {"name": "NAME"},
                }
            }
        }
        mapper = InventoryMapper(config)
        with patch("inventory.mapper.get_correlation_id", return_value="test"):
            errors = mapper.validate_config()
        self.assertTrue(any("id_column" in e for e in errors))
        self.assertTrue(any("Invalid column name" in e for e in errors))


# ---------------------------------------------------------------------------
# validate_config — flat_table invalid table and column names (lines 406-407, 416-417)
# ---------------------------------------------------------------------------

class TestValidateConfigFlatTableInvalidNames(TestCase):
    """Lines 406-407: invalid flat_table table name; lines 416-417: invalid column name."""

    def test_flat_table_invalid_table_name(self):
        config = {
            "flat_table": {
                "table": "'; DROP TABLE --",  # invalid
                "columns": {"name": "NAME"},
            }
        }
        mapper = InventoryMapper(config)
        with patch("inventory.mapper.get_correlation_id", return_value="test"):
            errors = mapper.validate_config()
        self.assertTrue(any("Invalid table name" in e for e in errors))

    def test_flat_table_invalid_column_name(self):
        config = {
            "flat_table": {
                "table": "INVENTORY",
                "columns": {"name": "'; DROP TABLE --"},  # invalid column
            }
        }
        mapper = InventoryMapper(config)
        with patch("inventory.mapper.get_correlation_id", return_value="test"):
            errors = mapper.validate_config()
        self.assertTrue(any("Invalid column name" in e for e in errors))


# ---------------------------------------------------------------------------
# _validate_table_name — name too long (lines 449-457)
# ---------------------------------------------------------------------------

class TestValidateTableNameTooLong(TestCase):
    """Lines 449-457: table or schema part longer than 30 characters raises."""

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_table_name_part_too_long_raises(self, _mock_corr):
        long_name = "A" * 31  # 31 chars, exceeds Oracle 30-char limit
        with self.assertRaises(MapperValidationError) as ctx:
            _validate_table_name(long_name)
        self.assertIn("exceeds Oracle 30 character limit", str(ctx.exception))

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_schema_part_too_long_raises(self, _mock_corr):
        long_schema = "S" * 31
        table_name = f"{long_schema}.TABLE"
        with self.assertRaises(MapperValidationError) as ctx:
            _validate_table_name(table_name)
        self.assertIn("exceeds Oracle 30 character limit", str(ctx.exception))

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_table_part_too_long_with_schema_raises(self, _mock_corr):
        long_table = "T" * 31
        table_name = f"SCHEMA.{long_table}"
        with self.assertRaises(MapperValidationError) as ctx:
            _validate_table_name(table_name)
        self.assertIn("exceeds Oracle 30 character limit", str(ctx.exception))

    def test_exactly_30_chars_is_valid(self):
        name = "A" * 30  # exactly 30 chars — valid
        _validate_table_name(name)  # Should not raise


# ---------------------------------------------------------------------------
# _validate_column_name — name too long (lines 486-493)
# ---------------------------------------------------------------------------

class TestValidateColumnNameTooLong(TestCase):
    """Lines 486-493: column name longer than 30 chars raises."""

    @patch("inventory.mapper.get_correlation_id", return_value="test-corr")
    def test_column_name_too_long_raises(self, _mock_corr):
        long_col = "C" * 31  # 31 chars
        with self.assertRaises(MapperValidationError) as ctx:
            _validate_column_name(long_col)
        self.assertIn("exceeds Oracle 30 character limit", str(ctx.exception))

    def test_exactly_30_chars_is_valid(self):
        col = "C" * 30  # exactly 30 chars — valid
        _validate_column_name(col)  # Should not raise
