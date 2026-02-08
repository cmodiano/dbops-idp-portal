"""
Tests for execution API in simulation mode (Story 19.0).
Validates that POST /executions creates simulated steps and GET /steps returns them.

Note: We mock start_simulation to run synchronously because SQLite in-memory
doesn't support concurrent access from threads (database table locked).
"""

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Action
from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from executions.simulation_service import SimulationService
from idp_auth.models import User


def _sync_start_simulation(execution):
    """Replacement for start_simulation that runs synchronously (no thread)."""
    from django.conf import settings
    if not getattr(settings, 'SIMULATE_EXECUTION_DEV', False):
        return
    from django.utils import timezone
    execution.status = ExecutionStatus.RUNNING
    execution.started_at = timezone.now()
    execution.save(update_fields=['status', 'started_at'])
    SimulationService._run_simulation(execution.id)


@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_FAILURE_RATE=0.0,
    SIMULATE_EXECUTION_STEP_DURATION=0,
)
@pytest.mark.django_db
class ExecutionAPISimulationTest(TestCase):
    """AC7, AC11: API integration tests for simulation mode."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='sim_user', profile='DBA')
        self.client.force_authenticate(user=self.user)

        self.action = Action.objects.create(
            name='Sim Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False,
        )

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_create_execution_creates_simulated_steps(self, mock_start, mock_sleep):
        """AC2, AC7: POST /executions in simulation mode creates 5 steps."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        steps = ExecutionStep.objects.filter(execution_id=execution_id).order_by('step_order')
        self.assertEqual(steps.count(), 5)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_create_execution_sets_running_or_completed(self, mock_start, mock_sleep):
        """AC2: Execution transitions to RUNNING then COMPLETED in simulation mode."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        execution = Execution.objects.get(id=execution_id)
        # Sync simulation should have completed
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_get_execution_steps_returns_simulated_steps(self, mock_start, mock_sleep):
        """AC7: GET /executions/{id}/steps returns simulated steps with output."""
        create_response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')
        execution_id = create_response.data['data']['execution_id']

        steps_response = self.client.get(f'/api/v1/executions/{execution_id}/steps/')
        self.assertEqual(steps_response.status_code, 200)

        steps_data = steps_response.data['data']
        self.assertEqual(len(steps_data), 5)

        first_step = steps_data[0]
        self.assertIn('step_order', first_step)
        self.assertIn('step_name', first_step)
        self.assertIn('status', first_step)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_get_execution_detail_after_simulation(self, mock_start, mock_sleep):
        """AC7: GET /executions/{id} returns correct status after simulation."""
        create_response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')
        execution_id = create_response.data['data']['execution_id']

        detail_response = self.client.get(f'/api/v1/executions/{execution_id}/')
        self.assertEqual(detail_response.status_code, 200)

    @override_settings(SIMULATE_EXECUTION_DEV=False)
    def test_simulation_disabled_no_steps_created(self):
        """When simulation is disabled, no steps are auto-created."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        steps = ExecutionStep.objects.filter(execution_id=execution_id)
        self.assertEqual(steps.count(), 0)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_steps_have_correct_names(self, mock_start, mock_sleep):
        """AC2: Steps match the specification names."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')
        execution_id = response.data['data']['execution_id']

        steps = list(
            ExecutionStep.objects.filter(execution_id=execution_id).order_by('step_order')
        )
        expected_names = [
            "Préparation",
            "Récupération secrets Vault",
            "Déclenchement plateforme",
            "Exécution distante",
            "Vérification résultat",
        ]
        actual_names = [s.step_name for s in steps]
        self.assertEqual(actual_names, expected_names)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_simulation_completes_all_steps(self, mock_start, mock_sleep):
        """AC3, AC5: After simulation completes, all steps are COMPLETED."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')
        execution_id = response.data['data']['execution_id']

        steps = ExecutionStep.objects.filter(execution_id=execution_id)
        for step in steps:
            self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)
            self.assertIsNotNone(step.started_at)
            self.assertIsNotNone(step.completed_at)

    @patch('executions.simulation_service.time.sleep')
    @patch.object(SimulationService, 'start_simulation', side_effect=_sync_start_simulation)
    def test_steps_have_logs_in_output(self, mock_start, mock_sleep):
        """AC4: Steps have log content in output field."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'environment': 'dev',
        }, format='json')
        execution_id = response.data['data']['execution_id']

        steps = ExecutionStep.objects.filter(execution_id=execution_id)
        for step in steps:
            self.assertIsNotNone(step.output)
            self.assertIn("[INFO]", step.output)
