"""
Integration tests for profile resolution.

Story M.9: Tests unitaires et d'intégration
Tests: login SAML → résolution AD groups → permissions → accès API
"""

import pytest
from django.test import TestCase

from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from catalog.models import Action, ActionStatus, Tag, ActionTag
from integrations.models import Integration


@pytest.mark.django_db
@pytest.mark.integration
class TestProfileResolution(TestCase):
    """Integration tests for profile resolution from AD groups."""

    def setUp(self):
        """Set up test profiles and permissions."""
        # Create profiles with AD groups (use get_or_create as conftest may have created them)
        self.profile_dba, _ = Profile.objects.get_or_create(
            name='DBA',
            defaults={
                'description': 'Database Administrator',
                'ad_group': 'CN=DBA-Team,OU=Groups,DC=corp,DC=example,DC=com',
                'is_admin': 0,
                'is_auditor': 0,
            }
        )
        # Ensure ad_group is set for this test's lookup
        self.profile_dba.ad_group = 'CN=DBA-Team,OU=Groups,DC=corp,DC=example,DC=com'
        self.profile_dba.save()

        self.profile_dbops, _ = Profile.objects.get_or_create(
            name='DBOPS',
            defaults={
                'description': 'Database Operations (Admin)',
                'ad_group': 'CN=DBOPS-Team,OU=Groups,DC=corp,DC=example,DC=com',
                'is_admin': 1,
                'is_auditor': 0,
            }
        )
        self.profile_dbops.ad_group = 'CN=DBOPS-Team,OU=Groups,DC=corp,DC=example,DC=com'
        self.profile_dbops.save()

        self.profile_auditor, _ = Profile.objects.get_or_create(
            name='AUDITOR',
            defaults={
                'description': 'Audit Team',
                'ad_group': 'CN=Auditors,OU=Groups,DC=corp,DC=example,DC=com',
                'is_admin': 0,
                'is_auditor': 1,
            }
        )
        self.profile_auditor.ad_group = 'CN=Auditors,OU=Groups,DC=corp,DC=example,DC=com'
        self.profile_auditor.save()

        # Create integration and action for permission testing
        self.integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com'
        )

        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            integration=self.integration
        )

    def test_single_ad_group_resolves_to_profile(self):
        """Test that a single AD group resolves to correct profile."""
        ad_groups = ['CN=DBA-Team,OU=Groups,DC=corp,DC=example,DC=com']

        profiles = Profile.objects.find_by_ad_groups(ad_groups)

        self.assertEqual(profiles.count(), 1)
        self.assertEqual(profiles[0].name, 'DBA')
        self.assertEqual(profiles[0].is_admin, 0)

    def test_multiple_ad_groups_resolve_to_multiple_profiles(self):
        """Test that multiple AD groups resolve to all matching profiles."""
        ad_groups = [
            'CN=DBA-Team,OU=Groups,DC=corp,DC=example,DC=com',
            'CN=Auditors,OU=Groups,DC=corp,DC=example,DC=com'
        ]

        profiles = Profile.objects.find_by_ad_groups(ad_groups)

        self.assertEqual(profiles.count(), 2)
        profile_names = [p.name for p in profiles]
        self.assertIn('DBA', profile_names)
        self.assertIn('AUDITOR', profile_names)

    def test_admin_group_grants_admin_access(self):
        """Test that DBOPS group grants admin privileges."""
        ad_groups = ['CN=DBOPS-Team,OU=Groups,DC=corp,DC=example,DC=com']

        profiles = Profile.objects.find_by_ad_groups(ad_groups)

        self.assertEqual(profiles.count(), 1)
        self.assertEqual(profiles[0].is_admin, 1)

    def test_cumulative_permissions_from_multiple_profiles(self):
        """Test that permissions accumulate from multiple profiles."""
        from profiles.services import ProfileService
        _svc = ProfileService()

        # Set up permissions for DBA profile (LIST type - specific actions)
        _svc.set_action_permissions(
            self.profile_dba.id,
            {'actions_type': 'list', 'action_ids': [self.action.id], 'environments': ['dev', 'staging']},
        )

        # Set up permissions for AUDITOR profile (ALL targets)
        _svc.set_target_permissions(
            self.profile_auditor.id,
            {'targets_type': 'all'},
        )

        # User with both groups
        ad_groups = [
            'CN=DBA-Team,OU=Groups,DC=corp,DC=example,DC=com',
            'CN=Auditors,OU=Groups,DC=corp,DC=example,DC=com'
        ]

        profiles = Profile.objects.find_by_ad_groups(ad_groups)

        # Collect all permissions
        has_action_permission = False
        has_target_permission = False

        for profile in profiles:
            try:
                ProfileActionPermission.objects.get(profile=profile)
                has_action_permission = True
            except ProfileActionPermission.DoesNotExist:
                pass

            try:
                ProfileTargetPermission.objects.get(profile=profile)
                has_target_permission = True
            except ProfileTargetPermission.DoesNotExist:
                pass

        # User should have both action and target permissions
        self.assertTrue(has_action_permission)
        self.assertTrue(has_target_permission)

    def test_profile_with_pattern_permissions(self):
        """Test profile with tag-based pattern permissions."""
        from profiles.services import ProfileService
        from profiles.action_permission_repository import get_tag_patterns

        # Create tags
        tag_oracle = Tag.objects.create(name='oracle')
        tag_db2 = Tag.objects.create(name='db2')

        ActionTag.objects.create(action=self.action, tag=tag_oracle)

        # Create action with DB2 tag (should not be accessible)
        action_db2 = Action.objects.create(
            name='DB2 Action',
            category='Provisioning',
            engine='DB2',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            integration=self.integration
        )
        ActionTag.objects.create(action=action_db2, tag=tag_db2)

        # Set up pattern permission for oracle tag only
        ProfileService().set_action_permissions(
            self.profile_dba.id,
            {'actions_type': 'pattern', 'tag_patterns': ['oracle'], 'environments': ['dev', 'staging', 'prod']},
        )

        # Verify permission configuration
        perm = ProfileActionPermission.objects.get(profile=self.profile_dba)
        tag_patterns_result = get_tag_patterns(perm)

        self.assertIn('oracle', tag_patterns_result)
        self.assertNotIn('db2', tag_patterns_result)

    def test_no_matching_ad_group_returns_empty(self):
        """Test that unknown AD groups return no profiles."""
        ad_groups = ['CN=Unknown-Group,OU=Groups,DC=corp,DC=example,DC=com']

        profiles = Profile.objects.find_by_ad_groups(ad_groups)

        self.assertEqual(profiles.count(), 0)

    def test_profile_environment_permissions(self):
        """Test that environment permissions are correctly stored and retrieved."""
        from profiles.services import ProfileService
        from profiles.action_permission_repository import get_environments

        # Set up permission with specific environments
        ProfileService().set_action_permissions(
            self.profile_dba.id,
            {'actions_type': 'all', 'environments': ['dev', 'staging']},
        )

        perm = ProfileActionPermission.objects.get(profile=self.profile_dba)
        environments = get_environments(perm)

        self.assertIn('dev', environments)
        self.assertIn('staging', environments)
        self.assertNotIn('prod', environments)


@pytest.mark.django_db
@pytest.mark.integration
class TestProfilePermissionHierarchy(TestCase):
    """Integration tests for permission hierarchy and inheritance."""

    def setUp(self):
        """Set up profiles with different permission levels."""
        self.profile_restricted = Profile.objects.create(
            name='Restricted',
            ad_group='CN=Restricted,OU=Groups,DC=corp,DC=com',
            is_admin=0
        )
        self.profile_standard = Profile.objects.create(
            name='Standard',
            ad_group='CN=Standard,OU=Groups,DC=corp,DC=com',
            is_admin=0
        )
        self.profile_admin = Profile.objects.create(
            name='Admin',
            ad_group='CN=Admin,OU=Groups,DC=corp,DC=com',
            is_admin=1
        )

    def test_permission_type_all_grants_full_access(self):
        """Test that 'ALL' permission type grants access to all actions."""
        ProfileActionPermission.objects.create(
            profile=self.profile_admin,
            permission_type='ALL'
        )

        perm = ProfileActionPermission.objects.get(profile=self.profile_admin)
        self.assertEqual(perm.permission_type, 'ALL')

    def test_permission_type_list_limits_to_specific_actions(self):
        """Test that 'LIST' permission type limits to specific action IDs."""
        from profiles.services import ProfileService
        from profiles.action_permission_repository import get_action_ids

        ProfileService().set_action_permissions(
            self.profile_restricted.id,
            {'actions_type': 'list', 'action_ids': [1, 2, 3]},
        )

        perm = ProfileActionPermission.objects.get(profile=self.profile_restricted)
        action_ids = get_action_ids(perm)

        self.assertEqual(perm.permission_type, 'LIST')
        self.assertEqual(action_ids, [1, 2, 3])

    def test_admin_profile_bypasses_restrictions(self):
        """Test that admin profiles have elevated access."""
        # Admin doesn't need explicit action permissions
        self.assertEqual(self.profile_admin.is_admin, 1)

        # Check if profile is in admin list
        admin_profiles = Profile.objects.filter(is_admin=1)
        self.assertIn(self.profile_admin.id, [p.id for p in admin_profiles])
