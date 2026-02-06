"""
Tests de sécurité des endpoints sensibles.
Story 15.2 - Task 4 (AC3).

Validates:
- AC3: POST /executions validates RBAC (action + target + env)
- AC3: GET /audit protected by auditor profile (DBA sees nothing, auditor sees all)
- AC3: PUT/DELETE /profiles restricted to DBOPS
- AC3: PUT/DELETE /integrations restricted to DBOPS
- AC3: Execution log isolation (owner + DBOPS only)
"""

import pytest
from rest_framework import status

from catalog.models import Action
from core.models import AuditLog, AuditActionType, AuditEntityType
from core.services import AuditService
from executions.models import Execution, ExecutionStatus
from idp_auth.models import User
from idp_auth.jwt_utils import create_access_token
from integrations.models import Integration
from profiles.models import Profile
from tests.security.conftest import make_auth_client, _token_data


# ============================================================================
# Subtask 4.2: POST /executions with RBAC validation
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestExecutionSubmissionRBAC:
    """POST /executions validates action_id and environment via RBAC."""

    @pytest.fixture
    def exec_setup(self, db):
        """Setup for execution submission tests."""
        integration = Integration.objects.create(
            type='aap',
            name='Exec Test AAP',
            base_url='https://aap.example.com',
        )
        user_dba = User.objects.create(
            username='exec_dba',
            display_name='Exec DBA',
            profile='dba',
        )
        user_business = User.objects.create(
            username='exec_business',
            display_name='Exec Business',
            profile='client_business',
        )
        action = Action.objects.create(
            name='Exec Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            created_by=user_dba,
            integration=integration,
            requires_target=False,
        )
        token_dba = create_access_token(_token_data(user_dba, ['dba']))
        token_business = create_access_token(_token_data(user_business, ['client_business']))
        return {
            'action': action,
            'user_dba': user_dba,
            'user_business': user_business,
            'token_dba': token_dba,
            'token_business': token_business,
        }

    def test_unauthenticated_cannot_submit_execution(self, anon_client):
        """POST /executions without auth returns 401."""
        response = anon_client.post('/api/v1/executions', format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_can_submit_execution(self, exec_setup):
        """DBA user can submit an execution for a published action."""
        client = make_auth_client(exec_setup['token_dba'])
        response = client.post(
            '/api/v1/executions',
            data={
                'action_id': exec_setup['action'].id,
                'environment': 'dev',
            },
            format='json',
        )
        # Should succeed (201) or at least not be 401/403
        assert response.status_code not in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_execution_requires_action_id(self, exec_setup):
        """POST /executions without action_id returns 400."""
        client = make_auth_client(exec_setup['token_dba'])
        response = client.post(
            '/api/v1/executions',
            data={'environment': 'dev'},
            format='json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_execution_nonexistent_action_returns_404(self, exec_setup):
        """POST /executions with non-existent action_id returns 404."""
        client = make_auth_client(exec_setup['token_dba'])
        response = client.post(
            '/api/v1/executions',
            data={'action_id': 999999, 'environment': 'dev'},
            format='json',
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Subtask 4.3: GET /audit protected by auditor profile
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestAuditEndpointAccess:
    """Audit endpoints are restricted to auditor profiles."""

    @pytest.fixture
    def audit_setup(self, db):
        """Setup auditor and non-auditor users."""
        user_auditor = User.objects.create(
            username='audit_auditor',
            display_name='Auditor User',
            profile='dba',
        )
        # Profile with is_auditor=1
        Profile.objects.create(
            name='DBA_AUDITOR',
            ad_group='dba_auditor',
            is_admin=0,
            is_auditor=1,
        )

        user_non_auditor = User.objects.create(
            username='audit_non_auditor',
            display_name='Non Auditor',
            profile='dba',
        )
        Profile.objects.create(
            name='DBA_REGULAR',
            ad_group='dba_regular',
            is_admin=0,
            is_auditor=0,
        )

        user_dbops = User.objects.create(
            username='audit_dbops',
            display_name='DBOPS Auditor',
            profile='dbops',
        )
        # DBOPS profile — is_admin=1 but NOT is_auditor=1 by default
        Profile.objects.create(
            name='DBOPS_NO_AUDIT',
            ad_group='dbops_no_audit',
            is_admin=1,
            is_auditor=0,
        )

        token_auditor = create_access_token(_token_data(user_auditor, ['dba_auditor']))
        token_non_auditor = create_access_token(_token_data(user_non_auditor, ['dba_regular']))
        token_dbops = create_access_token(_token_data(user_dbops, ['dbops_no_audit']))

        return {
            'token_auditor': token_auditor,
            'token_non_auditor': token_non_auditor,
            'token_dbops': token_dbops,
        }

    def test_auditor_can_access_audit_executions(self, audit_setup):
        """User with auditor profile can access /audit/executions."""
        client = make_auth_client(audit_setup['token_auditor'])
        response = client.get('/api/v1/audit/executions')
        assert response.status_code == status.HTTP_200_OK

    def test_non_auditor_denied_audit_executions(self, audit_setup):
        """Non-auditor user is denied access to /audit/executions."""
        client = make_auth_client(audit_setup['token_non_auditor'])
        response = client.get('/api/v1/audit/executions')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_without_auditor_denied_audit(self, audit_setup):
        """DBOPS without auditor flag is denied /audit/executions."""
        client = make_auth_client(audit_setup['token_dbops'])
        response = client.get('/api/v1/audit/executions')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_audit(self, anon_client):
        """Unauthenticated request to /audit/executions returns 401."""
        response = anon_client.get('/api/v1/audit/executions')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_auditor_can_reach_export_view(self, audit_setup):
        """Auditor reaches /audit/export (gets 400 for missing format, NOT 403)."""
        client = make_auth_client(audit_setup['token_auditor'])
        # Without ?format= the view returns 400 (format invalide), but NOT 403.
        # We avoid ?format=csv because DRF's URL_FORMAT_OVERRIDE intercepts it.
        response = client.get('/api/v1/audit/export')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_non_auditor_denied_audit_export(self, audit_setup):
        """Non-auditor is denied /audit/export (403 before format validation)."""
        client = make_auth_client(audit_setup['token_non_auditor'])
        response = client.get('/api/v1/audit/export')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Subtask 4.4: PUT/DELETE /profiles restricted to DBOPS
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestProfileWriteRestricted:
    """PUT/DELETE /admin/profiles/{id} restricted to DBOPS."""

    @pytest.fixture
    def profile_write_setup(self, db):
        """Setup a target profile and users."""
        target_profile = Profile.objects.create(
            name='TARGET_PROFILE',
            ad_group='target_profile',
            is_admin=0,
            is_auditor=0,
        )
        dbops_user = User.objects.create(
            username='pw_dbops', display_name='PW DBOPS', profile='dbops',
        )
        Profile.objects.create(
            name='PW_DBOPS', ad_group='pw_dbops', is_admin=1, is_auditor=0,
        )
        dba_user = User.objects.create(
            username='pw_dba', display_name='PW DBA', profile='dba',
        )
        Profile.objects.create(
            name='PW_DBA', ad_group='pw_dba', is_admin=0, is_auditor=0,
        )
        token_dbops = create_access_token(_token_data(dbops_user, ['pw_dbops']))
        token_dba = create_access_token(_token_data(dba_user, ['pw_dba']))
        return {
            'target_profile': target_profile,
            'token_dbops': token_dbops,
            'token_dba': token_dba,
        }

    def test_dbops_can_update_profile(self, profile_write_setup):
        """DBOPS can PUT /admin/profiles/{id}."""
        pid = profile_write_setup['target_profile'].id
        client = make_auth_client(profile_write_setup['token_dbops'])
        response = client.put(
            f'/api/v1/admin/profiles/{pid}/',
            data={'name': 'UPDATED_PROFILE', 'ad_group': 'updated'},
            format='json',
        )
        assert response.status_code == status.HTTP_200_OK

    def test_dba_cannot_update_profile(self, profile_write_setup):
        """DBA gets 403 on PUT /admin/profiles/{id}."""
        pid = profile_write_setup['target_profile'].id
        client = make_auth_client(profile_write_setup['token_dba'])
        response = client.put(
            f'/api/v1/admin/profiles/{pid}/',
            data={'name': 'HACKED', 'ad_group': 'hacked'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_can_delete_profile(self, profile_write_setup):
        """DBOPS can DELETE /admin/profiles/{id}."""
        pid = profile_write_setup['target_profile'].id
        client = make_auth_client(profile_write_setup['token_dbops'])
        response = client.delete(f'/api/v1/admin/profiles/{pid}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_dba_cannot_delete_profile(self, profile_write_setup):
        """DBA gets 403 on DELETE /admin/profiles/{id}."""
        pid = profile_write_setup['target_profile'].id
        client = make_auth_client(profile_write_setup['token_dba'])
        response = client.delete(f'/api/v1/admin/profiles/{pid}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Subtask 4.5: PUT/DELETE /integrations restricted to DBOPS
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestIntegrationWriteRestricted:
    """PUT/DELETE /admin/integrations/{id} restricted to DBOPS."""

    @pytest.fixture
    def integration_write_setup(self, db):
        """Setup a target integration and users."""
        integration = Integration.objects.create(
            type='aap',
            name='Write Test Integration',
            base_url='https://aap-write.example.com',
        )
        dbops_user = User.objects.create(
            username='iw_dbops', display_name='IW DBOPS', profile='dbops',
        )
        Profile.objects.create(
            name='IW_DBOPS', ad_group='iw_dbops', is_admin=1, is_auditor=0,
        )
        dba_user = User.objects.create(
            username='iw_dba', display_name='IW DBA', profile='dba',
        )
        Profile.objects.create(
            name='IW_DBA', ad_group='iw_dba', is_admin=0, is_auditor=0,
        )
        token_dbops = create_access_token(_token_data(dbops_user, ['iw_dbops']))
        token_dba = create_access_token(_token_data(dba_user, ['iw_dba']))
        return {
            'integration': integration,
            'token_dbops': token_dbops,
            'token_dba': token_dba,
        }

    def test_dba_cannot_update_integration(self, integration_write_setup):
        """DBA gets 403 on PUT /admin/integrations/{id}."""
        iid = integration_write_setup['integration'].id
        client = make_auth_client(integration_write_setup['token_dba'])
        response = client.put(
            f'/api/v1/admin/integrations/{iid}/',
            data={'name': 'HACKED', 'type': 'aap', 'base_url': 'https://h.com'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dba_cannot_delete_integration(self, integration_write_setup):
        """DBA gets 403 on DELETE /admin/integrations/{id}."""
        iid = integration_write_setup['integration'].id
        client = make_auth_client(integration_write_setup['token_dba'])
        response = client.delete(f'/api/v1/admin/integrations/{iid}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_can_list_integrations(self, integration_write_setup):
        """DBOPS can GET /admin/integrations/."""
        client = make_auth_client(integration_write_setup['token_dbops'])
        response = client.get('/api/v1/admin/integrations/')
        assert response.status_code == status.HTTP_200_OK

    def test_dba_cannot_create_integration(self, integration_write_setup):
        """DBA gets 403 on POST /admin/integrations/."""
        client = make_auth_client(integration_write_setup['token_dba'])
        response = client.post(
            '/api/v1/admin/integrations/',
            data={'name': 'New', 'type': 'aap', 'base_url': 'https://new.com'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Subtask 4.7: Execution logs isolation
# ============================================================================

@pytest.mark.django_db
@pytest.mark.security
class TestExecutionLogIsolation:
    """Users can only view execution detail/steps for their own executions (DBOPS sees all)."""

    @pytest.fixture
    def log_isolation_setup(self, db):
        """Setup users and executions for log isolation tests."""
        integration = Integration.objects.create(
            type='aap', name='Log Test AAP', base_url='https://aap-log.example.com',
        )
        owner = User.objects.create(
            username='log_owner', display_name='Log Owner', profile='dba',
        )
        other = User.objects.create(
            username='log_other', display_name='Log Other', profile='client_business',
        )
        dbops = User.objects.create(
            username='log_dbops', display_name='Log DBOPS', profile='dbops',
        )
        action = Action.objects.create(
            name='Log Test Action', category='Provisioning',
            engine='Oracle', platform='AAP', status='published',
            created_by=owner, integration=integration,
        )
        execution = Execution.objects.create(
            action=action, user=owner, environment='dev',
            status=ExecutionStatus.COMPLETED,
        )
        token_owner = create_access_token(_token_data(owner, ['dba']))
        token_other = create_access_token(_token_data(other, ['client_business']))
        token_dbops = create_access_token(_token_data(dbops, ['dbops']))
        return {
            'execution': execution,
            'token_owner': token_owner,
            'token_other': token_other,
            'token_dbops': token_dbops,
        }

    def test_owner_can_view_execution_detail(self, log_isolation_setup):
        """Owner can GET /executions/{id}."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_owner'])
        response = client.get(f'/api/v1/executions/{eid}')
        assert response.status_code == status.HTTP_200_OK

    def test_other_user_forbidden_execution_detail(self, log_isolation_setup):
        """Non-owner non-DBOPS gets 403 on GET /executions/{id}."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_other'])
        response = client.get(f'/api/v1/executions/{eid}')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_can_view_any_execution_detail(self, log_isolation_setup):
        """DBOPS can view any execution detail."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_dbops'])
        response = client.get(f'/api/v1/executions/{eid}')
        assert response.status_code == status.HTTP_200_OK

    def test_owner_can_view_execution_steps(self, log_isolation_setup):
        """Owner can GET /executions/{id}/steps."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_owner'])
        response = client.get(f'/api/v1/executions/{eid}/steps')
        assert response.status_code == status.HTTP_200_OK

    def test_other_user_forbidden_execution_steps(self, log_isolation_setup):
        """Non-owner gets 403 on GET /executions/{id}/steps."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_other'])
        response = client.get(f'/api/v1/executions/{eid}/steps')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dbops_can_view_any_execution_steps(self, log_isolation_setup):
        """DBOPS can view any execution's steps."""
        eid = log_isolation_setup['execution'].id
        client = make_auth_client(log_isolation_setup['token_dbops'])
        response = client.get(f'/api/v1/executions/{eid}/steps')
        assert response.status_code == status.HTTP_200_OK
