"""
Tests for Story 26.9: Standardiser le format de réponse API.

Validates:
- AC1: GET /scheduled-executions returns flat format (no data.data nesting)
- AC2: PATCH /scheduled-executions/{id} uses ScheduledExecutionSerializer
- AC4: All assertions match the standardized response format
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from catalog.models import Action, ActionStatus
from executions.models import ScheduledExecution, ScheduledExecutionStatus
from tests.factories import UserFactory


@patch('executions.views.scheduled_views._validate_environment_against_inventory')
@patch('executions.views.scheduled_views._get_allowed_action_ids_for_user', return_value=None)
class ScheduledExecutionsListFormatTests(TestCase):
    """AC1/AC4: GET /scheduled-executions returns standard flat format."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='testuser', profile='DBA')
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

    def test_list_returns_flat_format_no_data_data_nesting(self, mock_allowed, mock_validate):
        """AC1: Response has data (list) and pagination at top level, not nested."""
        future = timezone.now() + timedelta(days=1)
        ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.get('/api/v1/scheduled-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # AC1: data is a list (not a dict containing another data key)
        self.assertIn('data', response.data)
        self.assertIn('pagination', response.data)
        self.assertIsInstance(response.data['data'], list)
        self.assertGreaterEqual(len(response.data['data']), 1)

        # AC1: No nested data.data — first item is a serialized object
        first_item = response.data['data'][0]
        self.assertIn('scheduled_execution_id', first_item)
        self.assertIn('action_name', first_item)

    def test_list_pagination_at_top_level(self, mock_allowed, mock_validate):
        """AC1: Pagination is at response top level, not nested inside data."""
        response = self.client.get('/api/v1/scheduled-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        pagination = response.data['pagination']
        self.assertIn('page', pagination)
        self.assertIn('page_size', pagination)
        self.assertIn('total', pagination)
        self.assertIn('total_pages', pagination)

    def test_list_available_actions_at_top_level(self, mock_allowed, mock_validate):
        """AC1: available_actions is at response top level."""
        response = self.client.get('/api/v1/scheduled-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('available_actions', response.data)

    def test_list_empty_returns_correct_format(self, mock_allowed, mock_validate):
        """AC1: Empty list still returns correct flat format."""
        response = self.client.get('/api/v1/scheduled-executions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIn('pagination', response.data)
        self.assertEqual(response.data['data'], [])
        self.assertEqual(response.data['pagination']['total'], 0)

    def test_list_consistent_with_catalog_format(self, mock_allowed, mock_validate):
        """AC1: Format is consistent with GET /actions pattern: {data: [...], pagination: {...}}."""
        future = timezone.now() + timedelta(days=1)
        ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )
        response = self.client.get('/api/v1/scheduled-executions/')
        data = response.data

        # Exactly 3 top-level keys: data, pagination, available_actions
        self.assertEqual(set(data.keys()), {'data', 'pagination', 'available_actions'})

        # data is a list of objects
        self.assertIsInstance(data['data'], list)

        # pagination has standard fields
        self.assertEqual(set(data['pagination'].keys()), {'page', 'page_size', 'total', 'total_pages'})


@patch('executions.views.scheduled_views._validate_environment_against_inventory')
@patch('executions.views.scheduled_views._get_allowed_action_ids_for_user', return_value=None)
class ScheduledExecutionPatchFormatTests(TestCase):
    """AC2/AC4: PATCH /scheduled-executions/{id} uses ScheduledExecutionSerializer."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='patchuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action Patch',
            description='Test',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def _create_pending_se(self):
        future = timezone.now() + timedelta(days=1)
        return ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=future,
            status=ScheduledExecutionStatus.PENDING,
        )

    @patch('executions.views.scheduled_views.SchedulingService')
    def test_cancel_uses_serializer_fields(self, mock_svc_cls, mock_allowed, mock_validate):
        """AC2: Cancel response uses ScheduledExecutionSerializer with all fields."""
        se = self._create_pending_se()

        def mock_cancel(sid, user_id):
            se.status = ScheduledExecutionStatus.CANCELLED
            se.save(update_fields=['status'])
            return se

        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.side_effect = mock_cancel
        mock_svc_cls.return_value = mock_svc

        response = self.client.patch(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'status': 'cancelled'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']

        # AC2: Serializer includes all standard fields
        self.assertIn('scheduled_execution_id', data)
        self.assertIn('action_id', data)
        self.assertIn('action_name', data)
        self.assertIn('environment', data)
        self.assertIn('status', data)
        self.assertIn('scheduled_at', data)
        self.assertIn('created_at', data)
        # AC2: Serializer also includes fields that were missing in manual construction
        self.assertIn('parameters', data)
        self.assertIn('correlation_id', data)
        self.assertEqual(data['status'], ScheduledExecutionStatus.CANCELLED)

    @patch('executions.views.scheduled_views.SchedulingService')
    def test_cancel_response_wraps_in_data(self, mock_svc_cls, mock_allowed, mock_validate):
        """AC2: Cancel response wraps serializer in {data: ...} format."""
        se = self._create_pending_se()

        def mock_cancel(sid, user_id):
            se.status = ScheduledExecutionStatus.CANCELLED
            se.save(update_fields=['status'])
            return se

        mock_svc = MagicMock()
        mock_svc.cancel_scheduled_execution.side_effect = mock_cancel
        mock_svc_cls.return_value = mock_svc

        response = self.client.patch(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'status': 'cancelled'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Top level has 'data' key
        self.assertIn('data', response.data)
        # data is a dict (single object), not a list
        self.assertIsInstance(response.data['data'], dict)

    def test_executed_uses_serializer_fields(self, mock_allowed, mock_validate):
        """AC2: Executed response uses ScheduledExecutionSerializer with all fields."""
        se = self._create_pending_se()

        response = self.client.patch(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'status': 'executed', 'execution_id': 42},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']

        # AC2: Serializer includes all standard fields
        self.assertIn('scheduled_execution_id', data)
        self.assertIn('action_id', data)
        self.assertIn('action_name', data)
        self.assertIn('environment', data)
        self.assertIn('status', data)
        self.assertIn('scheduled_at', data)
        self.assertIn('created_at', data)
        self.assertIn('parameters', data)
        self.assertIn('correlation_id', data)

    def test_executed_status_correct(self, mock_allowed, mock_validate):
        """AC2: After marking executed (no recurring), status is 'executed'."""
        se = self._create_pending_se()

        response = self.client.patch(
            f'/api/v1/scheduled-executions/{se.id}/',
            {'status': 'executed', 'execution_id': 42},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['status'], ScheduledExecutionStatus.EXECUTED)
