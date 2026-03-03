"""
Tests du dispatcher _execute_step() et des méthodes associées — Story 57.3

AC#1 : step SKIPPED si condition non remplie, _execute_step() retourne COMPLETED
AC#2 : ServiceCallHandler.execute() invoqué pour step_type='service_call'
AC#3 : ValueError levée pour step_type inconnu
AC#4 : ordre d'opération dans _execute_step()
AC#7 : step SKIPPED sans step_id → pas d'entrée dans _step_outputs
"""

import pytest
from unittest.mock import patch

from django.test import override_settings

from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus,
    ExecutionStepType,
)
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


TEST_ENVIRONMENT_PROD = 'production'
TEST_ENVIRONMENT_LAB = 'lab'


@pytest.mark.django_db
class TestStepDispatcher:
    """Tests du dispatcher dans _execute_step() — AC: #1, #2, #3, #4, #7."""

    def setup_method(self):
        """Données de test communes."""
        self.user = UserFactory(username="dispatcher_test_user")
        self.ref_action = ActionFactory(
            name="Referenced Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )

    def _create_workflow_execution(self, steps, environment=TEST_ENVIRONMENT_LAB):
        workflow_action = ActionFactory(
            name="Dispatcher Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=steps,
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment=environment,
            status=ExecutionStatus.SUBMITTED,
        )
        return execution

    def _create_runtime(self, steps, environment=TEST_ENVIRONMENT_LAB):
        execution = self._create_workflow_execution(steps, environment)
        return ContainerWorkflowRuntime(execution)

    # --- AC#1 : step SKIPPED si condition non remplie ---

    @patch('executions.container_workflow_runtime.AuditService')
    def test_skipped_step_when_condition_not_met(self, mock_audit):
        """AC#1 : step SKIPPED si condition non remplie, retourne COMPLETED."""
        step = {
            'order': 1,
            'name': 'Create Change',
            'step_id': 'create-change',
            'step_type': 'service_call',
            'condition': {'environment_in': ['production']},
            'referenced_action_id': None,
        }
        execution = self._create_workflow_execution([step], environment=TEST_ENVIRONMENT_LAB)
        runtime = ContainerWorkflowRuntime(execution)

        result = runtime._execute_step(step)

        assert result == ExecutionStatus.COMPLETED
        skipped_step = ExecutionStep.objects.get(execution=execution, step_name='Create Change')
        assert skipped_step.status == ExecutionStepStatus.SKIPPED
        assert runtime._step_outputs.get('create-change') == {}

    @patch('executions.container_workflow_runtime.AuditService')
    def test_skipped_step_creates_correct_step_type(self, mock_audit):
        """Step SKIPPED avec step_type service_call → ExecutionStepType.SERVICE_CALL."""
        step = {
            'order': 1,
            'name': 'SNOW Step',
            'step_id': 'snow-step',
            'step_type': 'service_call',
            'condition': {'environment_in': ['production']},
        }
        execution = self._create_workflow_execution([step], environment=TEST_ENVIRONMENT_LAB)
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        skipped_step = ExecutionStep.objects.get(execution=execution, step_name='SNOW Step')
        assert skipped_step.step_type == ExecutionStepType.SERVICE_CALL
        assert skipped_step.started_at is not None
        assert skipped_step.completed_at is not None

    # --- AC#7 : SKIPPED sans step_id → pas d'entrée dans _step_outputs ---

    @patch('executions.container_workflow_runtime.AuditService')
    def test_skipped_step_without_step_id(self, mock_audit):
        """AC#7 : step SKIPPED sans step_id → pas d'entrée dans _step_outputs."""
        step = {
            'order': 1,
            'name': 'No ID Step',
            'step_type': 'service_call',
            'condition': {'environment_in': ['production']},
        }
        execution = self._create_workflow_execution([step], environment=TEST_ENVIRONMENT_LAB)
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        # _step_outputs ne doit pas avoir de clé None
        assert None not in runtime._step_outputs
        assert runtime._step_outputs == {}

    # --- Condition remplie : pas de SKIP ---

    @override_settings(
        SIMULATE_EXECUTION_DEV=True,
        SIMULATE_EXECUTION_STEP_DURATION=0,
        SIMULATE_EXECUTION_FAILURE_RATE=0,
    )
    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_skip_when_condition_met(self, mock_audit):
        """AC#6 : condition remplie → step exécuté normalement (pas SKIPPED)."""
        step = {
            'order': 1,
            'name': 'Prod Step',
            'step_id': 'prod-step',
            'step_type': 'platform',
            'condition': {'environment_in': ['production']},
            'referenced_action_id': self.ref_action.id,
        }
        execution = self._create_workflow_execution([step], environment=TEST_ENVIRONMENT_PROD)
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime._execute_step(step)

        # Ne doit pas être SKIPPED
        steps = ExecutionStep.objects.filter(execution=execution)
        assert not steps.filter(status=ExecutionStepStatus.SKIPPED).exists()
        # Doit être COMPLETED (child execution succeeded)
        assert result == ExecutionStatus.COMPLETED

    # --- AC#3 : ValueError pour step_type inconnu ---

    @patch('executions.container_workflow_runtime.AuditService')
    def test_unknown_step_type_raises_valueerror(self, mock_audit):
        """AC#3 : ValueError levée pour step_type inconnu."""
        step = {
            'order': 1,
            'name': 'Unknown Step',
            'step_type': 'alien_type',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)

        with pytest.raises(ValueError, match="alien_type"):
            runtime._execute_step(step)

    # --- AC#2 : ServiceCallHandler.execute() invoqué ---

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_dispatch_to_service_call_handler(self, mock_execute, mock_audit):
        """AC#2 : ServiceCallHandler.execute() invoqué pour step_type='service_call'."""
        mock_execute.return_value = {}
        step = {
            'order': 1,
            'name': 'Call Service',
            'step_id': 'call-svc',
            'step_type': 'service_call',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        mock_execute.assert_called_once()

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.http_request_handler.HttpRequestHandler.execute')
    def test_dispatch_to_http_request_handler(self, mock_execute, mock_audit):
        """http_request → HttpRequestHandler.execute() invoqué."""
        mock_execute.return_value = {}
        step = {
            'order': 1,
            'name': 'HTTP Request',
            'step_id': 'http-req',
            'step_type': 'http_request',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        mock_execute.assert_called_once()

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.evaluation_handler.EvaluationHandler.execute')
    def test_dispatch_to_evaluation_handler(self, mock_execute, mock_audit):
        """evaluation → EvaluationHandler.execute() invoqué."""
        mock_execute.return_value = {}
        step = {
            'order': 1,
            'name': 'Eval',
            'step_id': 'eval-step',
            'step_type': 'evaluation',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        mock_execute.assert_called_once()

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.gate_handler.GateHandler.execute')
    def test_dispatch_to_gate_handler(self, mock_execute, mock_audit):
        """gate → GateHandler.execute() invoqué."""
        mock_execute.return_value = {}
        step = {
            'order': 1,
            'name': 'Gate',
            'step_id': 'gate-step',
            'step_type': 'gate',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        runtime._execute_step(step)

        mock_execute.assert_called_once()

    # --- AC#4 : ordre d'opération ---

    @patch('executions.container_workflow_runtime.AuditService')
    def test_operation_order_skip_before_dispatch(self, mock_audit):
        """AC#4 : condition évaluée AVANT dispatch → SKIP sans appel handler."""
        step = {
            'order': 1,
            'name': 'Should Skip',
            'step_id': 'skip-me',
            'step_type': 'service_call',
            'condition': {'environment_in': ['production']},
        }
        execution = self._create_workflow_execution([step], environment=TEST_ENVIRONMENT_LAB)
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute') as mock_exec:
            result = runtime._execute_step(step)

        # Handler ne doit PAS être appelé
        mock_exec.assert_not_called()
        # Résultat COMPLETED (SKIP = continuer)
        assert result == ExecutionStatus.COMPLETED

    # --- Backward compatibility : step sans step_type → platform ---

    @override_settings(
        SIMULATE_EXECUTION_DEV=True,
        SIMULATE_EXECUTION_STEP_DURATION=0,
        SIMULATE_EXECUTION_FAILURE_RATE=0,
    )
    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_without_step_type_defaults_to_platform(self, mock_audit):
        """Backward compat : step sans step_type → dispatché comme 'platform'."""
        step = {
            'order': 1,
            'name': 'Legacy Step',
            'step_id': 'legacy',
            'referenced_action_id': self.ref_action.id,
            # pas de step_type
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime._execute_step(step)

        assert result == ExecutionStatus.COMPLETED
        exec_step = ExecutionStep.objects.get(execution=execution, step_name='Legacy Step')
        assert exec_step.step_type == ExecutionStepType.PLATFORM

    # --- _execute_handler_step : ExecutionStep créé avec bon step_type ---

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_step_creates_execution_step_with_correct_type(self, mock_execute, mock_audit):
        """_execute_handler_step crée un ExecutionStep avec le step_type correct."""
        mock_execute.return_value = {}
        step = {
            'order': 1,
            'name': 'SVC Call',
            'step_id': 'svc',
            'step_type': 'service_call',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime._execute_step(step)

        assert result == ExecutionStatus.COMPLETED
        exec_step = ExecutionStep.objects.get(execution=execution, step_name='SVC Call')
        assert exec_step.step_type == ExecutionStepType.SERVICE_CALL
        assert exec_step.status == ExecutionStepStatus.COMPLETED

    # --- _execute_handler_step : exception → step FAILED + re-levée ---

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute',
           side_effect=NotImplementedError("Not implemented"))
    def test_handler_exception_marks_step_failed_and_reraises(self, mock_execute, mock_audit):
        """Exception dans handler → ExecutionStep FAILED + exception re-levée."""
        step = {
            'order': 1,
            'name': 'SVC Call',
            'step_id': 'svc',
            'step_type': 'service_call',
        }
        execution = self._create_workflow_execution([step])
        runtime = ContainerWorkflowRuntime(execution)

        with pytest.raises(NotImplementedError):
            runtime._execute_step(step)

        exec_step = ExecutionStep.objects.get(execution=execution, step_name='SVC Call')
        assert exec_step.status == ExecutionStepStatus.FAILED

    # --- _create_skipped_step : tous les types mappés ---

    @patch('executions.container_workflow_runtime.AuditService')
    def test_create_skipped_step_all_types(self, mock_audit):
        """_create_skipped_step mappe correctement tous les step_types vers ExecutionStepType."""
        type_map = {
            'platform': ExecutionStepType.PLATFORM,
            'service_call': ExecutionStepType.SERVICE_CALL,
            'http_request': ExecutionStepType.HTTP_REQUEST,
            'evaluation': ExecutionStepType.EVALUATION,
            'gate': ExecutionStepType.GATE,
        }
        workflow_action = ActionFactory(
            name="Skip Types Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT_LAB,
            status=ExecutionStatus.SUBMITTED,
        )

        for step_type_str, expected_db_type in type_map.items():
            runtime = ContainerWorkflowRuntime(execution)
            result = runtime._create_skipped_step(
                step_name=f"Step {step_type_str}",
                step_id=f"id-{step_type_str}",
                step_type=step_type_str,
            )
            assert result == ExecutionStatus.COMPLETED
            skipped = ExecutionStep.objects.filter(
                execution=execution,
                step_name=f"Step {step_type_str}",
                status=ExecutionStepStatus.SKIPPED,
            ).first()
            assert skipped is not None
            assert skipped.step_type == expected_db_type
