"""
Tests for InventoryService.
Story 13.1 - Service tests with mocked external sources.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase

from inventory.services import InventoryService, InventoryServiceError
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
            ('fallback-srv-01', 'DEVELOPPEMENT', 'SERVER'),
            ('fallback-srv-02', 'PRODUCTION', 'SERVER'),
            ('fallback-db-01', 'DEVELOPPEMENT', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 3)
        self.assertEqual(len(targets), 3)
        self.assertEqual(targets[0]['name'], 'fallback-srv-01')
        self.assertEqual(targets[0]['environment'], 'developpement')

    @patch('inventory.services.connection')
    def test_fallback_with_environment_filter(self, mock_connection):
        """Test fallback with environment filter."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('fallback-srv-01', 'DEVELOPPEMENT', 'SERVER'),
            ('fallback-db-01', 'DEVELOPPEMENT', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets(environment='developpement')

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

    @patch('inventory.services.connection')
    def test_list_from_db_schema_uses_flat_table_column_mapping(self, mock_connection):
        """Test that flat_table config column mapping is used instead of hardcoded NAME, ENVIRONMENT, TYPE."""
        import json
        flat_config = {
            'flat_table': {
                'table': 'DBOPS_INVENTORY.INVENTORY_TARGETS',
                'columns': {'name': 'HOSTNAME', 'environment': 'ENV', 'type': 'TARGET_TYPE'},
            },
        }
        self.integration.config = json.dumps(flat_config)
        self.integration.save()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [('srv-01', 'PRODUCTION', 'server')]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['name'], 'srv-01')
        # Environment is normalized (Story 21.1, 26.7) - PRODUCTION becomes 'production' (lowercase)
        self.assertEqual(targets[0]['environment'], 'production')
        # Verify SQL uses mapped columns (HOSTNAME, ENV, TARGET_TYPE) not hardcoded NAME, ENVIRONMENT, TYPE
        call_args = str(mock_cursor.execute.call_args_list)
        self.assertIn('HOSTNAME', call_args)
        self.assertIn('ENV', call_args)
        self.assertIn('TARGET_TYPE', call_args)
        # Ensure we use mapped columns, not hardcoded defaults
        self.assertNotIn(', NAME,', call_args)
        self.assertNotIn(', ENVIRONMENT,', call_args)


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
            environments_json='["developpement", "certification"]'
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
            environments_json='["developpement", "certification", "production"]'
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
            environment='production'  # Not in allowed environments for dev-team
        )
        self.assertEqual(total, 0)

    @patch('inventory.services.connection')
    def test_list_targets_for_user_pattern_filtering(self, mock_connection):
        """Test that pattern-based restrictions filter targets."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-srv-01', 'developpement', 'server'),
            ('api-srv-01', 'developpement', 'server'),
            ('db-srv-01', 'developpement', 'database'),  # Should be filtered out
            ('batch-srv-01', 'developpement', 'server'),  # Should be filtered out
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
            ('web-srv-01', 'production', 'server'),
            ('db-srv-01', 'production', 'database'),
            ('batch-srv-01', 'production', 'server'),
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
        self.assertEqual(envs, {'developpement', 'certification'})

        envs = self.service.get_allowed_environments_for_user(['GRP-ADMIN'])
        self.assertEqual(envs, {'developpement', 'certification', 'production'})

        envs = self.service.get_allowed_environments_for_user(['GRP-UNKNOWN'])
        self.assertEqual(envs, set())

    def test_get_allowed_environments_certif_no_alias(self):
        """
        Story 53.1 / Story 21.2, Task 2.1: get_allowed_environments_for_user returns raw
        lowercased values only — no alias mapping (certif does NOT become staging).
        """
        certif_profile = Profile.objects.create(
            name='certif-profile',
            description='Certif access',
            ad_group='GRP-CERTIF'
        )
        ProfileActionPermission.objects.create(
            profile=certif_profile,
            permission_type='ALL',
            environments_json='["certif", "lab"]'
        )

        envs = self.service.get_allowed_environments_for_user(['GRP-CERTIF'])
        
        # Story 53.1 — no alias mapping; only lowercase values stored
        self.assertIn('certif', envs)   # Inventory value (lowercased)
        self.assertIn('lab', envs)      # Inventory value (lowercased)
        self.assertNotIn('staging', envs)  # certif is no longer aliased to staging


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

    def test_normalize_inventory_values_passthrough(self):
        """Story 53.1 — certif/certification pass through without alias mapping."""
        self.assertEqual(self.service._normalize_environment('certif'), 'certif')
        self.assertEqual(self.service._normalize_environment('certification'), 'certification')

    def test_normalize_no_aliases(self):
        """Story 53.1 — stg/development/production pass through as-is (no alias mapping)."""
        self.assertEqual(self.service._normalize_environment('stg'), 'stg')
        self.assertEqual(self.service._normalize_environment('development'), 'development')
        self.assertEqual(self.service._normalize_environment('production'), 'production')

    def test_normalize_unknown_returns_raw_value(self):
        """
        Story 21.1: Test that unknown values are returned as-is.
        Inventory is the source of truth - no default to 'dev'.
        """
        self.assertEqual(self.service._normalize_environment('unknown'), 'unknown')
        self.assertEqual(self.service._normalize_environment('test'), 'test')
        self.assertEqual(self.service._normalize_environment('lab'), 'lab')
        self.assertEqual(self.service._normalize_environment(''), '')

    @patch('inventory.services.connection')
    def test_oracle_environment_returned_as_raw_value(self, mock_connection):
        """
        Story 21.1: Test that environment values from Oracle are returned as-is.
        No normalization in _read_oracle_inventory - raw values preserved.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'CERTIF', 'SERVER'),
            ('srv-lab-01', 'lab', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 2)
        # Story 21.1: Raw values with lowercase/trim only
        self.assertEqual(targets[0]['environment'], 'certif')
        self.assertEqual(targets[1]['environment'], 'lab')

    @patch('inventory.services.connection')
    @patch('inventory.services.logger')
    def test_oracle_lab_environment_no_warning(self, mock_logger, mock_connection):
        """
        Story 21.1, AC1: Test that 'lab' from Oracle doesn't trigger warning.
        Raw values are accepted without 'unknown_environment_value_defaulted'.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['environment'], 'lab')
        
        # Verify no warning logged for unknown environment
        # Story 21.1: 'unknown_environment_value_defaulted' should never be logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list
            if 'unknown_environment_value_defaulted' in str(call)
        ]
        self.assertEqual(len(warning_calls), 0, 
                         "No 'unknown_environment_value_defaulted' warning should be logged for 'lab' environment")

    @patch('inventory.services.connection')
    def test_list_environments_returns_raw_values(self, mock_connection):
        """
        Story 21.1, AC3: Test that list_environments() returns distinct raw values.
        Includes non-standard environments like 'lab'.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'developpement', 'SERVER'),
            ('srv-lab-01', 'lab', 'SERVER'),
            ('srv-lab-02', 'lab', 'DATABASE'),
            ('srv-prod-01', 'production', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Clear cache to force fresh read
        from inventory.services import _environments_cache
        _environments_cache.clear()

        environments = self.service.list_environments()

        # Should return distinct raw values (sorted)
        self.assertEqual(environments, ['developpement', 'lab', 'production'])
        self.assertIn('lab', environments, "Non-standard environment 'lab' should be included")


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
            environments_json='["developpement", "certification"]'
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
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-stg-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),  # Should be filtered out
            ('srv-prod-02', 'production', 'database'),  # Should be filtered out
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
    def test_list_targets_staging_profile_cannot_access_certif(self, mock_connection):
        """
        Story 53.1 / Story 21.2, AC1: Profile with 'staging' does NOT access 'certif' targets.
        No alias mapping — certif and staging are distinct inventory values.
        Profile has ["developpement", "certification"] only, so certif/certification targets are filtered out.
        """
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'certif', 'server'),  # Raw value from Oracle
            ('srv-certif-02', 'certification', 'server'),  # Raw value from Oracle
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-DEV-STAGING']  # Profile has ["developpement", "certification"], NOT certif
        )

        # Profile has 'certification' access: srv-certif-02 (certification) passes, srv-certif-01 (certif) is filtered out
        self.assertEqual(total, 1)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['name'], 'srv-certif-02')

    @patch('inventory.services.connection')
    def test_list_targets_profile_env_certif_exact_match(self, mock_connection):
        """
        Story 53.1 / Story 21.2, AC1: Profile with 'certif' accesses ONLY 'certif' targets.
        No alias mapping — allowed_environments = {certif} only (not {staging, certif}).
        Target with env 'certification' does NOT match 'certif', so it is filtered out.
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

        # Story 53.1: allowed_environments = {certif} (no alias mapping)
        # Target 'certif' matches 'certif' → included
        # Target 'certification' does not match 'certif' → excluded
        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['environment'], 'certif')

    @patch('inventory.services.connection')
    def test_list_targets_profile_lab_dev_case_insensitive(self, mock_connection):
        """
        Story 21.2, AC1 / Task 5.2: Profile with ['lab','developpement'] should access lab targets.
        Case-insensitive matching, no alias needed for lab.
        """
        lab_dev_profile = Profile.objects.create(
            name='lab-dev-profile',
            description='Lab and developpement access',
            ad_group='GRP-LAB-DEV'
        )
        ProfileActionPermission.objects.create(
            profile=lab_dev_profile,
            permission_type='ALL',
            environments_json='["lab", "developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=lab_dev_profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-prod-01', 'production', 'server'),  # Should be filtered out
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-LAB-DEV']
        )

        # Should return lab and dev targets only
        self.assertEqual(total, 2)
        names = [t['name'] for t in targets]
        self.assertIn('srv-lab-01', names)
        self.assertIn('srv-dev-01', names)
        self.assertNotIn('srv-prod-01', names)

    @patch('inventory.services.connection')
    def test_list_targets_environment_filter_case_insensitive(self, mock_connection):
        """
        Story 21.2, AC1 / Task 1.3: Environment query param filter should be case-insensitive.
        """
        profile = Profile.objects.create(
            name='multi-env',
            description='Multi environment',
            ad_group='GRP-MULTI'
        )
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            environments_json='["lab", "developpement", "certification"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-lab-02', 'lab', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Filter with uppercase LAB should match lowercase lab
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1,
            ad_groups=['GRP-MULTI'],
            environment='LAB'  # Uppercase filter
        )

        self.assertEqual(total, 2)
        self.assertEqual(targets[0]['environment'], 'lab')
        self.assertEqual(targets[1]['environment'], 'lab')


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
            environments_json='["developpement"]'
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
            ('web-dev-01', 'developpement', 'server'),
            ('web-dev-02', 'developpement', 'server'),
            ('db-dev-01', 'developpement', 'database'),  # Should be filtered out
            ('api-dev-01', 'developpement', 'server'),  # Should be filtered out
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
            ('WEB-DEV-01', 'developpement', 'server'),  # Uppercase
            ('Web-Dev-02', 'developpement', 'server'),  # Mixed case
            ('web-dev-03', 'developpement', 'server'),  # Lowercase
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
            ('web-dev-01', 'developpement', 'server'),
            ('web-prod-01', 'production', 'server'),  # Should be filtered out (wrong env)
            ('db-dev-01', 'developpement', 'database'),  # Should be filtered out (wrong pattern)
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
            environments_json='["developpement", "certification"]'
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
            ('srv-01', 'developpement', 'server'),
            ('srv-02', 'certification', 'server'),
            ('srv-03', 'developpement', 'server'),  # Should be filtered out (not in list)
            ('srv-04', 'certification', 'server'),  # Should be filtered out (not in list)
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
            ('srv-01', 'developpement', 'server'),
            ('srv-02', 'production', 'server'),  # In list but wrong env
            ('srv-03', 'developpement', 'server'),  # Right env but not in list
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
            ('srv-01', 'developpement', 'server'),  # Exact match
            ('SRV-02', 'certification', 'server'),  # Uppercase in inventory - should match srv-02
            ('Srv-03', 'developpement', 'server'),  # Not in list - should be filtered out
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
            environments_json='["developpement"]'
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
            environments_json='["certification"]'
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
            ('srv-01', 'developpement', 'server'),
            ('srv-02', 'developpement', 'server'),  # DEV but not in profile A's list
            ('srv-stg-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),  # Should be filtered out
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
            environments_json='["developpement"]'
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
            environments_json='["developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile_d,
            permission_type='PATTERN',
            target_patterns_json='["web-*"]'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-dev-01', 'developpement', 'server'),
            ('db-dev-01', 'developpement', 'database'),
            ('api-dev-01', 'developpement', 'server'),  # Neither pattern matches
            ('srv-prod-01', 'production', 'server'),  # Wrong env
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
        Profile.objects.create(
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
            environments_json='["developpement", "certification", "production"]'
        )
        ProfileTargetPermission.objects.create(
            profile=admin_profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-stg-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),
            ('db-prod-01', 'production', 'database'),
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
            environments_json='["developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-dev-02', 'developpement', 'server'),
            ('srv-dev-03', 'developpement', 'server'),
            ('srv-dev-04', 'developpement', 'server'),
            ('srv-dev-05', 'developpement', 'server'),
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


# =============================================================================
# Story 21.3: Comprehensive tests for raw environment values
# =============================================================================


class InventoryRawEnvironmentTests(TestCase):
    """
    Story 21.3, Task 1: Tests for raw environment values in inventory.
    Validates that inventory returns environments as-is from Oracle (lowercase/trim).
    """

    def setUp(self):
        self.service = InventoryService()

    # -- Task 1.1: Verify alias coverage --

    def test_normalize_inventory_certif_passthrough(self):
        """Story 53.1 — certif is no longer aliased to staging; passes through as-is."""
        self.assertEqual(self.service._normalize_environment('certif'), 'certif')

    def test_normalize_inventory_certification_passthrough(self):
        """Story 53.1 — certification passes through as-is (inventory value)."""
        self.assertEqual(self.service._normalize_environment('certification'), 'certification')

    def test_normalize_inventory_stg_passthrough(self):
        """Story 53.1 — stg is no longer aliased to staging; passes through."""
        self.assertEqual(self.service._normalize_environment('stg'), 'stg')

    def test_normalize_inventory_development_passthrough(self):
        """Story 53.1 — development passes through as-is (inventory value)."""
        self.assertEqual(self.service._normalize_environment('development'), 'development')

    def test_normalize_inventory_production_passthrough(self):
        """Story 53.1 — production passes through as-is (inventory value)."""
        self.assertEqual(self.service._normalize_environment('production'), 'production')

    # -- Task 1.2: Non-standard environments returned as-is --

    def test_normalize_lab_returns_raw(self):
        """lab is not an alias, returned as-is."""
        self.assertEqual(self.service._normalize_environment('lab'), 'lab')

    def test_normalize_qa_returns_raw(self):
        """qa is not an alias, returned as-is."""
        self.assertEqual(self.service._normalize_environment('qa'), 'qa')

    def test_normalize_uat_returns_raw(self):
        """uat is not an alias, returned as-is."""
        self.assertEqual(self.service._normalize_environment('uat'), 'uat')

    def test_normalize_unknown_returns_raw(self):
        """Unknown env returned as-is, no fallback to 'dev'."""
        self.assertEqual(self.service._normalize_environment('custom_env'), 'custom_env')

    def test_normalize_case_handling(self):
        """Input is lowercased and trimmed. Story 53.1 — CERTIF → certif (no alias)."""
        self.assertEqual(self.service._normalize_environment('  LAB  '), 'lab')
        self.assertEqual(self.service._normalize_environment('CERTIF'), 'certif')

    def test_normalize_edge_cases(self):
        """Edge cases: None, empty, whitespace."""
        self.assertEqual(self.service._normalize_environment(None), '')
        self.assertEqual(self.service._normalize_environment(''), '')
        self.assertEqual(self.service._normalize_environment('   '), '')

    # -- Task 1.3: Oracle returns lab environments with lowercase --

    @patch('inventory.services.connection')
    def test_oracle_lab_environments_lowercased(self, mock_connection):
        """Oracle ENVIRONMENT='lab', 'LAB', 'Lab' → all returned as 'lab'."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'SERVER'),
            ('srv-lab-02', 'LAB', 'SERVER'),
            ('srv-lab-03', 'Lab', 'DATABASE'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 3)
        for target in targets:
            self.assertEqual(target['environment'], 'lab',
                             f"Expected 'lab' but got '{target['environment']}' for {target['name']}")

    @patch('inventory.services.connection')
    def test_oracle_mixed_non_standard_environments(self, mock_connection):
        """Oracle with lab, qa, uat → all returned as raw lowercase."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'LAB', 'SERVER'),
            ('srv-qa-01', 'QA', 'SERVER'),
            ('srv-uat-01', 'UAT', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total = self.service.list_targets()

        self.assertEqual(total, 3)
        self.assertEqual(targets[0]['environment'], 'lab')
        self.assertEqual(targets[1]['environment'], 'qa')
        self.assertEqual(targets[2]['environment'], 'uat')

    # -- Task 1.4: list_environments() with raw values --

    @patch('inventory.services.connection')
    def test_list_environments_with_non_standard(self, mock_connection):
        """list_environments() returns distinct raw values including non-standard."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            ('srv-1', 'developpement', 'SERVER'),
            ('srv-2', 'lab', 'SERVER'),
            ('srv-3', 'lab', 'DATABASE'),
            ('srv-4', 'certification', 'SERVER'),
            ('srv-5', 'production', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        from inventory.services import _environments_cache
        _environments_cache.clear()

        environments = self.service.list_environments()

        self.assertEqual(sorted(environments), ['certification', 'developpement', 'lab', 'production'])
        self.assertIn('lab', environments)

    # -- Task 1.5: Cache works with raw environments --

    @patch('inventory.services.connection')
    def test_environments_cache_with_raw_values(self, mock_connection):
        """Cache stores and returns raw environment values correctly."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'SERVER'),
            ('srv-dev-01', 'developpement', 'SERVER'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        from inventory.services import _environments_cache
        _environments_cache.clear()

        # First call — populates cache
        envs1 = self.service.list_environments()
        self.assertEqual(sorted(envs1), ['developpement', 'lab'])

        # Second call — should use cache (cursor not called again for env list)
        envs2 = self.service.list_environments()
        self.assertEqual(envs1, envs2)


class RBACNonStandardEnvironmentTests(TestCase):
    """
    Story 21.3, Task 2: Tests for RBAC with non-standard environments.
    Validates profile environment permissions with lab, certif, etc.
    """

    def setUp(self):
        self.service = InventoryService()

    # -- Task 2.1: Profile lab → lab targets --

    @patch('inventory.services.connection')
    def test_profile_lab_allows_lab_targets(self, mock_connection):
        """Profile with environments_json='["lab"]' + targets lab → authorized."""
        lab_profile = Profile.objects.create(
            name='lab-team', description='Lab team', ad_group='GRP-LAB-TEAM'
        )
        ProfileActionPermission.objects.create(
            profile=lab_profile, permission_type='ALL',
            environments_json='["lab"]'
        )
        ProfileTargetPermission.objects.create(
            profile=lab_profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-lab-02', 'lab', 'database'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-LAB-TEAM']
        )

        self.assertEqual(total, 2)
        for t in targets:
            self.assertEqual(t['environment'], 'lab')

    # -- Task 2.2: Profile certif → certif targets (raw + normalized) --

    @patch('inventory.services.connection')
    def test_profile_certif_allows_only_certif_targets(self, mock_connection):
        """Story 53.1 — Profile with certif → allowed_environments = {certif} only (no alias to staging)."""
        certif_profile = Profile.objects.create(
            name='certif-team', description='Certif', ad_group='GRP-CERTIF-TEAM'
        )
        ProfileActionPermission.objects.create(
            profile=certif_profile, permission_type='ALL',
            environments_json='["certif"]'
        )
        ProfileTargetPermission.objects.create(
            profile=certif_profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'certif', 'server'),
            ('srv-stg-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-CERTIF-TEAM']
        )

        # certif → allowed = {certif} only; staging and prod excluded
        self.assertEqual(total, 1)
        envs = {t['environment'] for t in targets}
        self.assertEqual(envs, {'certif'})

    # -- Task 2.3: Multi-environment profile --

    def test_get_allowed_environments_multi_env(self):
        """Profile with ["lab","dev","staging"] → returns all (plus aliases)."""
        multi_profile = Profile.objects.create(
            name='multi-env', description='Multi', ad_group='GRP-MULTI-ENV'
        )
        ProfileActionPermission.objects.create(
            profile=multi_profile, permission_type='ALL',
            environments_json='["lab", "developpement", "certification"]'
        )

        envs = self.service.get_allowed_environments_for_user(['GRP-MULTI-ENV'])

        # No alias mapping — raw values only
        self.assertIn('lab', envs)
        self.assertIn('developpement', envs)
        self.assertIn('certification', envs)

    # -- Task 2.4: Query param filter case-insensitive --

    @patch('inventory.services.connection')
    def test_environment_filter_case_insensitive_lab(self, mock_connection):
        """environment=LAB, Lab should match targets 'lab' case-insensitively."""
        profile = Profile.objects.create(
            name='lab-ci', description='Lab CI', ad_group='GRP-LAB-CI'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["lab"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Filter with 'LAB'
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-LAB-CI'], environment='LAB'
        )
        self.assertEqual(total, 1)
        self.assertEqual(targets[0]['environment'], 'lab')

        # Filter with 'Lab'
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-LAB-CI'], environment='Lab'
        )
        self.assertEqual(total, 1)

    # -- Task 2.5: Multi-profile union --

    @patch('inventory.services.connection')
    def test_multi_profile_union_lab_dev_staging(self, mock_connection):
        """Profile A(lab,dev) + Profile B(staging) → union {lab, dev, staging}."""
        profile_a = Profile.objects.create(
            name='profile-lab-dev', description='Lab+Dev', ad_group='GRP-A-LD'
        )
        ProfileActionPermission.objects.create(
            profile=profile_a, permission_type='ALL',
            environments_json='["lab", "developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile_a, permission_type='ALL'
        )

        profile_b = Profile.objects.create(
            name='profile-staging', description='Staging', ad_group='GRP-B-STG'
        )
        ProfileActionPermission.objects.create(
            profile=profile_b, permission_type='ALL',
            environments_json='["certification"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile_b, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-stg-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-A-LD', 'GRP-B-STG']
        )

        # Union of environments: lab, developpement, certification → production excluded
        self.assertEqual(total, 3)
        envs = {t['environment'] for t in targets}
        self.assertEqual(envs, {'lab', 'developpement', 'certification'})

    def test_multi_profile_get_allowed_environments_union(self):
        """get_allowed_environments union from multiple profiles."""
        p_a = Profile.objects.create(
            name='pa', description='PA', ad_group='GRP-PA-UNION'
        )
        ProfileActionPermission.objects.create(
            profile=p_a, permission_type='ALL',
            environments_json='["lab", "developpement"]'
        )
        p_b = Profile.objects.create(
            name='pb', description='PB', ad_group='GRP-PB-UNION'
        )
        ProfileActionPermission.objects.create(
            profile=p_b, permission_type='ALL',
            environments_json='["certification"]'
        )

        envs = self.service.get_allowed_environments_for_user(
            ['GRP-PA-UNION', 'GRP-PB-UNION']
        )

        self.assertIn('lab', envs)
        self.assertIn('developpement', envs)
        self.assertIn('certification', envs)
        self.assertNotIn('production', envs)


class EnvironmentVariantLegacyAliasTests(TestCase):
    """
    Story 21.3, Task 5 / Story 53.1: Environment normalization — no alias mapping.
    Inventory is the sole source of truth; values pass through as lowercased.
    """

    def setUp(self):
        self.service = InventoryService()

    def test_alias_certif_passthrough(self):
        """Story 53.1 — certif passes through as certif (no alias to staging)."""
        self.assertEqual(self.service._normalize_environment('certif'), 'certif')

    def test_alias_certification_passthrough(self):
        """Story 53.1 — certification passes through as certification."""
        self.assertEqual(self.service._normalize_environment('certification'), 'certification')

    def test_alias_stg_passthrough(self):
        """Story 53.1 — stg passes through as stg (no alias to staging)."""
        self.assertEqual(self.service._normalize_environment('stg'), 'stg')

    def test_alias_development_passthrough(self):
        """Story 53.1 — development passes through as development (no alias to dev)."""
        self.assertEqual(self.service._normalize_environment('development'), 'development')

    def test_alias_production_passthrough(self):
        """Story 53.1 — production passes through as production (no alias to prod)."""
        self.assertEqual(self.service._normalize_environment('production'), 'production')

    @patch('inventory.services.connection')
    def test_rbac_certif_profile_matches_only_certif_targets(self, mock_connection):
        """Story 53.1 — Profile with 'certif' authorizes ONLY certif targets (no staging alias)."""
        certif_profile = Profile.objects.create(
            name='certif-rbac', description='Certif RBAC', ad_group='GRP-CERTIF-RBAC'
        )
        ProfileActionPermission.objects.create(
            profile=certif_profile, permission_type='ALL',
            environments_json='["certif"]'
        )
        ProfileTargetPermission.objects.create(
            profile=certif_profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-certif-01', 'certif', 'server'),
            ('srv-staging-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-CERTIF-RBAC']
        )

        # Profile certif → allowed = {certif} only; staging and prod excluded
        self.assertEqual(total, 1)
        envs = {t['environment'] for t in targets}
        self.assertEqual(envs, {'certif'})

    def test_get_allowed_environments_certif_returns_certif_only(self):
        """Story 53.1 — get_allowed_environments for 'certif' returns only certif (no staging alias)."""
        profile = Profile.objects.create(
            name='certif-env', description='Certif env', ad_group='GRP-CERTIF-ENV'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["certif"]'
        )

        envs = self.service.get_allowed_environments_for_user(['GRP-CERTIF-ENV'])

        self.assertIn('certif', envs)
        self.assertNotIn('staging', envs)  # Story 53.1: alias mapping removed


class InventoryIntegrationEndToEndTests(TestCase):
    """
    Story 21.3, Task 6: Integration tests for inventory → profiles → executions.
    End-to-end scenarios with non-standard environments.
    """

    def setUp(self):
        self.service = InventoryService()

    # -- Task 6.1: End-to-end lab scenario --

    @patch('inventory.services.connection')
    def test_end_to_end_lab_scenario(self, mock_connection):
        """
        Full scenario: profile lab/dev → list targets → filter lab → verify access.
        """
        profile = Profile.objects.create(
            name='e2e-lab', description='E2E Lab', ad_group='GRP-E2E-LAB'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["lab", "developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-lab-02', 'lab', 'database'),
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Step 1: List all targets for user
        all_targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-LAB']
        )
        self.assertEqual(total, 3)  # lab + developpement, no production

        # Step 2: Filter by lab
        lab_targets, lab_total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-LAB'], environment='lab'
        )
        self.assertEqual(lab_total, 2)
        for t in lab_targets:
            self.assertEqual(t['environment'], 'lab')

        # Step 3: Verify get_allowed_environments
        envs = self.service.get_allowed_environments_for_user(['GRP-E2E-LAB'])
        self.assertIn('lab', envs)
        self.assertIn('developpement', envs)
        self.assertNotIn('production', envs)

    # -- AC#1 Story 53.1: Valeurs réelles Oracle (developpement, certification, production) --

    @patch('inventory.services.connection')
    def test_ac1_inventory_oracle_values_developpement(self, mock_connection):
        """
        Story 53.1, AC#1 + AC#2: list_servers(environment='developpement') retourne les serveurs
        quand l'inventaire Oracle contient ENV='developpement'.
        Aucun appel avec 'dev' — seules les valeurs brutes de l'inventaire sont utilisées.
        """
        profile = Profile.objects.create(
            name='e2e-oracle', description='E2E Oracle values', ad_group='GRP-E2E-ORACLE'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["developpement", "certification", "production"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-dev-fr-01', 'developpement', 'server'),
            ('srv-certif-fr-01', 'certification', 'server'),
            ('srv-prod-fr-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # AC#1: developpement retourne les serveurs
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-ORACLE']
        )
        self.assertEqual(total, 3)
        envs = {t['environment'] for t in targets}
        self.assertEqual(envs, {'developpement', 'certification', 'production'})

        # AC#1: filtrer par 'developpement' retourne uniquement les serveurs developpement
        dev_targets, dev_total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-ORACLE'], environment='developpement'
        )
        self.assertEqual(dev_total, 1)
        self.assertEqual(dev_targets[0]['environment'], 'developpement')

        # AC#2: allowed_environments ne contient pas 'dev' — valeurs brutes Oracle uniquement
        allowed = self.service.get_allowed_environments_for_user(['GRP-E2E-ORACLE'])
        self.assertIn('developpement', allowed)
        self.assertIn('certification', allowed)
        self.assertIn('production', allowed)
        self.assertNotIn('dev', allowed)
        self.assertNotIn('staging', allowed)
        self.assertNotIn('prod', allowed)

    # -- Task 6.2: Mixed environments scenario --

    @patch('inventory.services.connection')
    def test_mixed_environments_scenario(self, mock_connection):
        """Inventory with {lab, dev, certif, staging, prod} → RBAC filters appropriately."""
        profile = Profile.objects.create(
            name='e2e-mixed', description='E2E Mixed', ad_group='GRP-E2E-MIXED'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["lab", "certif", "developpement"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-dev-01', 'developpement', 'server'),
            ('srv-certif-01', 'certif', 'server'),
            ('srv-staging-01', 'certification', 'server'),
            ('srv-prod-01', 'production', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-MIXED']
        )

        # Story 53.1 — certif → allowed = {certif} only (no alias to staging)
        # allowed_environments = {lab, certif, developpement}
        # lab matches lab, developpement matches developpement, certif matches certif; staging and production excluded
        self.assertEqual(total, 3)
        envs = {t['environment'] for t in targets}
        self.assertEqual(envs, {'lab', 'developpement', 'certif'})

    # -- Task 6.3: Case-insensitive consistency --

    @patch('inventory.services.connection')
    def test_case_insensitive_consistency(self, mock_connection):
        """No forced normalization in inventory, case-insensitive comparison everywhere."""
        profile = Profile.objects.create(
            name='e2e-case', description='E2E Case', ad_group='GRP-E2E-CASE'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["lab"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-1', 'lab', 'server'),     # Already lowercase
            ('srv-2', 'LAB', 'server'),     # Uppercase from Oracle → lowercased in read
            ('srv-3', 'Lab', 'server'),     # Mixed → lowercased in read
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-CASE']
        )

        # All Oracle values are lowercased in _read_oracle_inventory
        self.assertEqual(total, 3)
        for t in targets:
            self.assertEqual(t['environment'], 'lab')

    # -- Task 6.4: Pagination with non-standard env filter --

    @patch('inventory.services.connection')
    def test_pagination_with_non_standard_env_filter(self, mock_connection):
        """Pagination works correctly when filtering non-standard environments."""
        profile = Profile.objects.create(
            name='e2e-page', description='E2E Pagination', ad_group='GRP-E2E-PAGE'
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL',
            environments_json='["lab"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_cursor.fetchall.return_value = [
            ('srv-lab-01', 'lab', 'server'),
            ('srv-lab-02', 'lab', 'server'),
            ('srv-lab-03', 'lab', 'server'),
            ('srv-lab-04', 'lab', 'server'),
            ('srv-lab-05', 'lab', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Page 1, size 2
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-PAGE'],
            environment='lab', page=1, page_size=2
        )
        self.assertEqual(total, 5)
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]['name'], 'srv-lab-01')

        # Page 3, size 2
        targets, total, _ = self.service.list_targets_for_user(
            user_id=1, ad_groups=['GRP-E2E-PAGE'],
            environment='lab', page=3, page_size=2
        )
        self.assertEqual(total, 5)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['name'], 'srv-lab-05')


class InventoryServiceDefaultEnvironmentsTests(TestCase):
    """Story 53.1 — get_default_environments() doit retourner [] (inventaire = seule source de vérité)."""

    def setUp(self):
        self.service = InventoryService()

    def test_get_default_environments_returns_empty_list(self):
        """get_default_environments() retourne [] — aucun fallback codé en dur."""
        result = self.service.get_default_environments()
        self.assertEqual(result, [])

    def test_get_default_environments_is_list(self):
        """Le retour est bien une liste (pas None, pas un set)."""
        result = self.service.get_default_environments()
        self.assertIsInstance(result, list)
