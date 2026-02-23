"""
Tests d'intégration for BUG-BE-3: user_id in audit logs.
Story 30.3 — Fixes MED-2.

Vérifie que les appels API authentifiés génèrent des logs contenant user_id.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionStatus
from tests.factories import UserFactory


@pytest.mark.django_db
class TestUserIdInAuditLogs(TestCase):
    """Tests d'intégration vérifiant que user_id est présent dans les audit logs."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='test_user_be3', profile='dba')
        self.action = Action.objects.create(
            name='Test Action BE3',
            description='For logging test',
            category='Test',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
        )

    def test_authenticated_api_call_logs_contain_user_id(self):
        """Real API call with authentication → structlog contains user_id."""
        self.client.force_authenticate(user=self.user)

        with self.assertLogs('core.middleware', level='INFO') as cm:
            response = self.client.get('/api/v1/catalog/actions')

        assert response.status_code == status.HTTP_200_OK

        # Check that logs contain user_id
        logs_output = '\n'.join(cm.output)
        assert str(self.user.id) in logs_output, f"Logs should contain user_id={self.user.id}"
        assert 'request_completed' in logs_output

    def test_unauthenticated_api_call_logs_no_user_id(self):
        """Unauthenticated API call → structlog should NOT contain user_id."""
        # No authentication
        with self.assertLogs('core.middleware', level='INFO') as cm:
            self.client.get('/api/v1/catalog/actions')

        # Request may succeed (public endpoint) or fail (auth required)
        # Either way, logs should NOT contain a user_id

        logs_output = '\n'.join(cm.output)
        # user_id may be null or absent, but should not be an actual user ID
        assert 'user_id=None' in logs_output or 'user_id' not in logs_output
