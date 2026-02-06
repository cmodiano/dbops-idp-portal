"""
Tests for inventory environments endpoint.
Story 13.7 - Tests for GET /api/v1/inventory/environments.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from inventory.services import InventoryService

User = get_user_model()


class InventoryEnvironmentsAPITests(TestCase):
    """Tests for GET /api/v1/inventory/environments endpoint."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

    @patch('inventory.views.InventoryService')
    def test_list_environments_success(self, mock_service_class):
        """Test listing environments from inventory."""
        mock_service = MagicMock()
        mock_service.list_environments.return_value = ['dev', 'staging', 'prod']
        mock_service_class.return_value = mock_service

        response = self.client.get('/api/v1/inventory/environments')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data, ['dev', 'staging', 'prod'])

    @patch('inventory.views.InventoryService')
    def test_list_environments_empty(self, mock_service_class):
        """Test listing environments when inventory is empty."""
        mock_service = MagicMock()
        mock_service.list_environments.return_value = []
        mock_service_class.return_value = mock_service

        response = self.client.get('/api/v1/inventory/environments')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    @patch('inventory.views.InventoryService')
    def test_list_environments_service_error(self, mock_service_class):
        """Test handling inventory service error."""
        from inventory.services import InventoryServiceError
        
        mock_service = MagicMock()
        mock_service.list_environments.side_effect = InventoryServiceError("Inventory unavailable")
        mock_service_class.return_value = mock_service

        response = self.client.get('/api/v1/inventory/environments')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('detail', response.data)

    def test_list_environments_requires_authentication(self):
        """Test endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/inventory/environments')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class InventoryServiceEnvironmentsTests(TestCase):
    """Tests for InventoryService.list_environments() method."""

    @patch('inventory.services.InventoryService.list_targets')
    def test_list_environments_from_targets(self, mock_list_targets):
        """Test extracting distinct environments from targets."""
        mock_list_targets.return_value = (
            [
                {'name': 'target1', 'environment': 'dev', 'target_type': 'server'},
                {'name': 'target2', 'environment': 'staging', 'target_type': 'database'},
                {'name': 'target3', 'environment': 'dev', 'target_type': 'server'},
                {'name': 'target4', 'environment': 'prod', 'target_type': 'database'},
            ],
            4
        )

        service = InventoryService()
        environments = service.list_environments()

        self.assertEqual(sorted(environments), ['dev', 'prod', 'staging'])

    @patch('inventory.services.InventoryService.list_targets')
    def test_list_environments_normalized(self, mock_list_targets):
        """Test environments are normalized (certif -> staging)."""
        mock_list_targets.return_value = (
            [
                {'name': 'target1', 'environment': 'dev', 'target_type': 'server'},
                {'name': 'target2', 'environment': 'certif', 'target_type': 'database'},  # Should normalize to staging
                {'name': 'target3', 'environment': 'staging', 'target_type': 'server'},
            ],
            3
        )

        service = InventoryService()
        environments = service.list_environments()

        # certif should be normalized to staging
        self.assertIn('staging', environments)
        self.assertNotIn('certif', environments)
        self.assertEqual(len(environments), 2)  # dev and staging (certif normalized)
