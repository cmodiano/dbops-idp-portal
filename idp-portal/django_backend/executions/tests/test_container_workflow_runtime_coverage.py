"""
Tests de couverture pour executions/container_workflow_runtime.py (Story 55.4).
Couvre les branches non couvertes par les tests existants.
"""
import json
import pytest
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from executions.container_workflow_runtime import ContainerWorkflowRuntime, MAX_STEP_TRANSITIONS
from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


def _make_trigger_mock_completing():
    """Return a side_effect function that marks child step COMPLETED immediately (Story 77.3)."""
    def _complete_child_step(kwargs, queue):
        exec_step_id = kwargs['execution_step_id']
        ExecutionStep.objects.filter(id=exec_step_id).update(
            status=ExecutionStepStatus.COMPLETED,
            completed_at=timezone.now(),
        )
    return _complete_child_step

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
            execution_steps=[], created_by=self.user,
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
    def test_run_normal_enqueues_steps(self, mock_audit):
        """Run normal (ADR-007 steps) → execution en RUNNING, steps enqueués (Story 81.2)."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)


# ─── Tests initial_wave is None → FAILED (Story 81.2) ────────────────────────

@pytest.mark.django_db
class TestRunNoInitialWaveFailed(TestCase):
    """run() — initial_wave is None → execution marquée FAILED directement (Story 81.2)."""

    def setUp(self):
        self.user = UserFactory(username='no_wave_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Steps sans step_id → _determine_initial_wave retourne None
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "Legacy Step", "referenced_action_id": self.action_a.id}],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_no_initial_wave_marks_failed(self, mock_audit):
        """Steps sans step_id → initial_wave=None → execution FAILED, pas de thread."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("Legacy fallback removed", execution.error_message)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_no_initial_wave_error_message(self, mock_audit):
        """Steps sans step_id → error_message contient 'No initial wave'."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        self.assertIn("No initial wave", execution.error_message)


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
            execution_steps=None,
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
    """Simulation désactivée → dispatch réel via trigger_platform_job (Story 77.3)."""

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
        # Story 77.3: mock trigger_platform_job pour que le child step soit COMPLETED
        patcher = patch('executions.container_workflow_runtime.trigger_platform_job')
        self.mock_trigger = patcher.start()
        self.mock_trigger.apply_async.side_effect = _make_trigger_mock_completing()
        self.addCleanup(patcher.stop)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_simulation_marks_child_completed(self, mock_audit):
        """Simulation off → child COMPLETED via dispatch réel (trigger_platform_job mocké)."""
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
            execution_steps=[],
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


# ─── Tests run() no initial wave — completed_at et completed_at set (Story 81.2) ─

@pytest.mark.django_db
class TestRunNoInitialWaveFields(TestCase):
    """run() initial_wave=None — champs completed_at et error_message sauvegardés (Story 81.2)."""

    def setUp(self):
        self.user = UserFactory(username='no_wave_fields_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Steps sans step_id → _determine_initial_wave retourne None
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "Legacy Step", "referenced_action_id": self.action_a.id}],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_no_initial_wave_completed_at_set(self, mock_audit):
        """Steps sans step_id → completed_at renseigné après FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run()

        execution.refresh_from_db()
        self.assertIsNotNone(execution.completed_at)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_no_initial_wave_no_exception_propagated(self, mock_audit):
        """Steps sans step_id → run() retourne sans lever d'exception."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # Doit retourner sans exception
        runtime.run()


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


# ─── Tests _execute_step — unknown step_type ───────────────────────────────────

@pytest.mark.django_db
class TestExecuteStepUnknownStepType(TestCase):
    """_execute_step — step_type inconnu → ValueError (séquentiel) ou FAILED (parallèle).

    Story 84.1 (T5.2) : vérifie que le comportement du registre est identique
    à l'ancien match step_type pour les cas non enregistrés (AC5).
    """

    def setUp(self):
        self.user = UserFactory(username='unknown_step_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Unknown Step', 'step_id': 'u1',
                'step_type': 'unknown_type_xyz',
            }],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_unknown_step_type_raises_value_error(self, mock_audit):
        """step_type inconnu en contexte séquentiel → ValueError (AC5)."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        with self.assertRaises(ValueError) as cm:
            runtime._execute_step(step)
        self.assertIn('unknown_type_xyz', str(cm.exception))

    @patch('executions.container_workflow_runtime.AuditService')
    def test_unknown_step_type_in_parallel_context_returns_failed(self, mock_audit):
        """step_type inconnu en contexte parallèle → ExecutionStatus.FAILED (AC5, Story 84.1)."""
        from executions.container_workflow_runtime import ParallelContext
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]
        parallel_ctx = ParallelContext(step_order=1)

        result = runtime._execute_step(step, parallel_context=parallel_ctx)

        self.assertEqual(result, ExecutionStatus.FAILED)


# ─── Tests _execute_platform_step — output_mapping not dict ────────────────────

@pytest.mark.django_db
class TestPlatformStepOutputMappingNotDict(TestCase):
    """_execute_platform_step — output_mapping non-dict → warning + fallback {}."""

    def setUp(self):
        self.user = UserFactory(username='output_map_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1, 'name': 'Platform Step', 'step_id': 'ps1',
                'referenced_action_id': self.action_a.id,
                'output_mapping': ['invalid', 'list'],  # list, not dict
            }],
            created_by=self.user,
        )
        # Story 77.3: mock trigger_platform_job pour que le child step soit COMPLETED
        patcher = patch('executions.container_workflow_runtime.trigger_platform_job')
        self.mock_trigger = patcher.start()
        self.mock_trigger.apply_async.side_effect = _make_trigger_mock_completing()
        self.addCleanup(patcher.stop)

    @patch('executions.container_workflow_runtime.logger')
    @patch('executions.container_workflow_runtime.AuditService')
    def test_output_mapping_not_dict_logs_warning_and_continues(self, mock_audit, mock_logger):
        """output_mapping est une liste → warning loggé, fallback {}, step COMPLETED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch('executions.container_workflow_runtime.SimulationService.is_enabled', return_value=False):
            result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.COMPLETED)
        self.assertEqual(runtime._step_outputs.get('ps1', {}), {})
        mock_logger.warning.assert_called_once()
        self.assertEqual(
            mock_logger.warning.call_args[0][0],
            "container_workflow_output_mapping_not_dict",
        )


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
