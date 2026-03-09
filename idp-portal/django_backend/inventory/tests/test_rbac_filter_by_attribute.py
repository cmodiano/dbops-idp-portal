"""
Tests for _apply_attribute_filter and attribute filtering in list_targets_for_user.
Story 23.4 - AC2, AC6, AC8: Tests for RBAC attribute-based filtering.
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock

from inventory.services import InventoryService
from inventory.rbac_filter import InventoryRBACFilter
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission


# --- Tests for _apply_attribute_filter helper ---

class TestApplyAttributeFilter(TestCase):
    """Tests for the _apply_attribute_filter helper function."""

    def setUp(self):
        self.servers = [
            {'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'name': 'srv02', 'environment': 'dev', 'engine_type': 'sqlserver'},
            {'name': 'srv03', 'environment': 'prod', 'engine_type': 'oracle'},
            {'name': 'srv04', 'environment': 'prod', 'engine_type': 'sqlserver'},
            {'name': 'srv05', 'environment': 'prod', 'engine_type': 'mysql'},
        ]

    def test_filter_by_single_attribute_single_value(self):
        """Filter by engine_type=oracle → only Oracle servers."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": ["oracle"]}, 'test-cid'
        )
        self.assertEqual(len(result), 2)
        self.assertEqual({s['name'] for s in result}, {'srv01', 'srv03'})

    def test_filter_by_single_attribute_multiple_values(self):
        """Filter by engine_type=[oracle, sqlserver] → Oracle + SQL."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": ["oracle", "sqlserver"]}, 'test-cid'
        )
        self.assertEqual(len(result), 4)
        self.assertNotIn('srv05', [s['name'] for s in result])

    def test_filter_by_multiple_attributes_and(self):
        """Filter by engine_type=oracle AND environment=prod → AND."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers,
            {"engine_type": ["oracle"], "environment": ["prod"]},
            'test-cid'
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'srv03')

    def test_empty_filter_returns_all(self):
        """Empty filter dict → all servers returned."""
        result = InventoryRBACFilter._apply_attribute_filter(self.servers, {}, 'test-cid')
        self.assertEqual(len(result), 5)

    def test_none_filter_returns_all(self):
        """None filter → all servers returned (via falsy check)."""
        result = InventoryRBACFilter._apply_attribute_filter(self.servers, None, 'test-cid')
        self.assertEqual(len(result), 5)

    def test_all_servers_filtered_out(self):
        """Filter excludes all servers → returns empty list."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": ["postgresql"]}, 'test-cid'
        )
        self.assertEqual(len(result), 0)

    def test_attribute_not_found_in_servers_ignored(self):
        """Attribute not in any server → filter ignored, all returned."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"nonexistent_attr": ["value"]}, 'test-cid'
        )
        self.assertEqual(len(result), 5)

    def test_fail_open_behavior_typo_in_attribute_key_grants_full_access(self):
        """
        INV-MED-03 — FAIL-OPEN security behavior: explicit test.

        When a profile's filter_by_attribute key contains a typo (e.g. "engine_tpe"
        instead of "engine_type"), the filter is silently skipped and ALL servers pass
        through unfiltered — potentially granting broader access than intended.

        This behavior is intentional (documented in _apply_attribute_filter docstring)
        and this test locks in the expected behavior. Operators must monitor the
        "rbac_filter_attribute_not_found" log warning.
        """
        # Typo: "engine_tpe" instead of "engine_type"
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_tpe": ["oracle"]}, 'test-cid'
        )
        # FAIL-OPEN: all 5 servers pass through despite the filter
        self.assertEqual(len(result), 5, (
            "FAIL-OPEN: typo in attribute key must return ALL servers "
            "(not an empty list or raise an error)"
        ))

    def test_case_insensitive_matching(self):
        """Filter values are matched case-insensitively."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": ["Oracle"]}, 'test-cid'
        )
        self.assertEqual(len(result), 2)

    def test_empty_allowed_values_skipped(self):
        """Empty allowed values list → criterion skipped."""
        result = InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": []}, 'test-cid'
        )
        self.assertEqual(len(result), 5)

    def test_preserves_original_list(self):
        """Filter does not mutate the original servers list."""
        original_len = len(self.servers)
        InventoryRBACFilter._apply_attribute_filter(
            self.servers, {"engine_type": ["oracle"]}, 'test-cid'
        )
        self.assertEqual(len(self.servers), original_len)


# --- Tests for attribute filtering in list_targets_for_user ---

class TestListTargetsForUserWithAttributeFilter(TestCase):
    """Tests for list_targets_for_user with attribute-based filtering."""

    def setUp(self):
        # Create profiles
        self.profile_oracle = Profile.objects.create(
            name='oracle_dba', ad_group='GRP-ORACLE-DBA',
        )
        self.action_perm_oracle = ProfileActionPermission.objects.create(
            profile=self.profile_oracle, permission_type='ALL',
        )
        self.action_perm_oracle.set_environments(['dev', 'prod'])
        self.action_perm_oracle.save()

        self.target_perm_oracle = ProfileTargetPermission.objects.create(
            profile=self.profile_oracle, permission_type='ALL',
        )
        self.target_perm_oracle.set_filter_by_attribute({"engine_type": ["oracle"]})
        self.target_perm_oracle.save()

        # Mock servers data
        self.mock_servers = [
            {'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'name': 'srv02', 'environment': 'dev', 'engine_type': 'sqlserver'},
            {'name': 'srv03', 'environment': 'prod', 'engine_type': 'oracle'},
            {'name': 'srv04', 'environment': 'prod', 'engine_type': 'sqlserver'},
        ]

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_filter_oracle_only_dev(self, mock_mapper, mock_list_servers):
        """Profile with engine_type=oracle → only Oracle servers for dev."""
        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'dev'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='dev',
        )

        # Only Oracle servers in dev should be returned
        names = [r['name'] for r in results]
        self.assertIn('srv01', names)
        self.assertNotIn('srv02', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_two_profiles_or_filter(self, mock_mapper, mock_list_servers):
        """Two profiles (Oracle + SQL) → union (OR) of servers."""
        # Create SQL profile
        profile_sql = Profile.objects.create(
            name='sql_dba', ad_group='GRP-SQL-DBA',
        )
        action_perm_sql = ProfileActionPermission.objects.create(
            profile=profile_sql, permission_type='ALL',
        )
        action_perm_sql.set_environments(['dev'])
        action_perm_sql.save()

        target_perm_sql = ProfileTargetPermission.objects.create(
            profile=profile_sql, permission_type='ALL',
        )
        target_perm_sql.set_filter_by_attribute({"engine_type": ["sqlserver"]})
        target_perm_sql.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'dev'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA', 'GRP-SQL-DBA'],
            environment='dev',
        )

        # Both Oracle and SQL servers in dev should be returned (OR)
        names = [r['name'] for r in results]
        self.assertIn('srv01', names)
        self.assertIn('srv02', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_profile_without_filter_passes_all(self, mock_mapper, mock_list_servers):
        """Profile without attribute filter → all targets pass through."""
        # Clear the filter
        self.target_perm_oracle.set_filter_by_attribute(None)
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'dev'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='dev',
        )

        # All servers in dev should be returned (no filter)
        self.assertEqual(total, 2)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_and_filter_within_profile(self, mock_mapper, mock_list_servers):
        """Profile with engine_type=oracle AND environment=prod → AND within profile."""
        self.target_perm_oracle.set_filter_by_attribute({
            "engine_type": ["oracle"],
        })
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'prod'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='prod',
        )

        names = [r['name'] for r in results]
        self.assertIn('srv03', names)
        self.assertNotIn('srv04', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_list_plus_filter_refines_list(self, mock_mapper, mock_list_servers):
        """LIST + filter_by_attribute → filter refines the LIST."""
        self.target_perm_oracle.permission_type = 'LIST'
        self.target_perm_oracle.set_target_names(['srv01', 'srv02', 'srv03'])
        self.target_perm_oracle.set_filter_by_attribute({"engine_type": ["oracle"]})
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = self.mock_servers

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
        )

        # LIST restricts to srv01, srv02, srv03
        # filter_by_attribute restricts to Oracle only
        # Result: srv01 (Oracle, dev) + srv03 (Oracle, prod)
        names = [r['name'] for r in results]
        self.assertIn('srv01', names)
        self.assertIn('srv03', names)
        self.assertNotIn('srv02', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_all_plus_filter_restricts_global(self, mock_mapper, mock_list_servers):
        """ALL + filter_by_attribute → filter restricts the global set."""
        self.target_perm_oracle.set_filter_by_attribute({"engine_type": ["oracle"]})
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = self.mock_servers

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
        )

        # ALL access but filtered to Oracle only
        names = [r['name'] for r in results]
        self.assertIn('srv01', names)
        self.assertIn('srv03', names)
        self.assertNotIn('srv02', names)
        self.assertNotIn('srv04', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_malformed_json_filter_ignored(self, mock_mapper, mock_list_servers):
        """Malformed JSON in filter_by_attribute → filter ignored gracefully."""
        self.target_perm_oracle.filter_by_attribute_json = '{invalid'
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'dev'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='dev',
        )

        # Malformed JSON → get_filter_by_attribute returns None → no filtering
        self.assertEqual(total, 2)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_empty_result_after_filter(self, mock_mapper, mock_list_servers):
        """Filter excludes all servers → returns empty list."""
        self.target_perm_oracle.set_filter_by_attribute({"engine_type": ["postgresql"]})
        self.target_perm_oracle.save()

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj

        mock_list_servers.return_value = [
            s for s in self.mock_servers if s['environment'] == 'dev'
        ]

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='dev',
        )

        self.assertEqual(total, 0)
        self.assertEqual(results, [])
