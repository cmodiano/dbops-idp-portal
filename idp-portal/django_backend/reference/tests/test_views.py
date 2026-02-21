"""
Tests for reference API views.
Story 13.7 - Tests for GET /api/v1/reference/engines and /api/v1/reference/platforms.
Story 30.6 - Updated to verify {"data": [...]} response format (APIFMT-3 fix).
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole

User = get_user_model()


class RefEnginesAPITests(TestCase):
    """Tests for GET /api/v1/reference/engines endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create test engines
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        RefEngine.objects.create(code='SQL Server', label='SQL Server', display_order=2, is_active=1)
        RefEngine.objects.create(code='DB2', label='DB2', display_order=3, is_active=1)
        RefEngine.objects.create(code='PostgreSQL', label='PostgreSQL', display_order=4, is_active=0)  # Inactive

    def test_list_engines_active_only(self):
        """Test listing active engines only (default)."""
        response = self.client.get('/api/v1/reference/engines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)  # Only active engines

        codes = [e['code'] for e in data]
        self.assertIn('Oracle', codes)
        self.assertIn('SQL Server', codes)
        self.assertIn('DB2', codes)
        self.assertNotIn('PostgreSQL', codes)

    def test_list_engines_all(self):
        """Test listing all engines including inactive."""
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 4)  # All engines including inactive

    def test_list_engines_ordered(self):
        """Test engines are ordered by display_order, then code."""
        response = self.client.get('/api/v1/reference/engines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        codes = [e['code'] for e in response.data['data']]
        self.assertEqual(codes, ['Oracle', 'SQL Server', 'DB2'])  # Ordered by display_order

    def test_list_engines_requires_authentication(self):
        """Test endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/reference/engines/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_engine_serializer_fields(self):
        """Test engine serializer includes all required fields (Story 29.3: + normalized_code)."""
        response = self.client.get('/api/v1/reference/engines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        engine = response.data['data'][0]
        self.assertIn('id', engine)
        self.assertIn('code', engine)
        self.assertIn('label', engine)
        self.assertIn('display_order', engine)
        self.assertIn('is_active', engine)
        self.assertIn('normalized_code', engine)  # Story 29.3

        # Valider que normalized_code est bien normalisé (minuscules + underscores)
        self.assertEqual(engine['normalized_code'], engine['code'].lower().replace(' ', '_'))

    def test_response_format_has_data_wrapper(self):
        """Story 30.6 APIFMT-3: Verify response is wrapped in {"data": [...]}."""
        response = self.client.get('/api/v1/reference/engines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)


class PlatformTypeCatalogueAPITests(TestCase):
    """Story 31.9: Tests for GET /api/v1/reference/platforms endpoint (now backed by IntegrationTypeCatalogue)."""

    def setUp(self):
        """Set up test data using IntegrationTypeCatalogue."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create IntegrationTypeCatalogue entries (role=platform)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP (Ansible Automation Platform)',
            integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        IntegrationTypeCatalogue.objects.create(
            code='github_actions', name='GitHub Actions',
            integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        IntegrationTypeCatalogue.objects.create(
            code='azure_devops', name='Azure DevOps',
            integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        IntegrationTypeCatalogue.objects.create(
            code='terraform_cloud', name='Terraform Cloud',
            integration_role=IntegrationRole.PLATFORM, is_active=False,  # Inactive
        )
        # Service type — should NOT appear in /reference/platforms
        IntegrationTypeCatalogue.objects.create(
            code='servicenow', name='ServiceNow',
            integration_role=IntegrationRole.SERVICE, is_active=True,
        )

    def test_list_platforms_active_only(self):
        """Test listing active platform types only (default)."""
        response = self.client.get('/api/v1/reference/platforms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 3)  # Only active platforms

        codes = [p['code'] for p in data]
        self.assertIn('aap', codes)
        self.assertIn('github_actions', codes)
        self.assertIn('azure_devops', codes)
        self.assertNotIn('terraform_cloud', codes)  # Inactive
        self.assertNotIn('servicenow', codes)  # Service, not platform

    def test_list_platforms_all(self):
        """Test listing all platforms including inactive."""
        response = self.client.get('/api/v1/reference/platforms/?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 4 platforms (active+inactive), NOT the service
        self.assertEqual(len(response.data['data']), 4)

    def test_list_platforms_ordered(self):
        """Test platforms are ordered by code."""
        response = self.client.get('/api/v1/reference/platforms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        codes = [p['code'] for p in response.data['data']]
        self.assertEqual(codes, sorted(codes))

    def test_list_platforms_requires_authentication(self):
        """Test endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/reference/platforms/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_serializer_fields(self):
        """Test platform serializer includes required fields."""
        response = self.client.get('/api/v1/reference/platforms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        platform = response.data['data'][0]
        self.assertIn('code', platform)
        self.assertIn('label', platform)
        self.assertIn('is_active', platform)
        self.assertIn('normalized_code', platform)

    def test_response_format_has_data_wrapper(self):
        """Story 30.6 APIFMT-3: Verify response is wrapped in {"data": [...]}."""
        response = self.client.get('/api/v1/reference/platforms/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
