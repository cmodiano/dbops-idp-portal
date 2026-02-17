"""
Tests for profile import/export YAML endpoints.
Tests: GET /admin/profiles/export, POST /admin/profiles/import
"""

import pytest
import yaml
from io import BytesIO
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from profiles.models import Profile


@pytest.mark.django_db
class TestProfileImportExportViews(TestCase):
    """Tests for profile import/export YAML endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create DBOPS user
        self.dbops_user = User.objects.create(
            username='dbops_user',
            profile='dbops'
        )
        
        # Create non-DBOPS user
        self.regular_user = User.objects.create(
            username='regular_user',
            profile='dba'
        )
        
        # Create test profile
        self.profile = Profile.objects.create(
            name='Existing Profile',
            description='Existing Description',
            ad_group='GRP-EXISTING',
            is_admin=1,
            is_auditor=0
        )
    
    def test_export_profiles_yaml(self):
        """Test GET /admin/profiles/export returns YAML file."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/profiles/export/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/x-yaml')
        self.assertIn('Content-Disposition', response)
        self.assertIn('filename=profiles.yaml', response['Content-Disposition'])
        
        # Parse YAML content
        content = response.content.decode('utf-8')
        parsed = yaml.safe_load(content)
        self.assertIn('profiles', parsed)
        self.assertIsInstance(parsed['profiles'], list)
    
    def test_import_profiles_yaml_new(self):
        """Test POST /admin/profiles/import creates new profiles and returns 201."""
        self.client.force_authenticate(user=self.dbops_user)
        
        yaml_data = {
            'profiles': [
                {
                    'name': 'New Profile',
                    'description': 'New Description',
                    'ad_group': 'GRP-NEW',
                    'is_admin': False,
                    'is_auditor': False,
                    'actions': {'type': 'all'},
                    'targets': {'type': 'all'},
                    'environments': []
                }
            ]
        }
        
        yaml_content = yaml.dump(yaml_data)
        file = BytesIO(yaml_content.encode('utf-8'))
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['created'], 1)
        self.assertEqual(response.data['data']['updated'], 0)
        
        # Verify profile was created
        self.assertTrue(Profile.objects.filter(name='New Profile').exists())
    
    def test_import_profiles_yaml_update(self):
        """Test POST /admin/profiles/import updates existing profiles and returns 200."""
        self.client.force_authenticate(user=self.dbops_user)
        
        yaml_data = {
            'profiles': [
                {
                    'name': 'Existing Profile',
                    'description': 'Updated Description',
                    'ad_group': 'GRP-UPDATED',
                    'is_admin': False,
                    'is_auditor': True,
                    'actions': {'type': 'all'},
                    'targets': {'type': 'all'},
                    'environments': []
                }
            ]
        }
        
        yaml_content = yaml.dump(yaml_data)
        file = BytesIO(yaml_content.encode('utf-8'))
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['created'], 0)
        self.assertEqual(response.data['data']['updated'], 1)
        
        # Verify profile was updated
        updated_profile = Profile.objects.get(name='Existing Profile')
        self.assertEqual(updated_profile.description, 'Updated Description')
        self.assertEqual(updated_profile.ad_group, 'GRP-UPDATED')
    
    def test_import_profiles_yaml_invalid_file(self):
        """Test POST /admin/profiles/import with invalid file extension returns 400."""
        self.client.force_authenticate(user=self.dbops_user)
        
        file = BytesIO(b'invalid content')
        file.name = 'profiles.txt'  # Wrong extension
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_import_profiles_yaml_invalid_syntax(self):
        """Test POST /admin/profiles/import with invalid YAML syntax returns 400."""
        self.client.force_authenticate(user=self.dbops_user)
        
        invalid_yaml = b'invalid: yaml: content: ['
        file = BytesIO(invalid_yaml)
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'INVALID_YAML_SYNTAX')
    
    def test_export_profiles_yaml_unauthenticated(self):
        """Test GET /admin/profiles/export without authentication returns 401."""
        response = self.client.get('/api/v1/admin/profiles/export/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_export_profiles_yaml_forbidden_non_dbops(self):
        """Test GET /admin/profiles/export with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/admin/profiles/export/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_import_profiles_yaml_unauthenticated(self):
        """Test POST /admin/profiles/import without authentication returns 401."""
        yaml_data = {'profiles': []}
        yaml_content = yaml.dump(yaml_data)
        file = BytesIO(yaml_content.encode('utf-8'))
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_import_profiles_yaml_forbidden_non_dbops(self):
        """Test POST /admin/profiles/import with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        yaml_data = {'profiles': []}
        yaml_content = yaml.dump(yaml_data)
        file = BytesIO(yaml_content.encode('utf-8'))
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_import_profiles_yaml_invalidates_cache(self, mock_invalidate):
        """Test POST /admin/profiles/import invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        
        yaml_data = {
            'profiles': [
                {
                    'name': 'Cache Test Profile',
                    'ad_group': 'GRP-CACHE',
                    'actions': {'type': 'all'},
                    'targets': {'type': 'all'},
                    'environments': []
                }
            ]
        }
        yaml_content = yaml.dump(yaml_data)
        file = BytesIO(yaml_content.encode('utf-8'))
        file.name = 'profiles.yaml'
        
        response = self.client.post('/api/v1/admin/profiles/import/', {'file': file}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_invalidate.assert_called_once()
