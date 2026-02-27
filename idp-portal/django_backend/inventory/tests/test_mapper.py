"""
Tests for InventoryMapper.
Story 23.1 AC2, AC7, AC8 — Config parsing, SQL building, security validation.
"""

from unittest.mock import patch
from django.test import TestCase

from inventory.mapper import (
    InventoryMapper,
    MapperValidationError,
    SAFE_TABLE_NAME_PATTERN,
    SAFE_COLUMN_NAME_PATTERN,
    _validate_table_name,
    _validate_column_name,
)


# -- Sample configs for tests --

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
                "environment": "ENV",
                "server_ref": "SERVER_NAME",
                "db_ref": "DB_NAME",
            },
        },
        "databases": {
            "table": "DBOPS_DATABASES",
            "id_column": "DB_ID",
            "columns": {
                "name": "DB_NAME",
                "environment": "ENV",
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


class InventoryMapperMultiTableTests(TestCase):
    """Tests for InventoryMapper with multi-table config."""

    def setUp(self):
        self.mapper = InventoryMapper(MULTI_TABLE_CONFIG)

    def test_is_multi_table(self):
        self.assertTrue(self.mapper.is_multi_table)
        self.assertFalse(self.mapper.is_flat_table)

    def test_get_entity_config_servers(self):
        config = self.mapper.get_entity_config('servers')
        self.assertIsNotNone(config)
        self.assertEqual(config['table'], 'DBOPS_SERVERS')
        self.assertEqual(config['id_column'], 'SERVER_ID')

    def test_get_entity_config_not_found(self):
        config = self.mapper.get_entity_config('nonexistent')
        self.assertIsNone(config)

    def test_get_table_name_servers(self):
        self.assertEqual(self.mapper.get_table_name('servers'), 'DBOPS_SERVERS')

    def test_get_table_name_instances(self):
        self.assertEqual(self.mapper.get_table_name('instances'), 'DBOPS_INSTANCES')

    def test_get_table_name_databases(self):
        self.assertEqual(self.mapper.get_table_name('databases'), 'DBOPS_DATABASES')

    def test_get_table_name_prepends_schema_when_configured(self):
        """When config has schema and entity table has no dot, prepend schema."""
        config_with_schema = {**MULTI_TABLE_CONFIG, 'schema': 'DBOPS_INVENTORY'}
        mapper = InventoryMapper(config_with_schema)
        self.assertEqual(mapper.get_table_name('servers'), 'DBOPS_INVENTORY.DBOPS_SERVERS')
        self.assertEqual(mapper.get_table_name('instances'), 'DBOPS_INVENTORY.DBOPS_INSTANCES')

    def test_get_table_name_does_not_prepend_when_table_has_schema(self):
        """When entity table already has schema prefix, do not double-prefix."""
        config = {
            'schema': 'OTHER_SCHEMA',
            'entities': {
                'servers': {'table': 'DBOPS_INVENTORY.DBOPS_SERVERS', 'id_column': 'ID', 'columns': {'name': 'N'}},
            },
        }
        mapper = InventoryMapper(config)
        self.assertEqual(mapper.get_table_name('servers'), 'DBOPS_INVENTORY.DBOPS_SERVERS')

    def test_get_table_name_not_configured(self):
        with self.assertRaises(MapperValidationError) as ctx:
            self.mapper.get_table_name('nonexistent')
        self.assertIn("not configured", str(ctx.exception))

    def test_get_column_servers_name(self):
        self.assertEqual(self.mapper.get_column('servers', 'name'), 'HOSTNAME')

    def test_get_column_servers_environment(self):
        self.assertEqual(self.mapper.get_column('servers', 'environment'), 'ENV')

    def test_get_column_instances_server_ref(self):
        self.assertEqual(self.mapper.get_column('instances', 'server_ref'), 'SERVER_NAME')

    def test_get_column_not_mapped(self):
        with self.assertRaises(MapperValidationError) as ctx:
            self.mapper.get_column('servers', 'nonexistent_concept')
        self.assertIn("not mapped", str(ctx.exception))

    def test_get_id_column(self):
        self.assertEqual(self.mapper.get_id_column('servers'), 'SERVER_ID')
        self.assertEqual(self.mapper.get_id_column('instances'), 'INSTANCE_ID')
        self.assertEqual(self.mapper.get_id_column('databases'), 'DB_ID')

    def test_build_select_clause_servers(self):
        select = self.mapper.build_select_clause('servers')
        # Should contain id column and mapped columns
        self.assertIn('SERVER_ID AS id', select)
        self.assertIn('HOSTNAME AS name', select)
        self.assertIn('ENV AS environment', select)
        self.assertIn('ENGINE AS engine_type', select)

    def test_build_select_clause_instances(self):
        select = self.mapper.build_select_clause('instances')
        self.assertIn('INSTANCE_ID AS id', select)
        self.assertIn('INSTANCE_NAME AS name', select)
        self.assertIn('SERVER_NAME AS server_ref', select)
        self.assertIn('DB_NAME AS db_ref', select)

    def test_build_where_clause_single_filter(self):
        where, params = self.mapper.build_where_clause('servers', {'environment': 'prod'})
        self.assertIn('UPPER(ENV)', where)
        self.assertIn(':p_environment', where)
        self.assertEqual(params['p_environment'], 'prod')

    def test_build_where_clause_multiple_filters(self):
        where, params = self.mapper.build_where_clause(
            'servers', {'environment': 'prod', 'engine_type': 'Oracle'}
        )
        self.assertIn('UPPER(ENV)', where)
        self.assertIn('UPPER(ENGINE)', where)
        self.assertEqual(params['p_environment'], 'prod')
        self.assertEqual(params['p_engine_type'], 'Oracle')

    def test_build_where_clause_no_filters(self):
        where, params = self.mapper.build_where_clause('servers', {})
        self.assertEqual(where, "")
        self.assertEqual(params, {})

    def test_build_where_clause_none_values_skipped(self):
        where, params = self.mapper.build_where_clause(
            'servers', {'environment': 'prod', 'engine_type': None}
        )
        self.assertIn('ENV', where)
        self.assertNotIn('ENGINE', where)
        self.assertNotIn('p_engine_type', params)

    def test_validate_config_multi_table_valid(self):
        errors = self.mapper.validate_config()
        self.assertEqual(errors, [])

    def test_build_select_clause_not_configured(self):
        with self.assertRaises(MapperValidationError):
            self.mapper.build_select_clause('nonexistent')


class InventoryMapperFlatTableTests(TestCase):
    """Tests for InventoryMapper with flat table config."""

    def setUp(self):
        self.mapper = InventoryMapper(FLAT_TABLE_CONFIG)

    def test_is_flat_table(self):
        self.assertTrue(self.mapper.is_flat_table)
        self.assertFalse(self.mapper.is_multi_table)

    def test_get_entity_config_returns_none(self):
        self.assertIsNone(self.mapper.get_entity_config('servers'))

    def test_validate_config_flat_table_valid(self):
        errors = self.mapper.validate_config()
        self.assertEqual(errors, [])


class InventoryMapperEmptyConfigTests(TestCase):
    """Tests for InventoryMapper with empty or None config."""

    def test_empty_config(self):
        mapper = InventoryMapper({})
        self.assertFalse(mapper.is_multi_table)
        self.assertFalse(mapper.is_flat_table)

    def test_none_config(self):
        mapper = InventoryMapper(None)
        self.assertFalse(mapper.is_multi_table)
        self.assertFalse(mapper.is_flat_table)

    def test_validate_empty_config(self):
        mapper = InventoryMapper({})
        errors = mapper.validate_config()
        self.assertEqual(len(errors), 1)
        self.assertIn("must define", errors[0])


class InventoryMapperValidationTests(TestCase):
    """Tests for config validation error cases."""

    def test_missing_table_in_entity(self):
        config = {
            "entities": {
                "servers": {
                    "columns": {"name": "HOSTNAME"},
                },
            },
        }
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("missing 'table'" in e for e in errors))

    def test_missing_columns_in_entity(self):
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                },
            },
        }
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("no 'columns'" in e for e in errors))

    def test_invalid_entity_config_not_dict(self):
        config = {"entities": {"servers": "invalid"}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("must be a dict" in e for e in errors))

    def test_invalid_table_name_in_entity(self):
        config = {
            "entities": {
                "servers": {
                    "table": "DROP TABLE; --",
                    "columns": {"name": "HOSTNAME"},
                },
            },
        }
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("Invalid table name" in e for e in errors))

    def test_invalid_column_name_in_entity(self):
        config = {
            "entities": {
                "servers": {
                    "table": "SERVERS",
                    "columns": {"name": "'; DROP TABLE --"},
                },
            },
        }
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("Invalid column name" in e for e in errors))

    def test_invalid_flat_table_not_dict(self):
        config = {"flat_table": "invalid"}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("must be a dict" in e for e in errors))

    def test_missing_table_in_flat(self):
        config = {"flat_table": {"columns": {"name": "NAME"}}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("missing 'table'" in e for e in errors))

    def test_missing_columns_in_flat(self):
        config = {"flat_table": {"table": "INVENTORY"}}
        mapper = InventoryMapper(config)
        errors = mapper.validate_config()
        self.assertTrue(any("no 'columns'" in e for e in errors))


class SafePatternValidationTests(TestCase):
    """Tests for SQL identifier validation patterns (AC7)."""

    # -- Table name pattern tests --

    def test_valid_table_names(self):
        valid_names = [
            'SERVERS', 'DBOPS_SERVERS', 'my_table', 'T1', '_temp',
            'SCHEMA.TABLE', 'dbo.Servers',
        ]
        for name in valid_names:
            self.assertTrue(
                SAFE_TABLE_NAME_PATTERN.match(name),
                f"Expected valid: {name}"
            )

    def test_invalid_table_names(self):
        invalid_names = [
            '1TABLE', ' SERVERS', 'SERVERS ', 'DROP TABLE;',
            "'; --", 'TABLE NAME', 'a b', '..TABLE',
        ]
        for name in invalid_names:
            self.assertFalse(
                SAFE_TABLE_NAME_PATTERN.match(name),
                f"Expected invalid: {name}"
            )
        # Empty string: match returns None (falsy)
        self.assertIsNone(SAFE_TABLE_NAME_PATTERN.match(''))

    # -- Column name pattern tests --

    def test_valid_column_names(self):
        valid_names = [
            'HOSTNAME', 'ENV', 'SERVER_ID', 'engine_type', 'col1', '_col',
        ]
        for name in valid_names:
            self.assertTrue(
                SAFE_COLUMN_NAME_PATTERN.match(name),
                f"Expected valid: {name}"
            )

    def test_invalid_column_names(self):
        invalid_names = [
            '1COL', ' COL', 'COL NAME', "'; DROP", 'a.b', 'col;',
        ]
        for name in invalid_names:
            self.assertFalse(
                SAFE_COLUMN_NAME_PATTERN.match(name),
                f"Expected invalid: {name}"
            )
        # Empty string: match returns None (falsy)
        self.assertIsNone(SAFE_COLUMN_NAME_PATTERN.match(''))

    # -- Validate functions tests (AC7: injection attempts) --

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_table_name_sql_injection(self, _):
        injection_attempts = [
            "SERVERS; DROP TABLE USERS",
            "'; DELETE FROM users; --",
            "SERVERS UNION SELECT * FROM passwords",
            "TABLE\nNAME",
            "TABLE'NAME",
        ]
        for attempt in injection_attempts:
            with self.assertRaises(MapperValidationError, msg=f"Should reject: {attempt}"):
                _validate_table_name(attempt)

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_column_name_sql_injection(self, _):
        injection_attempts = [
            "COL; DROP TABLE",
            "' OR '1'='1",
            "COL UNION SELECT",
            "COL\nNAME",
            "schema.col",
        ]
        for attempt in injection_attempts:
            with self.assertRaises(MapperValidationError, msg=f"Should reject: {attempt}"):
                _validate_column_name(attempt)

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_table_name_empty(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_table_name('')

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_table_name_none(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_table_name(None)

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_column_name_empty(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_column_name('')

    @patch('inventory.mapper.get_correlation_id', return_value='test-corr')
    def test_validate_column_name_none(self, _):
        with self.assertRaises(MapperValidationError):
            _validate_column_name(None)

    def test_validate_table_name_valid(self):
        # Should not raise
        _validate_table_name('MY_TABLE')
        _validate_table_name('SCHEMA.TABLE')

    def test_validate_column_name_valid(self):
        # Should not raise
        _validate_column_name('HOSTNAME')
        _validate_column_name('engine_type')
