"""
Global pytest fixtures for Django backend tests.

Story M.9: Tests unitaires et d'intégration
This module provides reusable fixtures following pytest best practices.
"""

import pytest
from rest_framework.test import APIClient

# Import factories (created in factories.py)
from tests.factories import (
    UserFactory,
    ActionFactory,
    IntegrationFactory,
    ProfileFactory,
    ProfileActionPermissionFactory,
    ProfileTargetPermissionFactory,
    ExecutionFactory,
    ExecutionStepFactory,
    ScheduledExecutionFactory,
    RecurringPatternFactory,
    AuditLogFactory,
    TagFactory,
)


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def db_user(db):
    """Standard user for tests."""
    return UserFactory.create(profile='DBA')


@pytest.fixture
def admin_user(db):
    """Admin user with DBOPS profile and full permissions."""
    return UserFactory.create(profile='DBOPS', username='admin_user')


@pytest.fixture
def auditor_user(db):
    """Auditor user with read-only access for audit reports."""
    return UserFactory.create(profile='AUDITOR', username='auditor_user')


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def api_client_authenticated(api_client, db_user):
    """Authenticated API client with standard user."""
    api_client.force_authenticate(user=db_user)
    return api_client


@pytest.fixture
def api_client_admin(api_client, admin_user):
    """Authenticated API client with admin user."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def api_client_auditor(api_client, auditor_user):
    """Authenticated API client with auditor user."""
    api_client.force_authenticate(user=auditor_user)
    return api_client


# ============================================================================
# Integration Fixtures
# ============================================================================

@pytest.fixture
def sample_integration(db):
    """Sample AAP integration for tests."""
    return IntegrationFactory.create(type='aap', name='Test AAP')


@pytest.fixture
def sample_integration_servicenow(db):
    """Sample ServiceNow integration for tests."""
    return IntegrationFactory.create(
        type='servicenow',
        name='Test ServiceNow',
        base_url='https://servicenow.example.com'
    )


@pytest.fixture
def sample_integration_terraform(db):
    """Sample Terraform integration for tests."""
    return IntegrationFactory.create(
        type='terraform',
        name='Test Terraform',
        base_url='https://terraform.example.com'
    )


# ============================================================================
# Action Fixtures
# ============================================================================

@pytest.fixture
def sample_action_draft(db, db_user, sample_integration):
    """Draft action for tests."""
    return ActionFactory.create(
        status='draft',
        created_by=db_user,
        integration=sample_integration
    )


@pytest.fixture
def sample_action_published(db, db_user, sample_integration):
    """Published action in catalog."""
    return ActionFactory.create(
        status='published',
        created_by=db_user,
        integration=sample_integration
    )


@pytest.fixture
def sample_action_disabled(db, db_user, sample_integration):
    """Disabled action for tests."""
    return ActionFactory.create(
        status='disabled',
        created_by=db_user,
        integration=sample_integration
    )


@pytest.fixture
def sample_action_workflow(db, db_user, sample_integration):
    """Workflow-type action for tests."""
    return ActionFactory.create(
        status='published',
        item_type='workflow',
        created_by=db_user,
        integration=sample_integration
    )


# ============================================================================
# Tag Fixtures
# ============================================================================

@pytest.fixture
def sample_tags(db):
    """Set of sample tags for tests."""
    return [
        TagFactory.create(name='oracle'),
        TagFactory.create(name='database'),
        TagFactory.create(name='provisioning'),
    ]


# ============================================================================
# Profile Fixtures
# ============================================================================

@pytest.fixture
def sample_profile(db):
    """Standard DBA profile with permissions."""
    profile = ProfileFactory.create(
        name='DBA',
        ad_group='CN=DBA,OU=Groups,DC=example,DC=com',
        is_admin=0,
        is_auditor=0
    )
    return profile


@pytest.fixture
def sample_profile_admin(db):
    """Admin DBOPS profile with full permissions."""
    profile = ProfileFactory.create(
        name='DBOPS',
        ad_group='CN=DBOPS,OU=Groups,DC=example,DC=com',
        is_admin=1,
        is_auditor=0
    )
    return profile


@pytest.fixture
def sample_profile_auditor(db):
    """Auditor profile with read-only access."""
    profile = ProfileFactory.create(
        name='AUDITOR',
        ad_group='CN=Auditors,OU=Groups,DC=example,DC=com',
        is_admin=0,
        is_auditor=1
    )
    return profile


@pytest.fixture
def sample_profile_with_action_permissions(db, sample_action_published):
    """Profile with specific action permissions (LIST type)."""
    profile = ProfileFactory.create(
        name='ProfileWithActionPerm',
        ad_group='CN=TestPerm,OU=Groups,DC=example,DC=com'
    )
    ProfileActionPermissionFactory.create(
        profile=profile,
        permission_type='LIST',
        action_ids_json=f'[{sample_action_published.id}]'
    )
    return profile


@pytest.fixture
def sample_profile_with_all_permissions(db):
    """Profile with ALL action and target permissions."""
    profile = ProfileFactory.create(
        name='ProfileAllPerm',
        ad_group='CN=AllPerm,OU=Groups,DC=example,DC=com'
    )
    ProfileActionPermissionFactory.create(
        profile=profile,
        permission_type='ALL'
    )
    ProfileTargetPermissionFactory.create(
        profile=profile,
        permission_type='ALL'
    )
    return profile


# ============================================================================
# Execution Fixtures
# ============================================================================

@pytest.fixture
def sample_execution_pending(db, db_user, sample_action_published):
    """Execution in SUBMITTED status."""
    return ExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        status='SUBMITTED',
        environment='dev'
    )


@pytest.fixture
def sample_execution_running(db, db_user, sample_action_published):
    """Execution in RUNNING status."""
    return ExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        status='RUNNING',
        environment='dev'
    )


@pytest.fixture
def sample_execution_completed(db, db_user, sample_action_published):
    """Execution in COMPLETED status."""
    return ExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        status='COMPLETED',
        environment='dev'
    )


@pytest.fixture
def sample_execution_failed(db, db_user, sample_action_published):
    """Execution in FAILED status."""
    return ExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        status='FAILED',
        environment='dev'
    )


@pytest.fixture
def sample_execution_with_steps(db, sample_execution_running):
    """Execution with multiple execution steps."""
    steps = [
        ExecutionStepFactory.create(
            execution=sample_execution_running,
            step_order=1,
            step_name='Fetch credentials',
            step_type='vault',
            status='COMPLETED'
        ),
        ExecutionStepFactory.create(
            execution=sample_execution_running,
            step_order=2,
            step_name='Create change ticket',
            step_type='servicenow',
            status='RUNNING'
        ),
        ExecutionStepFactory.create(
            execution=sample_execution_running,
            step_order=3,
            step_name='Execute on AAP',
            step_type='platform',
            status='PENDING'
        ),
    ]
    return sample_execution_running, steps


# ============================================================================
# Scheduled Execution Fixtures
# ============================================================================

@pytest.fixture
def sample_scheduled_execution(db, db_user, sample_action_published):
    """One-time scheduled execution for tests."""
    from django.utils import timezone
    return ScheduledExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        environment='dev',
        status='pending',
        scheduled_at=timezone.now() + timezone.timedelta(hours=1)
    )


@pytest.fixture
def sample_scheduled_execution_recurring(db, db_user, sample_action_published):
    """Recurring scheduled execution with daily pattern."""
    from django.utils import timezone
    scheduled = ScheduledExecutionFactory.create(
        action=sample_action_published,
        user=db_user,
        environment='dev',
        status='pending',
        scheduled_at=None  # Recurring uses next_execution_date
    )
    RecurringPatternFactory.create(
        scheduled_execution=scheduled,
        pattern_type='daily',
        next_execution_date=timezone.now() + timezone.timedelta(days=1),
        is_active=1
    )
    return scheduled


# ============================================================================
# Audit Log Fixtures
# ============================================================================

@pytest.fixture
def sample_audit_entry(db, sample_action_published):
    """Sample audit log entry for tests."""
    return AuditLogFactory.create(
        user_id='testuser',
        action_type='ACTION_CREATED',
        entity_type='action',
        entity_id=sample_action_published.id
    )


@pytest.fixture
def sample_audit_entries(db, sample_action_published):
    """Multiple audit log entries for pagination/filter tests."""
    entries = []
    action_types = [
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED',
        'EXECUTION_SUBMITTED', 'EXECUTION_COMPLETED'
    ]
    for i, action_type in enumerate(action_types):
        entries.append(AuditLogFactory.create(
            user_id=f'user{i}',
            action_type=action_type,
            entity_type='action' if action_type.startswith('ACTION') else 'execution',
            entity_id=sample_action_published.id + i
        ))
    return entries


# ============================================================================
# Mock Fixtures for External Services
# ============================================================================

@pytest.fixture
def mock_vault_service(mocker):
    """Mock Vault service for credential retrieval."""
    mock = mocker.patch('core.services.vault_service')
    mock.get_credentials.return_value = {
        'username': 'test_user',
        'password': 'test_password'
    }
    return mock


@pytest.fixture
def mock_servicenow_service(mocker):
    """Mock ServiceNow service for change ticket operations."""
    mock = mocker.patch('core.services.servicenow_service')
    mock.create_change.return_value = {'sys_id': 'CHG0001234', 'number': 'CHG0001234'}
    mock.update_change.return_value = True
    mock.close_change.return_value = True
    return mock


@pytest.fixture
def mock_aap_adapter(mocker):
    """Mock AAP adapter for execution."""
    mock = mocker.patch('executions.adapters.aap_adapter')
    mock.submit_job.return_value = {'job_id': 12345, 'status': 'pending'}
    mock.get_job_status.return_value = {'status': 'successful', 'finished': True}
    return mock


# ============================================================================
# Database Transaction Fixtures
# ============================================================================

@pytest.fixture
def transactional_db(db):
    """
    Fixture that wraps test in a transaction for rollback testing.
    Use with @pytest.mark.django_db(transaction=True)
    """
    from django.db import connection
    return connection


# ============================================================================
# Settings Override Fixtures
# ============================================================================

@pytest.fixture
def override_jwt_settings(settings):
    """Override JWT settings for tests."""
    settings.JWT_SECRET_KEY = 'test-secret-key-for-tests'
    settings.JWT_ALGORITHM = 'HS256'
    settings.JWT_EXPIRATION_MINUTES = 60
    return settings


@pytest.fixture
def override_saml_settings(settings):
    """Override SAML settings for tests."""
    settings.SAML_ENABLED = True
    settings.SAML_SP_ENTITY_ID = 'https://test-sp.example.com'
    settings.SAML_IDP_ENTITY_ID = 'https://test-idp.example.com'
    return settings
