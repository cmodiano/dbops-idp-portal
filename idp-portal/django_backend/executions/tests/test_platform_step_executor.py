"""
Tests unitaires pour PlatformStepExecutor (Story 88.5 — AC #5).

Couvre les 3 cas requis :
- execute_platform_step avec action valide → ExecutionStatus.COMPLETED
- execute_platform_step sans referenced_action_id → ExecutionStatus.FAILED, parent_step FAILED
- exception dans _run_child_execution → ExecutionStatus.FAILED + logger.error appelé
"""
import threading
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings

from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus, ExecutionStepType,
)
from executions.platform_step_executor import PlatformStepExecutor
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory

TEST_ENV = 'developpement'


def _make_executor(execution, execution_service=None):
    """Helper : construit un PlatformStepExecutor pour les tests."""
    if execution_service is None:
        execution_service = MagicMock()
    step_outputs = {}
    return PlatformStepExecutor(
        execution=execution,
        execution_service=execution_service,
        correlation_id=None,
        child_executions=[],
        step_outputs=step_outputs,
        step_outputs_lock=threading.Lock(),
        step_lock=threading.Lock(),
        get_step_parameters=lambda step: {},
    )


@pytest.mark.django_db
@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_STEP_DURATION=0,
    SIMULATE_EXECUTION_FAILURE_RATE=0,
)
class TestExecutePlatformStepCompleted(TestCase):
    """AC #5.4.2 : execute_platform_step avec action valide → COMPLETED."""

    def setUp(self):
        self.user = UserFactory(username='pse_completed_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Step A',
                'step_id': 'sa', 'referenced_action_id': self.action_a.id,
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execute_platform_step_valid_action_returns_completed(self, mock_audit):
        """Action valide + simulation → ExecutionStatus.COMPLETED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        mock_service = MagicMock()
        child_exec = Execution.objects.create(
            action=self.action_a, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        mock_service.create_execution.return_value = child_exec

        executor = _make_executor(execution, mock_service)
        step = {
            'order': 1, 'name': 'Step A',
            'step_id': 'sa', 'referenced_action_id': self.action_a.id,
        }

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=True):
            with patch('executions.container_workflow_runtime.SimulationService.create_simulated_steps'):
                with patch(
                    'executions.container_workflow_runtime.SimulationService._run_simulation',
                    side_effect=lambda exec_id, **kw: Execution.objects.filter(
                        id=exec_id,
                    ).update(status=ExecutionStatus.COMPLETED),
                ):
                    result = executor.execute_platform_step(
                        step, {}, 'Step A', 'sa', step_order_counter=1,
                    )

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        # step_outputs alimenté
        self.assertIn('sa', executor._step_outputs)


@pytest.mark.django_db
class TestExecutePlatformStepMissingReferenceId(TestCase):
    """AC #5.4.3 : execute_platform_step sans referenced_action_id → FAILED."""

    def setUp(self):
        self.user = UserFactory(username='pse_failed_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Step Sans Ref',
                'step_id': 'no_ref',
                # referenced_action_id absent
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execute_platform_step_missing_id_returns_failed(self, mock_audit):
        """Pas de referenced_action_id → parent_step FAILED, retour FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        executor = _make_executor(execution)
        step = {'order': 1, 'name': 'Step Sans Ref', 'step_id': 'no_ref'}

        result = executor.execute_platform_step(
            step, {}, 'Step Sans Ref', 'no_ref', step_order_counter=1,
        )

        self.assertEqual(result, ExecutionStatus.FAILED)

        # Vérifier que le parent_step est marqué FAILED en DB
        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        self.assertIsNotNone(parent_step)
        self.assertEqual(parent_step.status, ExecutionStepStatus.FAILED)
        self.assertIn("missing referenced_action_id", parent_step.error_message)


@pytest.mark.django_db
@override_settings(
    SIMULATE_EXECUTION_DEV=False,
)
class TestExecutePlatformStepChildRunException(TestCase):
    """AC #5.4.4 : exception dans _run_child_execution → FAILED + logger.error."""

    def setUp(self):
        self.user = UserFactory(username='pse_exc_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Step Exc',
                'step_id': 'exc_step', 'referenced_action_id': self.action_a.id,
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_exception_in_run_child_returns_failed_and_logs_error(self, mock_audit):
        """Exception dans _run_child_execution → FAILED + logger.error appelé."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        mock_service = MagicMock()
        child_exec = Execution.objects.create(
            action=self.action_a, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        mock_service.create_execution.return_value = child_exec

        executor = _make_executor(execution, mock_service)
        step = {
            'order': 1, 'name': 'Step Exc',
            'step_id': 'exc_step', 'referenced_action_id': self.action_a.id,
        }

        with patch('executions.container_workflow_runtime.logger') as mock_logger:
            with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=False):
                # Forcer une exception dans _run_child_execution via _create_child_execution mock
                executor._run_child_execution = MagicMock(
                    side_effect=RuntimeError("test forced error"),
                )

                result = executor.execute_platform_step(
                    step, {}, 'Step Exc', 'exc_step', step_order_counter=1,
                )

        self.assertEqual(result, ExecutionStatus.FAILED)
        mock_logger.error.assert_called()
        # Vérifier que l'event "container_workflow_platform_step_exception" a été loggé
        error_events = [
            call[0][0] for call in mock_logger.error.call_args_list
        ]
        self.assertIn("container_workflow_platform_step_exception", error_events)


@pytest.mark.django_db
@override_settings(
    SIMULATE_EXECUTION_DEV=True,
    SIMULATE_EXECUTION_STEP_DURATION=0,
    SIMULATE_EXECUTION_FAILURE_RATE=0,
)
class TestExecuteWorkerPlatformStep(TestCase):
    """Tests pour execute_worker_platform_step (AI-Review — coverage gap L-03)."""

    def setUp(self):
        self.user = UserFactory(username='pse_worker_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Worker Step',
                'step_id': 'ws', 'referenced_action_id': self.action_a.id,
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execute_worker_platform_step_valid_action_returns_completed(self, mock_audit):
        """execute_worker_platform_step avec action valide + simulation → COMPLETED."""
        from executions.models import ExecutionStepType
        execution = Execution.objects.create(
            action=self.wf, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        child_exec = Execution.objects.create(
            action=self.action_a, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        exec_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Worker Step',
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.RUNNING,
        )
        mock_service = MagicMock()
        mock_service.create_execution.return_value = child_exec

        executor = _make_executor(execution, mock_service)
        step_config = {
            'order': 1, 'step_id': 'ws',
            'referenced_action_id': self.action_a.id,
        }

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=True):
            with patch('executions.container_workflow_runtime.SimulationService.create_simulated_steps'):
                with patch(
                    'executions.container_workflow_runtime.SimulationService._run_simulation',
                    side_effect=lambda exec_id, **kw: Execution.objects.filter(
                        id=exec_id,
                    ).update(status=ExecutionStatus.COMPLETED),
                ):
                    result = executor.execute_worker_platform_step(exec_step, step_config, {})

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        # Vérifier thread-safety: step_outputs alimenté sans exception
        self.assertIn('ws', executor._step_outputs)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execute_worker_platform_step_missing_ref_returns_failed(self, mock_audit):
        """execute_worker_platform_step sans referenced_action_id → FAILED."""
        from executions.models import ExecutionStepType
        execution = Execution.objects.create(
            action=self.wf, user=self.user,
            environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        exec_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Worker Step No Ref',
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.RUNNING,
        )
        executor = _make_executor(execution)
        step_config = {'order': 1, 'step_id': 'no_ref'}  # pas de referenced_action_id

        result = executor.execute_worker_platform_step(exec_step, step_config, {})

        self.assertEqual(result, ExecutionStatus.FAILED)
        exec_step.refresh_from_db()
        self.assertEqual(exec_step.status, ExecutionStepStatus.FAILED)
