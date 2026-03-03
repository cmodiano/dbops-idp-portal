"""
Tests for profiles API endpoints (DRF ViewSets).
Tests: GET /admin/profiles, POST /admin/profiles, GET /admin/profiles/{id}, PUT /admin/profiles/{id}, DELETE /admin/profiles/{id}
"""

import pytest
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from profiles.models import Profile


@pytest.mark.django_db
class TestProfileViewSet(TestCase):
    """Tests for ProfileViewSet (admin profiles endpoints)."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create DBOPS user (required for admin endpoints)
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
            description='Test Description',
            ad_group='GRP-TEST',
            is_admin=0,
            is_auditor=0
        )
    
    def test_list_profiles_authenticated_dbops(self):
        """Test GET /admin/profiles with DBOPS user."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/profiles/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)
        self.assertGreaterEqual(len(response.data['data']), 1)
    
    def test_list_profiles_unauthenticated(self):
        """Test GET /admin/profiles without authentication returns 401."""
        response = self.client.get('/api/v1/admin/profiles/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_profiles_forbidden_non_dbops(self):
        """Test GET /admin/profiles with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/admin/profiles/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_profile_forbidden_non_dbops(self):
        """Test POST /admin/profiles with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        data = {
            'name': 'New Profile',
            'ad_group': 'GRP-NEW',
        }
        response = self.client.post('/api/v1/admin/profiles/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_profile_forbidden_non_dbops(self):
        """Test GET /admin/profiles/{id} with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_profile_forbidden_non_dbops(self):
        """Test PUT /admin/profiles/{id} with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        data = {'name': 'Updated Profile'}
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_profile_forbidden_non_dbops(self):
        """Test DELETE /admin/profiles/{id} with non-DBOPS user returns 403."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(f'/api/v1/admin/profiles/{self.profile.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_profile(self):
        """Test POST /admin/profiles creates profile and returns 201."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'name': 'New Profile',
            'description': 'New Description',
            'ad_group': 'GRP-NEW',
            'is_admin': False,
            'is_auditor': False
        }
        response = self.client.post('/api/v1/admin/profiles/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['name'], 'New Profile')
        self.assertEqual(response.data['data']['ad_group'], 'GRP-NEW')
        self.assertIn('is_approver', response.data['data'])
        self.assertFalse(response.data['data']['is_approver'])

    def test_create_profile_duplicate_name(self):
        """Test POST /admin/profiles with duplicate name returns 400."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'name': 'Test Profile',  # Already exists
            'ad_group': 'GRP-DUPLICATE',
        }
        response = self.client.post('/api/v1/admin/profiles/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_get_profile(self):
        """Test GET /admin/profiles/{id} returns profile."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['id'], self.profile.id)
        self.assertEqual(response.data['data']['name'], 'Test Profile')
    
    def test_get_profile_not_found(self):
        """Test GET /admin/profiles/{id} with invalid ID returns 404."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/profiles/99999/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_update_profile(self):
        """Test PUT /admin/profiles/{id} updates profile."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'name': 'Updated Profile',
            'description': 'Updated Description'
        }
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertEqual(response.data['data']['name'], 'Updated Profile')
        self.assertEqual(response.data['data']['description'], 'Updated Description')
    
    def test_delete_profile(self):
        """Test DELETE /admin/profiles/{id} deletes profile and returns 204."""
        self.client.force_authenticate(user=self.dbops_user)
        profile_id = self.profile.id
        response = self.client.delete(f'/api/v1/admin/profiles/{profile_id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Verify profile is deleted
        self.assertFalse(Profile.objects.filter(id=profile_id).exists())
    
    def test_delete_profile_not_found(self):
        """Test DELETE /admin/profiles/{id} with invalid ID returns 404."""
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.delete('/api/v1/admin/profiles/99999/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_create_profile_invalidates_cache(self, mock_invalidate):
        """Test POST /admin/profiles invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'name': 'Cache Test Profile',
            'ad_group': 'GRP-CACHE',
        }
        response = self.client.post('/api/v1/admin/profiles/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_invalidate.assert_called_once()
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_update_profile_invalidates_cache(self, mock_invalidate):
        """Test PUT /admin/profiles/{id} invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        data = {'name': 'Updated Cache Test'}
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_invalidate.assert_called_once()
    
    @patch('profiles.views.invalidate_permissions_cache')
    def test_delete_profile_invalidates_cache(self, mock_invalidate):
        """Test DELETE /admin/profiles/{id} invalidates RBAC cache (Task 7.6)."""
        self.client.force_authenticate(user=self.dbops_user)
        profile_id = self.profile.id
        response = self.client.delete(f'/api/v1/admin/profiles/{profile_id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_invalidate.assert_called_once()

    def test_list_profiles_includes_is_approver(self):
        """
        Story 57.14 AC3: GET /admin/profiles list includes is_approver field.
        """
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get('/api/v1/admin/profiles/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        items = response.data['data']
        self.assertGreater(len(items), 0)
        self.assertIn('is_approver', items[0])

    def test_get_profile_includes_is_approver(self):
        """
        Story 57.14 AC3: GET /admin/profiles/{id} returns is_approver field.
        """
        approver_profile = Profile.objects.create(
            name='Approver Test',
            ad_group='GRP-APPROVER-TEST',
            is_approver=1
        )
        self.client.force_authenticate(user=self.dbops_user)
        response = self.client.get(f'/api/v1/admin/profiles/{approver_profile.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_approver', response.data['data'])
        self.assertTrue(response.data['data']['is_approver'])

    def test_create_profile_with_is_approver(self):
        """
        Story 57.14 AC3: POST /admin/profiles accepts and stores is_approver.
        """
        self.client.force_authenticate(user=self.dbops_user)
        data = {
            'name': 'New Approver Profile',
            'ad_group': 'GRP-NEW-APPROVER',
            'is_admin': False,
            'is_auditor': False,
            'is_approver': True,
        }
        response = self.client.post('/api/v1/admin/profiles/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('is_approver', response.data['data'])
        self.assertTrue(response.data['data']['is_approver'])

    def test_update_profile_with_is_approver(self):
        """
        Story 57.14 AC3: PUT /admin/profiles/{id} updates is_approver field.
        """
        self.client.force_authenticate(user=self.dbops_user)
        data = {'is_approver': True}
        response = self.client.put(f'/api/v1/admin/profiles/{self.profile.id}/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('is_approver', response.data['data'])
        self.assertTrue(response.data['data']['is_approver'])
        # Verify persisted in DB
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.is_approver, 1)


@pytest.mark.django_db
class TestProfileIsApproverFilter(TestCase):
    """Tests for GET /admin/profiles?is_approver=true filter — Story 58.4 AC4."""

    def setUp(self):
        self.client = APIClient()
        self.dbops_user = User.objects.create(
            username='dbops_user_approver_filter',
            profile='dbops',
        )
        self.client.force_authenticate(user=self.dbops_user)

        # Profile approbateur
        self.approver_profile = Profile.objects.create(
            name='Approver Profile 58_4',
            ad_group='GRP-APPROVER',
            is_admin=0,
            is_approver=1,
        )
        # Profile non-approbateur
        self.non_approver_profile = Profile.objects.create(
            name='Non-Approver Profile 58_4',
            ad_group='GRP-REGULAR',
            is_admin=0,
            is_approver=0,
        )

    def test_filter_is_approver_true_returns_only_approvers(self):
        """GET ?is_approver=true retourne uniquement les profils is_approver=1."""
        response = self.client.get('/api/v1/admin/profiles/?is_approver=true')

        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        names = [p['name'] for p in data]
        self.assertIn('Approver Profile 58_4', names)
        self.assertNotIn('Non-Approver Profile 58_4', names)
        for p in data:
            self.assertTrue(p['is_approver'])

    def test_filter_is_approver_false_returns_all_profiles(self):
        """GET sans paramètre retourne tous les profils (comportement inchangé)."""
        response = self.client.get('/api/v1/admin/profiles/')

        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        names = [p['name'] for p in data]
        self.assertIn('Approver Profile 58_4', names)
        self.assertIn('Non-Approver Profile 58_4', names)
