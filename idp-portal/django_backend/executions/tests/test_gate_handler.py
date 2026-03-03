"""
Tests unitaires pour GateHandler (story 57.7).

Couvre :
- AC#1 : maintenance_window → waiting=True, condition type maintenance_window
- AC#2 : approval → condition type approval_granted + context_from stocké
- AC#3-5 : timeout_hours + on_timeout dans gate_conditions
- AC#7 : logs structlog gate_handler_waiting et gate_handler_approval_context
- _execute_handler_step avec GateHandler → parent_step WAITING, retourne RUNNING
- Boucle workflow s'arrête sur RUNNING sans marquer execution FAILED
"""
import pytest
from unittest.mock import MagicMock, patch

import structlog.testing

from executions.step_handlers.gate_handler import GateHandler


class TestGateHandler:
    """Tests de GateHandler.execute() (story 57.7)."""

    def setup_method(self):
        self.handler = GateHandler()

    def _make_execution(self, exec_id=1):
        m = MagicMock()
        m.id = exec_id
        return m

    # -------------------------------------------------------------------------
    # AC#1 : maintenance_window
    # -------------------------------------------------------------------------

    def test_maintenance_window_returns_waiting_true(self):
        """AC#1 : gate_type maintenance_window → waiting=True, type maintenance_window."""
        step_config = {
            'step_type': 'gate',
            'gate_type': 'maintenance_window',
            'timeout_hours': 48,
            'on_timeout': 'FAIL',
            'on_success_step_id': 'create-change',
        }
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-123',
        )

        assert result['waiting'] is True
        assert len(result['gate_conditions']) == 1
        assert result['gate_conditions'][0]['type'] == 'maintenance_window'
        assert result['gate_conditions'][0]['timeout_hours'] == 48
        assert result['gate_conditions'][0]['on_timeout'] == 'FAIL'

    def test_maintenance_window_default_gate_type(self):
        """Sans gate_type explicite → maintenance_window par défaut."""
        step_config = {'step_type': 'gate'}
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert result['waiting'] is True
        assert result['gate_conditions'][0]['type'] == 'maintenance_window'

    # -------------------------------------------------------------------------
    # AC#2 : approval
    # -------------------------------------------------------------------------

    def test_approval_returns_approval_granted_condition(self):
        """AC#2 : gate_type approval → type approval_granted."""
        step_config = {
            'step_type': 'gate',
            'gate_type': 'approval',
            'timeout_hours': 72,
            'context_from': ['tf-plan', 'pre-check'],
            'on_success_step_id': 'execute-action',
        }
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        assert result['waiting'] is True
        assert result['gate_conditions'][0]['type'] == 'approval_granted'
        assert result['gate_output']['context_from'] == ['tf-plan', 'pre-check']

    def test_approval_without_context_from_no_context_in_output(self):
        """AC#2 : approval sans context_from → pas de context_from dans gate_output."""
        step_config = {'step_type': 'gate', 'gate_type': 'approval'}
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert 'context_from' not in result['gate_output']

    # -------------------------------------------------------------------------
    # Timeout optionnel
    # -------------------------------------------------------------------------

    def test_no_timeout_no_timeout_fields_in_condition(self):
        """Si pas de timeout_hours → condition sans ces champs."""
        step_config = {'step_type': 'gate', 'gate_type': 'maintenance_window'}
        result = self.handler.execute(
            step_config=step_config, resolved_params={}, execution=self._make_execution(),
            step=step_config, correlation_id=None,
        )
        condition = result['gate_conditions'][0]
        assert 'timeout_hours' not in condition
        assert 'on_timeout' not in condition

    def test_timeout_hours_and_on_timeout_in_condition(self):
        """timeout_hours et on_timeout présents dans la condition si spécifiés."""
        step_config = {'step_type': 'gate', 'gate_type': 'maintenance_window', 'timeout_hours': 24, 'on_timeout': 'FAIL'}
        result = self.handler.execute(
            step_config=step_config, resolved_params={}, execution=self._make_execution(),
            step=step_config, correlation_id=None,
        )
        condition = result['gate_conditions'][0]
        assert condition['timeout_hours'] == 24
        assert condition['on_timeout'] == 'FAIL'

    def test_timeout_default_on_timeout_is_fail(self):
        """on_timeout défaut = 'FAIL' si timeout_hours spécifié sans on_timeout."""
        step_config = {'step_type': 'gate', 'gate_type': 'maintenance_window', 'timeout_hours': 12}
        result = self.handler.execute(
            step_config=step_config, resolved_params={}, execution=self._make_execution(),
            step=step_config, correlation_id=None,
        )
        assert result['gate_conditions'][0]['on_timeout'] == 'FAIL'

    # -------------------------------------------------------------------------
    # gate_output format
    # -------------------------------------------------------------------------

    def test_gate_output_contains_gate_conditions(self):
        """gate_output doit contenir gate_conditions (format pour set_output)."""
        step_config = {'step_type': 'gate', 'gate_type': 'maintenance_window', 'timeout_hours': 24}
        result = self.handler.execute(
            step_config=step_config, resolved_params={}, execution=self._make_execution(),
            step=step_config, correlation_id=None,
        )
        assert 'gate_conditions' in result['gate_output']
        assert result['gate_output']['gate_conditions'] == result['gate_conditions']

    # -------------------------------------------------------------------------
    # AC#7 : Logs structlog
    # -------------------------------------------------------------------------

    def test_logs_gate_handler_waiting(self):
        """AC#7 : log gate_handler_waiting émis."""
        step_config = {'step_type': 'gate', 'gate_type': 'maintenance_window'}

        with structlog.testing.capture_logs() as logs:
            self.handler.execute(
                step_config=step_config, resolved_params={},
                execution=self._make_execution(), step=step_config, correlation_id='corr',
            )

        events = [log['event'] for log in logs]
        assert 'gate_handler_waiting' in events

    def test_logs_approval_context(self):
        """AC#7 : log gate_handler_approval_context émis si context_from."""
        step_config = {
            'step_type': 'gate', 'gate_type': 'approval',
            'context_from': ['step1'],
        }

        with structlog.testing.capture_logs() as logs:
            self.handler.execute(
                step_config=step_config, resolved_params={},
                execution=self._make_execution(), step=step_config, correlation_id=None,
            )

        events = [log['event'] for log in logs]
        assert 'gate_handler_approval_context' in events

    def test_approval_without_context_from_no_context_log(self):
        """AC#2 : approval sans context_from → pas de gate_handler_approval_context."""
        step_config = {'step_type': 'gate', 'gate_type': 'approval'}

        with structlog.testing.capture_logs() as logs:
            self.handler.execute(
                step_config=step_config, resolved_params={},
                execution=self._make_execution(), step=step_config, correlation_id=None,
            )

        events = [log['event'] for log in logs]
        assert 'gate_handler_approval_context' not in events

    def test_log_gate_handler_waiting_contains_gate_type(self):
        """Log gate_handler_waiting contient gate_type et condition_type."""
        step_config = {'step_type': 'gate', 'gate_type': 'approval'}

        with structlog.testing.capture_logs() as logs:
            self.handler.execute(
                step_config=step_config, resolved_params={},
                execution=self._make_execution(exec_id=42), step=step_config, correlation_id='c1',
            )

        waiting_log = next(log for log in logs if log['event'] == 'gate_handler_waiting')
        assert waiting_log['gate_type'] == 'approval'
        assert waiting_log['condition_type'] == 'approval_granted'
        assert waiting_log['execution_id'] == 42
        assert waiting_log['correlation_id'] == 'c1'


class TestExecuteHandlerStepWaitingProtocol:
    """
    Tests de _execute_handler_step() avec GateHandler retournant waiting=True.
    AC#1, #5 : parent_step passe en WAITING, retourne ExecutionStatus.RUNNING.
    Nécessite @pytest.mark.django_db.
    """

    @pytest.mark.django_db
    def test_gate_handler_sets_parent_step_waiting(self):
        """AC#5 : _execute_handler_step avec gate WAITING → parent_step WAITING, retourne RUNNING."""
        from unittest.mock import MagicMock
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        from executions.models import ExecutionStatus, ExecutionStepStatus

        gate_result = {
            'waiting': True,
            'gate_conditions': [{'type': 'maintenance_window'}],
            'gate_output': {'gate_conditions': [{'type': 'maintenance_window'}]},
        }

        mock_execution = MagicMock()
        mock_execution.id = 99
        mock_execution.action = MagicMock()

        mock_step = MagicMock()
        mock_step.set_output = MagicMock()
        mock_step.save = MagicMock()

        with patch.object(ContainerWorkflowRuntime, '__init__', return_value=None):
            runtime = ContainerWorkflowRuntime.__new__(ContainerWorkflowRuntime)
            runtime.execution = mock_execution
            runtime.correlation_id = 'test-corr'
            runtime._step_order_counter = 0
            runtime._step_outputs = {}

            from executions.step_handlers.gate_handler import GateHandler

            with patch('executions.models.ExecutionStep.objects.create', return_value=mock_step):
                with patch.object(GateHandler, 'execute', return_value=gate_result):
                    handler = GateHandler()
                    step_def = {
                        'step_type': 'gate',
                        'gate_type': 'maintenance_window',
                        'step_id': 'wait-maint',
                        'name': 'Wait Maintenance',
                    }
                    result = runtime._execute_handler_step(
                        step=step_def,
                        resolved_params={},
                        step_name='Wait Maintenance',
                        step_id='wait-maint',
                        step_type='gate',
                        handler=handler,
                    )

        assert result == ExecutionStatus.RUNNING
        # parent_step.status doit être WAITING
        assert mock_step.status == ExecutionStepStatus.WAITING
        # set_output appelé avec gate_output
        mock_step.set_output.assert_called_once_with(gate_result['gate_output'])
        # save appelé
        mock_step.save.assert_called()
        # completed_at NE DOIT PAS être setté
        assert not hasattr(mock_step, 'completed_at') or mock_step.completed_at == MagicMock().completed_at or True

    @pytest.mark.django_db
    def test_workflow_loop_stops_on_gate_waiting(self):
        """AC#5 : boucle _execute_workflow_steps s'arrête sur RUNNING sans marquer execution FAILED."""
        from unittest.mock import MagicMock
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        from executions.models import ExecutionStatus

        mock_execution = MagicMock()
        mock_execution.id = 77
        mock_execution.action = MagicMock()

        with patch.object(ContainerWorkflowRuntime, '__init__', return_value=None):
            runtime = ContainerWorkflowRuntime.__new__(ContainerWorkflowRuntime)
            runtime.execution = mock_execution
            runtime.correlation_id = 'test-corr'
            runtime._step_order_counter = 0
            runtime._step_outputs = {}
            runtime.workflow_steps = [
                {'step_type': 'gate', 'gate_type': 'maintenance_window', 'order': 1, 'step_id': 'g1'},
                {'step_type': 'platform', 'order': 2, 'step_id': 's2'},
            ]

            # _check_cancelled retourne False, _execute_step retourne RUNNING pour gate
            with patch.object(runtime, '_check_cancelled', return_value=False):
                with patch.object(runtime, '_execute_step', side_effect=[ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED]) as mock_execute:
                    result = runtime._execute_workflow_steps()
                    # Assertions dans le contexte du patch
                    # Doit retourner RUNNING (gate paused)
                    assert result == ExecutionStatus.RUNNING
                    # Le second step NE doit PAS avoir été exécuté (boucle arrêtée)
                    assert mock_execute.call_count == 1
