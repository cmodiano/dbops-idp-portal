"""
Tests de couverture pour executions/container_workflow_runtime.py (Story 55.4).
Couvre les branches non couvertes par les tests existants.
"""
import json
import pytest
from unittest.mock import patch
from django.test import TestCase

from executions.container_workflow_runtime import ContainerWorkflowRuntime, MAX_STEP_TRANSITIONS
from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory

TEST_ENV = 'developpement'


def _make_steps(action_ids):
    return [
        {"order": i + 1, "name": f"Step {i + 1}", "referenced_action_id": aid, "step_id": f"s{i + 1}"}
        for i, aid in enumerate(action_ids)
    ]


# ─── Tests _cancel_child_executions ──────────────────────────────────────────

@pytest.mark.django_db
class TestCancelChildExecutionsCoverage(TestCase):
    """_cancel_child_executions — enfants cancellables et déjà terminés."""

    def setUp(self):
        self.user = UserFactory(username='cancel_cw_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_cancel_child_executions_cancellable_child(self, mock_audit):
        """Enfant SUBMITTED → annulé."""
        parent = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        child = Execution.objects.create(
            action=self.action_a, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED, parent_execution_id=parent.id,
        )
        runtime = ContainerWorkflowRuntime(parent)
        runtime.child_executions = [child]
        runtime._cancel_child_executions()

        child.refresh_from_db()
        self.assertEqual(child.status, ExecutionStatus.CANCELLED)
        self.assertIsNotNone(child.completed_at)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_cancel_child_executions_already_completed_skipped(self, mock_audit):
        """Enfant COMPLETED → non modifié."""
        parent = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        child = Execution.objects.create(
            action=self.action_a, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.COMPLETED, parent_execution_id=parent.id,
        )
        runtime = ContainerWorkflowRuntime(parent)
        runtime.child_executions = [child]
        runtime._cancel_child_executions()

        child.refresh_from_db()
        self.assertEqual(child.status, ExecutionStatus.COMPLETED)


# ─── Tests _execute_step — loop detection ────────────────────────────────────

@pytest.mark.django_db
class TestExecuteStepLoopDetection(TestCase):
    """Loop detection — transition_count > MAX_STEP_TRANSITIONS → FAILED."""

    def setUp(self):
        self.user = UserFactory(username='loop_cw_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_loop_detection_returns_failed(self, mock_audit):
        """Trop de transitions → FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime._transition_count = MAX_STEP_TRANSITIONS  # will become 101 > 100

        step = {"order": 1, "name": "Step 1", "referenced_action_id": self.action_a.id, "step_id": "s1"}
        result = runtime._execute_step(step)
        self.assertEqual(result, ExecutionStatus.FAILED)


# ─── Tests simulation error path ─────────────────────────────────────────────

@pytest.mark.django_db
class TestSimulationErrorCoverage(TestCase):
    """Exception dans SimulationService._run_simulation → child FAILED."""

    def setUp(self):
        self.user = UserFactory(username='sim_err_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_simulation_error_marks_child_failed(self, mock_audit):
        """Erreur simulation → child FAILED, parent FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=True):
            with patch('executions.container_workflow_runtime.SimulationService.create_simulated_steps'):
                with patch(
                    'executions.container_workflow_runtime.SimulationService._run_simulation',
                    side_effect=RuntimeError("sim failed"),
                ):
                    result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.FAILED)


# ─── Tests run() method ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRunMethodCoverage(TestCase):
    """run() — workflow vide et lancement normal du thread."""

    def setUp(self):
        self.user = UserFactory(username='run_cw_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_empty_workflow_marks_failed(self, mock_audit):
        """Workflow vide → FAILED, aucun thread lancé."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[], change_type_config=None, created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("no steps", execution.error_message)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_normal_starts_thread(self, mock_audit):
        """Run normal → thread démarré, execution en RUNNING."""
        import time
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        with patch.object(runtime, '_run_workflow_loop') as _mock_loop:
            runtime.run()
            time.sleep(0.1)  # let thread start
        # Thread should have been started (mock_loop may or may not have been called yet)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)


# ─── Tests _run_workflow_loop exception handling ──────────────────────────────

@pytest.mark.django_db
class TestRunWorkflowLoopException(TestCase):
    """_run_workflow_loop — gestion des exceptions et marquage FAILED."""

    def setUp(self):
        self.user = UserFactory(username='loop_exc_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_workflow_loop_invalid_id_handles_exception(self, mock_audit):
        """ID invalide → Execution.DoesNotExist gérée sans exception propagée."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # Call with invalid ID → Execution.DoesNotExist → exception handled
        runtime._run_workflow_loop(99999)  # no exception raised = covered

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_workflow_loop_marks_failed_on_exception(self, mock_audit):
        """Exception dans _execute_workflow_steps → execution marquée FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch.object(runtime, '_execute_workflow_steps', side_effect=RuntimeError("thread error")):
            runtime._run_workflow_loop(execution.id)

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("thread error", execution.error_message)


# ─── Tests _execute_workflow_steps — CANCELLED step path ─────────────────────

@pytest.mark.django_db
class TestExecuteWorkflowStepsCancelled(TestCase):
    """_execute_workflow_steps — step retourne CANCELLED → workflow CANCELLED."""

    def setUp(self):
        self.user = UserFactory(username='wf_cancelled_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_cancelled_step_stops_workflow(self, mock_audit):
        """Step retourne CANCELLED → workflow CANCELLED, step suivante non exécutée."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id, self.action_b.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.execution.started_at = None  # runtime needs these fields

        call_count = [0]
        original_execute_step = runtime._execute_step

        def mock_step(step):
            call_count[0] += 1
            if call_count[0] == 1:
                return ExecutionStatus.CANCELLED
            return original_execute_step(step)

        runtime._execute_step = mock_step
        result = runtime._execute_workflow_steps()

        self.assertEqual(result, ExecutionStatus.CANCELLED)
        self.assertEqual(call_count[0], 1)  # second step not called


# ─── Tests _load_workflow_steps — format invalide ─────────────────────────────

@pytest.mark.django_db
class TestLoadWorkflowStepsInvalidFormat(TestCase):
    """_load_workflow_steps — execution_steps non-liste → warning + retourne []."""

    def setUp(self):
        self.user = UserFactory(username='load_wf_invalid_user', profile='DBA')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execution_steps_not_list_returns_empty(self, mock_audit):
        """steps=dict → warning + return []."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            # Volontairement un dict au lieu d'une liste
            execution_steps={"order": 1, "name": "bad"},
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # workflow_steps doit être vide car execution_steps est un dict
        self.assertEqual(runtime.workflow_steps, [])

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execution_steps_none_returns_empty(self, mock_audit):
        """steps=None → warning + return []."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=None, change_type_config=None,
            created_by=self.user,
        )
        # Forcer execution_steps à None sur l'action
        wf.execution_steps = None
        wf.save()
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        self.assertEqual(runtime.workflow_steps, [])


# ─── Tests _get_step_parameters — workflow_step_parameters ───────────────────

@pytest.mark.django_db
class TestGetStepParametersCoverage(TestCase):
    """_get_step_parameters — fusion global params et workflow_step_parameters."""

    def setUp(self):
        self.user = UserFactory(username='step_params_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_parameters_injected(self, mock_audit):
        """wsp[order] contient parameters → merge avec global params."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        # Injecter workflow_step_parameters directement dans execution (JSON string)
        execution.parameters = json.dumps({
            "global_param": "global_value",
            "workflow_step_parameters": {
                "1": {
                    "parameters": {"step_specific": "step_value"}
                }
            }
        })
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        step = {"order": 1, "name": "Step 1", "referenced_action_id": self.action_a.id}
        result = runtime._get_step_parameters(step)

        self.assertEqual(result.get("step_specific"), "step_value")
        self.assertEqual(result.get("global_param"), "global_value")
        self.assertNotIn("workflow_step_parameters", result)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_parameters_empty_when_no_match(self, mock_audit):
        """wsp dict mais pas de clé pour cet ordre → global params uniquement."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        execution.parameters = json.dumps({
            "global_param": "global_value",
            "workflow_step_parameters": {
                "99": {"parameters": {"other": "value"}}
            }
        })
        execution.save()

        runtime = ContainerWorkflowRuntime(execution)
        step = {"order": 1, "name": "Step 1", "referenced_action_id": self.action_a.id}
        result = runtime._get_step_parameters(step)

        self.assertEqual(result.get("global_param"), "global_value")
        self.assertNotIn("other", result)


# ─── Tests _execute_step — missing referenced_action_id ──────────────────────

@pytest.mark.django_db
class TestExecuteStepMissingActionId(TestCase):
    """_execute_step — step sans referenced_action_id → FAILED."""

    def setUp(self):
        self.user = UserFactory(username='exec_step_no_ref_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "No Ref Step"}],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_missing_referenced_action_id_returns_failed(self, mock_audit):
        """referenced_action_id absent → FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step = {"order": 1, "name": "No Ref Step"}  # pas de referenced_action_id
        result = runtime._execute_step(step)
        self.assertEqual(result, ExecutionStatus.FAILED)


# ─── Tests _execute_step — Action.DoesNotExist ────────────────────────────────

@pytest.mark.django_db
class TestExecuteStepActionNotFound(TestCase):
    """_execute_step — referenced_action introuvable (DoesNotExist) → FAILED."""

    def setUp(self):
        self.user = UserFactory(username='exec_step_not_found_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "Bad Ref Step", "referenced_action_id": 99999}],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_action_not_found_returns_failed(self, mock_audit):
        """Action.DoesNotExist → FAILED + error loggé."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step = {"order": 1, "name": "Bad Ref Step", "referenced_action_id": 99999}
        result = runtime._execute_step(step)
        self.assertEqual(result, ExecutionStatus.FAILED)


# ─── Tests _execute_step — simulation désactivée ─────────────────────────────

@pytest.mark.django_db
class TestExecuteStepNoSimulation(TestCase):
    """Simulation désactivée → fallback direct status update sur child execution."""

    def setUp(self):
        self.user = UserFactory(username='exec_step_nosim_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_simulation_marks_child_completed(self, mock_audit):
        """Simulation off → child COMPLETED via direct update."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=False):
            result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        # Vérifie que l'enfant a bien été créé
        self.assertEqual(len(runtime.child_executions), 1)


# ─── Tests run_sync() — workflow vide ────────────────────────────────────────

@pytest.mark.django_db
class TestRunSyncEmptyWorkflow(TestCase):
    """run_sync() avec workflow vide → FAILED retourné."""

    def setUp(self):
        self.user = UserFactory(username='runsync_empty_user', profile='DBA')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_sync_empty_workflow_returns_failed(self, mock_audit):
        """Workflow vide → FAILED retourné."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[], change_type_config=None,
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.FAILED)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("no steps", execution.error_message)


# ─── Tests _execute_workflow_steps — boucle vide + annulation avant step ─────

@pytest.mark.django_db
class TestExecuteWorkflowStepsEdgeCases(TestCase):
    """_execute_workflow_steps — boucle vide et annulation détectée avant step."""

    def setUp(self):
        self.user = UserFactory(username='wf_edge_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_empty_steps_list_completes_immediately(self, mock_audit):
        """Liste vide → for loop skipée → COMPLETED."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # Forcer workflow_steps vide (déjà le cas mais on s'en assure)
        runtime.workflow_steps = []
        result = runtime._execute_workflow_steps()
        self.assertEqual(result, ExecutionStatus.COMPLETED)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_cancellation_before_first_step(self, mock_audit):
        """Annulation détectée avant premier step → CANCELLED."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch.object(runtime, '_check_cancelled', return_value=True):
            with patch.object(runtime, '_cancel_child_executions') as mock_cancel:
                result = runtime._execute_workflow_steps()

        self.assertEqual(result, ExecutionStatus.CANCELLED)
        mock_cancel.assert_called_once()

    @patch('executions.container_workflow_runtime.AuditService')
    def test_multiple_steps_second_step_executed_after_first_succeeds(self, mock_audit):
        """Boucle continue après step COMPLETED → les deux steps exécutées."""
        action_b = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id, action_b.id]),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        call_count = [0]

        def mock_step(step):
            call_count[0] += 1
            return ExecutionStatus.COMPLETED

        runtime._execute_step = mock_step
        result = runtime._execute_workflow_steps()

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        self.assertEqual(call_count[0], 2)  # les deux steps ont été exécutés


# ─── Tests _run_workflow_loop — finally close_old_connections ─────────────────

@pytest.mark.django_db
class TestRunWorkflowLoopFinally(TestCase):
    """_run_workflow_loop — finally close_old_connections toujours appelé."""

    def setUp(self):
        self.user = UserFactory(username='loop_finally_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_workflow_loop_exception_already_failed_not_updated(self, mock_audit):
        """Exception mais execution déjà FAILED → pas de double update."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.FAILED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        # On force _execute_workflow_steps à lancer une exception
        with patch.object(runtime, '_execute_workflow_steps', side_effect=RuntimeError("already failed scenario")):
            # Cette fois, l'execution est déjà en FAILED donc le bloc de cleanup ne la modifie pas
            runtime._run_workflow_loop(execution.id)

        execution.refresh_from_db()
        # Le statut reste FAILED (pas de double update)
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_workflow_loop_close_connections_called_on_exception(self, mock_audit):
        """finally close_old_connections toujours appelé même après exception."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.container_workflow_runtime.close_old_connections') as mock_close:
            with patch.object(runtime, '_execute_workflow_steps', side_effect=RuntimeError("error")):
                runtime._run_workflow_loop(execution.id)

        # close_old_connections doit être appelé (au moins une fois dans finally)
        self.assertGreaterEqual(mock_close.call_count, 1)


# ─── Tests _execute_handler_step — exception, output_mapping, status ─────────

@pytest.mark.django_db
class TestExecuteHandlerStepCoverage(TestCase):
    """_execute_handler_step — exception, output_mapping, statut retourné par handler."""

    def setUp(self):
        self.user = UserFactory(username='handler_step_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Handler Step', 'step_id': 'hs1', 'step_type': 'service_call',
                'integration_type': 'servicenow', 'operation': 'get_change_status',
            }],
            created_by=self.user,
        )

    def _create_execution(self):
        return Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_exception_returns_failed(self, mock_execute, mock_audit):
        """handler.execute raises → return FAILED, step sauvegardé FAILED."""
        mock_execute.side_effect = RuntimeError("handler failed")
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.FAILED)
        parent_step = ExecutionStep.objects.filter(execution=execution).first()
        self.assertIsNotNone(parent_step)
        self.assertEqual(parent_step.status, ExecutionStepStatus.FAILED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_returns_dict_with_status_completed(self, mock_execute, mock_audit):
        """Handler retourne status=COMPLETED → result COMPLETED."""
        mock_execute.return_value = {'status': ExecutionStatus.COMPLETED, 'raw_output': {}}
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_returns_dict_without_status_fail_closed(self, mock_execute, mock_audit):
        """Handler retourne dict sans status → fail-closed FAILED."""
        mock_execute.return_value = {'data': 'value'}  # no 'status' key
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.FAILED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_output_mapping_not_dict_warning(self, mock_execute, mock_audit):
        """output_mapping non-dict → warning, fallback to {}."""
        mock_execute.return_value = {'status': ExecutionStatus.COMPLETED, 'raw_output': {'x': 1}}
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = {**self.wf.execution_steps[0], 'output_mapping': ['invalid']}  # list, not dict

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_raw_output_extraction(self, mock_execute, mock_audit):
        """raw_output dans result → extrait dans _step_outputs."""
        mock_execute.return_value = {
            'status': ExecutionStatus.COMPLETED,
            'raw_output': {'change_number': 'CHG001'},
        }
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = {
            **self.wf.execution_steps[0],
            'output_mapping': {'change': '$.change_number'},
        }

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        self.assertEqual(runtime._step_outputs.get('hs1', {}).get('change'), 'CHG001')

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_non_dict_result_raw_output_empty(self, mock_execute, mock_audit):
        """Handler retourne non-dict → raw_output = {}, fail-closed FAILED."""
        mock_execute.return_value = "scalar"  # not a dict
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.FAILED)  # no status → fail-closed


# ─── Tests _execute_step — input_mapping non-dict ────────────────────────────

@pytest.mark.django_db
class TestInputMappingNotDictCoverage(TestCase):
    """Couvre le chemin input_mapping non-dict qui logue un warning."""

    def setUp(self):
        self.user = UserFactory(username='input_map_warn_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Bad Mapping Step', 'step_id': 'bm1',
                'step_type': 'service_call',
                'integration_type': 'servicenow', 'operation': 'get_change_status',
                'input_mapping': ['invalid', 'list'],  # list, pas un dict
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_input_mapping_not_dict_logs_warning_and_continues(self, mock_execute, mock_audit):
        """input_mapping est une liste → warning loggé, resolved_params={}, exécution continue."""
        mock_execute.return_value = {'status': ExecutionStatus.COMPLETED, 'raw_output': {}}
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        # Le handler a été appelé avec resolved_params={} (mapping ignoré)
        call_kwargs = mock_execute.call_args.kwargs
        self.assertEqual(call_kwargs.get('resolved_params'), {})


# ─── Story 57.11 — Tests wrapper backward compatibility ──────────────────────

@pytest.mark.django_db
class TestChangeWrapperApplied(TestCase):
    """AC#1 : action avec change_type_config, sans execution_steps, sans parent → 3 steps générés."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_applied_user', profile='DBA')
        self.action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"model": "standard", "category": "database", "assignment_group": "DBA-Team"},
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_wrapper_generates_three_steps(self, mock_audit):
        """Sans execution_steps + avec change_type_config + sans parent → 3 steps synthétiques."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        self.assertEqual(len(runtime.workflow_steps), 3)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_wrapper_step_ids(self, mock_audit):
        """Les step_ids sont create-change, execute-action, close-change."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step_ids = [s['step_id'] for s in runtime.workflow_steps]

        self.assertEqual(step_ids, ['create-change', 'execute-action', 'close-change'])

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.logger')
    def test_wrapper_logs_structlog_event(self, mock_logger, mock_audit):
        """L1-Fix : log structlog container_workflow_backward_compat_wrapper_applied émis avec action_id et execution_id."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        ContainerWorkflowRuntime(execution)

        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        wrapper_calls = [c for c in info_calls if 'container_workflow_backward_compat_wrapper_applied' in c]
        self.assertTrue(len(wrapper_calls) >= 1,
                        "Le log container_workflow_backward_compat_wrapper_applied doit être émis")
        # Vérifier les kwargs du call
        matching_call = next(
            call for call in mock_logger.info.call_args_list
            if call.args and call.args[0] == 'container_workflow_backward_compat_wrapper_applied'
        )
        self.assertEqual(matching_call.kwargs.get('action_id'), self.action.id)
        self.assertEqual(matching_call.kwargs.get('execution_id'), execution.id)


@pytest.mark.django_db
class TestChangeWrapperNotAppliedWithSteps(TestCase):
    """AC#2 : action avec execution_steps → steps originaux retournés sans wrapper."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_steps_user', profile='DBA')
        self.action_ref = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "Step 1", "step_id": "s1",
                               "referenced_action_id": None}],
            change_type_config={"model": "standard", "category": "db", "assignment_group": "DBA"},
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_existing_steps_returned_unchanged(self, mock_audit):
        """Avec execution_steps non-vides → pas de wrapper, steps originaux."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        self.assertEqual(len(runtime.workflow_steps), 1)
        self.assertEqual(runtime.workflow_steps[0]['step_id'], 's1')


@pytest.mark.django_db
class TestChangeWrapperNotAppliedWithoutConfig(TestCase):
    """AC#3 : action sans change_type_config et sans steps → [] (comportement inchangé)."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_no_config_user', profile='DBA')
        self.action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            change_type_config=None,
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_change_type_config_returns_empty(self, mock_audit):
        """Sans change_type_config → liste vide retournée, pas de wrapper."""
        # Forcer change_type_config à None sur l'action (overrider la factory)
        self.action.change_type_config = None
        self.action.save()

        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        self.assertEqual(runtime.workflow_steps, [])


@pytest.mark.django_db
class TestChangeWrapperNotAppliedForChild(TestCase):
    """AC#6 : guard anti-récursion — exécution enfant (parent_execution_id défini) → pas de wrapper."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_child_user', profile='DBA')
        self.action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"model": "standard", "category": "db", "assignment_group": "DBA"},
            created_by=self.user,
        )
        self.parent_execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.RUNNING,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_child_execution_skips_wrapper(self, mock_audit):
        """Exécution enfant (parent_execution_id défini) → pas de wrapper même avec change_type_config."""
        child_execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
            parent_execution_id=self.parent_execution.id,
        )
        runtime = ContainerWorkflowRuntime(child_execution)

        self.assertEqual(runtime.workflow_steps, [])


@pytest.mark.django_db
class TestChangeWrapperStepStructure(TestCase):
    """AC#4, #5, #7 : vérifier step_type, input_mapping, output_mapping, on_success_step_id."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_struct_user', profile='DBA')
        self.action = ActionFactory(
            name="Test Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"model": "normal", "category": "software", "assignment_group": "App-Team"},
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_create_change_step_structure(self, mock_audit):
        """AC#4 : create-change contient short_description, change_type, category, assignment_group."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        create_step = runtime.workflow_steps[0]
        self.assertEqual(create_step['step_id'], 'create-change')
        self.assertEqual(create_step['step_type'], 'service_call')
        self.assertEqual(create_step['integration_type'], 'servicenow')
        self.assertEqual(create_step['operation'], 'create_change')
        self.assertIn('short_description', create_step['input_mapping'])
        self.assertEqual(create_step['input_mapping']['change_type'], 'normal')
        self.assertEqual(create_step['input_mapping']['category'], 'software')
        self.assertEqual(create_step['input_mapping']['assignment_group'], 'App-Team')
        self.assertEqual(create_step['output_mapping'], {'change_number': '$.number', 'sys_id': '$.sys_id'})
        self.assertEqual(create_step['on_success_step_id'], 'execute-action')  # AC#7

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execute_action_step_structure(self, mock_audit):
        """execute-action : step_type=platform, referenced_action_id=action.id, on_success_step_id=close-change."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        exec_step = runtime.workflow_steps[1]
        self.assertEqual(exec_step['step_id'], 'execute-action')
        self.assertEqual(exec_step['step_type'], 'platform')
        self.assertEqual(exec_step['referenced_action_id'], self.action.id)
        self.assertEqual(exec_step['on_success_step_id'], 'close-change')  # AC#7

    @patch('executions.container_workflow_runtime.AuditService')
    def test_close_change_step_structure(self, mock_audit):
        """AC#5 : close-change contient change_id et close_code='successful'."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        close_step = runtime.workflow_steps[2]
        self.assertEqual(close_step['step_id'], 'close-change')
        self.assertEqual(close_step['step_type'], 'service_call')
        self.assertEqual(close_step['operation'], 'close_change')
        self.assertIn('change_id', close_step['input_mapping'])
        self.assertIn("steps['create-change']['change_number']", close_step['input_mapping']['change_id'])
        self.assertEqual(close_step['input_mapping']['close_code'], 'successful')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_partial_change_type_config_uses_fallback_defaults(self, mock_audit):
        """M2-Fix : change_type_config partiel → valeurs fallback correctes (AC#4)."""
        action = ActionFactory(
            name="Emergency Deploy",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"model": "emergency"},  # manque category et assignment_group
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        create_step = runtime.workflow_steps[0]
        self.assertEqual(create_step['input_mapping']['change_type'], 'emergency')
        self.assertEqual(create_step['input_mapping']['category'], '')
        self.assertEqual(create_step['input_mapping']['assignment_group'], '')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_change_type_config_without_model_uses_standard_default(self, mock_audit):
        """M2-Fix : change_type_config sans 'model' → fallback 'standard'."""
        action = ActionFactory(
            name="DB Patch",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"category": "database", "assignment_group": "DBA"},
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        create_step = runtime.workflow_steps[0]
        self.assertEqual(create_step['input_mapping']['change_type'], 'standard')


@pytest.mark.django_db
class TestChangeWrapperRunSyncIntegration(TestCase):
    """AC#1–#8 : run_sync() avec action wrappée → ServiceCallHandler mocké → COMPLETED."""

    def setUp(self):
        self.user = UserFactory(username='wrapper_runsync_user', profile='DBA')
        self.action = ActionFactory(
            name="Deploy DB",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            execution_steps=[],
            change_type_config={"model": "standard", "category": "database", "assignment_group": "DBA-Team"},
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_run_sync_with_wrapper_completes(self, mock_svc_execute, mock_audit):
        """run_sync() avec wrapper : create-change → execute-action → close-change → COMPLETED."""
        # ServiceCallHandler retourne succès avec les outputs ServiceNow
        mock_svc_execute.return_value = {
            'status': ExecutionStatus.COMPLETED,
            'raw_output': {'number': 'CHG001', 'sys_id': 'sys_abc123', 'closed': True},
        }

        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.SUBMITTED,
        )

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=False):
            runtime = ContainerWorkflowRuntime(execution)
            result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        # Vérifier que ServiceCallHandler a été appelé deux fois (create-change + close-change)
        self.assertEqual(mock_svc_execute.call_count, 2)
        # M1-Fix : vérifier que close-change a reçu change_id résolu depuis create-change outputs
        close_change_call = mock_svc_execute.call_args_list[1]
        resolved_params = close_change_call.kwargs.get('resolved_params', {})
        self.assertEqual(resolved_params.get('change_id'), 'CHG001',
                         "close-change doit recevoir change_id résolu depuis _step_outputs['create-change']")
        self.assertEqual(resolved_params.get('close_code'), 'successful')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_ac8_run_workflow_loop_reloads_wrapper_steps(self, mock_audit):
        """AC#8 : _run_workflow_loop appelle _load_workflow_steps() → wrapper appliqué lors du reload réel."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment=TEST_ENV,
            status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        # Patcher _execute_workflow_steps pour éviter l'exécution réelle tout en testant le reload
        with patch.object(runtime, '_execute_workflow_steps', return_value=ExecutionStatus.COMPLETED):
            runtime._run_workflow_loop(execution.id)

        # Après le reload dans _run_workflow_loop, workflow_steps doit contenir 3 steps synthétiques
        self.assertEqual(len(runtime.workflow_steps), 3)
        self.assertEqual(runtime.workflow_steps[0]['step_id'], 'create-change')
        self.assertEqual(runtime.workflow_steps[2]['step_id'], 'close-change')
