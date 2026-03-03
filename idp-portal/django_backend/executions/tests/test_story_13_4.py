"""
Story 13.4: Refactoring — target_names obligatoire, validation backend

Tests for:
- AC1: Une action existe une seule fois (pas de duplication par env)
- AC2: Logique d'autorisation basée sur target + permissions profil
- AC3: Environnement enregistré provient du target
- AC4: APIs et cache RBAC adaptés pour action_id + target(s)
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution


@pytest.mark.django_db
class ExecutionTargetRequiredTests(TestCase):
    """
    Story 13.4: Tests for mandatory target_names and environment derivation.
    """

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(
            username='target_test_user',
            profile='DBA'
        )
        self.client.force_authenticate(user=self.user)

        # Action requiring targets
        self.action_with_target = Action.objects.create(
            name='Action With Target Required',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )
        # Set impact_rules
        self.action_with_target.impact_rules = ({
            'DEV': {'level': 'low'},
            'PROD': {'level': 'high'}
        })
        self.action_with_target.save()

        # Action not requiring targets
        self.action_without_target = Action.objects.create(
            name='Action Without Target Required',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False
        )

    def test_execution_requires_target_names(self):
        """
        Subtask 6.1: POST /executions without target_names → 400 for requires_target=True.
        """
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action_with_target.id,
            'environment': 'dev'  # Only environment, no targets
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('target_names', str(response.data).lower())

    def test_execution_environment_from_target(self):
        """
        Subtask 6.2: Environment is derived from target.
        """
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_with_target.id,
                'target_names': ['srv-dev-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        self.assertEqual(execution.environment, 'dev')

    def test_execution_mixed_environments_rejected(self):
        """
        Subtask 6.3: Targets from different environments → 400.
        """
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_with_target.id,
                'target_names': ['srv-dev-01', 'srv-prod-01'],
            }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('environnement', str(response.data).lower())

    def test_execution_without_target_accepts_environment(self):
        """
        Actions with requires_target=False can use environment directly.
        """
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action_without_target.id,
            'environment': 'dev'
        }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        self.assertEqual(execution.environment, 'dev')

    def test_env_config_per_environment(self):
        """
        Subtask 6.5: Env config retrieved from target.environment.
        change_type_config removed (Story 57.18): change_required is always False.
        """
        allowed_targets = [
            {'name': 'srv-prod-01', 'environment': 'prod', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_with_target.id,
                'target_names': ['srv-prod-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        params = execution.get_parameters()
        self.assertIn('_env_config', params)
        self.assertFalse(params['_env_config']['change_required'])
        self.assertIsNone(params['_env_config']['change_model_code'])

    def test_impact_rules_per_environment(self):
        """
        Subtask 6.6: Impact level récupéré depuis target.environment.
        """
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action_with_target.id,
                'target_names': ['srv-dev-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        params = execution.get_parameters()
        self.assertIn('_env_config', params)
        self.assertEqual(params['_env_config']['impact_level'], 'low')

    def test_deprecated_environment_with_targets_warning(self):
        """
        Story 13.4, Subtask 6.7: Passing environment with target_names logs warning but still works.
        Environment is ignored and derived from targets. Asserts the deprecated warning is logged.
        """
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            with patch('executions.validators.payload_validator.logger.warning') as mock_warning:
                response = self.client.post('/api/v1/executions/', {
                    'action_id': self.action_with_target.id,
                    'environment': 'prod',  # Will be ignored
                    'target_names': ['srv-dev-01'],
                }, format='json')

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        self.assertEqual(execution.environment, 'dev')
        # Subtask 6.7: assert deprecated_environment_with_targets warning was logged
        mock_warning.assert_called_once()
        call_args = mock_warning.call_args
        self.assertEqual(call_args[0][0], 'deprecated_environment_with_targets')
