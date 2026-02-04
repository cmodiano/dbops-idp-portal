"""
Tests for profiles services (ProfileService).
"""

import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from profiles.services import ProfileService
from core.models import AuditLog


@pytest.mark.django_db
class TestProfileService(TestCase):
    """Tests for ProfileService."""
    
    def setUp(self):
        """Set up test data."""
        self.service = ProfileService()
    
    def test_create_profile(self):
        """Test create_profile() creates profile with audit."""
        profile_data = {
            'name': 'Test Profile',
            'description': 'Test Description',
            'ad_group': 'CN=Test,OU=Groups,DC=example,DC=com',
            'is_admin': 0,
            'is_auditor': 0
        }
        
        profile = self.service.create_profile(profile_data)
        
        self.assertIsNotNone(profile.id)
        self.assertEqual(profile.name, 'Test Profile')
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='profile',
            entity_id=profile.id,
            action_type='PROFILE_CREATED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_list_all_profiles(self):
        """Test list_all_profiles() returns profiles with permission count."""
        Profile.objects.create(
            name='Profile 1',
            ad_group='CN=Profile1,OU=Groups,DC=example,DC=com'
        )
        
        profiles = self.service.list_all_profiles()
        self.assertGreaterEqual(profiles.count(), 1)
    
    def test_get_profile_by_id(self):
        """Test get_profile_by_id() retrieves profile with permissions."""
        profile = Profile.objects.create(
            name='Test Profile',
            ad_group='CN=Test,OU=Groups,DC=example,DC=com'
        )
        
        retrieved = self.service.get_profile_by_id(profile.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, profile.id)
    
    def test_update_profile(self):
        """Test update_profile() updates profile and creates audit."""
        profile = Profile.objects.create(
            name='Original Name',
            ad_group='CN=Original,OU=Groups,DC=example,DC=com'
        )
        
        update_data = {
            'name': 'Updated Name',
            'description': 'Updated Description'
        }
        
        updated = self.service.update_profile(profile.id, update_data)
        
        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.description, 'Updated Description')
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='profile',
            entity_id=profile.id,
            action_type='PROFILE_UPDATED'
        ).first()
        self.assertIsNotNone(audit)
    
    def test_delete_profile(self):
        """Test delete_profile() deletes profile and creates audit."""
        profile = Profile.objects.create(
            name='Profile to Delete',
            ad_group='CN=Delete,OU=Groups,DC=example,DC=com'
        )
        profile_id = profile.id
        
        result = self.service.delete_profile(profile_id)
        
        self.assertTrue(result)
        self.assertFalse(Profile.objects.filter(id=profile_id).exists())
        
        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='profile',
            entity_id=profile_id,
            action_type='PROFILE_DELETED'
        ).first()
        self.assertIsNotNone(audit)
