"""
Tests for reference API views.
Story 13.7 - Tests for GET /api/v1/reference/engines and /api/v1/reference/platforms.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from reference.models import RefEngine, RefPlatform

User = get_user_model()


class RefEnginesAPITests(TestCase):
    """Tests for GET /api/v1/reference/engines endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

        # Create test engines
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        RefEngine.objects.create(code='SQL Server', label='SQL Server', display_order=2, is_active=1)
        RefEngine.objects.create(code='DB2', label='DB2', display_order=3, is_active=1)
        RefEngine.objects.create(code='PostgreSQL', label='PostgreSQL', display_order=4, is_active=0)  # Inactive

    def test_list_engines_active_only(self):
        """Test listing active engines only (default)."""
        response = self.client.get('/api/v1/reference/engines')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)  # Only active engines
        
        codes = [e['code'] for e in response.data]
        self.assertIn('Oracle', codes)
        self.assertIn('SQL Server', codes)
        self.assertIn('DB2', codes)
        self.assertNotIn('PostgreSQL', codes)

    def test_list_engines_all(self):
        """Test listing all engines including inactive."""
        response = self.client.get('/api/v1/reference/engines?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # All engines including inactive

    def test_list_engines_ordered(self):
        """Test engines are ordered by display_order, then code."""
        response = self.client.get('/api/v1/reference/engines')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        codes = [e['code'] for e in response.data]
        self.assertEqual(codes, ['DB2', 'Oracle', 'SQL Server'])  # Ordered by display_order

    def test_list_engines_requires_authentication(self):
        """Test endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/reference/engines')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_engine_serializer_fields(self):
        """Test engine serializer includes all required fields."""
        response = self.client.get('/api/v1/reference/engines')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        engine = response.data[0]
        self.assertIn('id', engine)
        self.assertIn('code', engine)
        self.assertIn('label', engine)
        self.assertIn('display_order', engine)
        self.assertIn('is_active', engine)


class RefPlatformsAPITests(TestCase):
    """Tests for GET /api/v1/reference/platforms endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

        # Create test platforms
        RefPlatform.objects.create(code='AAP', label='AAP (Ansible Automation Platform)', display_order=1, is_active=1)
        RefPlatform.objects.create(code='GitHub Actions', label='GitHub Actions', display_order=2, is_active=1)
        RefPlatform.objects.create(code='Azure DevOps', label='Azure DevOps', display_order=3, is_active=1)
        RefPlatform.objects.create(code='Terraform', label='Terraform', display_order=4, is_active=0)  # Inactive

    def test_list_platforms_active_only(self):
        """Test listing active platforms only (default)."""
        response = self.client.get('/api/v1/reference/platforms')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)  # Only active platforms
        
        codes = [p['code'] for p in response.data]
        self.assertIn('AAP', codes)
        self.assertIn('GitHub Actions', codes)
        self.assertIn('Azure DevOps', codes)
        self.assertNotIn('Terraform', codes)

    def test_list_platforms_all(self):
        """Test listing all platforms including inactive."""
        response = self.client.get('/api/v1/reference/platforms?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)  # All platforms including inactive

    def test_list_platforms_ordered(self):
        """Test platforms are ordered by display_order, then code."""
        response = self.client.get('/api/v1/reference/platforms')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        codes = [p['code'] for p in response.data]
        self.assertEqual(codes, ['AAP', 'Azure DevOps', 'GitHub Actions'])  # Ordered by display_order

    def test_list_platforms_requires_authentication(self):
        """Test endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/reference/platforms')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_platform_serializer_fields(self):
        """Test platform serializer includes all required fields."""
        response = self.client.get('/api/v1/reference/platforms')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        platform = response.data[0]
        self.assertIn('id', platform)
        self.assertIn('code', platform)
        self.assertIn('label', platform)
        self.assertIn('display_order', platform)
        self.assertIn('is_active', platform)
