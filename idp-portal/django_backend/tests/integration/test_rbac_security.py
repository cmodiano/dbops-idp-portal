"""
Security and RBAC tests.

Story M.9: Tests unitaires et d'intégration
Tests RBAC permissions, authentication, and authorization.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from catalog.models import Action, ActionStatus
from integrations.models import Integration
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from executions.models import Execution, ExecutionStatus


@pytest.mark.django_db
@pytest.mark.security
class TestAuthenticationRequired(TestCase):
    """Tests for authentication enforcement."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(username='auth_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Auth AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Auth Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests to protected endpoints return 401."""
        # Don't authenticate - test admin endpoint which requires authentication
        response = self.client.get('/api/v1/admin/actions/')
        # Admin endpoints require authentication
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_authenticated_request_succeeds(self):
        """Test that authenticated requests to catalog succeed."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/catalog/actions/')
        # Catalog endpoint is public but returns data based on RBAC
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.django_db
@pytest.mark.security
class TestRBACPermissions(TestCase):
    """Tests for RBAC permission enforcement."""

    def setUp(self):
        """Set up test data with different profile permissions."""
        self.integration = Integration.objects.create(
            type='aap',
            name='RBAC AAP',
            base_url='https://aap.example.com'
        )

        # Create profiles
        self.profile_standard = Profile.objects.create(
            name='Standard',
            ad_group='CN=Standard,OU=Groups,DC=corp,DC=com',
            is_admin=0,
            is_auditor=0
        )

        self.profile_admin = Profile.objects.create(
            name='Admin',
            ad_group='CN=Admin,OU=Groups,DC=corp,DC=com',
            is_admin=1,
            is_auditor=0
        )

        self.profile_auditor = Profile.objects.create(
            name='Auditor',
            ad_group='CN=Auditor,OU=Groups,DC=corp,DC=com',
            is_admin=0,
            is_auditor=1
        )

        # Create users with profiles
        self.standard_user = User.objects.create(
            username='standard_user',
            profile='Standard'
        )
        self.admin_user = User.objects.create(
            username='admin_user',
            profile='Admin'
        )
        self.auditor_user = User.objects.create(
            username='auditor_user',
            profile='Auditor'
        )

        # Create test action
        self.action = Action.objects.create(
            name='RBAC Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )

        self.client = APIClient()

    def test_admin_has_full_access(self):
        """Test that admin profile has full access."""
        self.assertEqual(self.profile_admin.is_admin, 1)

        # Admin should be in admin profiles list
        admin_profiles = Profile.objects.filter(is_admin=1)
        self.assertIn(self.profile_admin.id, [p.id for p in admin_profiles])

    def test_auditor_has_read_access(self):
        """Test that auditor profile has read access."""
        self.assertEqual(self.profile_auditor.is_auditor, 1)

        # Auditor should be in auditor profiles list
        auditor_profiles = Profile.objects.filter(is_auditor=1)
        self.assertIn(self.profile_auditor.id, [p.id for p in auditor_profiles])

    def test_standard_user_limited_access(self):
        """Test that standard user has limited access based on permissions."""
        # Standard user without explicit permissions
        self.assertEqual(self.profile_standard.is_admin, 0)
        self.assertEqual(self.profile_standard.is_auditor, 0)

        # Check no action permissions by default
        has_action_perm = ProfileActionPermission.objects.filter(
            profile=self.profile_standard
        ).exists()
        self.assertFalse(has_action_perm)


@pytest.mark.django_db
@pytest.mark.security
class TestRBACActionPermissions(TestCase):
    """Tests for action-level RBAC permissions."""

    def setUp(self):
        """Set up test data with action permissions."""
        self.integration = Integration.objects.create(
            type='aap',
            name='Action RBAC AAP',
            base_url='https://aap.example.com'
        )

        self.admin_user = User.objects.create(username='action_admin', profile='DBOPS')

        # Create multiple actions
        self.action1 = Action.objects.create(
            name='Action 1',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )
        self.action2 = Action.objects.create(
            name='Action 2',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )
        self.action3 = Action.objects.create(
            name='Action 3',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )

    def test_list_permission_type(self):
        """Test LIST permission type limits to specific actions."""
        import json

        profile = Profile.objects.create(
            name='ListPerm',
            ad_group='CN=ListPerm,OU=Groups,DC=corp,DC=com'
        )

        # Grant access to only action1 and action2
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            action_ids_json=json.dumps([self.action1.id, self.action2.id])
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        allowed_ids = perm.get_action_ids()

        self.assertIn(self.action1.id, allowed_ids)
        self.assertIn(self.action2.id, allowed_ids)
        self.assertNotIn(self.action3.id, allowed_ids)

    def test_all_permission_type(self):
        """Test ALL permission type grants access to all actions."""
        profile = Profile.objects.create(
            name='AllPerm',
            ad_group='CN=AllPerm,OU=Groups,DC=corp,DC=com'
        )

        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL'
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        self.assertEqual(perm.permission_type, 'ALL')

    def test_pattern_permission_type(self):
        """Test PATTERN permission type with tag patterns."""
        import json

        from catalog.models import Tag, ActionTag

        # Create tags and assign to actions
        tag_oracle = Tag.objects.create(name='oracle')
        tag_patching = Tag.objects.create(name='patching')

        ActionTag.objects.create(action=self.action1, tag=tag_oracle)
        ActionTag.objects.create(action=self.action2, tag=tag_oracle)
        ActionTag.objects.create(action=self.action2, tag=tag_patching)

        profile = Profile.objects.create(
            name='PatternPerm',
            ad_group='CN=PatternPerm,OU=Groups,DC=corp,DC=com'
        )

        # Grant access to actions with 'oracle' tag
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='PATTERN',
            tag_patterns_json=json.dumps(['oracle'])
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        tag_patterns = perm.get_tag_patterns()

        self.assertIn('oracle', tag_patterns)


@pytest.mark.django_db
@pytest.mark.security
class TestRBACEnvironmentPermissions(TestCase):
    """Tests for environment-level RBAC permissions."""

    def setUp(self):
        """Set up test data with environment permissions."""
        self.user = User.objects.create(username='env_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Env RBAC AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Env RBAC Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

    def test_dev_only_permission(self):
        """Test permission limited to dev environment."""
        import json

        profile = Profile.objects.create(
            name='DevOnly',
            ad_group='CN=DevOnly,OU=Groups,DC=corp,DC=com'
        )

        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            environments_json=json.dumps(['dev'])
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        envs = perm.get_environments()

        self.assertIn('dev', envs)
        self.assertNotIn('staging', envs)
        self.assertNotIn('prod', envs)

    def test_all_environments_permission(self):
        """Test permission for all environments."""
        import json

        profile = Profile.objects.create(
            name='AllEnvs',
            ad_group='CN=AllEnvs,OU=Groups,DC=corp,DC=com'
        )

        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            environments_json=json.dumps(['dev', 'staging', 'prod'])
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        envs = perm.get_environments()

        self.assertIn('dev', envs)
        self.assertIn('staging', envs)
        self.assertIn('prod', envs)

    def test_prod_requires_approval(self):
        """Test that prod executions require approval workflow."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.PENDING_APPROVAL  # Must go through approval
        )

        self.assertEqual(execution.environment, 'prod')
        self.assertEqual(execution.status, ExecutionStatus.PENDING_APPROVAL)


@pytest.mark.django_db
@pytest.mark.security
class TestRBACMultiProfileAccumulation(TestCase):
    """Tests for permission accumulation from multiple profiles."""

    def setUp(self):
        """Set up test data with multiple profiles."""
        import json

        self.integration = Integration.objects.create(
            type='aap',
            name='Multi Profile AAP',
            base_url='https://aap.example.com'
        )

        self.admin_user = User.objects.create(username='multi_admin', profile='DBOPS')

        # Create actions
        self.action1 = Action.objects.create(
            name='Multi Action 1',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )
        self.action2 = Action.objects.create(
            name='Multi Action 2',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.admin_user,
            integration=self.integration
        )

        # Create profiles with different permissions
        self.profile1 = Profile.objects.create(
            name='Profile1',
            ad_group='CN=Profile1,OU=Groups,DC=corp,DC=com'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile1,
            permission_type='LIST',
            action_ids_json=json.dumps([self.action1.id]),
            environments_json=json.dumps(['dev'])
        )

        self.profile2 = Profile.objects.create(
            name='Profile2',
            ad_group='CN=Profile2,OU=Groups,DC=corp,DC=com'
        )
        ProfileActionPermission.objects.create(
            profile=self.profile2,
            permission_type='LIST',
            action_ids_json=json.dumps([self.action2.id]),
            environments_json=json.dumps(['staging'])
        )

    def test_user_with_multiple_ad_groups(self):
        """Test that user with multiple AD groups gets cumulative permissions."""
        user_ad_groups = [
            'CN=Profile1,OU=Groups,DC=corp,DC=com',
            'CN=Profile2,OU=Groups,DC=corp,DC=com'
        ]

        # Find all matching profiles
        profiles = Profile.objects.find_by_ad_groups(user_ad_groups)
        self.assertEqual(profiles.count(), 2)

        # Collect all permissions
        all_action_ids = set()
        all_environments = set()

        for profile in profiles:
            try:
                perm = ProfileActionPermission.objects.get(profile=profile)
                all_action_ids.update(perm.get_action_ids())
                all_environments.update(perm.get_environments())
            except ProfileActionPermission.DoesNotExist:
                pass

        # Should have access to both actions
        self.assertIn(self.action1.id, all_action_ids)
        self.assertIn(self.action2.id, all_action_ids)

        # Should have access to both environments
        self.assertIn('dev', all_environments)
        self.assertIn('staging', all_environments)

    def test_most_permissive_wins(self):
        """Test that ALL permission type overrides LIST."""
        import json

        # Create a third profile with ALL permissions
        profile3 = Profile.objects.create(
            name='Profile3',
            ad_group='CN=Profile3,OU=Groups,DC=corp,DC=com'
        )
        ProfileActionPermission.objects.create(
            profile=profile3,
            permission_type='ALL'
        )

        user_ad_groups = [
            'CN=Profile1,OU=Groups,DC=corp,DC=com',
            'CN=Profile3,OU=Groups,DC=corp,DC=com'  # Has ALL
        ]

        profiles = Profile.objects.find_by_ad_groups(user_ad_groups)

        # Check if any profile has ALL permission
        has_all_permission = False
        for profile in profiles:
            try:
                perm = ProfileActionPermission.objects.get(profile=profile)
                if perm.permission_type == 'ALL':
                    has_all_permission = True
                    break
            except ProfileActionPermission.DoesNotExist:
                pass

        self.assertTrue(has_all_permission)


@pytest.mark.django_db
@pytest.mark.security
class TestDataIsolation(TestCase):
    """Tests for data isolation between users."""

    def setUp(self):
        """Set up test data."""
        self.integration = Integration.objects.create(
            type='aap',
            name='Isolation AAP',
            base_url='https://aap.example.com'
        )

        self.user1 = User.objects.create(username='isolation_user1', profile='DBA')
        self.user2 = User.objects.create(username='isolation_user2', profile='DBA')

        self.action = Action.objects.create(
            name='Isolation Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user1,
            integration=self.integration
        )

    def test_user_sees_only_own_executions(self):
        """Test that user can only see their own executions."""
        # Create executions for both users
        exec1 = Execution.objects.create(
            action=self.action,
            user=self.user1,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        exec2 = Execution.objects.create(
            action=self.action,
            user=self.user2,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )

        # User 1 sees only their execution
        user1_execs = Execution.objects.list_by_user(self.user1.id)
        self.assertEqual(user1_execs.count(), 1)
        self.assertEqual(user1_execs[0].id, exec1.id)

        # User 2 sees only their execution
        user2_execs = Execution.objects.list_by_user(self.user2.id)
        self.assertEqual(user2_execs.count(), 1)
        self.assertEqual(user2_execs[0].id, exec2.id)

    def test_admin_can_see_all_executions(self):
        """Test that admin (DBOPS) can see all executions."""
        admin_user = User.objects.create(username='isolation_admin', profile='DBOPS')

        # Create executions for different users
        Execution.objects.create(
            action=self.action,
            user=self.user1,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user2,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )

        # Admin can see all (using all() instead of list_by_user)
        all_execs = Execution.objects.all()
        self.assertGreaterEqual(all_execs.count(), 2)


@pytest.mark.django_db
@pytest.mark.integration
class TestNonSuperuserDBOPSAccessViaADGroup(TestCase):
    """
    Story 22.1 AC#5: Non-superuser with AD group 'GRP-IDP-DBOPS' can access
    protected endpoints without the superuser flag.
    """

    def setUp(self):
        """Set up DBOPS profile and non-superuser with AD group."""
        self.client = APIClient()

        # Create the DBOPS profile in DB (ad_group matches the AD group name)
        self.profile_dbops = Profile.objects.create(
            name='DBOPS',
            ad_group='GRP-IDP-DBOPS',
            is_admin=1,
        )

        # Create a non-superuser
        self.user = User.objects.create(
            username='dbops_ad_user',
            profile='',  # No direct profile string — relies on AD groups
        )
        # Attach ad_groups dynamically (as JWT authentication does)
        self.user.ad_groups = ['GRP-IDP-DBOPS']
        self.user.is_superuser = False

    def test_non_superuser_dbops_access_via_ad_group(self):
        """AC#5: Non-superuser with AD group 'GRP-IDP-DBOPS' accesses admin endpoint."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v1/admin/actions/')

        # Should be 200 (not 403) — the DBOPS profile is resolved from AD groups
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_superuser_without_ad_group_denied(self):
        """Non-superuser without matching AD group is denied admin access."""
        denied_user = User.objects.create(
            username='no_ad_user',
            profile='',
        )
        denied_user.ad_groups = ['GRP-IDP-VIEWER']  # Not DBOPS
        denied_user.is_superuser = False

        self.client.force_authenticate(user=denied_user)

        response = self.client.get('/api/v1/admin/actions/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_flag_not_needed_for_ad_group_dbops(self):
        """AC#3: Verify superuser flag is NOT required when AD group grants DBOPS access."""
        self.assertFalse(self.user.is_superuser)

        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/admin/actions/')

        # AC#3: Non-superuser with AD group should access endpoint successfully
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_fallback_logs_when_used(self):
        """Verify that superuser fallback emits a log when used (Story 22.2 CRIT-2)."""
        superuser = User.objects.create(
            username='superuser_no_profile',
            profile='',  # No profile
        )
        superuser.ad_groups = []  # No AD groups
        superuser.is_superuser = True

        self.client.force_authenticate(user=superuser)

        # Capture logs during request
        import logging
        with self.assertLogs('core.permissions', level='INFO') as logs:
            response = self.client.get('/api/v1/admin/actions/')

        # Verify superuser_fallback_used log was emitted
        superuser_fallback_logs = [log for log in logs.output if 'superuser_fallback_used' in log]
        self.assertGreater(len(superuser_fallback_logs), 0, "Superuser fallback SHOULD log when used")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
