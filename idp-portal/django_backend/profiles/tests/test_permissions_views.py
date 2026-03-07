"""
Tests for profile permissions API endpoints.
Tests: GET/PUT /admin/profiles/{id}/actions, GET/PUT /admin/profiles/{id}/targets
"""

import pytest
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from profiles.models import Profile


@pytest.mark.django_db
class TestProfilePermissionsViews(TestCase):
    """Tests for profile permissions endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Mock inventory list_environments so environment validation works without Oracle DB
        patcher = patch('profiles.validation.InventoryService.list_environments',
                        return_value=['developpement', 'certification', 'production', 'lab'])
        self.mock_list_envs = patcher.start()
        self.addCleanup(patcher.stop)

        # Profile records (DBOPS, DBA) created by conftest._ensure_admin_profiles

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
            name='Test Profile',
            ad_group='GRP-TEST'
        )
    
    def test_get_profile_actions_default(self):
        """Test GET /admin/profiles/{id}/actions returns default 'all' when no permissions exist."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/actions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['actions_type'], 'all')
        self.assertEqual(response.data['data']['action_ids'], [])
        self.assertEqual(response.data['data']['tag_patterns'], [])
    
    def test_set_profile_actions_list(self):
        """Test PUT /admin/profiles/{id}/actions with actions_type='list'."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'actions_type': 'list',
            'action_ids': [1, 2, 3],
            'environments': ['production', 'developpement']
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['actions_type'], 'list')
        self.assertEqual(response.data['data']['action_ids'], [1, 2, 3])
    
    def test_set_profile_actions_pattern(self):
        """Test PUT /admin/profiles/{id}/actions with actions_type='pattern'."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'actions_type': 'pattern',
            'tag_patterns': ['tag:oracle*', 'tag:database*'],
            'environments': ['production']
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['actions_type'], 'pattern')
        self.assertEqual(response.data['data']['tag_patterns'], ['tag:oracle*', 'tag:database*'])
    
    def test_set_profile_actions_all(self):
        """Test PUT /admin/profiles/{id}/actions with actions_type='all'."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'actions_type': 'all'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['actions_type'], 'all')
    
    def test_set_profile_actions_validation_error(self):
        """Test PUT /admin/profiles/{id}/actions with invalid data returns 400."""
        self.client.force_authenticate(user=self.dbops_user)
        # list type without action_ids
        data = {
            'actions_type': 'list'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_profile_targets_default(self):
        """Test GET /admin/profiles/{id}/targets returns default 'all' when no permissions exist."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/targets/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['targets_type'], 'all')
        self.assertEqual(response.data['data']['target_names'], [])
    
    def test_set_profile_targets_list(self):
        """Test PUT /admin/profiles/{id}/targets with targets_type='list'."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'targets_type': 'list',
            'target_names': ['target1', 'target2']
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/targets/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['targets_type'], 'list')
        self.assertEqual(response.data['data']['target_names'], ['target1', 'target2'])
    
    def test_set_profile_targets_pattern(self):
        """Test PUT /admin/profiles/{id}/targets with targets_type='pattern'."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'targets_type': 'pattern',
            'target_patterns': ['target-*', 'db-*']
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/targets/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['targets_type'], 'pattern')
        self.assertEqual(response.data['data']['target_patterns'], ['target-*', 'db-*'])
    
    def test_set_profile_targets_validation_error(self):
        """Test PUT /admin/profiles/{id}/targets with invalid data returns 400."""
        self.client.force_authenticate(user=self.dbops_user)
        # pattern type without target_patterns
        data = {
            'targets_type': 'pattern'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/targets/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_profile_actions_unauthenticated(self):
        """Test GET /admin/profiles/{id}/actions without authentication returns 401."""
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/actions/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_profile_actions_forbidden_non_dbops(self):
        """Test GET /admin/profiles/{id}/actions with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/actions/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_set_profile_actions_forbidden_non_dbops(self):
        """Test PUT /admin/profiles/{id}/actions with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        data = {'actions_type': 'all'}
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_profile_targets_unauthenticated(self):
        """Test GET /admin/profiles/{id}/targets without authentication returns 401."""
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/targets/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_get_profile_targets_forbidden_non_dbops(self):
        """Test GET /admin/profiles/{id}/targets with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/targets/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_set_profile_targets_forbidden_non_dbops(self):
        """Test PUT /admin/profiles/{id}/targets with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        data = {'targets_type': 'all'}
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/targets/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_set_profile_actions_invalidates_cache(self, mock_invalidate):
        """Test PUT /admin/profiles/{id}/actions invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'actions_type': 'all'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/actions/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_invalidate.assert_called_once()
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_set_profile_targets_invalidates_cache(self, mock_invalidate):
        """Test PUT /admin/profiles/{id}/targets invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'targets_type': 'all'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/targets/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_invalidate.assert_called_once()
