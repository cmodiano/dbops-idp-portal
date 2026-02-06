"""
Tests for InventoryService.
Story 13.1 - Service tests with mocked external sources.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase

from inventory.services import InventoryService, InventoryServiceError
from inventory.models import TargetEnvironment
from integrations.models import Integration, IntegrationType
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission


class InventoryServiceIntegrationTests(TestCase):
    """Tests for InventoryService integration detection."""

    def setUp(self):
        """Set up test data."""
        self.service = InventoryService()

    def test_get_active_inventory_integration_none(self):
        """Test when no inventory integration exists."""
        integration = self.service.get_active_inventory_integration()
        self.assertIsNone(integration)

    def test_get_active_inventory_integration_api(self):
        """Test finding API inventory integration."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY,
            name='API Inventory',
            base_url='https://inventory.example.com'
        )
        integration = self.service.get_active_inventory_integration()
        self.assertIsNotNone(integration)
        self.assertEqual(integration.type, IntegrationType.INVENTORY)

    def test_get_active_inventory_integration_db(self):
        """Test finding DB inventory integration."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost',
            config='{"schema": "CMDB", "table": "SERVERS"}'
        )
        integration = self.service.get_active_inventory_integration()
        self.assertIsNotNone(integration)
        self.assertEqual(integration.type, IntegrationType.INVENTORY_DB)

    def test_get_active_inventory_integration_prefers_api(self):
        """Test that API integration is preferred over DB."""
        Integration.objects.create(
            type=IntegrationType.INVENTORY,
            name='API Inventory',
            base_url='https://inventory.example.com'
        )
        Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='DB Inventory',
            base_url='oracle://localhost'
        )
        integration = self.service.get_active_inventory_integration()
        self.assertEqual(integration.type, IntegrationType.INVENTORY)


class InventoryServiceFallbackTests(TestCase):
    """Tests for InventoryService fallback to DBOPS_INVENTORY."""

    def setUp(self):
        """Set up test without inventory integration."""
        self.service = InventoryService()

    @patch('inventory.services.connection')
    def test_fallback_to_dbops_inventory(self, mock_connection):
        """Test fallback to DBOPS_INVENTORY when no integration."""
        # Mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)  # count
        mock_cursor.fetchall.return_value = [
            ('fallback-srv-01', 'DEV', 'SERVER'),
            ('fallback-srv-02', 'PROD', 'SERVER'),
            ('fallback-db-01', 'DEV', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 3)
        self.assertEqual(len(targets), 3)
        self.assertEqual(targets[0]['name'], 'fallback-srv-01')
        self.assertEqual(targets[0]['environment'], 'dev')

    @patch('inventory.services.connection')
    def test_fallback_with_environment_filter(self, mock_connection):
        """Test fallback with environment filter."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('fallback-srv-01', 'DEV', 'SERVER'),
            ('fallback-db-01', 'DEV', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets(environment='dev')

        self.assertEqual(total, 2)
        # Verify SQL was called
        mock_cursor.execute.assert_called()

    @patch('inventory.services.connection')
    def test_fallback_error_raises_exception(self, mock_connection):
        """Test fallback raises InventoryServiceError on Oracle errors."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = Exception("ORA-00942: table or view does not exist")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        with self.assertRaises(InventoryServiceError) as context:
            self.service.list_targets()

        self.assertIn("ORA-00942", str(context.exception))
        self.assertIn("DBOPS_INVENTORY", str(context.exception))


class InventoryServiceDBSchemaTests(TestCase):
    """Tests for InventoryService with inventory_db integration."""

    def setUp(self):
        """Set up with inventory_db integration."""
        self.service = InventoryService()
        self.integration = Integration.objects.create(
            type=IntegrationType.INVENTORY_DB,
            name='Schema Inventory',
            base_url='oracle://localhost',
            config='{"schema": "CMDB", "table": "SERVERS"}'
        )

    @patch('inventory.services.connection')
    def test_list_from_db_schema(self, mock_connection):
        """Test listing from DB schema integration."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('cmdb-srv-01', 'PROD', 'SERVER'),
            ('cmdb-srv-02', 'PROD', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 2)
        # Verify SQL uses correct schema.table
        call_args = str(mock_cursor.execute.call_args)
        self.assertIn('CMDB.SERVERS', call_args)


class InventoryServiceRBACTests(TestCase):
    """Tests for RBAC filtering in InventoryService."""

    def setUp(self):
        """Set up profiles with different permissions."""
        self.service = InventoryService()

        # Profile with dev access and pattern-based target restriction
        self.dev_profile = Profile.objects.create(
            name='dev-team',
            description='Development team',
            ad_group='GRP-DEV-TEAM'
        )
        ProfileActionPermission.objects.create(
            profile=self.dev_profile,
            permission_type='ALL',
            environments_json='["dev", "staging"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.dev_profile,
            permission_type='PATTERN',
            target_patterns_json='["web-*", "api-*"]'
        )

        # Profile with all access
        self.admin_profile = Profile.objects.create(
            name='admin',
            description='Admin',
            ad_group='GRP-ADMIN',
            is_admin=1
        )
        ProfileActionPermission.objects.create(
            profile=self.admin_profile,
            permission_type='ALL',
            environments_json='["dev", "staging", "prod"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.admin_profile,
            permission_type='ALL'
        )

    @patch('inventory.services.connection')
    def test_list_targets_for_user_no_profile(self, mock_connection):
        """Test listing targets with no matching profile."""
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-UNKNOWN']
        )
        self.assertEqual(total, 0)
        self.assertEqual(len(targets), 0)

    @patch('inventory.services.connection')
    def test_list_targets_for_user_with_env_filter(self, mock_connection):
        """Test that user without prod access gets empty result."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_cursor.fetchall.return_value = []
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-DEV-TEAM'],
            environment='prod'  # Not in allowed environments for dev-team
        )
        self.assertEqual(total, 0)

    @patch('inventory.services.connection')
    def test_list_targets_for_user_pattern_filtering(self, mock_connection):
        """Test that pattern-based restrictions filter targets."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-srv-01', 'dev', 'server'),
            ('api-srv-01', 'dev', 'server'),
            ('db-srv-01', 'dev', 'database'),  # Should be filtered out
            ('batch-srv-01', 'dev', 'server'),  # Should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-DEV-TEAM']
        )
        # Only web-* and api-* should pass pattern filter
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('web-srv-01', names)
        self.assertIn('api-srv-01', names)
        self.assertNotIn('db-srv-01', names)

    @patch('inventory.services.connection')
    def test_list_targets_for_admin_all_access(self, mock_connection):
        """Test that admin with ALL access gets all targets."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('web-srv-01', 'prod', 'server'),
            ('db-srv-01', 'prod', 'database'),
            ('batch-srv-01', 'prod', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-ADMIN']
        )
        self.assertEqual(total, 3)

    def test_get_allowed_environments_for_user(self):
        """Test getting allowed environments from profiles."""
        envs = self.service.get_allowed_environments_for_user(['GRP-DEV-TEAM'])
        self.assertEqual(envs, {'dev', 'staging'})

        envs = self.service.get_allowed_environments_for_user(['GRP-ADMIN'])
        self.assertEqual(envs, {'dev', 'staging', 'prod'})

        envs = self.service.get_allowed_environments_for_user(['GRP-UNKNOWN'])
        self.assertEqual(envs, set())


class InventoryServiceSecurityTests(TestCase):
    """Tests for security features in InventoryService."""

    def setUp(self):
        """Set up test data."""
        self.service = InventoryService()

    def test_sql_injection_blocked_semicolon(self):
        """Test that SQL injection with semicolon is blocked."""
        with self.assertRaises(InventoryServiceError) as context:
            self.service._read_oracle_inventory("DBOPS_INVENTORY; DROP TABLE USERS; --")

        self.assertIn("Invalid table/synonym name", str(context.exception))

    def test_sql_injection_blocked_quotes(self):
        """Test that SQL injection with quotes is blocked."""
        with self.assertRaises(InventoryServiceError) as context:
            self.service._read_oracle_inventory("DBOPS_INVENTORY' OR '1'='1")

        self.assertIn("Invalid table/synonym name", str(context.exception))

    def test_sql_injection_blocked_union(self):
        """Test that SQL injection with UNION is blocked."""
        with self.assertRaises(InventoryServiceError) as context:
            self.service._read_oracle_inventory("DBOPS_INVENTORY UNION SELECT")

        self.assertIn("Invalid table/synonym name", str(context.exception))

    def test_valid_table_name_accepted(self):
        """Test that valid table names are accepted."""
        from inventory.services import SAFE_TABLE_NAME_PATTERN

        # Valid names
        self.assertTrue(SAFE_TABLE_NAME_PATTERN.match("DBOPS_INVENTORY"))
        self.assertTrue(SAFE_TABLE_NAME_PATTERN.match("CMDB.SERVERS"))
        self.assertTrue(SAFE_TABLE_NAME_PATTERN.match("my_schema.my_table"))
        self.assertTrue(SAFE_TABLE_NAME_PATTERN.match("TABLE123"))

        # Invalid names
        self.assertFalse(SAFE_TABLE_NAME_PATTERN.match("TABLE; DROP"))
        self.assertFalse(SAFE_TABLE_NAME_PATTERN.match("TABLE'"))
        self.assertFalse(SAFE_TABLE_NAME_PATTERN.match("123TABLE"))  # Can't start with number
        self.assertFalse(SAFE_TABLE_NAME_PATTERN.match("TABLE--COMMENT"))


class InventoryServiceEnvironmentNormalizationTests(TestCase):
    """Tests for environment value normalization."""

    def setUp(self):
        """Set up test data."""
        self.service = InventoryService()

    def test_normalize_standard_values(self):
        """Test normalization of standard environment values."""
        self.assertEqual(self.service._normalize_environment('dev'), 'dev')
        self.assertEqual(self.service._normalize_environment('staging'), 'staging')
        self.assertEqual(self.service._normalize_environment('prod'), 'prod')

    def test_normalize_certif_to_staging(self):
        """Test that 'certif' is normalized to 'staging'."""
        self.assertEqual(self.service._normalize_environment('certif'), 'staging')
        self.assertEqual(self.service._normalize_environment('certification'), 'staging')

    def test_normalize_aliases(self):
        """Test normalization of common aliases."""
        self.assertEqual(self.service._normalize_environment('stg'), 'staging')
        self.assertEqual(self.service._normalize_environment('development'), 'dev')
        self.assertEqual(self.service._normalize_environment('production'), 'prod')

    def test_normalize_unknown_defaults_to_dev(self):
        """Test that unknown values default to dev."""
        self.assertEqual(self.service._normalize_environment('unknown'), 'dev')
        self.assertEqual(self.service._normalize_environment('test'), 'dev')
        self.assertEqual(self.service._normalize_environment(''), 'dev')

    @patch('inventory.services.connection')
    def test_certif_environment_normalized_in_results(self, mock_connection):
        """Test that CERTIF from Oracle is normalized to staging in results."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'CERTIF', 'SERVER'),
            ('srv-certif-02', 'certification', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 2)
        self.assertEqual(targets[0]['environment'], 'staging')
        self.assertEqual(targets[1]['environment'], 'staging')


# =============================================================================
# Story 13.3: RBAC environment and target permission tests
# =============================================================================

class RBACEnvironmentFilterTests(TestCase):
    """
    Story 13.3, AC1: Tests for RBAC environment-based filtering.
    Tests that users only see targets in their allowed environments.
    """

    def setUp(self):
        """Set up profiles with environment restrictions."""
        self.service = InventoryService()

        # Profile with DEV + STAGING access only (no PROD)
        self.dev_staging_profile = Profile.objects.create(
            name='dev-staging-team',
            description='Dev and Staging access',
            ad_group='GRP-DEV-STAGING'
        )
        ProfileActionPermission.objects.create(
            profile=self.dev_staging_profile,
            permission_type='ALL',
            environments_json='["dev", "staging"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.dev_staging_profile,
            permission_type='ALL'
        )

    @patch('inventory.services.connection')
    def test_list_targets_environment_filter(self, mock_connection):
        """
        AC1: User with DEV+STAGING access should not see PROD targets.
        Scenario 1 from story Dev Notes.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'dev', 'server'),
            ('srv-stg-01', 'staging', 'server'),
            ('srv-prod-01', 'prod', 'server'),  # Should be filtered out
            ('srv-prod-02', 'prod', 'database'),  # Should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-DEV-STAGING']
        )

        # Only DEV and STAGING targets should be returned
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('srv-dev-01', names)
        self.assertIn('srv-stg-01', names)
        self.assertNotIn('srv-prod-01', names)
        self.assertNotIn('srv-prod-02', names)

    @patch('inventory.services.connection')
    def test_list_targets_certif_normalized_to_staging(self, mock_connection):
        """
        AC1: CERTIF environment from inventory should be accessible
        as staging for users with staging permission.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'certif', 'server'),  # Normalized to staging
            ('srv-certif-02', 'certification', 'server'),  # Normalized to staging
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-DEV-STAGING']
        )

        # Certif targets normalized to staging should be accessible
        self.assertEqual(total, 2)
        self.assertEqual(targets[0]['environment'], 'staging')
        self.assertEqual(targets[1]['environment'], 'staging')

    @patch('inventory.services.connection')
    def test_list_targets_profile_env_certif_normalized_to_staging(self, mock_connection):
        """
        AC1: When profile has environments_json with 'certif', allowed_environments
        must be normalized so targets from inventory (certif -> staging) are included.
        """
        # Profile with raw "certif" in DB (no "staging" string)
        certif_only_profile = Profile.objects.create(
            name='certif-only',
            description='Certif only',
            ad_group='GRP-CERTIF-ONLY'
        )
        ProfileActionPermission.objects.create(
            profile=certif_only_profile,
            permission_type='ALL',
            environments_json='["certif"]'
        )
        ProfileTargetPermission.objects.create(
            profile=certif_only_profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'certif', 'server'),
            ('srv-certif-02', 'certification', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-CERTIF-ONLY']
        )

        self.assertEqual(total, 2)
        self.assertEqual(targets[0]['environment'], 'staging')
        self.assertEqual(targets[1]['environment'], 'staging')


class RBACPatternRestrictionTests(TestCase):
    """
    Story 13.3, AC2: Tests for RBAC pattern-based target restrictions.
    Tests that pattern restrictions filter targets correctly.
    """

    def setUp(self):
        """Set up profile with pattern restriction."""
        self.service = InventoryService()

        # Profile with DEV access and pattern restriction web-*
        self.web_only_profile = Profile.objects.create(
            name='web-team',
            description='Web servers only',
            ad_group='GRP-WEB-TEAM'
        )
        ProfileActionPermission.objects.create(
            profile=self.web_only_profile,
            permission_type='ALL',
            environments_json='["dev"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.web_only_profile,
            permission_type='PATTERN',
            target_patterns_json='["web-*"]'
        )

    @patch('inventory.services.connection')
    def test_list_targets_pattern_restriction(self, mock_connection):
        """
        AC2: Pattern web-* should only match web- prefixed targets.
        Scenario 2 from story Dev Notes.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-dev-01', 'dev', 'server'),
            ('web-dev-02', 'dev', 'server'),
            ('db-dev-01', 'dev', 'database'),  # Should be filtered out
            ('api-dev-01', 'dev', 'server'),  # Should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-WEB-TEAM']
        )

        # Only web-* targets should be returned
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('web-dev-01', names)
        self.assertIn('web-dev-02', names)
        self.assertNotIn('db-dev-01', names)
        self.assertNotIn('api-dev-01', names)

    @patch('inventory.services.connection')
    def test_list_targets_pattern_case_insensitive(self, mock_connection):
        """
        AC2: Pattern matching should be case insensitive.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('WEB-DEV-01', 'dev', 'server'),  # Uppercase
            ('Web-Dev-02', 'dev', 'server'),  # Mixed case
            ('web-dev-03', 'dev', 'server'),  # Lowercase
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-WEB-TEAM']
        )

        # All should match regardless of case
        self.assertEqual(total, 3)

    @patch('inventory.services.connection')
    def test_list_targets_pattern_with_env_filter_combined(self, mock_connection):
        """
        AC2: Pattern should combine with environment filter.
        PROD targets should never be visible even if pattern matches.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('web-dev-01', 'dev', 'server'),
            ('web-prod-01', 'prod', 'server'),  # Should be filtered out (wrong env)
            ('db-dev-01', 'dev', 'database'),  # Should be filtered out (wrong pattern)
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-WEB-TEAM']
        )

        # Only web-dev-01 matches both env and pattern
        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['name'], 'web-dev-01')


class RBACListRestrictionTests(TestCase):
    """
    Story 13.3, AC3: Tests for RBAC list-based target restrictions.
    Tests that explicit target lists filter correctly.
    """

    def setUp(self):
        """Set up profile with list restriction."""
        self.service = InventoryService()

        # Profile with DEV+STAGING access and explicit target list
        self.explicit_list_profile = Profile.objects.create(
            name='specific-servers',
            description='Access to specific servers only',
            ad_group='GRP-SPECIFIC'
        )
        ProfileActionPermission.objects.create(
            profile=self.explicit_list_profile,
            permission_type='ALL',
            environments_json='["dev", "staging"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.explicit_list_profile,
            permission_type='LIST',
            target_names_json='["srv-01", "srv-02"]'
        )

    @patch('inventory.services.connection')
    def test_list_targets_list_restriction(self, mock_connection):
        """
        AC3: Explicit list [srv-01, srv-02] should only match those targets.
        Scenario 3 from story Dev Notes.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'staging', 'server'),
            ('srv-03', 'dev', 'server'),  # Should be filtered out (not in list)
            ('srv-04', 'staging', 'server'),  # Should be filtered out (not in list)
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-SPECIFIC']
        )

        # Only srv-01 and srv-02 should be returned
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('srv-01', names)
        self.assertIn('srv-02', names)
        self.assertNotIn('srv-03', names)
        self.assertNotIn('srv-04', names)

    @patch('inventory.services.connection')
    def test_list_targets_list_with_env_filter(self, mock_connection):
        """
        AC3: List restriction should combine with environment filter.
        Targets in list but wrong environment should be filtered.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'prod', 'server'),  # In list but wrong env
            ('srv-03', 'dev', 'server'),  # Right env but not in list
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-SPECIFIC']
        )

        # Only srv-01 matches both env and list
        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['name'], 'srv-01')

    @patch('inventory.services.connection')
    def test_list_targets_list_case_insensitive(self, mock_connection):
        """
        AC3: List restriction should match case-insensitively (consistency with PATTERN).
        Profile list has srv-01, srv-02 (lowercase).
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),  # Exact match
            ('SRV-02', 'staging', 'server'),  # Uppercase in inventory - should match srv-02
            ('Srv-03', 'dev', 'server'),  # Not in list - should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-SPECIFIC']  # List has srv-01, srv-02 (lowercase)
        )

        # srv-01 and SRV-02 should match (case-insensitive); Srv-03 not in list
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('srv-01', names)
        self.assertIn('SRV-02', names)
        self.assertNotIn('Srv-03', names)


class RBACMultiProfileUnionTests(TestCase):
    """
    Story 13.3, AC5: Tests for multi-profile permission union (RM6).
    Tests that permissions from multiple profiles are combined.
    """

    def setUp(self):
        """Set up multiple profiles for the same user."""
        self.service = InventoryService()

        # Profile A: DEV access with explicit target list
        self.profile_a = Profile.objects.create(
            name='profile-a',
            description='DEV access with specific target',
            ad_group='GRP-PROFILE-A'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile_a,
            permission_type='ALL',
            environments_json='["dev"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.profile_a,
            permission_type='LIST',
            target_names_json='["srv-01"]'
        )

        # Profile B: STAGING access with ALL targets
        self.profile_b = Profile.objects.create(
            name='profile-b',
            description='STAGING access with all targets',
            ad_group='GRP-PROFILE-B'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile_b,
            permission_type='ALL',
            environments_json='["staging"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.profile_b,
            permission_type='ALL'
        )

    @patch('inventory.services.connection')
    def test_list_targets_multi_profile_union(self, mock_connection):
        """
        AC5/RM6: Multi-profile union should combine environments and targets.
        Scenario 4 from story Dev Notes.
        User with both profiles should see:
        - srv-01 from DEV (profile A)
        - All STAGING targets (profile B)
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'dev', 'server'),  # DEV but not in profile A's list
            ('srv-stg-01', 'staging', 'server'),
            ('srv-prod-01', 'prod', 'server'),  # Should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # User belongs to both profiles
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-PROFILE-A', 'GRP-PROFILE-B']
        )

        # Should see: srv-01 (DEV, in list) + srv-stg-01 (STAGING, ALL)
        # But NOT srv-02 (DEV but not in profile A's list) unless profile B also grants DEV
        # Actually: Profile A grants DEV with LIST restriction
        # Profile B grants STAGING with ALL
        # Union of envs = {dev, staging}
        # has_all_access = True (profile B has ALL)
        # So actually all DEV+STAGING targets should be visible
        self.assertEqual(total, 3)
        names = [t['name'] for t in targets]
        self.assertIn('srv-01', names)
        self.assertIn('srv-02', names)  # Visible because profile B has ALL
        self.assertIn('srv-stg-01', names)
        self.assertNotIn('srv-prod-01', names)

    @patch('inventory.services.connection')
    def test_list_targets_multi_profile_pattern_union(self, mock_connection):
        """
        AC5/RM6: Multiple pattern profiles should be unioned.
        """
        # Create profile C with different pattern
        profile_c = Profile.objects.create(
            name='profile-c',
            description='DEV access with db-* pattern',
            ad_group='GRP-PROFILE-C'
        )
        ProfileActionPermission.objects.create(
            profile=profile_c,
            permission_type='ALL',
            environments_json='["dev"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile_c,
            permission_type='PATTERN',
            target_patterns_json='["db-*"]'
        )

        # Profile D with web-* pattern
        profile_d = Profile.objects.create(
            name='profile-d',
            description='DEV access with web-* pattern',
            ad_group='GRP-PROFILE-D'
        )
        ProfileActionPermission.objects.create(
            profile=profile_d,
            permission_type='ALL',
            environments_json='["dev"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile_d,
            permission_type='PATTERN',
            target_patterns_json='["web-*"]'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-dev-01', 'dev', 'server'),
            ('db-dev-01', 'dev', 'database'),
            ('api-dev-01', 'dev', 'server'),  # Neither pattern matches
            ('srv-prod-01', 'prod', 'server'),  # Wrong env
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # User has both pattern profiles
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-PROFILE-C', 'GRP-PROFILE-D']
        )

        # Should see web-* and db-* (union of patterns)
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('web-dev-01', names)
        self.assertIn('db-dev-01', names)
        self.assertNotIn('api-dev-01', names)


class RBACEdgeCaseTests(TestCase):
    """
    Story 13.3: Edge case tests for RBAC filtering.
    """

    def setUp(self):
        """Set up test data."""
        self.service = InventoryService()

    @patch('inventory.services.connection')
    def test_no_profiles_returns_empty(self, mock_connection):
        """User with no matching profiles should get empty result."""
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-UNKNOWN']
        )
        self.assertEqual(total, 0)
        self.assertEqual(len(targets), 0)

    @patch('inventory.services.connection')
    def test_empty_ad_groups_returns_empty(self, mock_connection):
        """User with empty AD groups should get empty result."""
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=[]
        )
        self.assertEqual(total, 0)

    def test_profile_with_no_permissions_returns_empty(self):
        """Profile without permissions should return empty."""
        # Profile with no action/target permissions
        empty_profile = Profile.objects.create(
            name='empty-profile',
            description='No permissions',
            ad_group='GRP-EMPTY'
        )

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-EMPTY']
        )
        self.assertEqual(total, 0)

    @patch('inventory.services.connection')
    def test_admin_profile_gets_all_access(self, mock_connection):
        """Admin profile with is_admin=1 and ALL permissions gets full access."""
        admin_profile = Profile.objects.create(
            name='super-admin',
            description='Super admin',
            ad_group='GRP-SUPERADMIN',
            is_admin=1
        )
        ProfileActionPermission.objects.create(
            profile=admin_profile,
            permission_type='ALL',
            environments_json='["dev", "staging", "prod"]'
        )
        ProfileTargetPermission.objects.create(
            profile=admin_profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'dev', 'server'),
            ('srv-stg-01', 'staging', 'server'),
            ('srv-prod-01', 'prod', 'server'),
            ('db-prod-01', 'prod', 'database'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-SUPERADMIN']
        )

        # Admin should see all targets
        self.assertEqual(total, 4)

    @patch('inventory.services.connection')
    def test_pagination_works_with_rbac_filter(self, mock_connection):
        """Pagination should work correctly after RBAC filtering."""
        profile = Profile.objects.create(
            name='paginated-profile',
            description='For pagination test',
            ad_group='GRP-PAGINATED'
        )
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            environments_json='["dev"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'dev', 'server'),
            ('srv-dev-02', 'dev', 'server'),
            ('srv-dev-03', 'dev', 'server'),
            ('srv-dev-04', 'dev', 'server'),
            ('srv-dev-05', 'dev', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Request page 2 with page_size 2
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-PAGINATED'],
            page=2,
            page_size=2
        )

        # Total should be 5, but only 2 results on page 2
        self.assertEqual(total, 5)
        self.assertEqual(len(targets), 2)
        names = [t['name'] for t in targets]
        self.assertIn('srv-dev-03', names)
        self.assertIn('srv-dev-04', names)
