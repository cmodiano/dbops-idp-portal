"""
Tests for inventory API views.
Story 13.1 - Target API endpoint tests.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from inventory.services import InventoryServiceError


class TargetListViewTests(TestCase):
    """Tests for target list endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create profile with full access
        self.profile = Profile.objects.create(
            name='admin',
            description='Admin profile',
            ad_group='GRP-ADMIN',
            is_admin=1
        )
        ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
            environments_json='["dev", "staging", "prod"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )

        # Mock user for authentication
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.ad_groups = ['GRP-ADMIN']
        self.mock_user.is_authenticated = True
        # Prevent get_ad_groups from being callable
        del self.mock_user.get_ad_groups

    def _authenticate(self):
        """Helper to set up authenticated user."""
        self.client.force_authenticate(user=self.mock_user)

    def test_list_targets_unauthenticated(self):
        """Test listing targets requires authentication."""
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('inventory.services.connection')
    def test_list_targets_authenticated(self, mock_connection):
        """Test listing targets when authenticated."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'prod', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('items', data)
        self.assertIn('total', data)
        self.assertIn('rbac_truncated', data)
        self.assertFalse(data['rbac_truncated'])

    @patch('inventory.services.connection')
    def test_list_targets_with_environment_filter(self, mock_connection):
        """Test filtering targets by environment."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('dev-srv-01', 'dev', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/', {'environment': 'dev'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        for item in data['items']:
            self.assertEqual(item['environment'], 'dev')

    @patch('inventory.services.connection')
    def test_list_targets_pagination(self, mock_connection):
        """Test pagination of target list."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (50,)
        mock_cursor.fetchall.return_value = [
            (f'srv-{i:02d}', 'dev', 'server') for i in range(10)
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/', {'page': 1, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('page', data)
        self.assertIn('page_size', data)
        self.assertIn('total_pages', data)
        self.assertIn('rbac_truncated', data)

    @patch('inventory.views._inventory_service_factory')
    def test_list_targets_response_includes_rbac_truncated_true_when_truncated(self, mock_service_class):
        """Story 13.3: Response must include rbac_truncated; when True, client knows results may be incomplete."""
        mock_service = MagicMock()
        mock_service.list_targets_for_user.return_value = (
            [{'name': 'srv-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            True,
        )
        mock_service_class.return_value = mock_service

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('rbac_truncated', data)
        self.assertTrue(data['rbac_truncated'])

    @patch('inventory.views._inventory_service_factory')
    def test_list_targets_any_environment_accepted(self, mock_service_class):
        """Test any environment string is accepted (no more ChoiceField restriction)."""
        mock_service = MagicMock()
        mock_service.list_targets_for_user.return_value = (
            [{'name': 'srv-01', 'environment': 'quelconque', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )
        mock_service_class.return_value = mock_service

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/', {'environment': 'quelconque'})
        # CharField accepte toute chaîne — pas de 400 ValidationError (ancien comportement ChoiceField)
        self.assertNotEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TargetListAllViewTests(TestCase):
    """Tests for list all targets endpoint (admin only)."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create admin profile
        self.admin_profile = Profile.objects.create(
            name='admin',
            description='Admin profile',
            ad_group='GRP-ADMIN',
            is_admin=1
        )

        # Create non-admin profile
        self.regular_profile = Profile.objects.create(
            name='regular',
            description='Regular user',
            ad_group='GRP-REGULAR',
            is_admin=0
        )

        # Admin user
        self.admin_user = MagicMock()
        self.admin_user.id = 1
        self.admin_user.is_authenticated = True
        self.admin_user.is_staff = False
        self.admin_user.ad_groups = ['GRP-ADMIN']
        # Prevent get_ad_groups from being callable
        del self.admin_user.get_ad_groups

        # Regular user (non-admin)
        self.regular_user = MagicMock()
        self.regular_user.id = 2
        self.regular_user.is_authenticated = True
        self.regular_user.is_staff = False
        self.regular_user.ad_groups = ['GRP-REGULAR']
        # Prevent get_ad_groups from being callable
        del self.regular_user.get_ad_groups

        # Staff user (service account)
        self.staff_user = MagicMock()
        self.staff_user.id = 3
        self.staff_user.is_authenticated = True
        self.staff_user.is_staff = True
        self.staff_user.ad_groups = []
        # Prevent get_ad_groups from being callable
        del self.staff_user.get_ad_groups

    def test_list_all_targets_unauthenticated(self):
        """Test listing all targets requires authentication."""
        response = self.client.get('/api/v1/inventory/targets/all/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_all_targets_non_admin_forbidden(self):
        """Test that non-admin users cannot access /targets/all."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/inventory/targets/all/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('inventory.services.connection')
    def test_list_all_targets_admin_allowed(self, mock_connection):
        """Test that admin users can access /targets/all."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'staging', 'server'),
            ('srv-03', 'prod', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/inventory/targets/all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total'], 3)

    @patch('inventory.services.connection')
    def test_list_all_targets_staff_allowed(self, mock_connection):
        """Test that staff users (service accounts) can access /targets/all."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('srv-01', 'dev', 'server'),
            ('srv-02', 'prod', 'server'),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get('/api/v1/inventory/targets/all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('inventory.views._inventory_service_factory')
    def test_list_all_targets_invalid_environment(self, mock_service_class):
        """Test invalid environment parameter returns 400."""
        mock_service = MagicMock()
        mock_service.list_environments.return_value = ['dev', 'staging', 'prod']
        mock_service_class.return_value = mock_service

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/inventory/targets/all/', {'environment': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_all_targets_invalid_page(self):
        """Test invalid page parameter returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/inventory/targets/all/', {'page': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TargetRBACTests(TestCase):
    """Tests for RBAC filtering in target API."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create profile with limited access
        self.profile = Profile.objects.create(
            name='dev-only',
            description='Dev only access',
            ad_group='GRP-DEV-ONLY'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
            environments_json='["dev"]'  # Only dev access
        )
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )

        # Mock user with dev-only access
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.ad_groups = ['GRP-DEV-ONLY']
        self.mock_user.is_authenticated = True
        # Prevent get_ad_groups from being callable
        del self.mock_user.get_ad_groups

    def _authenticate(self):
        """Helper to set up authenticated user."""
        self.client.force_authenticate(user=self.mock_user)

    @patch('inventory.services.connection')
    def test_list_filters_by_environment_permission(self, mock_connection):
        """Test that list only returns targets in allowed environments."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (2,)
        mock_cursor.fetchall.return_value = [
            ('dev-srv-01', 'dev', 'server'),
            ('prod-srv-01', 'prod', 'server'),  # Should be filtered out by RBAC
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only see dev targets
        for item in data['items']:
            self.assertEqual(item['environment'], 'dev')

    @patch('inventory.services.connection')
    def test_request_forbidden_environment(self, mock_connection):
        """Test that requesting forbidden environment returns empty."""
        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/', {'environment': 'prod'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['total'], 0)


class TargetPatternPermissionTests(TestCase):
    """Tests for pattern-based permissions."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create profile with pattern-based access
        self.profile = Profile.objects.create(
            name='web-team',
            description='Web team access',
            ad_group='GRP-WEB-TEAM'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
            environments_json='["dev", "staging", "prod"]'
        )
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='PATTERN',
            target_patterns_json='["web-*"]'  # Only web-* targets
        )

        # Mock user
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.ad_groups = ['GRP-WEB-TEAM']
        self.mock_user.is_authenticated = True
        # Prevent get_ad_groups from being callable
        del self.mock_user.get_ad_groups

    def _authenticate(self):
        """Helper to set up authenticated user."""
        self.client.force_authenticate(user=self.mock_user)

    @patch('inventory.services.connection')
    def test_list_filters_by_pattern(self, mock_connection):
        """Test that list only returns targets matching pattern."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (4,)
        mock_cursor.fetchall.return_value = [
            ('web-srv-01', 'dev', 'server'),
            ('web-srv-02', 'dev', 'server'),
            ('db-srv-01', 'dev', 'database'),  # Should be filtered
            ('app-srv-01', 'dev', 'server'),   # Should be filtered
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        self._authenticate()
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should only see web-* targets
        self.assertEqual(data['total'], 2)
        for item in data['items']:
            self.assertTrue(item['name'].startswith('web-'))


class TargetServiceErrorTests(TestCase):
    """Tests for error handling when inventory service fails."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create admin profile
        self.admin_profile = Profile.objects.create(
            name='admin',
            description='Admin profile',
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

        self.admin_user = MagicMock()
        self.admin_user.id = 1
        self.admin_user.is_authenticated = True
        self.admin_user.is_staff = True
        self.admin_user.ad_groups = ['GRP-ADMIN']
        # Prevent get_ad_groups from being callable
        del self.admin_user.get_ad_groups

    @patch('inventory.views._inventory_service_factory')
    def test_list_targets_service_error_returns_503(self, mock_service_class):
        """Test that service errors return 503."""
        mock_service = MagicMock()
        mock_service.list_targets_for_user.side_effect = InventoryServiceError(
            "Failed to read inventory: ORA-00942"
        )
        mock_service_class.return_value = mock_service

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/inventory/targets/')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('ORA-00942', response.json()['detail'])

    @patch('inventory.views._inventory_service_factory')
    def test_list_all_targets_service_error_returns_503(self, mock_service_class):
        """Test that service errors on /targets/all return 503."""
        mock_service = MagicMock()
        mock_service.list_targets.side_effect = InventoryServiceError(
            "Invalid table/synonym name"
        )
        mock_service_class.return_value = mock_service

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/inventory/targets/all/')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Invalid table', response.json()['detail'])
