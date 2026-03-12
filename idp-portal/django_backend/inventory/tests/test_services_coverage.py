"""
Story 55.3 — Couverture `inventory/services.py` (AC #4)

Couvre les branches non couvertes :
- list_environments : cache hit, cache miss, erreur read_distinct_environments
- list_servers : rbac_filter + DBOPS, MapperValidationError, Exception générique
- list_instances : sans/avec server_name, avec server_names, exception
- list_databases : sans filtre, avec server_name, InventoryServiceError propagée
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from inventory.services import InventoryService, InventoryServiceError
from inventory.mapper import MapperValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service():
    """Instancie un InventoryService avec collaborateurs mockés."""
    with patch("inventory.services.InventorySourceResolver"), \
         patch("inventory.services.InventoryQueryExecutor"), \
         patch("inventory.services.InventoryRBACFilter"), \
         patch("inventory.services.RBACPermissionAggregator"), \
         patch("inventory.services.TargetLoader"):
        service = InventoryService()
    return service


# ---------------------------------------------------------------------------
# Tests list_environments (sous-tâche 4.1)
# ---------------------------------------------------------------------------

class TestListEnvironments:

    def test_cache_hit_returns_cached_result(self):
        """Cache hit (_environments_cache préchargé) → retour depuis cache."""
        import inventory.services as svc_mod
        svc_mod._environments_cache['environments_list'] = ['dev', 'prod']
        try:
            service = _make_service()
            result = service.list_environments()

            assert result == ['dev', 'prod']
            # query_executor.read_distinct_environments ne doit pas être appelé
            service.query_executor.read_distinct_environments.assert_not_called()
        finally:
            svc_mod._environments_cache.pop('environments_list', None)

    def test_cache_miss_calls_query_executor(self):
        """Cache miss → query_executor.read_distinct_environments appelé et résultat mis en cache."""
        import inventory.services as svc_mod
        svc_mod._environments_cache.clear()
        try:
            service = _make_service()
            service.query_executor.read_distinct_environments.return_value = ['dev', 'staging']

            result = service.list_environments()

            assert result == ['dev', 'staging']
            service.query_executor.read_distinct_environments.assert_called_once()
            assert 'environments_list' in svc_mod._environments_cache
        finally:
            svc_mod._environments_cache.clear()

    def test_read_distinct_environments_error_propagated(self):
        """Erreur dans read_distinct_environments → InventoryServiceError propagée."""
        import inventory.services as svc_mod
        svc_mod._environments_cache.clear()
        try:
            service = _make_service()
            service.query_executor.read_distinct_environments.side_effect = InventoryServiceError("db error")

            with pytest.raises(InventoryServiceError):
                service.list_environments()
        finally:
            svc_mod._environments_cache.clear()


# ---------------------------------------------------------------------------
# Tests list_servers (sous-tâche 4.2)
# ---------------------------------------------------------------------------

class TestListServers:

    def test_list_servers_valid_environment(self):
        """list_servers avec environment → délègue à query_executor.read_servers."""
        service = _make_service()
        service.query_executor.read_servers.return_value = [
            {'id': '1', 'name': 'server1', 'environment': 'dev', 'engine_type': None}
        ]
        result = service.list_servers("dev")
        assert len(result) == 1
        service.query_executor.read_servers.assert_called_once_with("dev", None)

    def test_list_servers_empty_environment_raises_value_error(self):
        """environment vide → ValueError."""
        service = _make_service()
        with pytest.raises(ValueError, match="environment is required"):
            service.list_servers("")

    def test_list_servers_mapper_validation_error_raises_inventory_error(self):
        """MapperValidationError → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_servers.side_effect = MapperValidationError("bad config")

        with pytest.raises(InventoryServiceError, match="Invalid inventory configuration"):
            service.list_servers("dev")

    def test_list_servers_generic_exception_raises_inventory_error(self):
        """Exception générique → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_servers.side_effect = RuntimeError("unexpected")

        with pytest.raises(InventoryServiceError, match="Failed to list servers"):
            service.list_servers("dev")

    def test_list_servers_inventory_service_error_propagated(self):
        """InventoryServiceError → re-raised."""
        service = _make_service()
        service.query_executor.read_servers.side_effect = InventoryServiceError("source error")

        with pytest.raises(InventoryServiceError, match="source error"):
            service.list_servers("dev")


# ---------------------------------------------------------------------------
# Tests list_instances (sous-tâche 4.3)
# ---------------------------------------------------------------------------

class TestListInstances:

    def test_list_instances_without_server_name(self):
        """Sans server_name → read_instances sans filtre server."""
        service = _make_service()
        service.query_executor.read_instances.return_value = [
            {'id': 'i1', 'name': 'inst1', 'environment': 'dev'}
        ]
        result = service.list_instances("dev")
        assert len(result) == 1

    def test_list_instances_with_server_name(self):
        """Avec server_name → read_instances avec filtre server_name."""
        service = _make_service()
        service.query_executor.read_instances.return_value = []
        service.list_instances("dev", server_name="srv1")
        service.query_executor.read_instances.assert_called_once_with(
            "dev", server_name="srv1", engine_type=None
        )

    def test_list_instances_with_server_names(self):
        """Avec server_names multiple → read_instances avec filtre server_names."""
        service = _make_service()
        service.query_executor.read_instances.return_value = []
        service.list_instances("dev", server_names=["srv1", "srv2"])
        service.query_executor.read_instances.assert_called_once_with(
            "dev", server_names=["srv1", "srv2"], engine_type=None
        )

    def test_list_instances_empty_server_names_raises_value_error(self):
        """server_names=[] → ValueError."""
        service = _make_service()
        with pytest.raises(ValueError, match="server_names cannot be empty"):
            service.list_instances("dev", server_names=[])

    def test_list_instances_both_server_name_and_names_raises_value_error(self):
        """server_name + server_names → ValueError."""
        service = _make_service()
        with pytest.raises(ValueError, match="Cannot specify both"):
            service.list_instances("dev", server_name="srv1", server_names=["srv2"])

    def test_list_instances_inventory_service_error_propagated(self):
        """InventoryServiceError → re-raised."""
        service = _make_service()
        service.query_executor.read_instances.side_effect = InventoryServiceError("query error")
        with pytest.raises(InventoryServiceError, match="query error"):
            service.list_instances("dev")

    def test_list_instances_mapper_validation_error_raises_inventory_error(self):
        """MapperValidationError → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_instances.side_effect = MapperValidationError("bad config")
        with pytest.raises(InventoryServiceError, match="Invalid inventory configuration"):
            service.list_instances("dev")

    def test_list_instances_generic_exception_raises_inventory_error(self):
        """Exception générique → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_instances.side_effect = RuntimeError("unexpected")
        with pytest.raises(InventoryServiceError, match="Failed to list instances"):
            service.list_instances("dev")


# ---------------------------------------------------------------------------
# Tests list_databases (sous-tâche 4.4)
# ---------------------------------------------------------------------------

class TestListDatabases:

    def test_list_databases_without_filter(self):
        """Sans filtre → read_databases appelé."""
        service = _make_service()
        service.query_executor.read_databases.return_value = [
            {'id': 'db1', 'name': 'mydb', 'environment': 'dev'}
        ]
        result = service.list_databases("dev")
        assert len(result) == 1

    def test_list_databases_with_server_name(self):
        """Avec server_name → read_databases avec filtre server_name."""
        service = _make_service()
        service.query_executor.read_databases.return_value = []
        service.list_databases("dev", server_name="srv1")
        service.query_executor.read_databases.assert_called_once_with(
            "dev", server_name="srv1", engine_type=None
        )

    def test_list_databases_inventory_service_error_propagated(self):
        """InventoryServiceError → propagée."""
        service = _make_service()
        service.query_executor.read_databases.side_effect = InventoryServiceError("db read error")
        with pytest.raises(InventoryServiceError, match="db read error"):
            service.list_databases("dev")

    def test_list_databases_mapper_validation_error_raises_inventory_error(self):
        """MapperValidationError → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_databases.side_effect = MapperValidationError("bad config")
        with pytest.raises(InventoryServiceError, match="Invalid inventory configuration"):
            service.list_databases("dev")

    def test_list_databases_generic_exception_raises_inventory_error(self):
        """Exception générique → InventoryServiceError."""
        service = _make_service()
        service.query_executor.read_databases.side_effect = RuntimeError("crash")
        with pytest.raises(InventoryServiceError, match="Failed to list databases"):
            service.list_databases("dev")

    def test_list_databases_empty_environment_raises_value_error(self):
        """environment vide → ValueError."""
        service = _make_service()
        with pytest.raises(ValueError, match="environment is required"):
            service.list_databases("")

    def test_list_databases_with_server_names(self):
        """Avec server_names → read_databases avec filtre server_names."""
        service = _make_service()
        service.query_executor.read_databases.return_value = []
        service.list_databases("dev", server_names=["srv1", "srv2"])
        service.query_executor.read_databases.assert_called_once_with(
            "dev", server_names=["srv1", "srv2"], engine_type=None
        )


# ---------------------------------------------------------------------------
# Tests méthodes de délégation (sous-tâche 4.5)
# ---------------------------------------------------------------------------

class TestDelegationMethods:

    def test_get_active_inventory_integration_delegates(self):
        """get_active_inventory_integration → source_resolver.get_active_inventory_integration."""
        service = _make_service()
        service.source_resolver.get_active_inventory_integration.return_value = MagicMock()
        service.get_active_inventory_integration()
        service.source_resolver.get_active_inventory_integration.assert_called_once()

    def test_get_default_environments_returns_empty(self):
        """get_default_environments → []."""
        service = _make_service()
        assert service.get_default_environments() == []

    def test_get_next_maintenance_window_returns_none(self):
        """get_next_maintenance_window → None."""
        service = _make_service()
        assert service.get_next_maintenance_window("target_1") is None

    def test_execute_mapped_query_delegates(self):
        """_execute_mapped_query → query_executor.execute_mapped_query."""
        service = _make_service()
        service.query_executor.execute_mapped_query.return_value = [{'id': 1}]
        result = service._execute_mapped_query("SELECT 1", {})
        assert result == [{'id': 1}]
        service.query_executor.execute_mapped_query.assert_called_once_with("SELECT 1", {})

    def test_read_oracle_inventory_delegates(self):
        """_read_oracle_inventory → query_executor.read_oracle_inventory."""
        service = _make_service()
        service.query_executor.read_oracle_inventory.return_value = ([], 0)
        result = service._read_oracle_inventory("DBOPS_INVENTORY")
        assert result == ([], 0)

    def test_read_servers_from_config_delegates(self):
        """_read_servers_from_config → query_executor.read_servers."""
        service = _make_service()
        service.query_executor.read_servers.return_value = []
        service._read_servers_from_config("dev", "aap")
        service.query_executor.read_servers.assert_called_once_with("dev", "aap")

    def test_read_instances_from_config_delegates(self):
        """_read_instances_from_config → query_executor.read_instances."""
        service = _make_service()
        service.query_executor.read_instances.return_value = []
        service._read_instances_from_config("dev", "srv1", None, "oracle")
        service.query_executor.read_instances.assert_called_once_with(
            "dev", "srv1", None, engine_type="oracle"
        )

    def test_read_databases_from_config_delegates(self):
        """_read_databases_from_config → query_executor.read_databases."""
        service = _make_service()
        service.query_executor.read_databases.return_value = []
        service._read_databases_from_config("dev", "srv1", None, "oracle")
        service.query_executor.read_databases.assert_called_once_with(
            "dev", "srv1", None, engine_type="oracle"
        )


# ---------------------------------------------------------------------------
# Tests list_targets (sous-tâche 4.2 — branches intégration)
# ---------------------------------------------------------------------------

class TestListTargets:

    def test_list_targets_no_integration_uses_fallback(self):
        """Pas d'intégration → DBOPS_INVENTORY fallback."""
        service = _make_service()
        service.source_resolver.get_active_inventory_integration.return_value = None
        service.query_executor.read_oracle_inventory.return_value = ([], 0)
        result = service.list_targets()
        assert result == ([], 0)

    def test_list_targets_inventory_type_raises_api_not_implemented(self):
        """integration.type == INVENTORY → _list_targets_from_api raises (API not yet implemented)."""
        from integrations.models import IntegrationType
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.type = IntegrationType.INVENTORY
        mock_integration.id = 1
        mock_integration.base_url = "https://api.example.com"
        service.source_resolver.get_active_inventory_integration.return_value = mock_integration
        with pytest.raises(InventoryServiceError, match="inventaire de type API"):
            service.list_targets()

    def test_list_multi_table_with_search_and_target_type_filters(self):
        """_list_targets_from_multi_table : search et target_type appliqués."""
        service = _make_service()
        mapper = MagicMock()
        mapper.is_multi_table = True
        service.query_executor.read_servers.return_value = [
            {'name': 'server-prod', 'environment': 'prod'},
            {'name': 'other-dev', 'environment': 'dev'},
        ]
        result, total = service._list_targets_from_multi_table(
            mapper, None, "prod", "server", 1, 10, "corr-123"
        )
        assert total == 1
        assert result[0]['name'] == 'server-prod'

    def test_list_multi_table_read_servers_error_raises(self):
        """_list_targets_from_multi_table : InventoryServiceError propagée."""
        service = _make_service()
        mapper = MagicMock()
        service.query_executor.read_servers.side_effect = InventoryServiceError("db error")
        with pytest.raises(InventoryServiceError):
            service._list_targets_from_multi_table(mapper, None, None, None, 1, 10, "corr")


# ---------------------------------------------------------------------------
# Story 55.3 — Branches non couvertes supplémentaires (sous-tâche 4.6 à 4.20)
# ---------------------------------------------------------------------------

class TestGetInventoryMapperDelegates:
    """_get_inventory_mapper delegates to query_executor (line 94)."""

    def test_get_inventory_mapper_delegates(self):
        service = _make_service()
        mock_mapper = MagicMock()
        service.query_executor._get_inventory_mapper.return_value = mock_mapper
        result = service._get_inventory_mapper()
        service.query_executor._get_inventory_mapper.assert_called_once()
        assert result is mock_mapper


class TestListTargetsInventoryDbBranch:
    """list_targets INVENTORY_DB branch (lines 158-162)."""

    def test_list_targets_inventory_db_type_delegates(self):
        from integrations.models import IntegrationType
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.type = IntegrationType.INVENTORY_DB
        service.source_resolver.get_active_inventory_integration.return_value = mock_integration

        with patch.object(service, '_list_targets_from_db_schema', return_value=([{'name': 'srv'}], 1)) as mock_db:
            result = service.list_targets()

        mock_db.assert_called_once()
        assert result == ([{'name': 'srv'}], 1)


class TestListTargetsFromDbSchema:
    """_list_targets_from_db_schema branches (lines 191-241)."""

    def test_multi_table_delegates_to_multi_table_method(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {}

        with patch("inventory.services.InventoryMapper") as MockMapper:
            mock_mapper = MagicMock()
            mock_mapper.is_multi_table = True
            MockMapper.return_value = mock_mapper

            with patch.object(service, '_list_targets_from_multi_table', return_value=([{'name': 'srv1'}], 1)):
                result = service._list_targets_from_db_schema(mock_integration)

        assert result == ([{'name': 'srv1'}], 1)

    def test_flat_table_as_dict_with_valid_config(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {
            'flat_table': {'table': 'MY_TABLE', 'columns': {'name': 'SERVER_NAME'}}
        }
        service.query_executor.read_oracle_inventory.return_value = ([{'name': 'srv'}], 1)

        with patch("inventory.services.InventoryMapper") as MockMapper:
            MockMapper.return_value.is_multi_table = False
            result = service._list_targets_from_db_schema(mock_integration)

        assert result == ([{'name': 'srv'}], 1)
        service.query_executor.read_oracle_inventory.assert_called_once()

    def test_flat_table_dict_empty_table_raises(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {
            'flat_table': {'table': '   ', 'columns': {}}
        }

        with patch("inventory.services.InventoryMapper") as MockMapper:
            MockMapper.return_value.is_multi_table = False
            with pytest.raises(InventoryServiceError, match="non-empty string"):
                service._list_targets_from_db_schema(mock_integration)

    def test_flat_table_dict_columns_not_dict_raises(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {
            'flat_table': {'table': 'MY_TABLE', 'columns': 'bad'}
        }

        with patch("inventory.services.InventoryMapper") as MockMapper:
            MockMapper.return_value.is_multi_table = False
            with pytest.raises(InventoryServiceError, match="columns must be a dict"):
                service._list_targets_from_db_schema(mock_integration)

    def test_flat_table_as_string_config_table(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {'table': 'INVENTORY'}
        service.query_executor.read_oracle_inventory.return_value = ([], 0)

        with patch("inventory.services.InventoryMapper") as MockMapper:
            MockMapper.return_value.is_multi_table = False
            result = service._list_targets_from_db_schema(mock_integration)

        assert result == ([], 0)

    def test_flat_table_with_schema_and_dot_in_table(self):
        service = _make_service()
        mock_integration = MagicMock()
        mock_integration.get_config.return_value = {
            'flat_table': {'table': 'SCHEMA.MY_TABLE', 'columns': {}}
        }
        service.query_executor.read_oracle_inventory.return_value = ([], 0)

        with patch("inventory.services.InventoryMapper") as MockMapper:
            MockMapper.return_value.is_multi_table = False
            result = service._list_targets_from_db_schema(mock_integration)

        assert result == ([], 0)
        # Table already has dot → used as-is
        call_args = service.query_executor.read_oracle_inventory.call_args
        assert 'SCHEMA.MY_TABLE' == call_args[0][0]


class TestListTargetsFromMultiTableNoFilters:
    """_list_targets_from_multi_table False branches when search/target_type are None."""

    def test_no_search_no_target_type_returns_all(self):
        service = _make_service()
        mapper = MagicMock()
        service.query_executor.read_servers.return_value = [
            {'name': 'server1', 'environment': 'dev'},
            {'name': 'server2', 'environment': 'prod'},
        ]
        result, total = service._list_targets_from_multi_table(
            mapper, None, None, None, 1, 10, "corr-123"
        )
        assert total == 2
        assert len(result) == 2


class TestListServersMinorBranches:
    """list_servers minor branches: result limit warning, ValueError propagation (lines 344, 354)."""

    def test_result_limit_reached_warning_logged(self):
        from inventory.query_executor import MAX_MULTI_TABLE_RESULTS
        service = _make_service()
        service.query_executor.read_servers.return_value = [
            {'name': f's{i}', 'environment': 'dev'} for i in range(MAX_MULTI_TABLE_RESULTS)
        ]
        result = service.list_servers("dev")
        assert len(result) == MAX_MULTI_TABLE_RESULTS

    def test_value_error_inside_try_propagated(self):
        """ValueError raised by read_servers inside try block → re-raised (line 354)."""
        service = _make_service()
        service.query_executor.read_servers.side_effect = ValueError("unexpected value error")
        with pytest.raises(ValueError, match="unexpected value error"):
            service.list_servers("dev")


class TestListInstancesMinorBranches:
    """list_instances minor branches (lines 408, 437, 447)."""

    def test_empty_environment_raises_value_error(self):
        """Empty environment → ValueError (line 408)."""
        service = _make_service()
        with pytest.raises(ValueError, match="environment is required"):
            service.list_instances("")

    def test_result_limit_reached_warning_logged(self):
        """len >= MAX_MULTI_TABLE_RESULTS → warning logged (line 437)."""
        from inventory.query_executor import MAX_MULTI_TABLE_RESULTS
        service = _make_service()
        service.query_executor.read_instances.return_value = [
            {'id': f'i{i}'} for i in range(MAX_MULTI_TABLE_RESULTS)
        ]
        result = service.list_instances("dev")
        assert len(result) == MAX_MULTI_TABLE_RESULTS

    def test_value_error_inside_try_propagated(self):
        """ValueError raised by read_instances inside try → re-raised (line 447)."""
        service = _make_service()
        service.query_executor.read_instances.side_effect = ValueError("internal")
        with pytest.raises(ValueError, match="internal"):
            service.list_instances("dev")


class TestListDatabasesMinorBranches:
    """list_databases minor branches (lines 503, 505, 530, 540)."""

    def test_both_server_name_and_names_raises(self):
        """server_name + server_names → ValueError (line 503)."""
        service = _make_service()
        with pytest.raises(ValueError, match="Cannot specify both"):
            service.list_databases("dev", server_name="srv1", server_names=["srv2"])

    def test_empty_server_names_raises(self):
        """server_names=[] → ValueError (line 505)."""
        service = _make_service()
        with pytest.raises(ValueError, match="server_names cannot be empty"):
            service.list_databases("dev", server_names=[])

    def test_result_limit_reached_warning_logged(self):
        """len >= MAX_MULTI_TABLE_RESULTS → warning logged (line 530)."""
        from inventory.query_executor import MAX_MULTI_TABLE_RESULTS
        service = _make_service()
        service.query_executor.read_databases.return_value = [
            {'id': f'db{i}'} for i in range(MAX_MULTI_TABLE_RESULTS)
        ]
        result = service.list_databases("dev")
        assert len(result) == MAX_MULTI_TABLE_RESULTS

    def test_value_error_inside_try_propagated(self):
        """ValueError raised by read_databases inside try → re-raised (line 540)."""
        service = _make_service()
        service.query_executor.read_databases.side_effect = ValueError("internal")
        with pytest.raises(ValueError, match="internal"):
            service.list_databases("dev")


class TestListTargetsForUser:
    """list_targets_for_user pipeline (lines 600-653)."""

    def test_no_profiles_returns_empty(self):
        """profiles.exists() False → ([], 0, False) (line 607-613)."""
        service = _make_service()
        with patch("inventory.services.Profile") as MockProfile:
            mock_qs = MagicMock()
            mock_qs.exists.return_value = False
            MockProfile.objects.find_by_ad_groups.return_value.prefetch_related.return_value = mock_qs
            result = service.list_targets_for_user(1, ['grp1'])
        assert result == ([], 0, False)

    def test_permissions_none_returns_empty(self):
        """permission_aggregator.aggregate returns None → ([], 0, False) (line 617-618)."""
        service = _make_service()
        with patch("inventory.services.Profile") as MockProfile:
            mock_qs = MagicMock()
            mock_qs.exists.return_value = True
            MockProfile.objects.find_by_ad_groups.return_value.prefetch_related.return_value = mock_qs
            service.permission_aggregator.aggregate.return_value = None
            result = service.list_targets_for_user(1, ['grp1'])
        assert result == ([], 0, False)

    def test_full_pipeline_returns_paginated_filtered_targets(self):
        """Full pipeline → targets filtered, paginated, returned (lines 600-653)."""
        service = _make_service()
        targets = [{'name': 'target1', 'environment': 'dev'}]
        permissions = {
            'has_all_access': True,
            'allowed_environments': {'dev'},
            'target_restrictions': [],
            'exclusion_patterns': [],
        }
        with patch("inventory.services.Profile") as MockProfile:
            mock_qs = MagicMock()
            mock_qs.exists.return_value = True
            MockProfile.objects.find_by_ad_groups.return_value.prefetch_related.return_value = mock_qs
            service.permission_aggregator.aggregate.return_value = permissions
            service.target_loader.load.return_value = (targets, False)
            with patch.object(service, '_apply_rbac_chain_for_user', return_value=targets):
                result = service.list_targets_for_user(1, ['grp1'], environment='dev')
        page_targets, total, rbac_truncated = result
        assert total == 1
        assert len(page_targets) == 1
        assert rbac_truncated is False


class TestBackwardCompatDelegations:
    """Backward-compat delegation methods (lines 659, 667, 691-699, 717-720, 730, 738)."""

    def test_aggregate_profile_permissions_delegates(self):
        """_aggregate_profile_permissions delegates to permission_aggregator (line 659)."""
        service = _make_service()
        service.permission_aggregator.aggregate.return_value = {'key': 'val'}
        result = service._aggregate_profile_permissions(MagicMock(), 'dev', 'corr-123')
        assert result == {'key': 'val'}

    def test_load_targets_delegates(self):
        """_load_targets delegates to target_loader (line 667)."""
        service = _make_service()
        service.target_loader.load.return_value = ([{'name': 't1'}], True)
        result = service._load_targets({'perms': {}}, {'dev'}, None, None, 1, 'corr-123')
        assert result == ([{'name': 't1'}], True)

    def test_apply_rbac_chain_for_user_filters_by_environment(self):
        """_apply_rbac_chain_for_user: env filter + rbac_filter applied (lines 691-699)."""
        service = _make_service()
        service.rbac_filter.apply_rbac_chain.return_value = [{'name': 'srv-dev', 'environment': 'dev'}]

        with patch("inventory.services.EnvironmentHelper") as MockEnvHelper:
            MockEnvHelper.is_in.side_effect = lambda env, allowed: env == 'dev'
            result = service._apply_rbac_chain_for_user(
                [{'name': 'srv-dev', 'environment': 'dev'}, {'name': 'srv-prod', 'environment': 'prod'}],
                {'dev'},
                {'has_all_access': True},
                1, 'corr-123',
            )

        assert len(result) == 1

    def test_paginate_returns_correct_page(self):
        """_paginate slices correctly (lines 717-720)."""
        service = _make_service()
        targets = [{'name': f't{i}'} for i in range(10)]
        page_results, total = service._paginate(targets, page=2, page_size=3)
        assert total == 10
        assert len(page_results) == 3
        assert page_results[0]['name'] == 't3'

    def test_normalize_environment_delegates(self):
        """_normalize_environment delegates to permission_aggregator (line 730)."""
        service = _make_service()
        service.permission_aggregator._normalize_environment.return_value = 'production'
        result = service._normalize_environment('PROD')
        assert result == 'production'

    def test_get_allowed_environments_for_user_delegates(self):
        """get_allowed_environments_for_user delegates to permission_aggregator (line 738)."""
        service = _make_service()
        service.permission_aggregator.get_allowed_environments.return_value = {'dev', 'prod'}
        result = service.get_allowed_environments_for_user(['grp1'])
        assert result == {'dev', 'prod'}
