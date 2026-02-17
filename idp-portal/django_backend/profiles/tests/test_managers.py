"""
Tests for profiles managers (ProfileManager).
"""

import pytest
from django.test import TestCase
from profiles.models import Profile


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
        self.assertIsNotNone(profile1_result.permission_count)
        self.assertGreaterEqual(profile1_result.permission_count, 1)

    # =========================================================================
    # Story M.9: Additional manager tests for edge cases and multi-profile
    # =========================================================================

    def test_find_by_ad_groups_nonexistent(self):
        """Test find_by_ad_groups() with non-existent groups returns empty."""
        results = Profile.objects.find_by_ad_groups(['CN=NonExistent,OU=Groups,DC=example,DC=com'])
        self.assertEqual(results.count(), 0)

    def test_find_by_ad_groups_partial_match(self):
        """
        Test find_by_ad_groups() with short group/profile code.

        In production payloads, groups may be provided as short values (e.g. "DBA")
        rather than full DNs. We accept matching by Profile.name for robustness.
        """
        results = Profile.objects.find_by_ad_groups(['DBA'])
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, 'DBA')

    def test_list_with_permissions_count_no_permissions(self):
        """Test list_with_permissions_count() when profile has no permissions."""
        profile_no_perm = Profile.objects.create(
            name='NoPerm',
            description='No permissions',
            ad_group='CN=NoPerm,OU=Groups,DC=example,DC=com',
            is_admin=0,
            is_auditor=0
        )

        profiles = Profile.objects.list_with_permissions_count()
        no_perm_result = profiles.get(id=profile_no_perm.id)
        self.assertEqual(no_perm_result.permission_count, 0)

    def test_list_with_permissions_count_both_permission_types(self):
        """Test list_with_permissions_count() counts both action and target permissions."""
        from profiles.models import ProfileActionPermission, ProfileTargetPermission

        profile = Profile.objects.create(
            name='BothPerm',
            description='Both permissions',
            ad_group='CN=BothPerm,OU=Groups,DC=example,DC=com',
            is_admin=0,
            is_auditor=0
        )

        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )

        profiles = Profile.objects.list_with_permissions_count()
        both_perm_result = profiles.get(id=profile.id)
        # Should have at least 2 (one action, one target permission)
        self.assertGreaterEqual(both_perm_result.permission_count, 2)


@pytest.mark.django_db
class TestProfileMultiGroupResolution(TestCase):
    """Story M.9: Tests for multi-profile AD group resolution."""

    def setUp(self):
        """Set up multiple profiles with different AD groups."""
        self.profile_dba = Profile.objects.create(
            name='DBA',
            ad_group='CN=DBA,OU=Groups,DC=corp,DC=com',
            is_admin=0
        )
        self.profile_dbops = Profile.objects.create(
            name='DBOPS',
            ad_group='CN=DBOPS,OU=Groups,DC=corp,DC=com',
            is_admin=1
        )
        self.profile_auditor = Profile.objects.create(
            name='Auditor',
            ad_group='CN=Auditors,OU=Groups,DC=corp,DC=com',
            is_auditor=1
        )

    def test_multi_group_resolution(self):
        """Test user with multiple AD groups resolves to multiple profiles."""
        user_groups = [
            'CN=DBA,OU=Groups,DC=corp,DC=com',
            'CN=Auditors,OU=Groups,DC=corp,DC=com'
        ]

        profiles = Profile.objects.find_by_ad_groups(user_groups)
        self.assertEqual(profiles.count(), 2)

        profile_names = [p.name for p in profiles]
        self.assertIn('DBA', profile_names)
        self.assertIn('Auditor', profile_names)

    def test_admin_profile_included(self):
        """Test that admin profile is included when user has admin AD group."""
        user_groups = ['CN=DBOPS,OU=Groups,DC=corp,DC=com']

        profiles = Profile.objects.find_by_ad_groups(user_groups)
        self.assertEqual(profiles.count(), 1)
        self.assertEqual(profiles[0].is_admin, 1)

    def test_profile_ordering(self):
        """Test profiles are returned ordered by name."""
        user_groups = [
            'CN=DBA,OU=Groups,DC=corp,DC=com',
            'CN=DBOPS,OU=Groups,DC=corp,DC=com',
            'CN=Auditors,OU=Groups,DC=corp,DC=com'
        ]

        profiles = list(Profile.objects.find_by_ad_groups(user_groups))
        names = [p.name for p in profiles]
        self.assertEqual(names, sorted(names))
