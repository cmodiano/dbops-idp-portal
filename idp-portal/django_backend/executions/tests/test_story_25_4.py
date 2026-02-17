"""
Story 25.4: Overrides par environnement (change_type_config enrichi).

Tests for:
- allowed=false → rejection on POST /executions (400)
- requires_maintenance_window, requires_approval stored in _env_config
- Backward compatibility: no allowed → treated as true
"""
import pytest
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus
from executions.models import Execution
from idp_auth.models import User


@pytest.mark.django_db
class TestStory254AllowedFlag(TestCase):
    """Task 2.2: allowed=false → refuse submission with BadRequestError."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='story254_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name='Story 25.4 Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
            change_type_config={
                'dev': {'allowed': False},
                'staging': {'allowed': True},
            },
        )

    def test_post_execution_env_allowed_false_returns_400(self):
        """POST /executions with env where allowed=false → 400 EXECUTION_NOT_ALLOWED_FOR_ENVIRONMENT."""
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'EXECUTION_NOT_ALLOWED_FOR_ENVIRONMENT')
        self.assertIn('dev', (response.data['error']['message'] or '').lower())
        self.assertEqual(Execution.objects.filter(action_id=self.action.id).count(), 0)

    def test_post_execution_env_allowed_true_succeeds(self):
        """POST /executions with env where allowed=true → 201."""
        allowed_targets = [
            {'name': 'srv-staging-01', 'environment': 'staging', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-staging-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        self.assertIn('execution_id', response.data['data'])


@pytest.mark.django_db
class TestStory254EnvConfigFlags(TestCase):
    """Task 2.3: requires_maintenance_window, requires_approval stored in parameters['_env_config']."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='story254_env_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        self.action = Action.objects.create(
            name='Story 25.4 Env Config Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
            change_type_config={
                'dev': {
                    'allowed': True,
                    'requires_maintenance_window': True,
                    'requires_approval': True,
                },
            },
        )

    def test_post_execution_env_config_contains_new_flags(self):
        """POST execution with requires_maintenance_window/requires_approval → _env_config contains them."""
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']
        execution = Execution.objects.get(id=execution_id)
        params = execution.get_parameters()
        env_config = params.get('_env_config', {})
        self.assertTrue(env_config.get('requires_maintenance_window'))
        self.assertTrue(env_config.get('requires_approval'))
        # Ensure case-insensitive env lookup works (config key 'dev' used by target env 'dev')
        self.assertEqual(execution.environment, 'dev')


@pytest.mark.django_db
class TestStory254BackwardCompatibility(TestCase):
    """Task 1.3: Absence of allowed → treated as true (backward compat)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='story254_compat_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        # Legacy config: no 'allowed' key
        self.action = Action.objects.create(
            name='Story 25.4 Legacy Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
            change_type_config={
                'dev': {'required': False},
            },
        )

    def test_post_execution_no_allowed_treated_as_true(self):
        """Config without allowed → execution succeeds (allowed defaults to true)."""
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)


@pytest.mark.django_db
class TestStory254DefensiveInvalidChangeTypeConfig(TestCase):
    """Regression: invalid persisted change_type_config should not crash execution creation."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='story254_invalid_ctc_user', profile='DBA')
        self.client.force_authenticate(user=self.user)
        # Simulate corrupted data in DB: change_type_config is not a dict
        self.action = Action.objects.create(
            name='Story 25.4 Invalid CTC Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
            change_type_config=['not', 'a', 'dict'],  # type: ignore[arg-type]
        )

    def test_post_execution_with_invalid_change_type_config_still_succeeds(self):
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventory:
            mock_inst = MagicMock()
            mock_inst.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventory.return_value = mock_inst

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)
