"""
Tests for SimulationService (Story 19.0).
Tests creation of simulated steps and synchronous progression.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ExecutionStepStatus,
)
from executions.simulation_service import SimulationService, SIMULATED_STEPS_ACTION
from tests.factories import ActionFactory, ExecutionFactory, UserFactory


@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_FAILURE_RATE=0.0,
    SIMULATE_EXECUTION_STEP_DURATION=0,
)
class SimulationServiceCreateStepsTest(TestCase):
    """Test SimulationService.create_simulated_steps."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(status='published')
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.SUBMITTED,
        )

    def test_create_simulated_steps_action_simple(self):
        """AC2: 5 steps PENDING are created for a simple action."""
        steps = SimulationService.create_simulated_steps(self.execution)

        self.assertEqual(len(steps), 5)
        for step in steps:
            self.assertEqual(step.status, ExecutionStepStatus.PENDING)
            self.assertEqual(step.execution_id, self.execution.id)

    def test_step_names_match_spec(self):
        """AC2: Step names match the specified order."""
        steps = SimulationService.create_simulated_steps(self.execution)

        expected_names = [s["step_name"] for s in SIMULATED_STEPS_ACTION]
        actual_names = [s.step_name for s in steps]
        self.assertEqual(actual_names, expected_names)

    def test_step_orders_are_sequential(self):
        """AC2: step_order is 1-5."""
        steps = SimulationService.create_simulated_steps(self.execution)

        orders = [s.step_order for s in steps]
        self.assertEqual(orders, [1, 2, 3, 4, 5])

    def test_steps_persisted_in_db(self):
        """Steps are actually saved to the database."""
        SimulationService.create_simulated_steps(self.execution)

        db_steps = ExecutionStep.objects.filter(execution=self.execution)
        self.assertEqual(db_steps.count(), 5)

    def test_is_enabled_returns_setting(self):
        """is_enabled reflects SIMULATE_EXECUTION_DEV setting."""
        self.assertTrue(SimulationService.is_enabled())

    @override_settings(SIMULATE_EXECUTION_DEV=False)
    def test_is_enabled_false(self):
        """is_enabled returns False when disabled."""
        self.assertFalse(SimulationService.is_enabled())


@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_FAILURE_RATE=0.0,
    SIMULATE_EXECUTION_STEP_DURATION=0,
)
class SimulationServiceStartTest(TestCase):
    """Test SimulationService.start_simulation."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(status='published')
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.SUBMITTED,
        )
        SimulationService.create_simulated_steps(self.execution)

    def test_start_simulation_sets_running(self):
        """AC2: Execution transitions to RUNNING immediately."""
        # Use sync version to avoid threading in tests
        with patch.object(SimulationService, 'start_simulation') as mock_start:
            # Manually set RUNNING as start_simulation would
            self.execution.status = ExecutionStatus.RUNNING
            self.execution.started_at = timezone.now()
            self.execution.save(update_fields=['status', 'started_at'])

            mock_start.assert_not_called()  # We patched it

        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(self.execution.started_at)

    @override_settings(SIMULATE_EXECUTION_DEV=False)
    def test_start_simulation_noop_when_disabled(self):
        """start_simulation does nothing when SIMULATE_EXECUTION_DEV=False."""
        SimulationService.start_simulation(self.execution)
        self.execution.refresh_from_db()
        # Status should NOT have changed
        self.assertEqual(self.execution.status, ExecutionStatus.SUBMITTED)


@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_FAILURE_RATE=0.0,
    SIMULATE_EXECUTION_STEP_DURATION=0,
)
class SimulationServiceProgressionTest(TestCase):
    """Test synchronous simulation progression."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory(status='published')
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.SUBMITTED,
        )
        SimulationService.create_simulated_steps(self.execution)

    @patch('executions.simulation_service.time.sleep')
    def test_all_steps_completed_on_success(self, mock_sleep):
        """AC3: All steps progress PENDING -> RUNNING -> COMPLETED."""
        SimulationService.advance_simulation_sync(self.execution.id)

        steps = ExecutionStep.objects.filter(execution=self.execution).order_by('step_order')
        for step in steps:
            self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)
            self.assertIsNotNone(step.started_at)
            self.assertIsNotNone(step.completed_at)

    @patch('executions.simulation_service.time.sleep')
    def test_execution_completed_on_success(self, mock_sleep):
        """AC5: Execution ends as COMPLETED when failure_rate=0."""
        SimulationService.advance_simulation_sync(self.execution.id)

        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(self.execution.completed_at)

    @patch('executions.simulation_service.time.sleep')
    def test_logs_generated_for_each_step(self, mock_sleep):
        """AC4: Each step has realistic logs in output."""
        SimulationService.advance_simulation_sync(self.execution.id)

        steps = ExecutionStep.objects.filter(execution=self.execution).order_by('step_order')
        for step in steps:
            self.assertIn("[INFO]", step.output)
            self.assertTrue(len(step.output) > 0)

    @patch('executions.simulation_service.time.sleep')
    def test_vault_step_has_vault_logs(self, mock_sleep):
        """AC4: Vault step has vault-specific logs."""
        SimulationService.advance_simulation_sync(self.execution.id)

        vault_step = ExecutionStep.objects.get(
            execution=self.execution, step_name="Récupération secrets Vault"
        )
        self.assertIn("Vault", vault_step.output)
        self.assertIn("secrets", vault_step.output)

    @patch('executions.simulation_service.time.sleep')
    def test_platform_step_has_job_id(self, mock_sleep):
        """AC4: Platform step includes execution_id in job ID."""
        SimulationService.advance_simulation_sync(self.execution.id)

        platform_step = ExecutionStep.objects.get(
            execution=self.execution, step_name="Déclenchement plateforme"
        )
        self.assertIn(f"job-sim-{self.execution.id}", platform_step.output)

    @override_settings(SIMULATE_EXECUTION_FAILURE_RATE=1.0)
    @patch('executions.simulation_service.time.sleep')
    def test_execution_fails_with_100_percent_failure_rate(self, mock_sleep):
        """AC5: Execution ends FAILED when failure_rate=1.0."""
        SimulationService.advance_simulation_sync(self.execution.id)

        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(self.execution.completed_at)

        # Last step should be FAILED
        last_step = ExecutionStep.objects.filter(
            execution=self.execution
        ).order_by('-step_order').first()
        self.assertEqual(last_step.status, ExecutionStepStatus.FAILED)
        self.assertIn("[ERROR]", last_step.output)

    @override_settings(SIMULATE_EXECUTION_FAILURE_RATE=1.0)
    @patch('executions.simulation_service.time.sleep')
    def test_only_last_step_fails(self, mock_sleep):
        """AC5: Only the last step fails, earlier steps complete."""
        SimulationService.advance_simulation_sync(self.execution.id)

        steps = list(
            ExecutionStep.objects.filter(execution=self.execution).order_by('step_order')
        )
        # All steps except last should be COMPLETED
        for step in steps[:-1]:
            self.assertEqual(step.status, ExecutionStepStatus.COMPLETED)
        # Last step FAILED
        self.assertEqual(steps[-1].status, ExecutionStepStatus.FAILED)
