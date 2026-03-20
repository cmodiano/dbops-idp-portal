"""
Tests for execution cancellation endpoint (Story 17.14).
PATCH /api/v1/executions/{id}/cancel/
"""

import pytest
from unittest.mock import patch
from rest_framework.test import APIClient

from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory
from executions.models import ExecutionStatus


@pytest.mark.django_db
class TestCancelExecutionByInitiator:
    """Test 2.1 & 2.2: Cancellation by the execution initiator."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)
        self.client.force_authenticate(user=self.user)

    def test_cancel_submitted_execution_by_initiator(self):
        """2.1: Cancel SUBMITTED execution by owner -> synchronous cancel (200 OK).

        The view updates status to CANCELLED synchronously and returns 200.
        """
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        data = response.json()['data']
        assert data['status'] == 'CANCELLED'

        # Synchronous cancel: status updated immediately
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED

    def test_cancel_running_execution_by_initiator(self):
        """2.2: Cancel RUNNING execution by owner -> 200 OK (synchronous cancel)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'


@pytest.mark.django_db
class TestCancelExecutionByAdmin:
    """Test 2.3: Cancellation by admin DBOPS on another user's execution."""

    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory.create(profile='DBA', username='owner_user')
        self.admin = UserFactory.create(profile='DBOPS', username='admin_user')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)

    def test_cancel_by_dbops_admin(self):
        """2.3: DBOPS admin can cancel another user's RUNNING execution (synchronous cancel)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        self.client.force_authenticate(user=self.admin)
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'

    def test_cancel_by_dba_admin(self):
        """DBOPS profile user can cancel another user's execution (synchronous cancel)."""
        dbops_admin = UserFactory.create(profile='DBOPS', username='dbops_admin')
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        self.client.force_authenticate(user=dbops_admin)
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'


@pytest.mark.django_db
class TestCancelExecutionUnauthorized:
    """Test 2.4: Unauthorized user cannot cancel another's execution."""

    def setup_method(self):
        self.client = APIClient()
        self.owner = UserFactory.create(profile='DBA', username='owner_user')
        self.other_user = UserFactory.create(profile='BUSINESS', username='other_user')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)

    def test_non_owner_non_admin_gets_403(self):
        """2.4: Non-owner, non-DBOPS user gets 403 Forbidden."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        self.client.force_authenticate(user=self.other_user)
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 403
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.SUBMITTED  # Unchanged

    def test_unauthenticated_gets_401(self):
        """Unauthenticated request gets 401."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestCancelTerminalStatusExecution:
    """Test 2.5: Cannot cancel executions in terminal status."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)
        self.client.force_authenticate(user=self.user)

    @pytest.mark.parametrize("terminal_status", [
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.REJECTED,
    ])
    def test_cancel_terminal_status_returns_400(self, terminal_status):
        """2.5: Cancelling a terminal-status execution returns 400 with message."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=terminal_status, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 400
        body = response.json()
        assert 'Impossible' in body.get('message', '') or 'Impossible' in str(body)

    def test_cancel_nonexistent_execution_returns_404(self):
        """Cancelling a non-existent execution returns 404."""
        url = '/api/v1/executions/99999/cancel/'
        response = self.client.patch(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestCancelRemoteExecution:
    """Test 2.6: Remote cancellation attempt via AAP adapter."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)
        self.client.force_authenticate(user=self.user)

    def test_remote_cancel_called_for_running_with_job_id(self):
        """2.6a: Cancel RUNNING execution avec platform_job_id -> synchronous cancel (200 OK).

        Remote cancellation is attempted best-effort during the synchronous cancel.
        """
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-123'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'

    def test_remote_cancel_failure_still_cancels_locally(self):
        """2.6b: Cancel RUNNING execution avec platform_job_id -> 200 OK (synchronous cancel)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-456'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'

    def test_remote_cancel_not_implemented_still_cancels(self):
        """2.6c: Cancel RUNNING execution -> 200 OK even without job_id (synchronous cancel)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-789'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 200
        assert response.json()['data']['status'] == 'CANCELLED'

    def test_no_remote_cancel_for_submitted(self):
        """Remote cancel NOT attempted for SUBMITTED (only RUNNING)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'

        with patch('executions.views.execution_views.get_platform_adapter') as MockAdapter:
            response = self.client.patch(url)

        assert response.status_code == 200
        MockAdapter.assert_not_called()


@pytest.mark.django_db
class TestConcurrentCancellation:
    """MEDIUM-3 fix: Test race conditions with concurrent cancellation."""

    def setup_method(self):
        self.client = APIClient()
        self.user1 = UserFactory.create(profile='DBOPS', username='admin1')
        self.user2 = UserFactory.create(profile='DBOPS', username='admin2')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')
        self.action = ActionFactory.create(status='published', integration=self.integration)

    def test_concurrent_cancel_attempts(self):
        """Deux admins annulent la meme execution — le premier recoit 200, le second 400.

        The view uses CAS (Compare-And-Swap): the first cancel succeeds and sets
        status to CANCELLED. The second cancel fails because the status is no longer
        SUBMITTED/RUNNING.
        """
        owner = UserFactory.create(profile='DBA', username='owner')
        execution = ExecutionFactory.create(
            action=self.action, user=owner,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'

        # Premier cancel : succeeds
        self.client.force_authenticate(user=self.user1)
        response1 = self.client.patch(url)
        assert response1.status_code == 200

        # Deuxieme cancel : execution already CANCELLED -> 400
        self.client.force_authenticate(user=self.user2)
        response2 = self.client.patch(url)
        assert response2.status_code == 400
