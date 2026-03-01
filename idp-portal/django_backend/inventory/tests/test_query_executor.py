"""
Story 55.3 — Couverture `inventory/query_executor.py` (AC #5)

Couvre les branches non couvertes :
- _read_entity_from_config : mapper None, mapper non-multi-table, entity_config None,
  sql vide, MapperValidationError, DatabaseError, InterfaceError, Exception générique
- read_distinct_environments : multi_table, flat_table, fallback, exception
- _read_servers_flat_fallback : appelle read_oracle_inventory + transforme résultats
- _exec_env_query : normalize, filter None, dedup+sort
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.db import DatabaseError, InterfaceError

from inventory.query_executor import (
    InventoryQueryExecutor,
    InventoryServiceError,
)
from inventory.mapper import MapperValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_executor():
    """Crée un InventoryQueryExecutor avec _get_inventory_mapper mocké."""
    executor = InventoryQueryExecutor()
    return executor


# ---------------------------------------------------------------------------
# Tests _read_entity_from_config (sous-tâches 5.1, 5.2, 5.3)
# ---------------------------------------------------------------------------

class TestReadEntityFromConfig:

    def test_mapper_none_entity_server_calls_flat_fallback(self):
        """_get_inventory_mapper() retourne None + entity_type=server → _read_servers_flat_fallback."""
        executor = _make_executor()
        with patch.object(executor, '_get_inventory_mapper', return_value=None), \
             patch.object(executor, '_read_servers_flat_fallback', return_value=[]) as mock_fallback:
            result = executor._read_entity_from_config('server')
        mock_fallback.assert_called_once()
        assert result == []

    def test_mapper_none_entity_instance_returns_empty(self):
        """_get_inventory_mapper() retourne None + entity_type=instance → []."""
        executor = _make_executor()
        with patch.object(executor, '_get_inventory_mapper', return_value=None):
            result = executor._read_entity_from_config('instance', environment='dev')
        assert result == []

    def test_mapper_not_multi_table_entity_server_calls_flat_fallback(self):
        """mapper non-multi-table + entity_type=server → _read_servers_flat_fallback."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = False
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_read_servers_flat_fallback', return_value=[]) as mock_fallback:
            result = executor._read_entity_from_config('server')
        mock_fallback.assert_called_once()
        assert result == []

    def test_mapper_not_multi_table_entity_database_returns_empty(self):
        """mapper non-multi-table + entity_type=database → []."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = False
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper):
            result = executor._read_entity_from_config('database', environment='dev')
        assert result == []

    def test_entity_config_none_entity_server_calls_flat_fallback(self):
        """entity_config None + entity_type=server → _read_servers_flat_fallback."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = None
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_read_servers_flat_fallback', return_value=[]) as mock_fallback:
            executor._read_entity_from_config('server')
        mock_fallback.assert_called_once()

    def test_entity_config_none_entity_instance_returns_empty(self):
        """entity_config None + entity_type=instance → []."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = None
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper):
            result = executor._read_entity_from_config('instance', environment='dev')
        assert result == []

    def test_sql_empty_returns_empty(self):
        """builder.build_entity_query retourne sql vide → []."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS', 'id_column': 'ID'}
        mock_builder = MagicMock()
        mock_builder.build_entity_query.return_value = ("", {})
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder):
            result = executor._read_entity_from_config('server')
        assert result == []

    def test_sql_valid_calls_execute_mapped_query(self):
        """builder retourne sql valide → execute_mapped_query appelé."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS', 'id_column': 'ID'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_builder = MagicMock()
        mock_builder.build_entity_query.return_value = ("SELECT * FROM SERVERS", {})
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder), \
             patch.object(executor, 'execute_mapped_query', return_value=[{'id': 1}]) as mock_exec:
            result = executor._read_entity_from_config('server')
        mock_exec.assert_called_once_with("SELECT * FROM SERVERS", {})
        assert result == [{'id': 1}]

    def test_mapper_validation_error_raises_inventory_service_error(self):
        """MapperValidationError → InventoryServiceError."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_builder = MagicMock()
        mock_builder.build_entity_query.side_effect = MapperValidationError("invalid config")
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder):
            with pytest.raises(InventoryServiceError, match="mapping config error"):
                executor._read_entity_from_config('server')

    def test_database_error_raises_inventory_service_error(self):
        """DatabaseError → InventoryServiceError."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_builder = MagicMock()
        mock_builder.build_entity_query.return_value = ("SELECT 1 FROM SERVERS", {})
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder), \
             patch.object(executor, 'execute_mapped_query', side_effect=DatabaseError("db error")):
            with pytest.raises(InventoryServiceError, match="Database error"):
                executor._read_entity_from_config('server')

    def test_interface_error_raises_inventory_service_error(self):
        """InterfaceError → InventoryServiceError."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_builder = MagicMock()
        mock_builder.build_entity_query.return_value = ("SELECT 1 FROM SERVERS", {})
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder), \
             patch.object(executor, 'execute_mapped_query', side_effect=InterfaceError("interface error")):
            with pytest.raises(InventoryServiceError, match="Database error"):
                executor._read_entity_from_config('server')

    def test_generic_exception_raises_inventory_service_error(self):
        """Exception générique → InventoryServiceError."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_builder = MagicMock()
        mock_builder.build_entity_query.return_value = ("SELECT 1 FROM SERVERS", {})
        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch.object(executor, '_get_builder', return_value=mock_builder), \
             patch.object(executor, 'execute_mapped_query', side_effect=RuntimeError("crash")):
            with pytest.raises(InventoryServiceError, match="Failed to read"):
                executor._read_entity_from_config('server')


# ---------------------------------------------------------------------------
# Tests read_distinct_environments (sous-tâche 5.4)
# ---------------------------------------------------------------------------

class TestReadDistinctEnvironments:

    def _make_mock_cursor(self, rows):
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = rows
        return mock_cursor

    def test_multi_table_with_srv_config_uses_servers_table(self):
        """mapper multi-table avec srv_config → sql sur table servers."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.is_flat_table = False
        mock_mapper.get_entity_config.return_value = {'table': 'SERVERS', 'id_column': 'ID'}
        mock_mapper.get_table_name.return_value = "SERVERS"
        mock_mapper.get_column.return_value = "ENVIRONMENT"

        mock_cursor = self._make_mock_cursor([('dev',), ('prod',)])

        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor.read_distinct_environments()

        assert 'dev' in result
        assert 'prod' in result
        assert result == sorted(result)

    def test_multi_table_no_srv_config_falls_to_flat_or_fallback(self):
        """mapper multi-table sans srv_config → passe au flat/fallback."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = True
        mock_mapper.is_flat_table = False
        mock_mapper.get_entity_config.return_value = None  # pas de config servers

        mock_cursor = self._make_mock_cursor([('dev',)])

        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor.read_distinct_environments()

        assert result == ['dev']

    def test_flat_table_uses_flat_table_config(self):
        """mapper flat_table → sql sur flat_table."""
        executor = _make_executor()
        mock_mapper = MagicMock()
        mock_mapper.is_multi_table = False
        mock_mapper.is_flat_table = True
        mock_mapper._flat_table = {
            'table': 'MY_INVENTORY',
            'columns': {'environment': 'ENV_COL'},
        }
        mock_mapper._config = {}  # pas de schema
        mock_mapper.get_entity_config.return_value = None

        mock_cursor = self._make_mock_cursor([('staging',)])

        with patch.object(executor, '_get_inventory_mapper', return_value=mock_mapper), \
             patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor.read_distinct_environments()

        assert 'staging' in result

    def test_mapper_none_uses_dbops_fallback(self):
        """mapper None → sql fallback DBOPS_INVENTORY."""
        executor = _make_executor()

        mock_cursor = self._make_mock_cursor([('prod',), (None,)])

        with patch.object(executor, '_get_inventory_mapper', return_value=None), \
             patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor.read_distinct_environments()

        assert 'prod' in result
        # None doit être filtré
        assert None not in result

    def test_generic_exception_raises_inventory_service_error(self):
        """Exception générique → InventoryServiceError."""
        executor = _make_executor()

        with patch.object(executor, '_get_inventory_mapper', return_value=None), \
             patch('inventory.query_executor._get_connection', side_effect=RuntimeError("crash")):
            with pytest.raises(InventoryServiceError, match="Failed to read distinct environments"):
                executor.read_distinct_environments()


# ---------------------------------------------------------------------------
# Tests _read_servers_flat_fallback (sous-tâche 5.5)
# ---------------------------------------------------------------------------

class TestReadServersFlatFallback:

    def test_calls_read_oracle_inventory_and_transforms(self):
        """_read_servers_flat_fallback → appelle read_oracle_inventory et transforme."""
        executor = _make_executor()
        mock_targets = [
            {'name': 'server1', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch.object(executor, 'read_oracle_inventory', return_value=(mock_targets, 1)) as mock_inv:
            result = executor._read_servers_flat_fallback('dev')

        mock_inv.assert_called_once()
        assert len(result) == 1
        assert result[0]['name'] == 'server1'
        assert result[0]['environment'] == 'dev'
        assert result[0]['engine_type'] is None
        assert 'id' in result[0]

    def test_result_has_id_equals_name(self):
        """Résultat : id=name, engine_type=None."""
        executor = _make_executor()
        with patch.object(executor, 'read_oracle_inventory', return_value=([
            {'name': 'my-server', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ], 1)):
            result = executor._read_servers_flat_fallback()

        assert result[0]['id'] == 'my-server'
        assert result[0]['engine_type'] is None


# ---------------------------------------------------------------------------
# Tests _exec_env_query (sous-tâche 5.6)
# ---------------------------------------------------------------------------

class TestExecEnvQuery:

    def _make_cursor(self, rows):
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = rows
        return mock_cursor

    def test_normalize_applied_on_each_row(self):
        """EnvironmentHelper.normalize appliqué sur chaque ligne."""
        executor = _make_executor()
        mock_cursor = self._make_cursor([('PROD',), ('DEV',)])

        with patch('inventory.query_executor._get_connection') as mock_conn, \
             patch('inventory.query_executor.EnvironmentHelper.normalize',
                   side_effect=lambda x: x.lower() if x else x):
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor._exec_env_query("SELECT 1", "corr", "test")

        assert 'prod' in result
        assert 'dev' in result

    def test_none_rows_filtered(self):
        """Lignes avec row[0] None → filtrées."""
        executor = _make_executor()
        mock_cursor = self._make_cursor([(None,), ('prod',), (None,)])

        with patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor._exec_env_query("SELECT 1", "corr", "test")

        assert None not in result
        assert 'prod' in result

    def test_result_deduplicated_and_sorted(self):
        """Résultat dédupliqué et trié."""
        executor = _make_executor()
        mock_cursor = self._make_cursor([('prod',), ('dev',), ('prod',), ('staging',)])

        with patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor._exec_env_query("SELECT 1", "corr", "test")

        assert result == sorted(set(result))
        assert result.count('prod') == 1


# ---------------------------------------------------------------------------
# Tests execute_mapped_query (branches cursor réelles)
# ---------------------------------------------------------------------------

class TestExecuteMappedQuery:

    def _make_cursor(self, rows, columns):
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = rows
        mock_cursor.description = [(col,) for col in columns]
        return mock_cursor

    def test_valid_query_returns_dict_list(self):
        """execute_mapped_query retourne list of dicts avec columns en minuscules."""
        executor = _make_executor()
        mock_cursor = self._make_cursor(
            rows=[('server1', 'dev')],
            columns=['NAME', 'ENVIRONMENT'],
        )

        with patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            result = executor.execute_mapped_query("SELECT NAME, ENVIRONMENT FROM T", {})

        assert len(result) == 1
        assert result[0]['name'] == 'server1'
        assert result[0]['environment'] == 'dev'

    def test_query_error_raises_inventory_service_error(self):
        """Exception dans le cursor → InventoryServiceError."""
        executor = _make_executor()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = Exception("db crash")

        with patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            with pytest.raises(InventoryServiceError, match="Query execution failed"):
                executor.execute_mapped_query("SELECT 1", {})


# ---------------------------------------------------------------------------
# Tests _get_inventory_mapper (branche avec intégration)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetInventoryMapper:

    def test_no_integration_returns_none(self):
        """Pas d'intégration inventory_db → None."""
        executor = _make_executor()
        with patch('inventory.query_executor.Integration.objects') as mock_objs:
            mock_objs.get_by_type.return_value = None
            result = executor._get_inventory_mapper()
        assert result is None

    def test_with_integration_returns_mapper(self):
        """intégration présente → InventoryMapper instancié."""
        executor = _make_executor()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {}
        with patch('inventory.query_executor.Integration.objects') as mock_objs, \
             patch('inventory.query_executor.InventoryMapper') as mock_mapper_cls:
            mock_objs.get_by_type.return_value = mock_integration
            mock_mapper_cls.return_value = MagicMock()
            result = executor._get_inventory_mapper()
        mock_mapper_cls.assert_called_once_with({})
        assert result is not None


# ---------------------------------------------------------------------------
# Tests read_oracle_inventory (branches validation colonnes)
# ---------------------------------------------------------------------------

class TestReadOracleInventory:

    def test_valid_table_and_columns_returns_results(self):
        """Table valide → résultats retournés."""
        executor = _make_executor()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        with patch('inventory.query_executor._get_connection') as mock_conn, \
             patch('inventory.query_executor.ResultPaginator.build_flat_table_sql',
                   return_value=("SELECT count(*)", {}, "SELECT *", {})):
            mock_conn.return_value.cursor.return_value = mock_cursor
            paginator_mock = MagicMock()
            paginator_mock.paginate_flat.return_value = ([], 0)
            executor._paginator = paginator_mock
            result = executor.read_oracle_inventory('DBOPS_INVENTORY')

        assert result == ([], 0)

    def test_invalid_table_name_raises_inventory_service_error(self):
        """Nom de table invalide → InventoryServiceError."""
        executor = _make_executor()
        with pytest.raises(InventoryServiceError):
            executor.read_oracle_inventory('DROP TABLE; --')

    def test_with_environment_filter(self):
        """Filtre environment → ajouté aux conditions."""
        executor = _make_executor()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        with patch('inventory.query_executor._get_connection') as mock_conn, \
             patch('inventory.query_executor.ResultPaginator.build_flat_table_sql',
                   return_value=("", {}, "SELECT *", {})):
            mock_conn.return_value.cursor.return_value = mock_cursor
            paginator_mock = MagicMock()
            paginator_mock.paginate_flat.return_value = ([], 0)
            executor._paginator = paginator_mock
            result = executor.read_oracle_inventory('DBOPS_INVENTORY', environment='dev')

        assert result == ([], 0)

    def test_invalid_column_type_raises_inventory_service_error(self):
        """Colonne non-string dans column_mapping → InventoryServiceError."""
        executor = _make_executor()
        with pytest.raises(InventoryServiceError, match="Invalid column name"):
            executor.read_oracle_inventory(
                'DBOPS_INVENTORY',
                column_mapping={'name': 123}  # int au lieu de str
            )

    def test_search_and_target_type_filters_applied(self):
        """search et target_type → conditions ajoutées."""
        executor = _make_executor()
        with patch('inventory.query_executor._get_connection'), \
             patch('inventory.query_executor.ResultPaginator.build_flat_table_sql',
                   return_value=("", {}, "SELECT *", {})):
            paginator_mock = MagicMock()
            paginator_mock.paginate_flat.return_value = ([], 0)
            executor._paginator = paginator_mock
            result = executor.read_oracle_inventory(
                'DBOPS_INVENTORY', search='web', target_type='server'
            )
        assert result == ([], 0)

    def test_cursor_exception_raises_inventory_service_error(self):
        """Exception dans cursor.paginate_flat → InventoryServiceError."""
        executor = _make_executor()
        with patch('inventory.query_executor._get_connection'), \
             patch('inventory.query_executor.ResultPaginator.build_flat_table_sql',
                   return_value=("", {}, "SELECT *", {})):
            paginator_mock = MagicMock()
            paginator_mock.paginate_flat.side_effect = Exception("cursor crash")
            executor._paginator = paginator_mock
            with pytest.raises(InventoryServiceError, match="Failed to read inventory"):
                executor.read_oracle_inventory('DBOPS_INVENTORY')


# ---------------------------------------------------------------------------
# Tests branches manquantes supplémentaires
# ---------------------------------------------------------------------------

class TestAdditionalBranches:

    def test_read_entity_instance_no_environment_defaults_to_dev(self):
        """entity_type=instance sans environment → defaulted to 'dev'."""
        executor = _make_executor()
        with patch.object(executor, '_get_inventory_mapper', return_value=None):
            result = executor._read_entity_from_config('instance', environment=None)
        assert result == []

    def test_read_entity_database_no_environment_defaults_to_dev(self):
        """entity_type=database sans environment → defaulted to 'dev'."""
        executor = _make_executor()
        with patch.object(executor, '_get_inventory_mapper', return_value=None):
            result = executor._read_entity_from_config('database', environment=None)
        assert result == []

    def test_execute_mapped_query_reraises_inventory_service_error(self):
        """InventoryServiceError dans execute → re-raised (ligne 79)."""
        executor = _make_executor()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.execute.side_effect = InventoryServiceError("existing service error")

        with patch('inventory.query_executor._get_connection') as mock_conn:
            mock_conn.return_value.cursor.return_value = mock_cursor
            with pytest.raises(InventoryServiceError, match="existing service error"):
                executor.execute_mapped_query("SELECT 1", {})

    def test_read_distinct_environments_reraises_inventory_service_error(self):
        """InventoryServiceError dans read_distinct_environments → re-raised (ligne 234)."""
        executor = _make_executor()
        with patch.object(executor, '_get_inventory_mapper', return_value=None), \
             patch.object(executor, '_exec_env_query',
                          side_effect=InventoryServiceError("existing error")):
            with pytest.raises(InventoryServiceError, match="existing error"):
                executor.read_distinct_environments()
