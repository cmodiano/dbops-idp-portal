"""
Tests for InventoryService multi-table public methods.
Story 23.2 — list_servers, list_instances, list_databases, list_targets_for_user adaptation.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from integrations.models import Integration, IntegrationType
from inventory.services import (
    InventoryService,
    InventoryServiceError,
    MAX_MULTI_TABLE_RESULTS,
)


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


def _setup_mock_cursor(mock_conn, description, rows):
    """Helper to set up mock cursor for Oracle queries."""
    mock_cursor = MagicMock()
    mock_cursor.description = description
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


def _setup_flat_mock_cursor(mock_conn, count, rows):
    """Helper to set up mock cursor for flat table queries (count + data)."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (count,)
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_cursor


# ---- AC1: list_servers ----

class ListServersTests(TestCase):
    """Tests for list_servers (AC1)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    def test_list_servers_requires_environment(self):
        """AC1: environment is required."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_servers(environment='')
        self.assertIn("environment is required", str(ctx.exception))

    def test_list_servers_requires_non_whitespace_environment(self):
        """AC1: whitespace-only environment is rejected."""
        with self.assertRaises(ValueError):
            self.service.list_servers(environment='   ')

    @patch('inventory.services.connection')
    def test_list_servers_multi_table(self, mock_conn):
        """AC1: Returns servers from multi-table config."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [
            (1, 'srv-oracle-01', 'production', 'Oracle'),
            (2, 'srv-sql-01', 'production', 'SQL Server'),
        ])

        results = self.service.list_servers(environment='production')

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'srv-oracle-01')
        self.assertEqual(results[0]['environment'], 'production')
        self.assertEqual(results[0]['engine_type'], 'Oracle')

    @patch('inventory.services.connection')
    def test_list_servers_with_engine_type_filter(self, mock_conn):
        """AC1: Filters by engine_type when provided."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [
            (1, 'srv-oracle-01', 'production', 'Oracle'),
        ])

        results = self.service.list_servers(environment='production', engine_type='Oracle')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['engine_type'], 'Oracle')

    @patch('inventory.services.connection')
    def test_list_servers_flat_fallback(self, mock_conn):
        """AC1: Falls back to flat table when no entities.servers."""
        self._create_inventory_db(FLAT_TABLE_CONFIG)
        _setup_flat_mock_cursor(mock_conn, 2, [
            ('fallback-srv-01', 'production', 'server'),
            ('fallback-srv-02', 'production', 'server'),
        ])

        results = self.service.list_servers(environment='production')

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'fallback-srv-01')
        self.assertIsNone(results[0].get('engine_type'))

    @patch('inventory.services.connection')
    def test_list_servers_logs_operation(self, mock_conn):
        """AC1: Logs operation with correlation_id."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [(1, 'srv-01', 'production', 'Oracle')])

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_servers(environment='production')
            # Check that inventory_list_servers was logged
            calls = [c for c in mock_logger.info.call_args_list
                     if c[0][0] == 'inventory_list_servers']
            self.assertEqual(len(calls), 1)
            kwargs = calls[0][1]
            self.assertEqual(kwargs['environment'], 'production')
            self.assertEqual(kwargs['nb_results'], 1)

    @patch('inventory.services.connection')
    def test_list_servers_result_limit_warning(self, mock_conn):
        """AC7: Logs warning when result count hits MAX_MULTI_TABLE_RESULTS."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        # Generate exactly MAX_MULTI_TABLE_RESULTS results
        rows = [(i, f'srv-{i}', 'production', 'Oracle') for i in range(MAX_MULTI_TABLE_RESULTS)]
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], rows)

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_servers(environment='production')
            warning_calls = [c for c in mock_logger.warning.call_args_list
                           if c[0][0] == 'inventory_result_limit_reached']
            self.assertEqual(len(warning_calls), 1)
            self.assertEqual(warning_calls[0][1]['entity'], 'servers')


# ---- AC2: list_instances ----

class ListInstancesTests(TestCase):
    """Tests for list_instances (AC2)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    def test_list_instances_requires_environment(self):
        """AC2: environment is required."""
        with self.assertRaises(ValueError):
            self.service.list_instances(environment='')

    def test_list_instances_rejects_both_server_params(self):
        """AC2: Cannot specify both server_name and server_names."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_instances(
                environment='production',
                server_name='srv-01',
                server_names=['srv-01', 'srv-02']
            )
        self.assertIn("Cannot specify both", str(ctx.exception))

    def test_list_instances_rejects_empty_server_names(self):
        """AC2: Empty server_names list is rejected (likely caller error)."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_instances(environment='production', server_names=[])
        self.assertIn("cannot be empty", str(ctx.exception))

    @patch('inventory.services.connection')
    def test_list_instances_without_server_filter(self, mock_conn):
        """AC2: Returns all instances for environment."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [
            (1, 'inst-01', 'production', 'srv-01', 'db-01'),
            (2, 'inst-02', 'production', 'srv-02', 'db-02'),
        ])

        results = self.service.list_instances(environment='production')

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'inst-01')
        self.assertEqual(results[0]['server_ref'], 'srv-01')

    @patch('inventory.services.connection')
    def test_list_instances_with_server_name(self, mock_conn):
        """AC2: Filters by single server_name."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [
            (1, 'inst-01', 'production', 'srv-01', 'db-01'),
        ])

        results = self.service.list_instances(environment='production', server_name='srv-01')

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['server_ref'], 'srv-01')

    @patch('inventory.services.connection')
    def test_list_instances_with_server_names(self, mock_conn):
        """AC2: Filters by multiple server_names using optimized IN clause."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        # Optimized version uses single query with IN clause
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [
            (1, 'inst-01', 'production', 'srv-01', 'db-01'),
            (2, 'inst-02', 'production', 'srv-02', 'db-02'),
        ])

        results = self.service.list_instances(
            environment='production', server_names=['srv-01', 'srv-02']
        )

        self.assertEqual(len(results), 2)
        names = {r['name'] for r in results}
        self.assertEqual(names, {'inst-01', 'inst-02'})

    @patch('inventory.services.connection')
    def test_list_instances_server_names_deduplicates(self, mock_conn):
        """AC2: server_names query uses DISTINCT in SQL to avoid duplicates."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        # Single query returns deduplicated results
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [
            (1, 'inst-shared', 'production', 'srv-01', 'db-01'),
        ])

        results = self.service.list_instances(
            environment='production', server_names=['srv-01', 'srv-02']
        )

        self.assertEqual(len(results), 1)

    def test_list_instances_flat_fallback_returns_empty(self):
        """AC2: Flat table mode returns empty list for instances."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(FLAT_TABLE_CONFIG),
        )
        results = self.service.list_instances(environment='production')
        self.assertEqual(results, [])

    @patch('inventory.services.connection')
    def test_list_instances_logs_operation(self, mock_conn):
        """AC2: Logs operation with correlation_id and nb instances."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [(1, 'inst-01', 'production', 'srv-01', 'db-01')])

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_instances(environment='production', server_name='srv-01')
            calls = [c for c in mock_logger.info.call_args_list
                     if c[0][0] == 'inventory_list_instances']
            self.assertEqual(len(calls), 1)
            kwargs = calls[0][1]
            self.assertEqual(kwargs['environment'], 'production')
            self.assertEqual(kwargs['server_filter'], 'srv-01')
            self.assertEqual(kwargs['nb_results'], 1)


# ---- AC3: list_databases ----

class ListDatabasesTests(TestCase):
    """Tests for list_databases (AC3)."""

    def setUp(self):
        self.service = InventoryService()

    def _create_inventory_db(self, config):
        return Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(config),
        )

    def test_list_databases_requires_environment(self):
        """AC3: environment is required."""
        with self.assertRaises(ValueError):
            self.service.list_databases(environment='')

    def test_list_databases_rejects_both_server_params(self):
        """AC3: Cannot specify both server_name and server_names."""
        with self.assertRaises(ValueError):
            self.service.list_databases(
                environment='production',
                server_name='srv-01',
                server_names=['srv-01']
            )

    def test_list_databases_rejects_empty_server_names(self):
        """AC3: Empty server_names list is rejected (likely caller error)."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_databases(environment='production', server_names=[])
        self.assertIn("cannot be empty", str(ctx.exception))

    @patch('inventory.services.connection')
    def test_list_databases_without_server_filter(self, mock_conn):
        """AC3: Returns all databases for environment."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',),
        ], [
            (1, 'ORCL_PROD', 'production'),
            (2, 'MYDB_PROD', 'production'),
        ])

        results = self.service.list_databases(environment='production')

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'ORCL_PROD')

    @patch('inventory.services.connection')
    def test_list_databases_with_server_name_joins_instances(self, mock_conn):
        """AC3: Filters databases via instance JOIN when server_name provided."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        mock_cursor = _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',),
        ], [
            (1, 'DB_01', 'production'),
        ])

        results = self.service.list_databases(environment='production', server_name='srv-01')

        self.assertEqual(len(results), 1)
        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('INNER JOIN', sql)
        self.assertIn('DBOPS_INSTANCES', sql)

    @patch('inventory.services.connection')
    def test_list_databases_with_server_names(self, mock_conn):
        """AC3: Filters by multiple server_names using optimized IN clause."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        # Optimized version uses single query with IN clause
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',)
        ], [
            (1, 'DB_01', 'production'),
            (2, 'DB_02', 'production'),
        ])

        results = self.service.list_databases(
            environment='production', server_names=['srv-01', 'srv-02']
        )

        self.assertEqual(len(results), 2)

    def test_list_databases_flat_fallback_returns_empty(self):
        """AC3: Flat table mode returns empty list for databases."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config=json.dumps(FLAT_TABLE_CONFIG),
        )
        results = self.service.list_databases(environment='production')
        self.assertEqual(results, [])

    @patch('inventory.services.connection')
    def test_list_databases_logs_operation(self, mock_conn):
        """AC3: Logs operation with correlation_id and nb databases."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',),
        ], [(1, 'ORCL_PROD', 'production')])

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_databases(environment='production')
            calls = [c for c in mock_logger.info.call_args_list
                     if c[0][0] == 'inventory_list_databases']
            self.assertEqual(len(calls), 1)


# ---- AC4: list_targets_for_user with multi-tables ----

class ListTargetsForUserMultiTableTests(TestCase):
    """Tests for list_targets_for_user multi-table adaptation (AC4)."""

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
    @patch('inventory.services.Profile.objects')
    def test_list_targets_uses_list_servers_when_multi_table(self, mock_profiles, mock_conn):
        """AC4: Uses list_servers instead of list_targets when multi-table config active."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        # Mock profiles with target permissions
        mock_profile = MagicMock()
        mock_profile.is_admin = 1
        mock_action_perm = MagicMock()
        mock_action_perm.get_environments.return_value = ['production']
        mock_profile.profileactionpermission = mock_action_perm
        mock_target_perm = MagicMock()
        mock_target_perm.permission_type = 'ALL'
        mock_profile.profiletargetpermission = mock_target_perm

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profiles.find_by_ad_groups.return_value = mock_qs

        # Mock cursor for list_servers
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [
            (1, 'srv-prod-01', 'production', 'Oracle'),
            (2, 'srv-prod-02', 'production', 'SQL Server'),
        ])

        results, total, rbac_truncated = self.service.list_targets_for_user(
            user_id=1, ad_groups=['DBA_TEAM'], environment='production'
        )

        self.assertEqual(total, 2)
        self.assertFalse(rbac_truncated)
        self.assertEqual(results[0]['target_type'], 'server')

    @patch('inventory.services.connection')
    @patch('inventory.services.Profile.objects')
    def test_list_targets_falls_back_to_legacy_without_multi_table(self, mock_profiles, mock_conn):
        """AC4: Falls back to list_targets when no multi-table config."""
        self._create_inventory_db(FLAT_TABLE_CONFIG)

        mock_profile = MagicMock()
        mock_profile.is_admin = 1
        mock_action_perm = MagicMock()
        mock_action_perm.get_environments.return_value = ['production']
        mock_profile.profileactionpermission = mock_action_perm
        mock_target_perm = MagicMock()
        mock_target_perm.permission_type = 'ALL'
        mock_profile.profiletargetpermission = mock_target_perm

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profiles.find_by_ad_groups.return_value = mock_qs

        # Mock cursor for legacy path (count + data)
        _setup_flat_mock_cursor(mock_conn, 1, [
            ('srv-01', 'production', 'server'),
        ])

        results, total, rbac_truncated = self.service.list_targets_for_user(
            user_id=1, ad_groups=['DBA_TEAM'], environment='production'
        )

        self.assertEqual(total, 1)

    @patch('inventory.services.connection')
    @patch('inventory.services.Profile.objects')
    def test_list_targets_multi_table_applies_rbac_filters(self, mock_profiles, mock_conn):
        """AC4: RBAC filters (LIST, PATTERN) still applied on multi-table servers."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_profile = MagicMock()
        mock_profile.is_admin = 0
        mock_action_perm = MagicMock()
        mock_action_perm.get_environments.return_value = ['production']
        mock_profile.profileactionpermission = mock_action_perm
        mock_target_perm = MagicMock()
        mock_target_perm.permission_type = 'LIST'
        mock_target_perm.get_target_names.return_value = ['srv-prod-01']
        mock_target_perm.get_target_patterns.return_value = None
        mock_profile.profiletargetpermission = mock_target_perm

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profiles.find_by_ad_groups.return_value = mock_qs

        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [
            (1, 'srv-prod-01', 'production', 'Oracle'),
            (2, 'srv-prod-02', 'production', 'SQL Server'),
        ])

        results, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['DBA_TEAM'], environment='production'
        )

        # Only srv-prod-01 allowed by LIST restriction
        self.assertEqual(total, 1)
        self.assertEqual(results[0]['name'], 'srv-prod-01')

    @patch('inventory.services.Profile.objects')
    def test_list_targets_no_profiles_returns_empty(self, mock_profiles):
        """AC4: No profiles returns empty result."""
        mock_qs = MagicMock()
        mock_qs.exists.return_value = False
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profiles.find_by_ad_groups.return_value = mock_qs

        results, total, truncated = self.service.list_targets_for_user(
            user_id=1, ad_groups=['UNKNOWN_GROUP']
        )

        self.assertEqual(results, [])
        self.assertEqual(total, 0)
        self.assertFalse(truncated)

    @patch('inventory.services.connection')
    @patch('inventory.services.Profile.objects')
    def test_list_targets_multi_table_all_envs_fail_raises_error(self, mock_profiles, mock_conn):
        """AC4: If all environments fail in multi-table mode, raises error instead of silent empty."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_profile = MagicMock()
        mock_profile.is_admin = 1
        mock_action_perm = MagicMock()
        mock_action_perm.get_environments.return_value = ['production', 'certification']
        mock_profile.profileactionpermission = mock_action_perm
        mock_target_perm = MagicMock()
        mock_target_perm.permission_type = 'ALL'
        mock_profile.profiletargetpermission = mock_target_perm

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profiles.find_by_ad_groups.return_value = mock_qs

        # Make all list_servers calls fail
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("ORA-00942: table does not exist")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        from inventory.services import InventoryServiceError
        with self.assertRaises(InventoryServiceError) as ctx:
            self.service.list_targets_for_user(user_id=1, ad_groups=['DBA_TEAM'])

        self.assertIn("all", str(ctx.exception).lower())
        self.assertIn("environments", str(ctx.exception).lower())


# ---- AC6: Error handling ----

class ErrorHandlingTests(TestCase):
    """Tests for error handling across all methods (AC6)."""

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
    def test_list_servers_invalid_config_raises(self, mock_conn):
        """AC6: Invalid config raises InventoryServiceError."""
        bad_config = {
            "entities": {
                "servers": {
                    "table": "DROP TABLE; --",
                    "id_column": "ID",
                    "columns": {"name": "NAME", "environment": "ENV"},
                },
            },
        }
        self._create_inventory_db(bad_config)

        with self.assertRaises(InventoryServiceError):
            self.service.list_servers(environment='production')

    @patch('inventory.services.connection')
    def test_list_servers_db_error_raises(self, mock_conn):
        """AC6: Database error raises InventoryServiceError."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("ORA-00942: table does not exist")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError):
            self.service.list_servers(environment='production')

    @patch('inventory.services.connection')
    def test_list_instances_db_error_raises(self, mock_conn):
        """AC6: Database error in instances raises InventoryServiceError."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("ORA-00942")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError):
            self.service.list_instances(environment='production')

    @patch('inventory.services.connection')
    def test_list_databases_db_error_raises(self, mock_conn):
        """AC6: Database error in databases raises InventoryServiceError."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("ORA-00942")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError):
            self.service.list_databases(environment='production')

    @patch('inventory.services.connection')
    def test_list_servers_error_logs_with_correlation_id(self, mock_conn):
        """AC6: Errors are logged with correlation_id."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Connection lost")
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch('inventory.services.logger') as mock_logger:
            with self.assertRaises(InventoryServiceError):
                self.service.list_servers(environment='production')

            error_calls = [c for c in mock_logger.error.call_args_list]
            self.assertTrue(len(error_calls) > 0)

    @patch('inventory.services.connection')
    def test_error_message_no_sql_details(self, mock_conn):
        """AC6: Error messages don't expose SQL details."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception(
            "ORA-00942: SELECT * FROM DBOPS_SERVERS WHERE ENV='prod'"
        )
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with self.assertRaises(InventoryServiceError):
            self.service.list_servers(environment='production')


# ---- AC5: RBAC documentation (verified in docstrings) ----

class RbacDocumentationTests(TestCase):
    """Tests for RBAC documentation presence (AC5)."""

    def test_list_instances_docstring_mentions_no_rbac(self):
        """AC5: list_instances docstring documents no RBAC filtering."""
        self.assertIn("NO RBAC FILTERING", InventoryService.list_instances.__doc__)

    def test_list_databases_docstring_mentions_no_rbac(self):
        """AC5: list_databases docstring documents no RBAC filtering."""
        self.assertIn("NO RBAC FILTERING", InventoryService.list_databases.__doc__)

    def test_list_instances_docstring_mentions_caller_responsibility(self):
        """AC5: list_instances docstring documents caller responsibility."""
        doc = InventoryService.list_instances.__doc__
        self.assertIn("caller", doc.lower())
        self.assertIn("validate", doc.lower())

    def test_list_databases_docstring_mentions_caller_responsibility(self):
        """AC5: list_databases docstring documents caller responsibility."""
        doc = InventoryService.list_databases.__doc__
        self.assertIn("caller", doc.lower())


# ---- AC7: Performance limits ----

class PerformanceLimitsTests(TestCase):
    """Tests for performance limits (AC7)."""

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
    def test_list_instances_result_limit_warning(self, mock_conn):
        """AC7: Logs warning when instances hit MAX_MULTI_TABLE_RESULTS."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        rows = [(i, f'inst-{i}', 'production', f'srv-{i}', f'db-{i}')
                for i in range(MAX_MULTI_TABLE_RESULTS)]
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], rows)

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_instances(environment='production')
            warning_calls = [c for c in mock_logger.warning.call_args_list
                           if c[0][0] == 'inventory_result_limit_reached']
            self.assertEqual(len(warning_calls), 1)
            self.assertEqual(warning_calls[0][1]['entity'], 'instances')

    @patch('inventory.services.connection')
    def test_list_databases_result_limit_warning(self, mock_conn):
        """AC7: Logs warning when databases hit MAX_MULTI_TABLE_RESULTS."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        rows = [(i, f'db-{i}', 'production') for i in range(MAX_MULTI_TABLE_RESULTS)]
        _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',),
        ], rows)

        with patch('inventory.services.logger') as mock_logger:
            self.service.list_databases(environment='production')
            warning_calls = [c for c in mock_logger.warning.call_args_list
                           if c[0][0] == 'inventory_result_limit_reached']
            self.assertEqual(len(warning_calls), 1)
            self.assertEqual(warning_calls[0][1]['entity'], 'databases')

    @patch('inventory.services.connection')
    def test_sql_uses_rownum_limit(self, mock_conn):
        """AC7: Underlying SQL uses ROWNUM limit from story 23.1."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)
        mock_cursor = _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('ENGINE_TYPE',),
        ], [])

        self.service.list_servers(environment='production')

        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('ROWNUM', sql)
        self.assertIn(str(MAX_MULTI_TABLE_RESULTS), sql)

    @patch('inventory.services.connection')
    def test_no_n_plus_one_queries_server_names(self, mock_conn):
        """AC7: server_names uses optimized IN clause - single query instead of N+1."""
        self._create_inventory_db(MULTI_TABLE_CONFIG)

        mock_cursor = _setup_mock_cursor(mock_conn, [
            ('ID',), ('NAME',), ('ENVIRONMENT',), ('SERVER_REF',), ('DB_REF',),
        ], [
            (1, 'inst-1', 'production', 'srv-01', 'db-01'),
            (2, 'inst-2', 'production', 'srv-02', 'db-02'),
        ])

        results = self.service.list_instances(
            environment='production', server_names=['srv-01', 'srv-02']
        )

        # Only 1 query with IN clause (not N queries for N servers)
        self.assertEqual(mock_cursor.execute.call_count, 1)
        self.assertEqual(len(results), 2)

        # Verify SQL contains IN clause
        sql = mock_cursor.execute.call_args[0][0]
        self.assertIn('IN (', sql.upper())
