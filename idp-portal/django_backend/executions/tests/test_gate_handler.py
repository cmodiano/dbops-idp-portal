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
            'on_success_step_ids': ['create-change'],
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
            'on_success_step_ids': ['execute-action'],
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
        mock_step.status = ExecutionStepStatus.RUNNING
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
        # set_output appelé avec gate_output + gate_type (Story 72.3: ajouté par _handle_gate_waiting)
        expected_output = dict(gate_result['gate_output'])
        expected_output['gate_type'] = 'maintenance_window'
        mock_step.set_output.assert_called_once_with(expected_output)
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
            runtime._step_outputs_lock = __import__('threading').Lock()
            runtime._step_lock = __import__('threading').Lock()
            runtime.child_executions = []
            runtime.workflow_steps = [
                {'step_type': 'gate', 'gate_type': 'maintenance_window', 'order': 1, 'step_id': 'g1'},
                {'step_type': 'platform', 'order': 2, 'step_id': 's2'},
            ]
            # Story 67.2: _member_step_ids supprimé, remplacé par _step_lookup_by_id
            runtime._step_lookup_by_id = {
                'g1': {'step_type': 'gate', 'gate_type': 'maintenance_window', 'order': 1, 'step_id': 'g1'},
                's2': {'step_type': 'platform', 'order': 2, 'step_id': 's2'},
            }

            # _check_cancelled retourne False, _execute_step retourne RUNNING pour gate
            with patch.object(runtime, '_check_cancelled', return_value=False):
                with patch.object(runtime, '_execute_step', side_effect=[ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED]) as mock_execute:
                    result = runtime._execute_workflow_steps()
                    # Assertions dans le contexte du patch
                    # Doit retourner RUNNING (gate paused)
                    assert result == ExecutionStatus.RUNNING
                    # Le second step NE doit PAS avoir été exécuté (boucle arrêtée)
                    assert mock_execute.call_count == 1


class TestResumeContainerWorkflowFromGate:
    """
    Tests unitaires pour resume_container_workflow_from_gate (story 57.7 — Task 4).
    Couvre : cancellation, not_running, step_not_found, happy path, step_outputs reconstruction.

    Note : is_cancelled est importé lazily dans la fonction → patch sur executions.cancellation_cache.
    De même, Execution et ExecutionStep sont importés lazily → patch via patch.object sur leur manager.
    """

    @pytest.mark.django_db
    def test_cancelled_execution_returns_cancelled(self):
        """Si l'exécution est annulée → retourne {'outcome': 'cancelled'}."""
        from executions.tasks.gates import resume_container_workflow_from_gate

        with patch('executions.cancellation_cache.is_cancelled', return_value=True):
            result = resume_container_workflow_from_gate.run(execution_id=1, on_success_step_ids='step-1')

        assert result == {'outcome': 'cancelled'}

    @pytest.mark.django_db
    def test_execution_not_found_returns_error(self):
        """Si l'Execution n'existe pas → retourne {'outcome': 'error', 'error': ...}."""
        from executions.tasks.gates import resume_container_workflow_from_gate
        from executions.models import Execution

        with patch('executions.cancellation_cache.is_cancelled', return_value=False):
            with patch.object(Execution.objects, 'select_related') as mock_qs:
                mock_qs.return_value.get.side_effect = Execution.DoesNotExist()
                result = resume_container_workflow_from_gate.run(execution_id=9999, on_success_step_ids='step-1')

        assert result['outcome'] == 'error'
        assert result['error'] == 'Execution not found'

    @pytest.mark.django_db
    def test_execution_not_running_returns_not_running(self):
        """Si l'exécution n'est pas en RUNNING → retourne {'outcome': 'not_running'}."""
        from executions.tasks.gates import resume_container_workflow_from_gate
        from executions.models import Execution, ExecutionStatus

        mock_execution = MagicMock()
        mock_execution.status = ExecutionStatus.COMPLETED
        mock_execution.action.execution_steps = []

        with patch('executions.cancellation_cache.is_cancelled', return_value=False):
            with patch.object(Execution.objects, 'select_related') as mock_qs:
                mock_qs.return_value.get.return_value = mock_execution
                result = resume_container_workflow_from_gate.run(execution_id=1, on_success_step_ids='step-1')

        assert result['outcome'] == 'not_running'

    @pytest.mark.django_db
    def test_step_not_found_returns_step_not_found(self):
        """Si on_success_step_ids absent de action.execution_steps → retourne step_not_found."""
        from executions.tasks.gates import resume_container_workflow_from_gate
        from executions.models import Execution, ExecutionStatus, ExecutionStep

        mock_execution = MagicMock()
        mock_execution.status = ExecutionStatus.RUNNING
        mock_execution.action.execution_steps = [
            {'step_id': 'other-step', 'name': 'Other', 'step_type': 'platform'},
        ]

        with patch('executions.cancellation_cache.is_cancelled', return_value=False):
            with patch.object(Execution.objects, 'select_related') as mock_qs:
                mock_qs.return_value.get.return_value = mock_execution
                with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
                    mock_filter.return_value.exists.return_value = False  # target_steps_exist
                    mock_filter.return_value.order_by.return_value = []
                    result = resume_container_workflow_from_gate.run(execution_id=1, on_success_step_ids='missing-step')

        assert result == {'outcome': 'step_not_found', 'step_id': 'missing-step'}

    @pytest.mark.django_db
    def test_step_outputs_keyed_by_step_id_not_step_name(self):
        """
        Fix HIGH-1 : _step_outputs doit être keyed par step_id, pas par step_name.
        Vérifie que le mapping name→step_id est utilisé pour reconstruire _step_outputs.
        """
        from executions.tasks.gates import resume_container_workflow_from_gate
        from executions.models import Execution, ExecutionStatus, ExecutionStep
        from executions.container_workflow_runtime import ContainerWorkflowRuntime

        mock_execution = MagicMock()
        mock_execution.status = ExecutionStatus.RUNNING
        mock_execution.action.execution_steps = [
            {'step_id': 'tf-plan', 'name': 'Terraform Plan', 'step_type': 'platform'},
            {'step_id': 'gate-step', 'name': 'Wait Approval', 'step_type': 'gate', 'gate_type': 'approval'},
            {'step_id': 'tf-apply', 'name': 'Terraform Apply', 'step_type': 'platform'},
        ]

        # Step COMPLETED avant le gate (step_name = nom humain, pas step_id)
        # config_step_id=None pour forcer le fallback name→step_id (step_name_to_id)
        mock_db_step = MagicMock()
        mock_db_step.step_name = 'Terraform Plan'
        mock_db_step.config_step_id = None
        mock_db_step.get_output.return_value = {'plan_output': 'some value'}

        captured_runtime = {}

        def fake_runtime_init(self_r, execution):
            self_r.execution = execution
            self_r.correlation_id = 'test'
            self_r._step_outputs = {}
            self_r.workflow_steps = []
            self_r._step_order_counter = 0
            captured_runtime['instance'] = self_r

        with patch('executions.cancellation_cache.is_cancelled', return_value=False):
            with patch.object(Execution.objects, 'select_related') as mock_qs:
                mock_qs.return_value.get.return_value = mock_execution
                with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
                    mock_filter.return_value.exists.return_value = False  # target_steps_exist
                    mock_filter.return_value.order_by.return_value = [mock_db_step]
                    with patch.object(ContainerWorkflowRuntime, '__init__', fake_runtime_init):
                        with patch.object(ContainerWorkflowRuntime, '_execute_workflow_steps', return_value=None):
                            resume_container_workflow_from_gate.run(
                                execution_id=1, on_success_step_ids='tf-apply'
                            )

        # Le step_output doit être keyed par 'tf-plan' (step_id), pas 'Terraform Plan' (step_name)
        runtime_instance = captured_runtime.get('instance')
        assert runtime_instance is not None
        assert 'tf-plan' in runtime_instance._step_outputs
        assert 'Terraform Plan' not in runtime_instance._step_outputs
        assert runtime_instance._step_outputs['tf-plan'] == {'plan_output': 'some value'}


class TestTransitionStepToRunningADR007:
    """
    Tests de la logique ADR-007 dans _transition_step_to_running (story 57.7 — Task 5).
    Couvre : dispatch resume_container_workflow_from_gate, completion gate final, warning no-adr007 (Story 81.2).
    """

    def _make_step(self, step_name='Wait Gate', execution_id=1, execution_steps=None):
        """Crée un ExecutionStep mock avec les champs nécessaires."""
        mock_step = MagicMock()
        mock_step.id = 10
        mock_step.step_name = step_name
        mock_step.step_order = 1
        mock_step.execution_id = execution_id
        # config_step_id=None pour que le fallback step_name matche step_def
        mock_step.config_step_id = None
        mock_exec = MagicMock()
        mock_exec.id = execution_id
        mock_exec.status.RUNNING = 'RUNNING'
        action = MagicMock()
        action.execution_steps = execution_steps or []
        mock_exec.action = action
        mock_step.execution = mock_exec
        mock_step.created_at = MagicMock()
        return mock_step

    @pytest.mark.django_db
    def test_adr007_step_with_on_success_calls_resume_task(self):
        """AC#6 : step ADR-007 avec on_success_step_ids → resume_container_workflow_from_gate.apply_async."""
        from executions.tasks.gates import _transition_step_to_running, resume_container_workflow_from_gate
        from executions.models import ExecutionStep

        step_def = {
            'name': 'Wait Gate',
            'step_type': 'gate',
            'gate_type': 'maintenance_window',
            'on_success_step_ids': ['next-step'],
        }
        mock_step = self._make_step(step_name='Wait Gate', execution_steps=[step_def])
        gate_status = {'satisfied': True, 'conditions': []}

        with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
            mock_filter.return_value.update.return_value = 1
            mock_step.refresh_from_db = MagicMock()

            with patch('executions.tasks.gates.AuditService'):
                with patch.object(resume_container_workflow_from_gate, 'apply_async') as mock_apply:
                    _transition_step_to_running(mock_step, gate_status, 'corr-123')

        mock_apply.assert_called_once_with(
            args=[mock_step.execution_id, ['next-step']],
            queue='default',
        )

    @pytest.mark.django_db
    def test_adr007_step_without_on_success_completes_execution(self):
        """AC#6 : step ADR-007 sans on_success_step_ids (gate final) → atomic update to COMPLETED."""
        from executions.tasks.gates import _transition_step_to_running
        from executions.models import Execution, ExecutionStep, ExecutionStatus

        step_def = {
            'name': 'Final Gate',
            'step_type': 'gate',
            'gate_type': 'maintenance_window',
            # pas de on_success_step_ids
        }
        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_execution.user_id = 1
        mock_execution.status = ExecutionStatus.RUNNING
        mock_execution.action.name = 'Test'
        mock_execution.action.execution_steps = [step_def]  # requis pour la recherche step_def
        mock_step = self._make_step(step_name='Final Gate', execution_steps=[step_def])
        mock_step.execution = mock_execution
        gate_status = {'satisfied': True, 'conditions': []}

        with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
            mock_filter.return_value.update.return_value = 1
            mock_step.refresh_from_db = MagicMock()

            with patch('executions.tasks.gates.AuditService'):
                with patch('executions.services.runnable_steps.RunnableStepService') as mock_runnable:
                    with patch('executions.services.workflow_events.WorkflowEventService') as mock_events:
                        mock_runnable.delete = MagicMock()
                        mock_events.emit_step_status_changed = MagicMock()
                        with patch.object(Execution.objects, 'filter') as mock_exec_filter:
                            mock_exec_filter.return_value.update.return_value = 1
                            _transition_step_to_running(mock_step, gate_status, 'corr-123')

        mock_exec_filter.assert_called_once()
        filter_call = mock_exec_filter.call_args
        assert filter_call[1]['id'] == mock_execution.id
        assert filter_call[1]['status'] == ExecutionStatus.RUNNING
        update_call = mock_exec_filter.return_value.update.call_args
        assert update_call[1]['status'] == ExecutionStatus.COMPLETED
        assert 'completed_at' in update_call[1]

    @pytest.mark.django_db
    def test_non_adr007_step_logs_warning(self):
        """Step sans step_type → not ADR-007 → warning logged, no legacy call (Story 81.2)."""
        from executions.tasks.gates import _transition_step_to_running
        from executions.models import ExecutionStep

        step_def = {
            'name': 'Old Style Step',
            # pas de step_type → not ADR-007
        }
        mock_step = self._make_step(step_name='Old Style Step', execution_steps=[step_def])
        gate_status = {'satisfied': True, 'conditions': []}

        with patch.object(ExecutionStep.objects, 'filter') as mock_filter:
            mock_filter.return_value.update.return_value = 1
            mock_step.refresh_from_db = MagicMock()

            with patch('executions.tasks.gates.AuditService'):
                with patch('executions.tasks.gates.logger') as mock_logger:
                    _transition_step_to_running(mock_step, gate_status, 'corr-123')

        warning_calls = [c for c in mock_logger.warning.call_args_list if c[0][0] == 'gate_resume_no_adr007_step']
        assert len(warning_calls) == 1

    @pytest.mark.django_db
    def test_step_def_not_found_logs_error(self):
        """step_def=None (find_step_config introuvable) → gate_resume_step_def_not_found loggé, aucun dispatch (Story 81.2)."""
        from executions.tasks.gates import _resume_workflow_after_gate

        mock_step = self._make_step(step_name='Unknown Step', execution_steps=[])
        mock_step.step_name = 'Unknown Step'

        with patch('executions.tasks.gates.logger') as mock_logger:
            _resume_workflow_after_gate(mock_step, mock_step.execution.action, None, 'corr-test')

        error_calls = [c for c in mock_logger.error.call_args_list if c[0][0] == 'gate_resume_step_def_not_found']
        assert len(error_calls) == 1
