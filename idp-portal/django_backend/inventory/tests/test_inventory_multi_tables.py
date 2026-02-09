"""
Tests for InventoryService multi-table entity reading.
Story 23.1 AC3-AC6, AC8 — Config-driven servers, instances, databases + fallback.
"""

import json
from unittest.mock import patch, MagicMock, call

from django.test import TestCase

from integrations.models import Integration, IntegrationType
from inventory.services import InventoryService, InventoryServiceError


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


class ReadServersFromConfigTests(TestCase):
    """Tests for _read_servers_from_config (AC3)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    @patch('inventory.services.connection')
    def test_read_servers_multi_table(self, mock_conn):
        """AC3: Read servers using mapped table/columns."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'srv-oracle-01', 'prod', 'Oracle'),
            (2, 'srv-sql-01', 'dev', 'SQL Server'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_servers_from_config()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'srv-oracle-01')
        self.assertEqual(results[0]['environment'], 'prod')
        self.assertEqual(results[0]['engine_type'], 'Oracle')

        # Verify SQL contains mapped column names
        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('DBOPS_SERVERS', sql)
        self.assertIn('HOSTNAME AS name', sql)
        self.assertIn('ENV AS environment', sql)
        self.assertIn('ENGINE AS engine_type', sql)

    @patch('inventory.services.connection')
    def test_read_servers_with_environment_filter(self, mock_conn):
        """AC3: Filter servers by environment using mapped column."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'srv-prod-01', 'prod', 'Oracle'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_servers_from_config(environment='prod')

        self.assertEqual(len(results), 1)
        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('UPPER(ENV)', sql)
        params = mock_cursor.execute.call_args[0][1]
        self.assertEqual(params['p_environment'], 'prod')

    @patch('inventory.services.connection')
    def test_read_servers_with_engine_type_filter(self, mock_conn):
        """AC3: Filter servers by engine_type using mapped column."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'srv-oracle-01', 'prod', 'Oracle'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_servers_from_config(engine_type='Oracle')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('UPPER(ENGINE)', sql)
        params = mock_cursor.execute.call_args[0][1]
        self.assertEqual(params['p_engine_type'], 'Oracle')

    @patch('inventory.services.connection')
    def test_read_servers_flat_fallback(self, mock_conn):
        """AC6: Fallback to flat table when no entities.servers."""
        self._create_inventory_db(FLAT_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('fallback-srv-01', 'dev', 'server'),
            ('fallback-srv-02', 'prod', 'server'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_servers_from_config()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'fallback-srv-01')
        self.assertEqual(results[0]['id'], 'fallback-srv-01')
        self.assertIsNone(results[0].get('engine_type'))

    def test_read_servers_no_integration(self):
        """AC6: No inventory integration returns empty via flat fallback."""
        # No integration exists → mapper is None → flat fallback with DBOPS_INVENTORY
        with patch('inventory.services.connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,)
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            results = self.service._read_servers_from_config()
            self.assertEqual(results, [])


class ReadInstancesFromConfigTests(TestCase):
    """Tests for _read_instances_from_config (AC4)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    @patch('inventory.services.connection')
    def test_read_instances_multi_table(self, mock_conn):
        """AC4: Read instances using mapped table/columns."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'inst-01', 'prod', 'srv-01', 'db-01'),
            (2, 'inst-02', 'prod', 'srv-01', 'db-02'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_instances_from_config()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'inst-01')
        self.assertEqual(results[0]['server_ref'], 'srv-01')
        self.assertEqual(results[0]['db_ref'], 'db-01')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('DBOPS_INSTANCES', sql)
        self.assertIn('INSTANCE_NAME AS name', sql)
        self.assertIn('SERVER_NAME AS server_ref', sql)

    @patch('inventory.services.connection')
    def test_read_instances_with_server_filter(self, mock_conn):
        """AC4: Filter instances by server_name via server_ref mapped column."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ]
        mock_cursor.fetchall.return_value = [
            (1, 'inst-01', 'prod', 'srv-01', 'db-01'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_instances_from_config(server_name='srv-01')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('UPPER(SERVER_NAME)', sql)
        params = mock_cursor.execute.call_args[0][1]
        self.assertEqual(params['p_server_ref'], 'srv-01')

    @patch('inventory.services.connection')
    def test_read_instances_with_environment_filter(self, mock_conn):
        """AC4: Filter instances by environment."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ]
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        self.service._read_instances_from_config(environment='prod', server_name='srv-01')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('UPPER(ENV)', sql)
        self.assertIn('UPPER(SERVER_NAME)', sql)

    def test_read_instances_flat_fallback_returns_empty(self):
        """AC6: Flat table mode returns empty list for instances."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(FLAT_TABLE_CONFIG),
        )
        results = self.service._read_instances_from_config()
        self.assertEqual(results, [])

    def test_read_instances_no_integration_returns_empty(self):
        """No integration returns empty list."""
        results = self.service._read_instances_from_config()
        self.assertEqual(results, [])


class ReadDatabasesFromConfigTests(TestCase):
    """Tests for _read_databases_from_config (AC5)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    @patch('inventory.services.connection')
    def test_read_databases_multi_table(self, mock_conn):
        """AC5: Read databases using mapped table/columns."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',), ('ENVIRONMENT',)]
        mock_cursor.fetchall.return_value = [
            (1, 'ORCL_PROD', 'prod'),
            (2, 'ORCL_DEV', 'dev'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_databases_from_config()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'ORCL_PROD')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('DBOPS_DATABASES', sql)
        self.assertIn('DB_NAME AS name', sql)

    @patch('inventory.services.connection')
    def test_read_databases_with_environment_filter(self, mock_conn):
        """AC5: Filter databases by environment."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',), ('ENVIRONMENT',)]
        mock_cursor.fetchall.return_value = [
            (1, 'ORCL_PROD', 'prod'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_databases_from_config(environment='prod')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('UPPER(ENV)', sql)
        params = mock_cursor.execute.call_args[0][1]
        self.assertEqual(params['p_environment'], 'prod')

    @patch('inventory.services.connection')
    def test_read_databases_with_server_filter_joins_instances(self, mock_conn):
        """AC5: Filter databases via instance join when server_name provided."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',), ('ENVIRONMENT',)]
        mock_cursor.fetchall.return_value = [
            (1, 'DB_01', 'prod'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._read_databases_from_config(
            environment='prod', server_name='srv-01'
        )

        sql = mock_cursor.execute.call_args[0][0]
        # Should have INNER JOIN with instances
        self.assertIn('INNER JOIN', sql)
        self.assertIn('DBOPS_INSTANCES', sql)
        self.assertIn('DBOPS_DATABASES', sql)
        self.assertIn('DB_NAME', sql)
        self.assertIn('SERVER_NAME', sql)
        params = mock_cursor.execute.call_args[0][1]
        self.assertEqual(params['p_server_name'], 'srv-01')

    def test_read_databases_flat_fallback_returns_empty(self):
        """AC6: Flat table mode returns empty list for databases."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(FLAT_TABLE_CONFIG),
        )
        results = self.service._read_databases_from_config()
        self.assertEqual(results, [])

    def test_read_databases_no_integration_returns_empty(self):
        """No integration returns empty list."""
        results = self.service._read_databases_from_config()
        self.assertEqual(results, [])


class InventoryMapperIntegrationInServiceTests(TestCase):
    """Tests for _get_inventory_mapper helper and error handling."""

    def setUp(self):
        self.service = InventoryService()

    def test_get_inventory_mapper_returns_none_no_integration(self):
        mapper = self.service._get_inventory_mapper()
        self.assertIsNone(mapper)

    def test_get_inventory_mapper_returns_mapper(self):
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(MULTI_TABLE_CONFIG),
        )
        mapper = self.service._get_inventory_mapper()
        self.assertIsNotNone(mapper)
        self.assertTrue(mapper.is_multi_table)

    def test_get_inventory_mapper_empty_config(self):
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=None,
        )
        mapper = self.service._get_inventory_mapper()
        self.assertIsNotNone(mapper)
        self.assertFalse(mapper.is_multi_table)

    @patch('inventory.services.connection')
    def test_read_servers_invalid_config_raises(self, mock_conn):
        """Invalid table name in config raises InventoryServiceError."""
        bad_config = {
            "entities": {
                "servers": {
                    "table": "DROP TABLE; --",
                    "id_column": "ID",
                    "columns": {"name": "NAME", "environment": "ENV"},
                },
            },
        }
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(bad_config),
        )
        with self.assertRaises(InventoryServiceError) as ctx:
            self.service._read_servers_from_config()
        self.assertIn("mapping config error", str(ctx.exception))

    @patch('inventory.services.connection')
    def test_read_servers_db_error_raises(self, mock_conn):
        """Database error during query raises InventoryServiceError."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(MULTI_TABLE_CONFIG),
        )

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("ORA-00942: table does not exist")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError) as ctx:
            self.service._read_servers_from_config()
        self.assertIn("Failed to read servers", str(ctx.exception))


class ExecuteMappedQueryTests(TestCase):
    """Tests for _execute_mapped_query helper."""

    def setUp(self):
        self.service = InventoryService()

    @patch('inventory.services.connection')
    def test_execute_mapped_query_returns_dicts(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',), ('ENV',)]
        mock_cursor.fetchall.return_value = [
            (1, 'srv-01', 'prod'),
            (2, 'srv-02', 'dev'),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._execute_mapped_query("SELECT ...", {})

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {'id': 1, 'name': 'srv-01', 'env': 'prod'})

    @patch('inventory.services.connection')
    def test_execute_mapped_query_empty_results(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('NAME',)]
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        results = self.service._execute_mapped_query("SELECT ...", {})
        self.assertEqual(results, [])

    @patch('inventory.services.connection')
    def test_execute_mapped_query_db_error(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB connection lost")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError) as ctx:
            self.service._execute_mapped_query("SELECT ...", {})
        self.assertIn("Query execution failed", str(ctx.exception))
