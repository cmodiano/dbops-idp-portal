"""
Tests for Story 11.11: POST recurring_pattern admin restriction (AC2, AC3).

PUT field restriction tests are in test_scheduled_execution_put.py (dedicated file).
"""

from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from catalog.models import Action, ActionStatus
from tests.factories import UserFactory


# =============================================================================
# POST /scheduled-executions — recurring_pattern admin restriction (AC2, AC3)
# =============================================================================


@patch('executions.views.scheduled_views.validate_environment_against_inventory')
class PostRecurringAdminRestrictionTests(TestCase):
    """Story 11.11 AC2/AC3: Recurring patterns require admin."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='regular_user', profile='DBA')
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

    @patch('executions.views.scheduled_views.is_admin_user', return_value=False)
    def test_post_recurring_returns_403_for_non_admin(self, mock_is_admin, mock_validate):
        """AC2: Non-admin user creating recurring execution gets 403."""
        mock_validate.return_value = None
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/api/v1/scheduled-executions/',
            {
                'action_id': self.action.id,
                'environment': 'dev',
                'recurring_pattern': {
                    'pattern_type': 'daily',
                    'pattern_config': {'hour': 10, 'minute': 0},
                },
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        error = response.json()['error']
        self.assertEqual(error['code'], 'ADMIN_REQUIRED')
        self.assertIn('administrateurs', error['message'])

    @patch('executions.views.scheduled_views.is_admin_user', return_value=True)
    def test_post_recurring_succeeds_for_admin(self, mock_is_admin, mock_validate):
        """AC3: Admin user creating recurring execution succeeds."""
        mock_validate.return_value = None
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/api/v1/scheduled-executions/',
            {
                'action_id': self.action.id,
                'environment': 'dev',
                'recurring_pattern': {
                    'pattern_type': 'daily',
                    'pattern_config': {'hour': 10, 'minute': 0},
                },
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.json())

    @patch('executions.views.scheduled_views.is_admin_user', return_value=False)
    def test_post_onetime_allowed_for_non_admin(self, mock_is_admin, mock_validate):
        """Non-admin can create one-time scheduled execution (no recurring_pattern)."""
        mock_validate.return_value = None
        self.client.force_authenticate(user=self.user)
        future = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.post(
            '/api/v1/scheduled-executions/',
            {
                'action_id': self.action.id,
                'environment': 'dev',
                'scheduled_at': future,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('data', response.json())

    @patch('executions.views.scheduled_views.is_admin_user', return_value=False)
    def test_post_recurring_empty_dict_not_blocked(self, mock_is_admin, mock_validate):
        """Empty recurring_pattern ({}) is falsy, so it's not blocked by admin check."""
        mock_validate.return_value = None
        self.client.force_authenticate(user=self.user)
        future = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.post(
            '/api/v1/scheduled-executions/',
            {
                'action_id': self.action.id,
                'environment': 'dev',
                'scheduled_at': future,
                'recurring_pattern': {},
            },
            format='json',
        )
        # Empty dict is falsy in Python, so admin check is skipped
        # Since recurring_pattern is empty (falsy), only scheduled_at is used
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
