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
        targets, total = self.service.list_targets_for_user(
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

        targets, total = self.service.list_targets_for_user(
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

        targets, total = self.service.list_targets_for_user(
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

        targets, total = self.service.list_targets_for_user(
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
