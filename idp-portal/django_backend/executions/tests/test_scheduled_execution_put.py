"""
Tests for PUT /api/v1/scheduled-executions/{id} (Story 13.8, AC4).
"""

from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from catalog.models import Action, ActionStatus
from executions.models import ScheduledExecution, ScheduledExecutionStatus, RecurringPattern

User = get_user_model()


@patch('executions.views._validate_environment_against_inventory')
class ScheduledExecutionPutTests(TestCase):
    """Tests for PUT scheduled execution (Story 13.8)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='creator', profile='DBA')
        self.other_user = User.objects.create_user(username='other', profile='DBA')
        self.dbops_user = User.objects.create_user(username='dbops', profile='DBOPS')
        self.action = Action.objects.create(
            name='Test Action',
            description='Test',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def test_put_scheduled_at_one_time(self, mock_validate):
        """PUT updates scheduled_at for one-time execution."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        new_at = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}',
            {'scheduled_at': new_at},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.json())
        se.refresh_from_db()
        self.assertIsNotNone(se.scheduled_at)

    def test_put_returns_403_for_non_creator_dba(self, mock_validate):
        """PUT by DBA who is not creator returns 403."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        self.client.force_authenticate(user=self.other_user)
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}',
            {'scheduled_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_returns_400_when_not_pending(self, mock_validate):
        """PUT on executed/cancelled execution returns 400."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.CANCELLED,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}',
            {'scheduled_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_returns_404_for_missing_id(self, mock_validate):
        """PUT on non-existent id returns 404."""
        response = self.client.put(
            '/api/v1/scheduled-executions/99999',
            {'scheduled_at': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_put_target_names_empty_clears_targets(self, mock_validate):
        """PUT with target_names=[] clears _targets and allows environment update (Story 13.8 code review)."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        se.set_parameters({'_targets': ['t1'], 'key': 'v1'})
        se.save(update_fields=['parameters'])
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}',
            {'target_names': [], 'environment': 'staging'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        se.refresh_from_db()
        params = se.get_parameters()
        self.assertEqual(params.get('_targets'), [])
        self.assertEqual(se.environment, 'staging')

    def test_put_parameters_does_not_accept_targets_injection(self, mock_validate):
        """PUT with parameters._targets does not persist _targets (RBAC bypass fix)."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        se.set_parameters({'_targets': ['allowed'], 'x': 1})
        se.save(update_fields=['parameters'])
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}',
            {'parameters': {'x': 2, '_targets': ['injected']}},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        se.refresh_from_db()
        params = se.get_parameters()
        self.assertEqual(params.get('_targets'), ['allowed'])
        self.assertEqual(params.get('x'), 2)
