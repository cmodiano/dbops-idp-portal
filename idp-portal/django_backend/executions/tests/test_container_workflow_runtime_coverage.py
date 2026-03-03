"""
Tests de couverture pour executions/container_workflow_runtime.py (Story 55.4).
Couvre les branches non couvertes par les tests existants.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from executions.container_workflow_runtime import ContainerWorkflowRuntime, MAX_STEP_TRANSITIONS
from executions.models import Execution, ExecutionStep, ExecutionStatus, ExecutionStepStatus
from catalog.models import ActionStatus, ActionItemType
from core.exceptions import ServiceUnavailableError
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
    """Lignes 161-167 — _cancel_child_executions avec enfant cancellable."""

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
        """Lignes 161-167 — enfant SUBMITTED → annulé."""
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
        """Ligne 162 — enfant COMPLETED → non modifié."""
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
    """Lignes 193-199 — loop detection (transition_count > MAX_STEP_TRANSITIONS)."""

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
        """Lignes 193-199 — trop de transitions → FAILED."""
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
    """Lignes 292-303 — exception dans SimulationService._run_simulation."""

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
        """Lignes 292-303 — erreur simulation → child FAILED, parent FAILED."""
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
    """Lignes 352-412 — run() method."""

    def setUp(self):
        self.user = UserFactory(username='run_cw_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_servicenow_error_marks_failed(self, mock_audit):
        """Lignes 362-385 — ServiceNow error → FAILED, no thread."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch.object(
            runtime, '_create_servicenow_change_if_required',
            side_effect=ServiceUnavailableError(
                code="SN_ERROR", message="SN unavailable", details={},
            ),
        ):
            runtime.run()

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("ServiceNow", execution.error_message)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_empty_workflow_marks_failed(self, mock_audit):
        """Lignes 392-403 — workflow vide → FAILED, no thread."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[], created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        with patch.object(runtime, '_create_servicenow_change_if_required'):
            runtime.run()

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("no steps", execution.error_message)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_normal_starts_thread(self, mock_audit):
        """Lignes 405-416 — run normal → thread démarré."""
        import time
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        with patch.object(runtime, '_create_servicenow_change_if_required'):
            with patch.object(runtime, '_run_workflow_loop') as _mock_loop:
                runtime.run()
                time.sleep(0.1)  # let thread start
        # Thread should have been started (mock_loop may or may not have been called yet)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)


# ─── Tests run_sync() ServiceNow error ───────────────────────────────────────

@pytest.mark.django_db
class TestRunSyncServiceNowError(TestCase):
    """Lignes 436-457 — run_sync() avec erreur ServiceNow."""

    def setUp(self):
        self.user = UserFactory(username='runsync_sn_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_sync_servicenow_error_returns_failed(self, mock_audit):
        """Lignes 436-457 — erreur ServiceNow → FAILED."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch.object(
            runtime, '_create_servicenow_change_if_required',
            side_effect=ServiceUnavailableError(
                code="SN_MISS", message="SN missing", details={},
            ),
        ):
            result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.FAILED)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("ServiceNow", execution.error_message)


# ─── Tests _create_servicenow_change_if_required ─────────────────────────────

@pytest.mark.django_db
class TestCreateServiceNowChangeCoverage(TestCase):
    """Lignes 497-547 — _create_servicenow_change_if_required."""

    def setUp(self):
        self.user = UserFactory(username='sn_change_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_change_required_returns_early(self, mock_audit):
        """Ligne 494 — required=False → retour anticipé."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
            change_type_config={'developpement': {'required': False}},
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime._create_servicenow_change_if_required(TEST_ENV)  # no exception = pass

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_integration_raises(self, mock_audit):
        """Lignes 517-532 — pas d'intégration → ServiceUnavailableError."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
            change_type_config={'developpement': {'required': True, 'change_model_code': 'CHG001'}},
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        with patch('integrations.services.IntegrationService.get_by_id', return_value=None):
            with patch('integrations.services.IntegrationService.get_by_type', return_value=None):
                with self.assertRaises(ServiceUnavailableError):
                    runtime._create_servicenow_change_if_required(TEST_ENV)

    @patch('executions.container_workflow_runtime.AuditService')
    def test_with_integration_creates_change(self, mock_audit):
        """Lignes 533-553 — intégration disponible → change créé."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
            change_type_config={'developpement': {'required': True, 'change_model_code': 'CHG001'}},
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        mock_integration = MagicMock()
        mock_integration.base_url = 'https://sn.example.com'
        mock_integration.id = 42

        with patch('integrations.services.IntegrationService.get_by_id', return_value=None):
            with patch('integrations.services.IntegrationService.get_by_type', return_value=mock_integration):
                with patch('adapters.utils.build_auth_headers', return_value={}):
                    with patch('services.servicenow_service.ServiceNowService.create_change',
                               return_value={'number': 'CHG0001234', 'sys_id': 'abc123'}):
                        runtime._create_servicenow_change_if_required(TEST_ENV)

        execution.refresh_from_db()
        self.assertEqual(execution.servicenow_change_id, 'CHG0001234')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_gate_config_integration_not_servicenow_type(self, mock_audit):
        """Lignes 505-511 — intégration gate_config non-servicenow → fallback."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]), created_by=self.user,
            change_type_config={'developpement': {'required': True}},
            gate_config={'servicenow_change': {'integration_id': 999}},
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        bad_integration = MagicMock()
        bad_integration.type = 'aap'  # Not servicenow → should be ignored
        mock_sn = MagicMock()
        mock_sn.base_url = 'https://sn.example.com'
        mock_sn.id = 43

        with patch('integrations.services.IntegrationService.get_by_id', return_value=bad_integration):
            with patch('integrations.services.IntegrationService.get_by_type', return_value=mock_sn):
                with patch('adapters.utils.build_auth_headers', return_value={}):
                    with patch('services.servicenow_service.ServiceNowService.create_change',
                               return_value={'number': 'CHG0009999', 'sys_id': 'xyz999'}):
                        runtime._create_servicenow_change_if_required(TEST_ENV)


# ─── Tests _run_workflow_loop exception handling ──────────────────────────────

@pytest.mark.django_db
class TestRunWorkflowLoopException(TestCase):
    """Lignes 557-590 — _run_workflow_loop exception handling."""

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
        """Lignes 557-590 — ID invalide → exception gérée."""
        execution = Execution.objects.create(
            action=self.wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.RUNNING,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # Call with invalid ID → Execution.DoesNotExist → exception handled
        runtime._run_workflow_loop(99999)  # no exception raised = covered

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_workflow_loop_marks_failed_on_exception(self, mock_audit):
        """Lignes 580-588 — exception → execution marquée FAILED."""
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
    """Lignes 630-637 — _execute_workflow_steps avec step CANCELLED."""

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
        """Lignes 630-637 — step CANCELLED → workflow CANCELLED."""
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
    """Lignes 109-115 — execution_steps n'est pas une liste."""

    def setUp(self):
        self.user = UserFactory(username='load_wf_invalid_user', profile='DBA')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_execution_steps_not_list_returns_empty(self, mock_audit):
        """Lignes 109-115 — steps=dict → warning + return []."""
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
        """Lignes 108-115 — steps=None → warning + return []."""
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
    """Lignes 144-147 — wsp dict avec step_entry dict."""

    def setUp(self):
        self.user = UserFactory(username='step_params_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_parameters_injected(self, mock_audit):
        """Lignes 144-147 — wsp[order] contient parameters → merge."""
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
        """Lignes 141-150 — wsp dict mais pas de clé pour cet ordre → global only."""
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
    """Lignes 222-226 — step sans referenced_action_id."""

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
        """Lignes 222-226 — referenced_action_id absent → FAILED."""
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
    """Lignes 233-250 — referenced_action introuvable → FAILED."""

    def setUp(self):
        self.user = UserFactory(username='exec_step_not_found_user', profile='DBA')
        self.wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[{"order": 1, "name": "Bad Ref Step", "referenced_action_id": 99999}],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_action_not_found_returns_failed(self, mock_audit):
        """Lignes 233-250 — Action.DoesNotExist → FAILED + error logged."""
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
    """Lignes 311-320 — simulation désactivée → fallback direct status update."""

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
        """Lignes 311-324 — simulation off → child COMPLETED via direct update."""
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
    """Lignes 464-468 — run_sync() avec workflow vide."""

    def setUp(self):
        self.user = UserFactory(username='runsync_empty_user', profile='DBA')

    @patch('executions.container_workflow_runtime.AuditService')
    def test_run_sync_empty_workflow_returns_failed(self, mock_audit):
        """Lignes 464-468 — workflow vide → FAILED retourné."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        with patch.object(runtime, '_create_servicenow_change_if_required'):
            result = runtime.run_sync()

        self.assertEqual(result, ExecutionStatus.FAILED)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIn("no steps", execution.error_message)


# ─── Tests _create_servicenow_change_if_required — gate integration valide ───

@pytest.mark.django_db
class TestServiceNowGateIntegrationValid(TestCase):
    """Lignes 503-513 — gate_config integration valide de type servicenow."""

    def setUp(self):
        self.user = UserFactory(username='sn_gate_valid_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_gate_integration_valid_servicenow_used_directly(self, mock_audit):
        """Lignes 503-512 — integration gate_config valide (type=servicenow) → utilisée directement sans fallback."""
        wf = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_steps([self.action_a.id]),
            created_by=self.user,
            change_type_config={'developpement': {'required': True, 'change_model_code': 'CHG001'}},
            gate_config={'servicenow_change': {'integration_id': 42}},
        )
        execution = Execution.objects.create(
            action=wf, user=self.user, environment=TEST_ENV, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)

        valid_integration = MagicMock()
        valid_integration.type = 'servicenow'
        valid_integration.base_url = 'https://sn.example.com'
        valid_integration.id = 42

        with patch('integrations.services.IntegrationService.get_by_id', return_value=valid_integration):
            with patch('integrations.services.IntegrationService.get_by_type') as mock_fallback:
                with patch('adapters.utils.build_auth_headers', return_value={}):
                    with patch('services.servicenow_service.ServiceNowService.create_change',
                               return_value={'number': 'CHG0042', 'sys_id': 'sys42'}):
                        runtime._create_servicenow_change_if_required(TEST_ENV)

        # Le fallback ne doit pas avoir été appelé
        mock_fallback.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.servicenow_change_id, 'CHG0042')


# ─── Tests _execute_workflow_steps — boucle vide + annulation avant step ─────

@pytest.mark.django_db
class TestExecuteWorkflowStepsEdgeCases(TestCase):
    """Lignes 601->640, 604-612 — boucle vide et annulation avant step."""

    def setUp(self):
        self.user = UserFactory(username='wf_edge_user', profile='DBA')
        self.action_a = ActionFactory(
            status=ActionStatus.PUBLISHED, item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_empty_steps_list_completes_immediately(self, mock_audit):
        """Lignes 601->640 — liste vide → for loop skipée → COMPLETED."""
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
        """Lignes 604-612 — annulation détectée avant premier step → CANCELLED."""
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
        """Lignes 629->601 — continuation de la boucle après step COMPLETED."""
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
    """Lignes 582->590 — finally close_old_connections après exception avec cleanup réussi."""

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
        """Lignes 582-588 — exception mais execution déjà FAILED → pas de double update."""
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
        """Lignes 589-590 — finally close_old_connections toujours appelé."""
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
    """Lignes 517-575 — _execute_handler_step: exception, output_mapping, result status."""

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
        """Lignes 525-534 — handler.execute raises → return FAILED, step saved FAILED."""
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
        """Lignes 562-565 — handler returns status=COMPLETED → result COMPLETED."""
        mock_execute.return_value = {'status': ExecutionStatus.COMPLETED, 'raw_output': {}}
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_returns_dict_without_status_fail_closed(self, mock_execute, mock_audit):
        """Lignes 560-565 — handler returns dict sans status → fail-closed FAILED."""
        mock_execute.return_value = {'data': 'value'}  # no 'status' key
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.FAILED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_output_mapping_not_dict_warning(self, mock_execute, mock_audit):
        """Lignes 538-546 — output_mapping not dict → warning, fallback to {}."""
        mock_execute.return_value = {'status': ExecutionStatus.COMPLETED, 'raw_output': {'x': 1}}
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = {**self.wf.execution_steps[0], 'output_mapping': ['invalid']}  # list, not dict

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.COMPLETED)

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute')
    def test_handler_raw_output_extraction(self, mock_execute, mock_audit):
        """Lignes 550-555 — raw_output in result → extracted to _step_outputs."""
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
        """Lignes 550-553 — handler returns non-dict → raw_output = {}."""
        mock_execute.return_value = "scalar"  # not a dict
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        step = self.wf.execution_steps[0]

        result = runtime._execute_step(step)

        self.assertEqual(result, ExecutionStatus.FAILED)  # no status → fail-closed
