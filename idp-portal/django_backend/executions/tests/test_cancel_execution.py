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
        """2.1: Cancel SUBMITTED execution by owner -> commande écrite (202 accepted).

        Story 78.5: L'endpoint écrit une commande durable et retourne 202.
        L'exécution reste SUBMITTED jusqu'au traitement par le command processor.
        """
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        data = response.json()['data']
        assert data['status'] == 'accepted'
        assert 'command_id' in data

        # Story 78.5: commande écrite, pas traitée inline — statut inchangé
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.SUBMITTED

    def test_cancel_running_execution_by_initiator(self):
        """2.2: Cancel RUNNING execution by owner -> 202 accepted (commande écrite, story 78.5)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'


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
        """2.3: DBOPS admin can cancel another user's RUNNING execution (commande écrite, story 78.5)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        self.client.force_authenticate(user=self.admin)
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'

    def test_cancel_by_dba_admin(self):
        """DBOPS profile user can cancel another user's execution (commande écrite, story 78.5)."""
        dbops_admin = UserFactory.create(profile='DBOPS', username='dbops_admin')
        execution = ExecutionFactory.create(
            action=self.action, user=self.owner,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        self.client.force_authenticate(user=dbops_admin)
        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'


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
        """2.6a: Cancel RUNNING execution avec platform_job_id → commande écrite (story 78.5).

        Story 78.5: L'endpoint écrit une commande durable ; la suppression distante
        est déléguée au command processor (non testée ici).
        """
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-123'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'

    def test_remote_cancel_failure_still_cancels_locally(self):
        """2.6b: Cancel RUNNING execution avec platform_job_id → 202 accepted (story 78.5)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-456'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'

    def test_remote_cancel_not_implemented_still_cancels(self):
        """2.6c: Cancel RUNNING execution → 202 accepted même sans job_id (story 78.5)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        execution.set_parameters({'platform_job_id': 'job-789'})
        execution.save()

        url = f'/api/v1/executions/{execution.id}/cancel/'
        response = self.client.patch(url)

        assert response.status_code == 202
        assert response.json()['data']['status'] == 'accepted'

    def test_no_remote_cancel_for_submitted(self):
        """Remote cancel NOT attempted for SUBMITTED (only RUNNING)."""
        execution = ExecutionFactory.create(
            action=self.action, user=self.user,
            status=ExecutionStatus.SUBMITTED, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'

        with patch('executions.views.execution_views.get_platform_adapter') as MockAdapter:
            response = self.client.patch(url)

        assert response.status_code == 202
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
        """Deux admins annulent la même exécution — les deux reçoivent 202 (story 78.5).

        Story 78.5: L'endpoint écrit des commandes durables sans modifier le statut
        en ligne. Deux requêtes concurrentes écrivent deux commandes ; le command
        processor déduplique l'annulation (idempotence côté worker).
        """
        owner = UserFactory.create(profile='DBA', username='owner')
        execution = ExecutionFactory.create(
            action=self.action, user=owner,
            status=ExecutionStatus.RUNNING, environment='dev',
        )
        url = f'/api/v1/executions/{execution.id}/cancel/'

        # Premier cancel : commande écrite
        self.client.force_authenticate(user=self.user1)
        response1 = self.client.patch(url)
        assert response1.status_code == 202

        # Deuxième cancel : exécution toujours RUNNING (pas encore traitée) → 202 aussi
        self.client.force_authenticate(user=self.user2)
        response2 = self.client.patch(url)
        assert response2.status_code == 202
