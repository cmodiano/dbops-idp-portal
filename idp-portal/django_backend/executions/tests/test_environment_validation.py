"""
Tests for execution environment validation against inventory.
Story 13.7 - Tests for environment validation in executions.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionStatus
from inventory.services import InventoryServiceError
from tests.factories import UserFactory


class ExecutionEnvironmentValidationTests(TestCase):
    """Tests for environment validation in execution creation."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory(
            username='testuser',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

        # Create a published action
        self.action = Action.objects.create(
            name='Test Action',
            description='Test',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            created_by=self.user
        )

    @patch('executions.views._validate_environment_against_inventory')
    @patch('executions.views.ExecutionService')
    def test_create_execution_with_valid_environment(self, mock_exec_service, mock_validate):
        """Test creating execution with valid environment."""
        mock_validate.return_value = None  # Validation passes
        mock_exec_service.return_value.create_execution.return_value = MagicMock(id=1)

        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id,
            'environment': 'dev',
            'parameters': {}
        })

        # Should call validation
        mock_validate.assert_called_once_with('dev')

    @patch('executions.views._validate_environment_against_inventory')
    def test_create_execution_with_invalid_environment(self, mock_validate):
        """Test creating execution with invalid environment returns 400."""
        from core.exceptions import BadRequestError
        
        mock_validate.side_effect = BadRequestError(
            code="INVALID_ENVIRONMENT",
            message="Environnement invalide: invalid_env",
            details={"environment": "invalid_env", "valid_environments": ["dev", "staging", "prod"]}
        )

        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id,
            'environment': 'invalid_env',
            'parameters': {}
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('executions.views._validate_environment_against_inventory')
    @patch('executions.views.SchedulingService')
    def test_create_scheduled_execution_with_valid_environment(self, mock_sched_service, mock_validate):
        """Test creating scheduled execution with valid environment."""
        mock_validate.return_value = None  # Validation passes
        mock_sched_service.return_value.create_scheduled_execution.return_value = MagicMock(id=1)

        response = self.client.post('/api/v1/scheduled-executions', {
            'action_id': self.action.id,
            'environment': 'dev',
            'parameters': {},
            'scheduled_at': '2026-02-10T10:00:00Z'
        })

        # Should call validation
        mock_validate.assert_called_once_with('dev')
