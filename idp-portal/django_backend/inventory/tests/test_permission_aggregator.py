"""
Tests unitaires pour RBACPermissionAggregator.

Story 34.8 - AC6: Tests unitaires en isolation (DI via constructeur).
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from inventory.permission_aggregator import RBACPermissionAggregator
from inventory.query_executor import InventoryServiceError


def _make_aggregator(environments=None):
    """Helper: build RBACPermissionAggregator with mocked callables.

    Story 53.1 — inventory is the sole source of truth; no default_environments fallback.
    """
    environments = environments if environments is not None else ['developpement', 'certification', 'production']
    return RBACPermissionAggregator(
        list_environments_fn=lambda: environments,
    )


def _make_profile(
    is_admin=0,
    action_envs=None,
    perm_type=None,
    target_patterns=None,
    target_names=None,
    attr_filter=None,
    exclusion_patterns=None,
):
    """Helper: build a MagicMock profile with the given attributes."""
    profile = MagicMock()
    profile.id = 1
    profile.is_admin = is_admin

    if action_envs is not None:
        action_perm = MagicMock()
        action_perm.get_environments.return_value = action_envs
        profile.profileactionpermission = action_perm
    else:
        del profile.profileactionpermission  # trigger AttributeError → getattr returns None

    if perm_type is not None:
        target_perm = MagicMock()
        target_perm.permission_type = perm_type
        target_perm.get_filter_by_attribute.return_value = attr_filter
        target_perm.get_exclusion_patterns.return_value = exclusion_patterns or []
        if perm_type == 'PATTERN':
            target_perm.get_target_patterns.return_value = target_patterns or []
        elif perm_type == 'LIST':
            target_perm.get_target_names.return_value = target_names or []
        profile.profiletargetpermission = target_perm
    else:
        del profile.profiletargetpermission

    return profile


class TestRBACPermissionAggregatorNormalize(TestCase):
    """Tests pour _normalize_environment."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_normalize_standard(self):
        self.assertEqual(self.agg._normalize_environment('dev'), 'dev')
        self.assertEqual(self.agg._normalize_environment('staging'), 'staging')
        self.assertEqual(self.agg._normalize_environment('prod'), 'prod')

    def test_normalize_inventory_values_pass_through(self):
        """Story 53.1 — Alias mapping removed; inventory values pass through as-is (lowercased)."""
        self.assertEqual(self.agg._normalize_environment('developpement'), 'developpement')
        self.assertEqual(self.agg._normalize_environment('certification'), 'certification')
        self.assertEqual(self.agg._normalize_environment('production'), 'production')
        self.assertEqual(self.agg._normalize_environment('certif'), 'certif')
        self.assertEqual(self.agg._normalize_environment('development'), 'development')

    def test_normalize_unknown_returns_raw(self):
        self.assertEqual(self.agg._normalize_environment('lab'), 'lab')
        self.assertEqual(self.agg._normalize_environment('qa'), 'qa')
        self.assertEqual(self.agg._normalize_environment('custom'), 'custom')

    def test_normalize_case_insensitive(self):
        """Story 53.1 — Uppercase is lowercased only; no alias mapping."""
        self.assertEqual(self.agg._normalize_environment('CERTIF'), 'certif')
        self.assertEqual(self.agg._normalize_environment('  LAB  '), 'lab')

    def test_normalize_empty_string(self):
        self.assertEqual(self.agg._normalize_environment(''), '')

    def test_normalize_none(self):
        self.assertEqual(self.agg._normalize_environment(None), '')


class TestRBACPermissionAggregatorAggregateAllAccess(TestCase):
    """Tests pour aggregate() — profil ALL."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_profile_all_access_with_environments(self):
        profile = _make_profile(
            action_envs=['dev', 'prod'],
            perm_type='ALL',
        )
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertTrue(result['has_all_access'])
        self.assertIn('dev', result['allowed_environments'])
        self.assertIn('prod', result['allowed_environments'])
        self.assertEqual(result['target_restrictions'], [])

    def test_profile_all_access_no_environments_returns_none(self):
        """If no environments found and no admin, returns None."""
        profile = _make_profile(perm_type='ALL')  # no action_envs
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNone(result)


class TestRBACPermissionAggregatorAggregatePattern(TestCase):
    """Tests pour aggregate() — profil PATTERN."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_profile_pattern_with_environments(self):
        profile = _make_profile(
            action_envs=['dev'],
            perm_type='PATTERN',
            target_patterns=['srv-*', 'db-*'],
        )
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertFalse(result['has_all_access'])
        self.assertEqual(len(result['target_restrictions']), 1)
        perm_type, patterns = result['target_restrictions'][0]
        self.assertEqual(perm_type, 'PATTERN')
        self.assertEqual(patterns, ['db-*', 'srv-*'])

    def test_profile_pattern_empty_patterns_excluded(self):
        """PATTERN with empty patterns list is not added to target_restrictions."""
        profile = _make_profile(
            action_envs=['dev'],
            perm_type='PATTERN',
            target_patterns=[],
        )
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertEqual(result['target_restrictions'], [])


class TestRBACPermissionAggregatorAggregateList(TestCase):
    """Tests pour aggregate() — profil LIST."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_profile_list_with_environments(self):
        profile = _make_profile(
            action_envs=['staging'],
            perm_type='LIST',
            target_names=['server-a', 'server-b'],
        )
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertFalse(result['has_all_access'])
        self.assertEqual(len(result['target_restrictions']), 1)
        perm_type, names = result['target_restrictions'][0]
        self.assertEqual(perm_type, 'LIST')
        self.assertEqual(names, ['server-a', 'server-b'])

    def test_profile_list_empty_names_excluded(self):
        profile = _make_profile(
            action_envs=['dev'],
            perm_type='LIST',
            target_names=[],
        )
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertEqual(result['target_restrictions'], [])


class TestRBACPermissionAggregatorAggregateAdmin(TestCase):
    """Tests pour aggregate() — profil admin (is_admin=1)."""

    def setUp(self):
        self.agg = _make_aggregator(environments=['developpement', 'certification', 'production', 'lab'])

    def test_admin_no_action_perm_uses_list_environments(self):
        """Admin without profileactionpermission falls back to list_environments_fn."""
        profile = _make_profile(is_admin=1, perm_type='ALL')
        result = self.agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertIn('lab', result['allowed_environments'])
        self.assertTrue(result['has_all_access'])

    def test_admin_fallback_inventory_unavailable_returns_none(self):
        """Story 53.1 — Admin fallback when list_environments_fn raises returns None (no hardcoded defaults)."""
        def raise_inventory_error():
            raise InventoryServiceError("fail")

        agg = RBACPermissionAggregator(
            list_environments_fn=raise_inventory_error,
        )
        profile = _make_profile(is_admin=1, perm_type='ALL')
        result = agg.aggregate([profile], environment=None, correlation_id='cid')
        self.assertIsNone(result)


class TestRBACPermissionAggregatorAggregateMixedAdminNonAdmin(TestCase):
    """Tests pour aggregate() — mélange admin + profil RBAC classique."""

    def setUp(self):
        self.agg = _make_aggregator(environments=['developpement', 'certification', 'production', 'lab'])

    def test_admin_and_non_admin_environments_merged(self):
        """Admin brings all environments; non-admin brings specific ones; union is returned."""
        admin_profile = _make_profile(is_admin=1, perm_type='ALL')
        non_admin_profile = _make_profile(action_envs=['dev'], perm_type='PATTERN', target_patterns=['srv-*'])

        result = self.agg.aggregate([admin_profile, non_admin_profile], environment=None, correlation_id='cid')

        self.assertIsNotNone(result)
        # Admin contributes all environments from list_environments_fn
        self.assertIn('lab', result['allowed_environments'])
        # Non-admin contributes 'dev'
        self.assertIn('dev', result['allowed_environments'])
        # Admin has ALL access; non-admin adds PATTERN restriction
        self.assertTrue(result['has_all_access'])
        self.assertEqual(len(result['target_restrictions']), 1)

    def test_admin_fallback_all_envs_when_non_admin_has_no_envs(self):
        """If non-admin profile has no action_perm, admin fallback covers all environments."""
        admin_profile = _make_profile(is_admin=1, perm_type='ALL')
        non_admin_profile = _make_profile(perm_type='PATTERN', target_patterns=['db-*'])

        result = self.agg.aggregate([non_admin_profile, admin_profile], environment=None, correlation_id='cid')

        self.assertIsNotNone(result)
        self.assertTrue(result['has_all_access'])
        # Admin-contributed environments cover all
        self.assertIn('lab', result['allowed_environments'])


class TestRBACPermissionAggregatorAggregateMultiProfile(TestCase):
    """Tests pour aggregate() — multi-profils."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_multi_profile_union_environments(self):
        p1 = _make_profile(action_envs=['dev'], perm_type='ALL')
        p2 = _make_profile(action_envs=['prod'], perm_type='ALL')
        result = self.agg.aggregate([p1, p2], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertIn('dev', result['allowed_environments'])
        self.assertIn('prod', result['allowed_environments'])

    def test_multi_profile_union_restrictions(self):
        p1 = _make_profile(action_envs=['dev'], perm_type='PATTERN', target_patterns=['srv-*'])
        p2 = _make_profile(action_envs=['dev'], perm_type='LIST', target_names=['server-x'])
        result = self.agg.aggregate([p1, p2], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['target_restrictions']), 2)

    def test_multi_profile_exclusion_patterns_union(self):
        p1 = _make_profile(action_envs=['dev'], perm_type='ALL', exclusion_patterns=['bad-*'])
        p2 = _make_profile(action_envs=['prod'], perm_type='ALL', exclusion_patterns=['legacy-*'])
        result = self.agg.aggregate([p1, p2], environment=None, correlation_id='cid')
        self.assertIsNotNone(result)
        self.assertIn('bad-*', result['exclusion_patterns'])
        self.assertIn('legacy-*', result['exclusion_patterns'])


class TestRBACPermissionAggregatorAggregateEnvironmentFilter(TestCase):
    """Tests pour aggregate() — filtrage par environment."""

    def setUp(self):
        self.agg = _make_aggregator()

    def test_environment_filter_allowed_returns_result(self):
        profile = _make_profile(action_envs=['dev', 'prod'], perm_type='ALL')
        result = self.agg.aggregate([profile], environment='dev', correlation_id='cid')
        self.assertIsNotNone(result)

    def test_environment_filter_not_allowed_returns_none(self):
        """Environment not in allowed_environments → returns None."""
        profile = _make_profile(action_envs=['dev'], perm_type='ALL')
        result = self.agg.aggregate([profile], environment='prod', correlation_id='cid')
        self.assertIsNone(result)

    def test_environment_filter_certification_exact_match(self):
        """Story 53.1 — Inventory value 'certification' matches filter 'certification' (no alias mapping)."""
        profile = _make_profile(action_envs=['certification'], perm_type='ALL')
        result = self.agg.aggregate([profile], environment='certification', correlation_id='cid')
        self.assertIsNotNone(result)


class TestRBACPermissionAggregatorGetAllowedEnvironments(TestCase):
    """Tests pour get_allowed_environments()."""

    def setUp(self):
        self.agg = _make_aggregator()

    @patch('inventory.permission_aggregator.Profile')
    def test_profiles_found_returns_environments(self, mock_profile_cls):
        profile = _make_profile(action_envs=['dev', 'prod'])
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profile_cls.objects.find_by_ad_groups.return_value = mock_qs

        result = self.agg.get_allowed_environments(['GROUP_DBA'])
        self.assertIn('dev', result)
        self.assertIn('prod', result)

    @patch('inventory.permission_aggregator.Profile')
    def test_no_profiles_returns_empty_set(self, mock_profile_cls):
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profile_cls.objects.find_by_ad_groups.return_value = mock_qs

        result = self.agg.get_allowed_environments(['GROUP_UNKNOWN'])
        self.assertEqual(result, set())

    @patch('inventory.permission_aggregator.Profile')
    def test_inventory_value_stored_as_is(self, mock_profile_cls):
        """Story 53.1 — Inventory values are stored lowercased without alias mapping."""
        profile = _make_profile(action_envs=['certification'])
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([profile]))
        mock_qs.prefetch_related.return_value = mock_qs
        mock_profile_cls.objects.find_by_ad_groups.return_value = mock_qs

        result = self.agg.get_allowed_environments(['GROUP_DBA'])
        self.assertIn('certification', result)
        self.assertNotIn('staging', result)
