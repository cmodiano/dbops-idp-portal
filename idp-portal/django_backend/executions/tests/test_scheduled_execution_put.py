"""
Tests for PUT /api/v1/scheduled-executions/{id}.
Story 11.11: Only date fields are modifiable (scheduled_at for one-time, next_execution_date for recurring).
Story 26.10: Updated @patch decorators after function renaming.
"""

from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from catalog.models import Action, ActionStatus
from executions.models import ScheduledExecution, ScheduledExecutionStatus, RecurringPattern
from tests.factories import UserFactory


@patch('executions.views.scheduled_views.validate_environment_against_inventory')
class ScheduledExecutionPutTests(TestCase):
    """Tests for PUT scheduled execution — Story 11.11 restrictions."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='creator', profile='DBA')
        self.other_user = UserFactory(username='other', profile='DBA')
        self.dbops_user = UserFactory(username='dbops', profile='DBOPS')
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
            f'/api/v1/scheduled-executions/{se.id}/',
            {'scheduled_at': new_at},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.json())
        se.refresh_from_db()
        self.assertIsNotNone(se.scheduled_at)

    def test_put_returns_403_for_non_owner_non_admin(self, mock_validate):
        """PUT by DBA (non-admin, is_admin=0) who is not owner returns 403."""
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
            f'/api/v1/scheduled-executions/{se.id}/',
            {'scheduled_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        # DBA has is_admin=0, not owner → 403
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
            f'/api/v1/scheduled-executions/{se.id}/',
            {'scheduled_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_put_returns_404_for_missing_id(self, mock_validate):
        """PUT on non-existent id returns 404."""
        response = self.client.put(
            '/api/v1/scheduled-executions/99999/',
            {'scheduled_at': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Story 11.11: Forbidden fields now return 400

    def test_put_rejects_environment_field(self, mock_validate):
        """Story 11.11 AC1: PUT with environment returns 400 FIELD_NOT_MODIFIABLE."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'environment': 'staging'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_MODIFIABLE')

    def test_put_rejects_target_names_field(self, mock_validate):
        """Story 11.11 AC1: PUT with target_names returns 400 FIELD_NOT_MODIFIABLE."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'target_names': ['t1']},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_MODIFIABLE')

    def test_put_rejects_parameters_field(self, mock_validate):
        """Story 11.11 AC1: PUT with parameters returns 400 FIELD_NOT_MODIFIABLE."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'parameters': {'key': 'val'}},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_MODIFIABLE')

    def test_put_rejects_recurring_pattern_field(self, mock_validate):
        """Story 11.11 AC1: PUT with recurring_pattern returns 400 FIELD_NOT_MODIFIABLE."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'recurring_pattern': {'pattern_type': 'daily', 'pattern_config': {'hour': 10, 'minute': 0}}},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_MODIFIABLE')

    def test_put_rejects_multiple_forbidden_fields(self, mock_validate):
        """Story 11.11 AC1: PUT with multiple forbidden fields returns 400 with all listed."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'environment': 'staging', 'target_names': [], 'scheduled_at': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_data = response.json()['error']
        self.assertEqual(error_data['code'], 'FIELD_NOT_MODIFIABLE')
        self.assertIn('environment', error_data['details']['forbidden_fields'])
        self.assertIn('target_names', error_data['details']['forbidden_fields'])

    def test_put_next_execution_date_recurring(self, mock_validate):
        """Story 11.11 AC1: PUT updates next_execution_date for recurring execution."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ScheduledExecutionStatus.PENDING,
        )
        rp = RecurringPattern.objects.create(
            scheduled_execution=se,
            pattern_type='daily',
            pattern_config='{"hour": 10, "minute": 0}',
            next_execution_date=future,
            is_active=1,
        )
        new_date = (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'next_execution_date': new_date},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rp.refresh_from_db()
        self.assertIsNotNone(rp.next_execution_date)

    def test_put_scheduled_at_must_be_future(self, mock_validate):
        """PUT with past scheduled_at returns 400."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        past_at = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'scheduled_at': past_at},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'INVALID_SCHEDULED_DATE')

    def test_put_rejects_next_execution_date_on_onetime(self, mock_validate):
        """PUT with next_execution_date on one-time execution returns 400 FIELD_NOT_APPLICABLE."""
        mock_validate.return_value = None
        future = timezone.now() + timedelta(days=1)
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            scheduled_at=future, status=ScheduledExecutionStatus.PENDING,
        )
        new_date = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'next_execution_date': new_date},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_APPLICABLE')

    def test_put_rejects_scheduled_at_on_recurring(self, mock_validate):
        """PUT with scheduled_at on recurring execution returns 400 FIELD_NOT_APPLICABLE."""
        mock_validate.return_value = None
        se = ScheduledExecution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ScheduledExecutionStatus.PENDING,
        )
        RecurringPattern.objects.create(
            scheduled_execution=se, pattern_type='daily',
            pattern_config='{"hour": 10, "minute": 0}',
            next_execution_date=timezone.now() + timedelta(days=1),
            is_active=1,
        )
        new_at = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.put(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'scheduled_at': new_at},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'FIELD_NOT_APPLICABLE')
