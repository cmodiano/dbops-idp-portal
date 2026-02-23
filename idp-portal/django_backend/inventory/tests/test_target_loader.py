"""
Tests unitaires pour TargetLoader.

Story 34.8 - AC6: Tests unitaires en isolation (DI via constructeur).
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from inventory.target_loader import TargetLoader
from inventory.query_executor import InventoryServiceError, MAX_MULTI_TABLE_RESULTS
from inventory.rbac_filter import MAX_TARGETS_FOR_RBAC_FILTER


def _make_loader(mapper=None, targets=None, servers=None, total_available=None):
    """Helper: build TargetLoader with mocked callables and query_executor."""
    query_executor = MagicMock()
    query_executor._get_inventory_mapper.return_value = mapper

    if targets is not None and total_available is not None:
        list_targets_fn = MagicMock(return_value=(targets, total_available))
    elif targets is not None:
        list_targets_fn = MagicMock(return_value=(targets, len(targets)))
    else:
        list_targets_fn = MagicMock(return_value=([], 0))

    if servers is not None:
        list_servers_fn = MagicMock(return_value=servers)
    else:
        list_servers_fn = MagicMock(return_value=[])

    loader = TargetLoader(
        query_executor=query_executor,
        list_targets_fn=list_targets_fn,
        list_servers_fn=list_servers_fn,
    )
    return loader, query_executor, list_targets_fn, list_servers_fn


def _make_multi_table_mapper():
    """Helper: build a multi-table mapper mock."""
    mapper = MagicMock()
    mapper.is_multi_table = True
    return mapper


def _make_flat_mapper():
    """Helper: build a flat mapper mock."""
    mapper = MagicMock()
    mapper.is_multi_table = False
    return mapper


def _make_permissions(allowed_environments=None):
    return {
        'has_all_access': True,
        'target_restrictions': [],
        'attribute_filters': [],
        'all_access_attribute_filters': [],
        'exclusion_patterns': [],
        'allowed_environments': set(allowed_environments or ['dev']),
    }


class TestTargetLoaderFlatTable(TestCase):
    """Tests pour TargetLoader en mode flat-table."""

    def test_flat_table_returns_targets(self):
        targets = [
            {'name': 'srv01', 'environment': 'dev'},
            {'name': 'srv02', 'environment': 'dev'},
        ]
        loader, _, list_targets_fn, _ = _make_loader(mapper=None, targets=targets, total_available=2)
        permissions = _make_permissions(['dev'])

        result_targets, rbac_truncated = loader.load(
            permissions, {'dev'}, None, None, 42, 'cid-test'
        )

        self.assertEqual(len(result_targets), 2)
        self.assertFalse(rbac_truncated)

    def test_flat_table_rbac_truncated_true(self):
        """rbac_truncated=True when total_available > MAX_TARGETS_FOR_RBAC_FILTER."""
        targets = [{'name': f'srv{i}', 'environment': 'dev'} for i in range(10)]
        total = MAX_TARGETS_FOR_RBAC_FILTER + 1

        loader, _, _, _ = _make_loader(mapper=None, targets=targets, total_available=total)
        permissions = _make_permissions(['dev'])

        _, rbac_truncated = loader.load(
            permissions, {'dev'}, None, None, 42, 'cid-test'
        )

        self.assertTrue(rbac_truncated)

    def test_flat_table_rbac_not_truncated_at_limit(self):
        """rbac_truncated=False when total_available == MAX_TARGETS_FOR_RBAC_FILTER."""
        targets = []
        total = MAX_TARGETS_FOR_RBAC_FILTER

        loader, _, _, _ = _make_loader(mapper=None, targets=targets, total_available=total)
        permissions = _make_permissions(['dev'])

        _, rbac_truncated = loader.load(
            permissions, {'dev'}, None, None, 42, 'cid-test'
        )

        self.assertFalse(rbac_truncated)

    def test_flat_table_passes_search_and_type_to_list_targets(self):
        """list_targets_fn is called with search and target_type from load()."""
        loader, _, list_targets_fn, _ = _make_loader(mapper=None, targets=[], total_available=0)
        permissions = _make_permissions(['dev'])

        loader.load(permissions, {'dev'}, 'myserver', 'oracle', 42, 'cid')

        list_targets_fn.assert_called_once_with(
            environment=None,
            search='myserver',
            target_type='oracle',
            page=1,
            page_size=MAX_TARGETS_FOR_RBAC_FILTER,
        )

    def test_flat_table_uses_flat_mapper(self):
        """Flat mapper (is_multi_table=False) triggers flat-table path."""
        flat_mapper = _make_flat_mapper()
        targets = [{'name': 'srv01', 'environment': 'dev'}]
        loader, _, list_targets_fn, _ = _make_loader(mapper=flat_mapper, targets=targets, total_available=1)
        permissions = _make_permissions(['dev'])

        result_targets, _ = loader.load(permissions, {'dev'}, None, None, 1, 'cid')
        self.assertEqual(len(result_targets), 1)
        list_targets_fn.assert_called_once()


class TestTargetLoaderMultiTable(TestCase):
    """Tests pour TargetLoader en mode multi-table."""

    def test_multi_table_loads_servers_per_env(self):
        """For each allowed env, list_servers_fn is called."""
        multi_mapper = _make_multi_table_mapper()
        servers = [
            {'name': 'srv01', 'environment': 'dev'},
            {'name': 'srv02', 'environment': 'dev'},
        ]
        loader, _, _, list_servers_fn = _make_loader(mapper=multi_mapper, servers=servers)
        permissions = _make_permissions(['dev'])

        result_targets, rbac_truncated = loader.load(
            permissions, {'dev'}, None, None, 1, 'cid'
        )

        self.assertEqual(len(result_targets), 2)
        self.assertFalse(rbac_truncated)
        list_servers_fn.assert_called_once_with(environment='dev')

    def test_multi_table_multiple_envs(self):
        """Servers from all envs are collected."""
        multi_mapper = _make_multi_table_mapper()

        def servers_by_env(environment):
            if environment == 'dev':
                return [{'name': 'dev-srv', 'environment': 'dev'}]
            elif environment == 'prod':
                return [{'name': 'prod-srv', 'environment': 'prod'}]
            return []

        query_executor = MagicMock()
        query_executor._get_inventory_mapper.return_value = multi_mapper
        list_servers_fn = MagicMock(side_effect=lambda environment: servers_by_env(environment))
        list_targets_fn = MagicMock()

        loader = TargetLoader(
            query_executor=query_executor,
            list_targets_fn=list_targets_fn,
            list_servers_fn=list_servers_fn,
        )

        permissions = _make_permissions(['dev', 'prod'])
        result_targets, _ = loader.load(permissions, {'dev', 'prod'}, None, None, 1, 'cid')

        self.assertEqual(len(result_targets), 2)
        names = {t['name'] for t in result_targets}
        self.assertIn('dev-srv', names)
        self.assertIn('prod-srv', names)

    def test_multi_table_one_env_fails_ignored(self):
        """If one env fails, its targets are skipped but others succeed."""
        multi_mapper = _make_multi_table_mapper()

        def servers_by_env(environment):
            if environment == 'dev':
                return [{'name': 'dev-srv', 'environment': 'dev'}]
            raise InventoryServiceError("DB down")

        query_executor = MagicMock()
        query_executor._get_inventory_mapper.return_value = multi_mapper
        list_servers_fn = MagicMock(side_effect=lambda environment: servers_by_env(environment))
        list_targets_fn = MagicMock()

        loader = TargetLoader(
            query_executor=query_executor,
            list_targets_fn=list_targets_fn,
            list_servers_fn=list_servers_fn,
        )

        permissions = _make_permissions(['dev', 'prod'])
        result_targets, _ = loader.load(permissions, {'dev', 'prod'}, None, None, 1, 'cid')

        # Only dev-srv should be present
        self.assertEqual(len(result_targets), 1)
        self.assertEqual(result_targets[0]['name'], 'dev-srv')

    def test_multi_table_all_envs_fail_raises_error(self):
        """If all envs fail, InventoryServiceError is raised."""
        multi_mapper = _make_multi_table_mapper()

        query_executor = MagicMock()
        query_executor._get_inventory_mapper.return_value = multi_mapper
        list_servers_fn = MagicMock(side_effect=InventoryServiceError("fail"))
        list_targets_fn = MagicMock()

        loader = TargetLoader(
            query_executor=query_executor,
            list_targets_fn=list_targets_fn,
            list_servers_fn=list_servers_fn,
        )

        permissions = _make_permissions(['dev', 'prod'])

        with self.assertRaises(InventoryServiceError):
            loader.load(permissions, {'dev', 'prod'}, None, None, 1, 'cid')

    def test_multi_table_no_mapper_falls_back_to_flat(self):
        """No mapper (None) → flat table path is used."""
        targets = [{'name': 'srv01', 'environment': 'dev'}]
        loader, _, list_targets_fn, list_servers_fn = _make_loader(
            mapper=None, targets=targets, total_available=1
        )
        permissions = _make_permissions(['dev'])

        loader.load(permissions, {'dev'}, None, None, 1, 'cid')

        list_targets_fn.assert_called_once()
        list_servers_fn.assert_not_called()

    def test_multi_table_server_fields_preserved(self):
        """Extra server fields beyond 'name'/'environment' are included in target dict."""
        multi_mapper = _make_multi_table_mapper()
        servers = [
            {'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle', 'ip': '10.0.0.1'},
        ]
        loader, _, _, _ = _make_loader(mapper=multi_mapper, servers=servers)
        permissions = _make_permissions(['dev'])

        result_targets, _ = loader.load(permissions, {'dev'}, None, None, 1, 'cid')

        self.assertEqual(len(result_targets), 1)
        target = result_targets[0]
        self.assertEqual(target['name'], 'srv01')
        self.assertEqual(target['environment'], 'dev')
        self.assertEqual(target['target_type'], 'server')
        self.assertEqual(target['engine_type'], 'oracle')
        self.assertEqual(target['ip'], '10.0.0.1')


class TestTargetLoaderGetMapperFn(TestCase):
    """Tests pour le paramètre get_mapper_fn."""

    def test_custom_get_mapper_fn_used(self):
        """If get_mapper_fn is provided, it is called instead of query_executor._get_inventory_mapper."""
        custom_mapper = _make_multi_table_mapper()
        custom_get_mapper_fn = MagicMock(return_value=custom_mapper)
        query_executor = MagicMock()

        servers = [{'name': 'srv01', 'environment': 'dev'}]
        loader = TargetLoader(
            query_executor=query_executor,
            list_targets_fn=MagicMock(return_value=([], 0)),
            list_servers_fn=MagicMock(return_value=servers),
            get_mapper_fn=custom_get_mapper_fn,
        )

        permissions = _make_permissions(['dev'])
        loader.load(permissions, {'dev'}, None, None, 1, 'cid')

        custom_get_mapper_fn.assert_called_once()
        query_executor._get_inventory_mapper.assert_not_called()
