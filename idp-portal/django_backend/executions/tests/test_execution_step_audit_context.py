"""
Story 61.8 — Enrichissement audit steps exécution

Vérifie que les entrées EXECUTION_STEP_* incluent `action_name` et `execution_id`
dans leurs `details` pour les 4 fichiers modifiés :
- workflow_retry.py (RetryHandler)
- workflow_step_executor.py (StepExecutor)
- tasks/gates.py (_transition_step_to_running)
- tasks/retry.py (retry_workflow_step)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from executions.workflow_retry import RetryHandler
from executions.workflow_runtime import StepResult, StepOutcome
from core.models import AuditActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execution(exec_id=99, action_name="Mon Action Test"):
    """Mock Execution avec action."""
    execution = MagicMock()
    execution.id = exec_id
    execution.user_id = 1
    execution.action = MagicMock()
    execution.action.name = action_name
    return execution


def _make_execution_no_action(exec_id=99):
    """Mock Execution sans action (action=None)."""
    execution = MagicMock()
    execution.id = exec_id
    execution.user_id = 1
    execution.action = None
    return execution


# ---------------------------------------------------------------------------
# 6.1 — RetryHandler : RETRY_ATTEMPT inclut execution_id et action_name (AC1)
# ---------------------------------------------------------------------------

class TestRetryHandlerAuditContext(TestCase):
    """AC1 : EXECUTION_STEP_RETRY_* (RetryHandler) incluent action_name et execution_id."""

    @patch('executions.workflow_retry.AuditService.create_entry')
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_attempt_includes_execution_id_and_action_name(self, _mock_cancelled, mock_audit):
        """RETRY_ATTEMPT (première tentative échouée) inclut execution_id et action_name."""
        execution = _make_execution(exec_id=42, action_name="Audit Step Test")
        handler = RetryHandler(execution, correlation_id="test-corr")

        step = {
            'step_id': 's1',
            'retry_enabled': True,
            'retry_max_attempts': 3,
            'retry_interval_seconds': 10,
            'retry_backoff_multiplier': 2.0,
            'name': 'Step 1',
            'order': 1,
        }
        error_result = StepResult(outcome=StepOutcome.ERROR, error_message="timeout")
        execute_fn = MagicMock(return_value=error_result)
        counter_fn = MagicMock(return_value=1)

        with patch('executions.tasks.retry_workflow_step') as mock_celery:
            mock_celery.apply_async = MagicMock()
            handler.execute_with_retry(step, execute_fn, counter_fn)

        attempt_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT
        ]
        self.assertTrue(len(attempt_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_ATTEMPT trouvé")
        details = attempt_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], '42')
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], 'Audit Step Test')

    @patch('executions.workflow_retry.AuditService.create_entry')
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_success_includes_execution_id_and_action_name(self, _mock_cancelled, mock_audit):
        """RETRY_SUCCESS (première tentative réussie) inclut execution_id et action_name."""
        execution = _make_execution(exec_id=77, action_name="Success Action")
        handler = RetryHandler(execution, correlation_id="test-corr")

        step = {
            'step_id': 's2',
            'retry_enabled': True,
            'retry_max_attempts': 3,
            'retry_interval_seconds': 10,
            'retry_backoff_multiplier': 2.0,
            'name': 'Step 2',
            'order': 2,
        }
        success_result = StepResult(outcome=StepOutcome.SUCCESS)
        execute_fn = MagicMock(return_value=success_result)
        counter_fn = MagicMock(return_value=1)

        handler.execute_with_retry(step, execute_fn, counter_fn)

        success_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_SUCCESS
        ]
        self.assertTrue(len(success_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_SUCCESS trouvé")
        details = success_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], '77')
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], 'Success Action')

    @patch('executions.workflow_retry.AuditService.create_entry')
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_aborted_includes_execution_id_and_action_name(self, _mock_cancelled, mock_audit):
        """RETRY_ABORTED (erreur non-retryable) inclut execution_id et action_name."""
        execution = _make_execution(exec_id=33, action_name="Aborted Action")
        handler = RetryHandler(execution, correlation_id="test-corr")

        step = {
            'step_id': 's_aborted',
            'retry_enabled': True,
            'retry_max_attempts': 3,
            'retry_interval_seconds': 10,
            'retry_backoff_multiplier': 2.0,
            'name': 'Step Aborted',
            'order': 1,
        }
        # Erreur non-retryable : contient 'validation'
        error_result = StepResult(outcome=StepOutcome.ERROR, error_message="validation error")
        execute_fn = MagicMock(return_value=error_result)
        counter_fn = MagicMock(return_value=1)

        handler.execute_with_retry(step, execute_fn, counter_fn)

        aborted_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ABORTED
        ]
        self.assertTrue(len(aborted_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_ABORTED trouvé")
        details = aborted_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], '33')
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], 'Aborted Action')

    @patch('executions.workflow_retry.AuditService.create_entry')
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_exhausted_includes_execution_id_and_action_name(self, _mock_cancelled, mock_audit):
        """RETRY_EXHAUSTED (max_attempts=1, pas de retry) inclut execution_id et action_name."""
        execution = _make_execution(exec_id=55, action_name="Exhausted Action")
        handler = RetryHandler(execution, correlation_id="test-corr")

        step = {
            'step_id': 's3',
            'retry_enabled': True,
            'retry_max_attempts': 1,
            'retry_interval_seconds': 10,
            'retry_backoff_multiplier': 2.0,
            'name': 'Step 3',
            'order': 3,
        }
        # Un retry error non-retryable ne déclenche pas EXHAUSTED mais ABORTED.
        # Pour EXHAUSTED, il faut max_attempts=1 avec une erreur retryable (ou vide).
        error_result = StepResult(outcome=StepOutcome.ERROR, error_message="")
        execute_fn = MagicMock(return_value=error_result)
        counter_fn = MagicMock(return_value=1)

        handler.execute_with_retry(step, execute_fn, counter_fn)

        exhausted_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED
        ]
        self.assertTrue(len(exhausted_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_EXHAUSTED trouvé")
        details = exhausted_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], '55')
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], 'Exhausted Action')


# ---------------------------------------------------------------------------
# 6.2 — StepExecutor : WAITING inclut execution_id et action_name (AC2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStepExecutorWaitingAuditContext(TestCase):
    """AC2 : EXECUTION_STEP_WAITING (StepExecutor) inclut action_name et execution_id."""

    def setUp(self):
        from tests.factories import UserFactory, ActionFactory
        from executions.models import Execution, ExecutionStatus
        from catalog.models import ActionStatus, ActionItemType

        self.user = UserFactory(username="step_exec_audit_61_8")
        self.action = ActionFactory(
            name="StepExec Audit 61-8",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
        )
        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.RUNNING,
        )

    @patch('executions.workflow_step_executor.AuditService.create_entry')
    @patch('executions.utils.websocket_broadcast.broadcast_step_update')
    @patch('executions.gate_context.build_waiting_context', return_value={'gate_conditions': []})
    def test_waiting_includes_execution_id_and_action_name(
        self, _mock_ctx, _mock_broadcast, mock_audit
    ):
        """EXECUTION_STEP_WAITING inclut execution_id et action_name."""
        from executions.workflow_step_executor import StepExecutor

        step = {
            'step_id': 'gate-step-1',
            'name': 'Step Gate',
            'order': 1,
            'gate_conditions': [{'type': 'approval_granted'}],
        }

        executor = StepExecutor(self.execution, correlation_id="test-waiting-corr")
        executor.execute(step, step_order=1, step_parameters={})

        waiting_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_WAITING
        ]
        self.assertTrue(len(waiting_calls) > 0, "Aucun appel EXECUTION_STEP_WAITING trouvé")
        details = waiting_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], str(self.execution.id))
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], self.action.name)


# ---------------------------------------------------------------------------
# 6.3 — tasks/gates.py : GATE_SATISFIED inclut execution_id et action_name (AC4)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGatesSatisfiedAuditContext(TestCase):
    """AC4 : EXECUTION_STEP_GATE_SATISFIED inclut action_name et execution_id."""

    def setUp(self):
        from django.utils import timezone
        from tests.factories import ExecutionFactory, ExecutionStepFactory
        from executions.models import ExecutionStatus, ExecutionStepStatus

        self.execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        self.step = ExecutionStepFactory(
            execution=self.execution,
            status=ExecutionStepStatus.WAITING,
        )
        self.step.set_output({
            'waiting_since': timezone.now().isoformat(),
            'gate_conditions': [{'type': 'approval_granted'}],
            'gate_status': [{'type': 'approval_granted', 'satisfied': True}],
        })
        self.step.save()

    @patch('executions.tasks.gates.AuditService.create_entry')
    @patch('executions.tasks.retry_workflow_step')
    @patch('executions.tasks.gates.resume_container_workflow_from_gate')
    def test_gate_satisfied_includes_execution_id_and_action_name(
        self, _mock_resume, _mock_retry, mock_audit
    ):
        """EXECUTION_STEP_GATE_SATISFIED inclut execution_id et action_name."""
        from executions.tasks.gates import _transition_step_to_running

        gate_status = {
            'gates': [{'type': 'approval_granted', 'satisfied': True}],
            'timeout_triggered': False,
        }

        _transition_step_to_running(self.step, gate_status, "test-gate-corr")

        satisfied_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_GATE_SATISFIED
        ]
        self.assertTrue(len(satisfied_calls) > 0, "Aucun appel EXECUTION_STEP_GATE_SATISFIED trouvé")
        details = satisfied_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], str(self.execution.id))
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], self.execution.action.name)


# ---------------------------------------------------------------------------
# 6.4 — tasks/retry.py : RETRY_SUCCESS (Celery) inclut execution_id et action_name (AC1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCeleryRetryAuditContext(TestCase):
    """AC1 : EXECUTION_STEP_RETRY_SUCCESS (tâche Celery) inclut action_name et execution_id."""

    def setUp(self):
        from tests.factories import UserFactory, ActionFactory
        from executions.models import Execution, ExecutionStatus
        from catalog.models import ActionStatus, ActionItemType

        self.user = UserFactory(username="celery_audit_61_8")
        self.action = ActionFactory(
            name="Celery Audit 61-8",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )
        self.action.execution_steps = [{
            "step_id": "s1", "order": 1, "name": "Step 1",
            "retry_enabled": True, "retry_max_attempts": 3,
            "retry_interval_seconds": 10, "retry_backoff_multiplier": 2.0,
        }]
        self.action.save()
        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.RUNNING,
        )

    @patch("executions.tasks.AuditService.create_entry")
    def test_celery_retry_success_includes_action_name_and_execution_id(self, mock_audit):
        """RETRY_SUCCESS (Celery) inclut execution_id et action_name."""
        from executions.tasks import retry_workflow_step
        from executions.workflow_runtime import WorkflowRuntime

        step = self.action.execution_steps[0]

        with patch.object(WorkflowRuntime, '_execute_step', return_value=StepResult(
            outcome=StepOutcome.SUCCESS,
        )):
            retry_workflow_step(
                execution_id=self.execution.id,
                step=step,
                attempt=2,
            )

        success_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_SUCCESS
        ]
        self.assertTrue(len(success_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_SUCCESS trouvé")
        details = success_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], str(self.execution.id))
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], self.action.name)


# ---------------------------------------------------------------------------
# 6.5 — Cas conditionnel : action_name absent (None) quand execution.action est None (AC5)
# ---------------------------------------------------------------------------

class TestActionNameConditional(TestCase):
    """AC5 : action_name est None quand execution.action est None."""

    @patch('executions.workflow_retry.AuditService.create_entry')
    @patch('executions.cancellation_cache.is_cancelled', return_value=False)
    def test_retry_attempt_action_name_is_none_when_no_action(self, _mock_cancelled, mock_audit):
        """action_name vaut None quand execution.action est None (RETRY_ATTEMPT)."""
        execution = _make_execution_no_action(exec_id=11)
        handler = RetryHandler(execution, correlation_id="no-action-corr")

        step = {
            'step_id': 's_no_action',
            'retry_enabled': True,
            'retry_max_attempts': 3,
            'retry_interval_seconds': 10,
            'retry_backoff_multiplier': 2.0,
            'name': 'Step No Action',
            'order': 1,
        }
        error_result = StepResult(outcome=StepOutcome.ERROR, error_message="timeout")
        execute_fn = MagicMock(return_value=error_result)
        counter_fn = MagicMock(return_value=1)

        with patch('executions.tasks.retry_workflow_step') as mock_celery:
            mock_celery.apply_async = MagicMock()
            handler.execute_with_retry(step, execute_fn, counter_fn)

        attempt_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT
        ]
        self.assertTrue(len(attempt_calls) > 0, "Aucun appel EXECUTION_STEP_RETRY_ATTEMPT trouvé")
        details = attempt_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertIsNone(details.get('action_name'),
                          "action_name doit être None quand execution.action est None")


# ---------------------------------------------------------------------------
# 6.6 — tasks/gates.py : GATE_TIMEOUT inclut execution_id et action_name (AC4)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGatesTimeoutAuditContext(TestCase):
    """AC4 : EXECUTION_STEP_GATE_TIMEOUT inclut action_name et execution_id."""

    def setUp(self):
        from django.utils import timezone
        from tests.factories import ExecutionFactory, ExecutionStepFactory
        from executions.models import ExecutionStatus, ExecutionStepStatus

        self.execution = ExecutionFactory(status=ExecutionStatus.RUNNING)
        self.step = ExecutionStepFactory(
            execution=self.execution,
            status=ExecutionStepStatus.WAITING,
        )
        self.step.set_output({
            'waiting_since': timezone.now().isoformat(),
            'gate_conditions': [{'type': 'approval_granted'}],
        })
        self.step.save()

    @patch('executions.tasks.gates.AuditService.create_entry')
    def test_gate_timeout_includes_execution_id_and_action_name(self, mock_audit):
        """EXECUTION_STEP_GATE_TIMEOUT inclut execution_id et action_name."""
        from executions.tasks.gates import _handle_gate_timeout

        gate_status = {
            'action': 'FAILED',
            'timeout_hours': 24,
            'timeout_triggered': True,
        }

        _handle_gate_timeout(self.step, gate_status, "test-timeout-corr")

        timeout_calls = [
            c for c in mock_audit.call_args_list
            if c.kwargs.get('action_type') == AuditActionType.EXECUTION_STEP_GATE_TIMEOUT
        ]
        self.assertTrue(len(timeout_calls) > 0, "Aucun appel EXECUTION_STEP_GATE_TIMEOUT trouvé")
        details = timeout_calls[0].kwargs['details']
        self.assertIn('execution_id', details)
        self.assertEqual(details['execution_id'], str(self.execution.id))
        self.assertIn('action_name', details)
        self.assertEqual(details['action_name'], self.execution.action.name)
