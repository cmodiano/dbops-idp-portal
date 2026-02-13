"""
Tests d'intégration pour filter_by_attribute.
Story 23.4 - AC8: Flow complet création profil → list_targets_for_user → serveurs filtrés.
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock

from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from inventory.services import InventoryService


MOCK_SERVERS = [
    {'name': 'oracle-srv-01', 'environment': 'dev', 'engine_type': 'oracle'},
    {'name': 'oracle-srv-02', 'environment': 'dev', 'engine_type': 'oracle'},
    {'name': 'sql-srv-01', 'environment': 'dev', 'engine_type': 'sqlserver'},
    {'name': 'sql-srv-02', 'environment': 'dev', 'engine_type': 'sqlserver'},
    {'name': 'mysql-srv-01', 'environment': 'dev', 'engine_type': 'mysql'},
    {'name': 'oracle-prod-01', 'environment': 'prod', 'engine_type': 'oracle'},
    {'name': 'sql-prod-01', 'environment': 'prod', 'engine_type': 'sqlserver'},
]


class TestIntegrationFilterByAttribute(TestCase):
    """Integration tests for the full RBAC filter_by_attribute flow."""

    def _create_profile_with_filter(self, name, ad_group, envs, perm_type, filter_attr, target_names=None):
        """Helper: create profile with action + target permissions."""
        profile = Profile.objects.create(name=name, ad_group=ad_group)

        action_perm = ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
        )
        action_perm.set_environments(envs)
        action_perm.save()

        target_perm = ProfileTargetPermission.objects.create(
            profile=profile, permission_type=perm_type,
        )
        if target_names:
            target_perm.set_target_names(target_names)
        if filter_attr:
            target_perm.set_filter_by_attribute(filter_attr)
        target_perm.save()

        return profile

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_full_flow_create_profile_filter_oracle(self, mock_mapper, mock_list_servers):
        """
        Integration: Create profile with filter → list_targets_for_user → only Oracle.
        """
        self._create_profile_with_filter(
            'oracle_dba', 'GRP-ORACLE-DBA',
            envs=['dev', 'prod'],
            perm_type='ALL',
            filter_attr={"engine_type": ["oracle"]},
        )

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj
        mock_list_servers.return_value = [s for s in MOCK_SERVERS if s['environment'] == 'dev']

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA'],
            environment='dev',
        )

        names = [r['name'] for r in results]
        self.assertIn('oracle-srv-01', names)
        self.assertIn('oracle-srv-02', names)
        self.assertNotIn('sql-srv-01', names)
        self.assertNotIn('sql-srv-02', names)
        self.assertNotIn('mysql-srv-01', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_multi_profile_oracle_plus_sql_union(self, mock_mapper, mock_list_servers):
        """
        Integration: Two profiles (Oracle + SQL) → union of servers.
        """
        self._create_profile_with_filter(
            'oracle_dba', 'GRP-ORACLE-DBA',
            envs=['dev'],
            perm_type='ALL',
            filter_attr={"engine_type": ["oracle"]},
        )
        self._create_profile_with_filter(
            'sql_dba', 'GRP-SQL-DBA',
            envs=['dev'],
            perm_type='ALL',
            filter_attr={"engine_type": ["sqlserver"]},
        )

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj
        mock_list_servers.return_value = [s for s in MOCK_SERVERS if s['environment'] == 'dev']

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ORACLE-DBA', 'GRP-SQL-DBA'],
            environment='dev',
        )

        names = [r['name'] for r in results]
        self.assertIn('oracle-srv-01', names)
        self.assertIn('sql-srv-01', names)
        # MySQL excluded
        self.assertNotIn('mysql-srv-01', names)

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_restrictive_filter_empty_result(self, mock_mapper, mock_list_servers):
        """
        Integration: Restrictive filter → empty result (no matching servers).
        """
        self._create_profile_with_filter(
            'pg_dba', 'GRP-PG-DBA',
            envs=['dev'],
            perm_type='ALL',
            filter_attr={"engine_type": ["postgresql"]},
        )

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj
        mock_list_servers.return_value = [s for s in MOCK_SERVERS if s['environment'] == 'dev']

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-PG-DBA'],
            environment='dev',
        )

        self.assertEqual(total, 0)
        self.assertEqual(results, [])

    @patch.object(InventoryService, 'list_servers')
    @patch.object(InventoryService, '_get_inventory_mapper')
    def test_list_plus_filter_refines(self, mock_mapper, mock_list_servers):
        """
        Integration: LIST + filter → filter refines the LIST.
        """
        self._create_profile_with_filter(
            'mixed_dba', 'GRP-MIXED-DBA',
            envs=['dev'],
            perm_type='LIST',
            filter_attr={"engine_type": ["oracle"]},
            target_names=['oracle-srv-01', 'sql-srv-01', 'mysql-srv-01'],
        )

        mock_mapper_obj = MagicMock()
        mock_mapper_obj.is_multi_table = True
        mock_mapper.return_value = mock_mapper_obj
        mock_list_servers.return_value = [s for s in MOCK_SERVERS if s['environment'] == 'dev']

        service = InventoryService()
        results, total, truncated = service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-MIXED-DBA'],
            environment='dev',
        )

        names = [r['name'] for r in results]
        # LIST restricts to 3 servers, filter refines to Oracle only
        self.assertIn('oracle-srv-01', names)
        self.assertNotIn('sql-srv-01', names)
        self.assertNotIn('mysql-srv-01', names)
