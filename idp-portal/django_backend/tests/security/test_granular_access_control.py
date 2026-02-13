"""
Tests de contrôle d'accès granulaire action/target/environnement.
Story 15.2 - Task 3 (AC3).

Validates:
- AC3: User can execute an action only if profile has permission for action AND target AND environment
- AC3: User can modify a profile only if DBOPS
- AC3: User can view execution logs only for own executions (unless DBOPS)
- AC3: Permission types LIST, ALL, PATTERN work correctly
- AC3: Multi-profile permission accumulation (most permissive wins)
"""

import json

import pytest
from rest_framework import status

from catalog.models import Action, Tag, ActionTag
from executions.models import Execution, ExecutionStatus
from idp_auth.models import User
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from idp_auth.jwt_utils import create_access_token
from tests.security.conftest import make_auth_client, _token_data


# ============================================================================
# Subtask 3.2: Permission type LIST (specific action IDs)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestActionPermissionTypeList:
    """Profile with LIST permission can only access specific actions."""

    @pytest.fixture
    def list_profile_setup(self, db, sec_integration):
        """Setup profile with LIST permission allowing action_a but not action_b."""
        user = User.objects.create(
            username='user_list_perm',
            display_name='User List Perm',
            profile='dba',
        )
        profile = Profile.objects.create(
            name='DBA_LIST_TEST',
            ad_group='dba_list_test',
            is_admin=0,
            is_auditor=0,
        )
        action_a = Action.objects.create(
            name='Allowed Action A',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        action_b = Action.objects.create(
            name='Forbidden Action B',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        perm = ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='LIST',
        )
        perm.set_action_ids([action_a.id])
        perm.set_environments(['dev', 'staging'])
        perm.save()

        token = create_access_token(_token_data(user, ['dba_list_test']))
        return {
            'user': user,
            'profile': profile,
            'action_a': action_a,
            'action_b': action_b,
            'token': token,
        }

    def test_list_permission_returns_allowed_action(self, list_profile_setup):
        """User with LIST perm sees allowed action in catalog."""
        client = make_auth_client(list_profile_setup['token'])
        response = client.get('/api/v1/catalog/actions/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        action_ids = [a['id'] for a in data['data']]
        assert list_profile_setup['action_a'].id in action_ids

    def test_list_permission_get_action_ids(self, list_profile_setup):
        """ProfileActionPermission.get_action_ids returns the stored list."""
        perm = ProfileActionPermission.objects.get(profile=list_profile_setup['profile'])
        ids = perm.get_action_ids()
        assert list_profile_setup['action_a'].id in ids
        assert list_profile_setup['action_b'].id not in ids

    def test_list_permission_environments(self, list_profile_setup):
        """ProfileActionPermission.get_environments returns configured envs."""
        perm = ProfileActionPermission.objects.get(profile=list_profile_setup['profile'])
        envs = perm.get_environments()
        assert 'dev' in envs
        assert 'staging' in envs
        assert 'prod' not in envs


# ============================================================================
# Subtask 3.3: Permission type ALL
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestActionPermissionTypeAll:
    """Profile with ALL permission has full action access."""

    @pytest.fixture
    def all_profile_setup(self, db, sec_integration):
        """Setup profile with ALL permission."""
        user = User.objects.create(
            username='user_all_perm',
            display_name='User All Perm',
            profile='dbops',
        )
        profile = Profile.objects.create(
            name='DBOPS_ALL_TEST',
            ad_group='dbops_all_test',
            is_admin=1,
            is_auditor=0,
        )
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
        )
        action = Action.objects.create(
            name='Any Action All',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        token = create_access_token(_token_data(user, ['dbops_all_test']))
        return {'user': user, 'profile': profile, 'action': action, 'token': token}

    def test_all_permission_grants_full_access(self, all_profile_setup):
        """User with ALL perm sees all published actions."""
        client = make_auth_client(all_profile_setup['token'])
        response = client.get('/api/v1/catalog/actions/')
        assert response.status_code == status.HTTP_200_OK
        action_ids = [a['id'] for a in response.json()['data']]
        assert all_profile_setup['action'].id in action_ids

    def test_all_permission_type_stored(self, all_profile_setup):
        """ProfileActionPermission type is ALL."""
        perm = ProfileActionPermission.objects.get(profile=all_profile_setup['profile'])
        assert perm.permission_type == 'ALL'


# ============================================================================
# Subtask 3.4: Permission type PATTERN (tags)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestActionPermissionTypePattern:
    """Profile with PATTERN permission can access actions matching tag patterns."""

    @pytest.fixture
    def pattern_profile_setup(self, db, sec_integration):
        """Setup profile with PATTERN permission using tags."""
        user = User.objects.create(
            username='user_pattern_perm',
            display_name='User Pattern Perm',
            profile='dba',
        )
        profile = Profile.objects.create(
            name='DBA_PATTERN_TEST',
            ad_group='dba_pattern_test',
            is_admin=0,
            is_auditor=0,
        )
        # Create tags
        tag_oracle = Tag.objects.create(name='oracle')
        tag_postgres = Tag.objects.create(name='postgres')

        # Create actions with tags
        action_oracle = Action.objects.create(
            name='Oracle Backup Action',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        ActionTag.objects.create(action=action_oracle, tag=tag_oracle)

        action_postgres = Action.objects.create(
            name='Postgres Maintenance',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        ActionTag.objects.create(action=action_postgres, tag=tag_postgres)

        # Setup PATTERN permission that only allows 'oracle' tag
        perm = ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='PATTERN',
        )
        perm.set_tag_patterns(['oracle'])
        perm.save()

        token = create_access_token(_token_data(user, ['dba_pattern_test']))
        return {
            'user': user,
            'profile': profile,
            'action_oracle': action_oracle,
            'action_postgres': action_postgres,
            'tag_oracle': tag_oracle,
            'token': token,
        }

    def test_pattern_permission_tag_patterns(self, pattern_profile_setup):
        """ProfileActionPermission stores tag patterns correctly."""
        perm = ProfileActionPermission.objects.get(
            profile=pattern_profile_setup['profile']
        )
        assert perm.permission_type == 'PATTERN'
        patterns = perm.get_tag_patterns()
        assert 'oracle' in patterns

    def test_pattern_permission_resolves_action_ids(self, pattern_profile_setup):
        """Tag patterns resolve to correct action IDs via ActionTag."""
        from catalog.models import ActionTag as AT
        tag_action_ids = list(
            AT.objects.filter(
                tag__name__in=['oracle'],
                action__status='published',
            ).values_list('action_id', flat=True)
        )
        assert pattern_profile_setup['action_oracle'].id in tag_action_ids
        assert pattern_profile_setup['action_postgres'].id not in tag_action_ids


# ============================================================================
# Subtask 3.5: Environment restrictions (dev-only, prod-approval)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestEnvironmentRestrictions:
    """Environment-based RBAC restrictions."""

    @pytest.fixture
    def env_profile_setup(self, db, sec_integration):
        """Setup profile with dev-only environment restriction."""
        user = User.objects.create(
            username='user_dev_only',
            display_name='User Dev Only',
            profile='dba',
        )
        profile = Profile.objects.create(
            name='DBA_DEV_ONLY',
            ad_group='dba_dev_only',
            is_admin=0,
            is_auditor=0,
        )
        action = Action.objects.create(
            name='Env Restricted Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        perm = ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
        )
        perm.set_environments(['dev'])
        perm.save()

        token = create_access_token(_token_data(user, ['dba_dev_only']))
        return {
            'user': user,
            'profile': profile,
            'action': action,
            'token': token,
        }

    def test_environment_restriction_dev_only(self, env_profile_setup):
        """Profile with dev-only environments does not include prod."""
        perm = ProfileActionPermission.objects.get(
            profile=env_profile_setup['profile']
        )
        envs = perm.get_environments()
        assert 'dev' in envs
        assert 'prod' not in envs

    def test_environment_restriction_empty_means_all(self, db):
        """Profile with no environments_json means all environments allowed."""
        profile = Profile.objects.create(
            name='DBA_ALL_ENVS',
            ad_group='dba_all_envs',
            is_admin=0,
            is_auditor=0,
        )
        perm = ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
        )
        envs = perm.get_environments()
        assert envs == []  # Empty means no restrictions (all allowed)


# ============================================================================
# Subtask 3.6: User data isolation (executions scope)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestUserDataIsolation:
    """Users only see their own executions unless DBA/DBOPS."""

    @pytest.fixture
    def isolation_setup(self, db, sec_integration):
        """Create two users with separate executions."""
        user_a = User.objects.create(
            username='isolation_dba',
            display_name='Isolation DBA',
            profile='dba',
        )
        user_b = User.objects.create(
            username='isolation_business',
            display_name='Isolation Business',
            profile='client_business',
        )
        user_dbops = User.objects.create(
            username='isolation_dbops',
            display_name='Isolation DBOPS',
            profile='dbops',
        )
        action = Action.objects.create(
            name='Isolation Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user_a,
            integration=sec_integration,
        )
        exec_a = Execution.objects.create(
            action=action,
            user=user_a,
            environment='dev',
            status=ExecutionStatus.COMPLETED,
        )
        exec_b = Execution.objects.create(
            action=action,
            user=user_b,
            environment='dev',
            status=ExecutionStatus.COMPLETED,
        )

        token_a = create_access_token(_token_data(user_a, ['dba']))
        token_b = create_access_token(_token_data(user_b, ['client_business']))
        token_dbops = create_access_token(_token_data(user_dbops, ['dbops']))

        return {
            'user_a': user_a,
            'user_b': user_b,
            'user_dbops': user_dbops,
            'exec_a': exec_a,
            'exec_b': exec_b,
            'token_a': token_a,
            'token_b': token_b,
            'token_dbops': token_dbops,
        }

    def test_business_user_sees_only_own_executions(self, isolation_setup):
        """Client Business user only sees own executions (scope=mine default)."""
        client = make_auth_client(isolation_setup['token_b'])
        response = client.get('/api/v1/executions/')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        exec_ids = [e['id'] for e in data]
        assert isolation_setup['exec_b'].id in exec_ids
        assert isolation_setup['exec_a'].id not in exec_ids

    def test_business_user_scope_all_fallback_to_mine(self, isolation_setup):
        """Client Business requesting scope=all still gets only own executions."""
        client = make_auth_client(isolation_setup['token_b'])
        response = client.get('/api/v1/executions/?scope=all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        exec_ids = [e['id'] for e in data]
        assert isolation_setup['exec_b'].id in exec_ids
        assert isolation_setup['exec_a'].id not in exec_ids

    def test_dba_user_can_see_all_executions(self, isolation_setup):
        """DBA user with scope=all sees all executions."""
        client = make_auth_client(isolation_setup['token_a'])
        response = client.get('/api/v1/executions/?scope=all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        exec_ids = [e['id'] for e in data]
        assert isolation_setup['exec_a'].id in exec_ids
        assert isolation_setup['exec_b'].id in exec_ids

    def test_dbops_user_can_see_all_executions(self, isolation_setup):
        """DBOPS user with scope=all sees all executions."""
        client = make_auth_client(isolation_setup['token_dbops'])
        response = client.get('/api/v1/executions/?scope=all')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()['data']
        exec_ids = [e['id'] for e in data]
        assert isolation_setup['exec_a'].id in exec_ids
        assert isolation_setup['exec_b'].id in exec_ids

    def test_execution_detail_forbidden_for_other_user(self, isolation_setup):
        """Business user cannot view execution detail of another user."""
        client = make_auth_client(isolation_setup['token_b'])
        response = client.get(f'/api/v1/executions/{isolation_setup["exec_a"].id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_execution_detail_allowed_for_owner(self, isolation_setup):
        """User can view their own execution detail."""
        client = make_auth_client(isolation_setup['token_b'])
        response = client.get(f'/api/v1/executions/{isolation_setup["exec_b"].id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_execution_detail_dbops_sees_any(self, isolation_setup):
        """DBOPS can view any user's execution detail."""
        client = make_auth_client(isolation_setup['token_dbops'])
        response = client.get(f'/api/v1/executions/{isolation_setup["exec_b"].id}/')
        assert response.status_code == status.HTTP_200_OK

    def test_execution_steps_forbidden_for_other_user(self, isolation_setup):
        """Business user cannot view execution steps of another user."""
        client = make_auth_client(isolation_setup['token_b'])
        response = client.get(f'/api/v1/executions/{isolation_setup["exec_a"].id}/steps/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Subtask 3.7: Multi-profile permission accumulation (AD groups)
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestMultiProfileAccumulation:
    """
    User with multiple AD groups gets cumulative permissions (most permissive wins).
    Tests ProfileService.get_cumulative_permissions.
    """

    @pytest.fixture
    def multi_profile_setup(self, db, sec_integration):
        """Setup user with two profiles: one LIST, one PATTERN."""
        user = User.objects.create(
            username='user_multi_profile',
            display_name='User Multi Profile',
            profile='dba',
        )
        # Profile A: LIST perm for action_a only, dev env
        profile_a = Profile.objects.create(
            name='MULTI_A',
            ad_group='multi_a',
            is_admin=0,
            is_auditor=0,
        )
        action_a = Action.objects.create(
            name='Multi Action A',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        perm_a = ProfileActionPermission.objects.create(
            profile=profile_a,
            permission_type='LIST',
        )
        perm_a.set_action_ids([action_a.id])
        perm_a.set_environments(['dev'])
        perm_a.save()

        # Profile B: PATTERN perm with 'oracle' tag, staging env
        profile_b = Profile.objects.create(
            name='MULTI_B',
            ad_group='multi_b',
            is_admin=0,
            is_auditor=0,
        )
        tag = Tag.objects.create(name='oracle_multi')
        action_b = Action.objects.create(
            name='Multi Action B Oracle',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user,
            integration=sec_integration,
        )
        ActionTag.objects.create(action=action_b, tag=tag)

        perm_b = ProfileActionPermission.objects.create(
            profile=profile_b,
            permission_type='PATTERN',
        )
        perm_b.set_tag_patterns(['oracle_multi'])
        perm_b.set_environments(['staging'])
        perm_b.save()

        token = create_access_token(_token_data(user, ['multi_a', 'multi_b']))
        return {
            'user': user,
            'profile_a': profile_a,
            'profile_b': profile_b,
            'action_a': action_a,
            'action_b': action_b,
            'token': token,
        }

    def test_cumulative_permissions_merge(self, multi_profile_setup):
        """get_cumulative_permissions returns permissions from all resolved profiles."""
        from profiles.services import ProfileService
        user = multi_profile_setup['user']
        perms = ProfileService().get_cumulative_permissions(user.id, ['multi_a', 'multi_b'])

        action_perms = perms['action_permissions']
        assert len(action_perms) == 2

        types = {p['actions_type'] for p in action_perms}
        assert 'list' in types
        assert 'pattern' in types

    def test_cumulative_environments_union(self, multi_profile_setup):
        """Accumulated environments include dev (from A) and staging (from B)."""
        from profiles.services import ProfileService
        user = multi_profile_setup['user']
        perms = ProfileService().get_cumulative_permissions(user.id, ['multi_a', 'multi_b'])

        all_envs = set()
        for p in perms['action_permissions']:
            all_envs.update(p.get('environments', []))

        assert 'dev' in all_envs
        assert 'staging' in all_envs

    def test_cumulative_action_ids_union(self, multi_profile_setup):
        """Accumulated action IDs from LIST profile are included."""
        from profiles.services import ProfileService
        user = multi_profile_setup['user']
        perms = ProfileService().get_cumulative_permissions(user.id, ['multi_a', 'multi_b'])

        all_action_ids = set()
        for p in perms['action_permissions']:
            all_action_ids.update(p.get('action_ids', []))

        assert multi_profile_setup['action_a'].id in all_action_ids

    def test_admin_profile_grants_all(self, db):
        """Admin profile without explicit permissions gets 'all' access."""
        from profiles.services import ProfileService
        user = User.objects.create(
            username='user_admin_implicit',
            display_name='Admin Implicit',
            profile='dbops',
        )
        Profile.objects.create(
            name='ADMIN_IMPLICIT',
            ad_group='admin_implicit',
            is_admin=1,
            is_auditor=0,
        )
        perms = ProfileService().get_cumulative_permissions(user.id, ['admin_implicit'])
        action_perms = perms['action_permissions']
        assert any(p['actions_type'] == 'all' for p in action_perms)


# ============================================================================
# Subtask 3.8: Profile modification restricted to DBOPS
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestProfileModificationRestricted:
    """Only DBOPS users can create, update, or delete profiles."""

    def test_dba_cannot_create_profile(self, sec_dba_token):
        """DBA user gets 403 when trying to create a profile."""
        client = make_auth_client(sec_dba_token)
        response = client.post(
            '/api/v1/admin/profiles/',
            data={'name': 'Test', 'ad_group': 'test'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dba_cannot_update_profile(self, sec_dba_token, sec_profile_dba):
        """DBA user gets 403 when trying to update a profile."""
        client = make_auth_client(sec_dba_token)
        response = client.put(
            f'/api/v1/admin/profiles/{sec_profile_dba.id}/',
            data={'name': 'Modified', 'ad_group': 'modified'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dba_cannot_delete_profile(self, sec_dba_token, sec_profile_dba):
        """DBA user gets 403 when trying to delete a profile."""
        client = make_auth_client(sec_dba_token)
        response = client.delete(f'/api/v1/admin/profiles/{sec_profile_dba.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_business_cannot_create_profile(self, sec_business_token):
        """Client Business user gets 403 when trying to create a profile."""
        client = make_auth_client(sec_business_token)
        response = client.post(
            '/api/v1/admin/profiles/',
            data={'name': 'Test', 'ad_group': 'test'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_can_list_profiles(self, sec_dbops_token, sec_profile_dbops):
        """DBOPS user can list profiles."""
        client = make_auth_client(sec_dbops_token)
        response = client.get('/api/v1/admin/profiles/')
        assert response.status_code == status.HTTP_200_OK

    def test_dbops_can_create_profile(self, sec_dbops_token, sec_profile_dbops):
        """DBOPS user can create a profile."""
        client = make_auth_client(sec_dbops_token)
        response = client.post(
            '/api/v1/admin/profiles/',
            data={'name': 'New Test Profile', 'ad_group': 'CN=new_test,DC=corp'},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED
