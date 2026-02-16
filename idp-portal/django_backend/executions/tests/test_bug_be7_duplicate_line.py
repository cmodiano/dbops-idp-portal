"""
Tests for BUG-BE-7: duplicate line `se.environment = ...` removed.
Story 30.3 — AC6.

Verifies that PUT /scheduled-executions/{id} correctly assigns environment once.
"""

from unittest.mock import patch
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionStatus
from executions.models import ScheduledExecution, ScheduledExecutionStatus
from tests.factories import UserFactory


@patch('executions.views.scheduled_views.validate_environment_against_inventory')
@pytest.mark.django_db
class TestDuplicateLineRemoved(TestCase):
    """Tests that environment assignment is not duplicated."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='creator_be7', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action BE7',
            description='Test',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def test_put_environment_assigned_correctly(self, mock_validate):
        """PUT with environment=prod → se.environment == 'prod' (assigned correctly)."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'environment': 'prod', 'target_names': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        se.refresh_from_db()
        self.assertEqual(se.environment, 'prod')

    def test_put_environment_staging_with_empty_targets(self, mock_validate):
        """PUT with target_names=[] and environment=staging → se.environment == 'staging'."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'environment': 'staging', 'target_names': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        se.refresh_from_db()
        self.assertEqual(se.environment, 'staging')
