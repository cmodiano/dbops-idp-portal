"""
Tests for profiles managers (ProfileManager).
"""

import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileManager


@pytest.mark.django_db
class TestProfileManager(TestCase):
    """Tests for ProfileManager."""
    
    def setUp(self):
        """Set up test data."""
        self.profile1 = Profile.objects.create(
            name='DBA',
            description='Database Administrator',
            ad_group='CN=DBA,OU=Groups,DC=example,DC=com',
            is_admin=1,
            is_auditor=0
        )
        self.profile2 = Profile.objects.create(
            name='DBOPS',
            description='Database Operations',
            ad_group='CN=DBOPS,OU=Groups,DC=example,DC=com',
            is_admin=0,
            is_auditor=1
        )
    
    def test_find_by_ad_groups(self):
        """Test find_by_ad_groups() finds profiles by AD groups."""
        results = Profile.objects.find_by_ad_groups([
            'CN=DBA,OU=Groups,DC=example,DC=com'
        ])
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, self.profile1.id)
        
        # Multiple groups
        results = Profile.objects.find_by_ad_groups([
            'CN=DBA,OU=Groups,DC=example,DC=com',
            'CN=DBOPS,OU=Groups,DC=example,DC=com'
        ])
        self.assertEqual(results.count(), 2)
    
    def test_find_by_ad_groups_empty(self):
        """Test find_by_ad_groups() with empty list."""
        results = Profile.objects.find_by_ad_groups([])
        self.assertEqual(results.count(), 0)
    
    def test_list_with_permissions_count(self):
        """Test list_with_permissions_count() includes permission count."""
        from profiles.models import ProfileActionPermission
        
        # Create permission
        ProfileActionPermission.objects.create(
            profile=self.profile1,
            permission_type='ALL'
        )
        
        profiles = Profile.objects.list_with_permissions_count()
        profile1_result = profiles.get(id=self.profile1.id)
        self.assertIsNotNone(profile1_result.permissions_count)
        self.assertGreaterEqual(profile1_result.permissions_count, 1)
