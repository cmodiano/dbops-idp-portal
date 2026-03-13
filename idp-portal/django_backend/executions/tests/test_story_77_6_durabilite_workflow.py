"""
Tests Story 77.6 — Renforcer les tests de durabilité workflow

Ce fichier consolide les tests de durabilité end-to-end des corrections 77.1–77.5 :

AC1 : list/dict forwarding via input_mapping (types natifs) — wrapper de référence
AC2 : output d'un service_call après resume de gate approval — régression croisée
AC3 : output d'un http_request après resume de gate maintenance_window — TEST NOUVEAU
AC4 : extraction d'artifacts platform dans un step en aval — régression croisée
AC5 : absence d'émission d'événement avant commit en cas de rollback après approve
"""
import pytest
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionStepType,
)
from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.template_resolver import StepTemplateResolver
from executions.tasks.gates import resume_container_workflow_from_gate
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory


TEST_ENVIRONMENT = 'developpement'


# ---------------------------------------------------------------------------
# Task 1 — AC3 : http_request + gate maintenance_window (TEST VRAIMENT NOUVEAU)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAC3HttpRequestMaintenanceWindowResume:
    """
    AC3 : Workflow http_request → gate maintenance_window → step platform consommateur.

    Ce scénario n'est couvert par aucun test des stories 77.1–77.5 :
    - 77.1 couvre service_call + gate approval
    - 77.2 couvre les types natifs

    Vérifie que extracted_output du http_request est accessible au step consommateur
    après resume via resume_container_workflow_from_gate.
    """

    def setup_method(self):
        self.user = UserFactory()

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.tasks.gates.AuditService')
    def test_http_request_output_after_maintenance_window_resume(
        self, mock_gate_audit, mock_runtime_audit,
    ):
        """AC3 : http_request extracted_output accessible après resume de gate maintenance_window."""
        consumer_action = ActionFactory(
            name="Consumer Token Action 77-6",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="HTTP + MW Gate + Consumer Workflow 77-6",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    'order': 1,
                    'name': 'Fetch Token',
                    'step_id': 'fetch-token',
                    'step_type': 'http_request',
                    'url': 'https://api.example.com/token',
                    'method': 'GET',
                    'output_mapping': {
                        'token': '$.token',
                        'expires_in': '$.expires_in',
                    },
                    'on_success_step_ids': ['gate-mw'],
                },
                {
                    'order': 2,
                    'name': 'Maintenance Window Gate',
                    'step_id': 'gate-mw',
                    'step_type': 'gate',
                    'gate_type': 'maintenance_window',
                    'timeout_hours': 4,
                    'on_success_step_ids': ['use-token'],
                },
                {
                    'order': 3,
                    'name': 'Use Token',
                    'step_id': 'use-token',
                    'step_type': 'platform',
                    'referenced_action_id': consumer_action.id,
                    'input_mapping': {
                        'auth_token': "{{ steps['fetch-token']['token'] }}",
                    },
                },
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )

        # Construire manuellement l'état post-gate : http_request COMPLETED + gate WAITING
        http_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Fetch Token',
            config_step_id='fetch-token',
            step_type=ExecutionStepType.HTTP_REQUEST,
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        http_step.set_output({
            'raw_output': {'token': 'Bearer abc-xyz', 'expires_in': 3600},
            'extracted_output': {'token': 'Bearer abc-xyz', 'expires_in': 3600},
            'status_context': {'status': 'COMPLETED'},
        })
        http_step.save()

        # AC3 : vérifier que l'output du http_request contient raw_output + extracted_output + status_context
        # (valide la sérialisation/désérialisation de set_output/get_output)
        stored_http = http_step.get_output()
        assert stored_http.get('raw_output') == {'token': 'Bearer abc-xyz', 'expires_in': 3600}, (
            f"AC3 : raw_output incorrect : {stored_http.get('raw_output')!r}"
        )
        assert stored_http.get('extracted_output') == {'token': 'Bearer abc-xyz', 'expires_in': 3600}, (
            f"AC3 : extracted_output incorrect : {stored_http.get('extracted_output')!r}"
        )
        assert stored_http.get('status_context') == {'status': 'COMPLETED'}, (
            f"AC3 : status_context incorrect : {stored_http.get('status_context')!r}"
        )

        gate_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=2,
            step_name='Maintenance Window Gate',
            config_step_id='gate-mw',
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
            started_at=timezone.now(),
        )
        gate_step.set_output({
            'gate_type': 'maintenance_window',
            'gate_conditions': [{'type': 'maintenance_window'}],
        })
        gate_step.save()

        with override_settings(
            SIMULATE_EXECUTION_DEV=True,
            SIMULATE_EXECUTION_STEP_DURATION=0,
            SIMULATE_EXECUTION_FAILURE_RATE=0,
        ):
            with patch(
                'executions.container_workflow_runtime.ContainerWorkflowRuntime._run_child_execution'
            ) as mock_run:
                mock_run.side_effect = lambda child_exec: None
                result = resume_container_workflow_from_gate.run(
                    execution.id,
                    ['use-token'],
                )

        assert result.get('outcome') == 'completed', (
            f"AC3 : resume doit retourner outcome='completed', reçu: {result}"
        )

        # AC3 : le step consommateur a reçu auth_token depuis extracted_output du http_request
        consumer_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='use-token',
        ).first()
        assert consumer_step is not None, "Le step consommateur doit être créé après resume"

        child_id = consumer_step.platform_job_id
        assert child_id, "Le platform step doit avoir un platform_job_id (child execution)"

        child = Execution.objects.get(id=int(child_id))
        child_params = child.get_parameters() or {}
        assert child_params.get('auth_token') == 'Bearer abc-xyz', (
            f"AC3 : auth_token doit être 'Bearer abc-xyz', reçu: {child_params.get('auth_token')!r}"
        )


# ---------------------------------------------------------------------------
# Task 2 — AC1 : list/dict forwarding via input_mapping (types natifs)
# ---------------------------------------------------------------------------

class TestAC1ListDictForwarding:
    """
    AC1 : list et dict forwarding via input_mapping — wrapper de référence.

    Vérifie que les types natifs Python (list, dict, int) sont préservés
    lors du forwarding via StepTemplateResolver et lors du resume de gate.
    """

    def test_list_forwarding_preserved_through_gate_resume(self):
        """
        AC1 (2.2) : extracted_output contenant une liste → StepTemplateResolver préserve le type
        après reconstruction des step_outputs depuis extracted_output.
        """
        # Simuler les step_outputs reconstruits depuis extracted_output après resume
        step_outputs = {
            'discovery': {
                'databases': ['DB1', 'DB2'],
                'count': 2,
            }
        }

        resolver = StepTemplateResolver(step_outputs)
        result = resolver.resolve({
            'extra_vars': {
                'databases': '{{ steps.discovery.databases }}',
                'count': '{{ steps.discovery.count }}',
                'label': 'Patching {{ steps.discovery.count }} databases',
            }
        })

        # AC1 : databases est une liste native
        databases = result['extra_vars']['databases']
        assert databases == ['DB1', 'DB2'], (
            f"AC1 : databases doit être ['DB1', 'DB2'], reçu: {databases!r}"
        )
        assert isinstance(databases, list), (
            f"AC1 : databases doit être une list, reçu: {type(databases).__name__}"
        )

        # count est un entier natif
        count = result['extra_vars']['count']
        assert count == 2
        assert isinstance(count, int)

        # label est un template mixte → string
        assert result['extra_vars']['label'] == 'Patching 2 databases'
        assert isinstance(result['extra_vars']['label'], str)

    def test_dict_forwarding_preserved(self):
        """
        AC1 (2.3) : dict forwarding via StepTemplateResolver — pattern 77.2 test unitaire.
        """
        step_outputs = {
            'config-step': {
                'settings': {'timeout': 30, 'retries': 3},
                'tags': ['critical', 'production'],
            }
        }

        resolver = StepTemplateResolver(step_outputs)
        result = resolver.resolve({
            'config': "{{ steps['config-step']['settings'] }}",
            'labels': "{{ steps['config-step']['tags'] }}",
        })

        # settings est un dict natif
        assert result['config'] == {'timeout': 30, 'retries': 3}
        assert isinstance(result['config'], dict), (
            f"AC1 : settings doit être un dict, reçu: {type(result['config']).__name__}"
        )

        # tags est une liste native
        assert result['labels'] == ['critical', 'production']
        assert isinstance(result['labels'], list), (
            f"AC1 : tags doit être une list, reçu: {type(result['labels']).__name__}"
        )


# ---------------------------------------------------------------------------
# Task 3 — AC2 : service_call après gate approval (régression croisée 77.1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAC2ServiceCallAfterApprovalGate:
    """
    AC2 : service_call output accessible après resume de gate approval.

    Reprend le patron du test test_resume_after_gate_uses_extracted_output de 77.1
    et vérifie explicitement que _build_step_outputs_from_completed utilise extracted_output.
    """

    def setup_method(self):
        self.user = UserFactory()

    def test_build_step_outputs_uses_extracted_output(self):
        """
        AC2 (3.2a) : _build_step_outputs_from_completed utilise extracted_output si présent.
        Régression croisée directe du fix 77.1.
        """
        from unittest.mock import MagicMock
        from executions.tasks.gates import _build_step_outputs_from_completed

        db_step = MagicMock()
        db_step.config_step_id = 'create-change'
        db_step.step_name = 'Create Change'
        db_step.get_output.return_value = {
            'raw_output': {'number': 'CHG9999', 'sys_id': 'sid-999', 'extra': 'data'},
            'extracted_output': {'change_number': 'CHG9999'},
            'status_context': {'status': 'COMPLETED'},
        }

        step_config = {
            'step_id': 'create-change',
            'output_mapping': {'change_number': '$.number'},
        }
        step_config_by_id = {'create-change': step_config}
        step_name_to_id = {'Create Change': 'create-change'}

        step_outputs = {}
        _build_step_outputs_from_completed(
            completed_steps=[db_step],
            step_config_by_id=step_config_by_id,
            step_name_to_id=step_name_to_id,
            step_outputs=step_outputs,
        )

        assert 'create-change' in step_outputs
        # Doit utiliser extracted_output directement (pas recalculer depuis raw)
        assert step_outputs['create-change'] == {'change_number': 'CHG9999'}, (
            f"AC2 : step_outputs doit être {{'change_number': 'CHG9999'}}, "
            f"reçu: {step_outputs['create-change']!r}"
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.tasks.gates.AuditService')
    def test_service_call_output_accessible_after_approval_resume(
        self, mock_gate_audit, mock_runtime_audit,
    ):
        """
        AC2 (3.2b) : le child execution du consumer reçoit le paramètre mappé
        depuis extracted_output du service_call après resume de gate approval.
        """
        consumer_action = ActionFactory(
            name="Consumer Action AC2 77-6",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="AC2 Service Call + Approval Gate 77-6",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    'order': 1,
                    'name': 'Create Change',
                    'step_id': 'create-change',
                    'step_type': 'service_call',
                    'integration_type': 'servicenow',
                    'operation': 'create_change',
                    'output_mapping': {'change_number': '$.number'},
                    'on_success_step_ids': ['gate-approval'],
                },
                {
                    'order': 2,
                    'name': 'Gate Approval',
                    'step_id': 'gate-approval',
                    'step_type': 'gate',
                    'gate_type': 'approval',
                    'timeout_hours': 24,
                    'on_success_step_ids': ['consume-change'],
                },
                {
                    'order': 3,
                    'name': 'Consume Change',
                    'step_id': 'consume-change',
                    'step_type': 'platform',
                    'referenced_action_id': consumer_action.id,
                    'input_mapping': {
                        'change_number': "{{ steps['create-change']['change_number'] }}",
                    },
                },
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )

        # Construire l'état post-gate manuellement (pattern 77.1 AC3 test 2)
        svc_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Create Change',
            config_step_id='create-change',
            step_type=ExecutionStepType.SERVICE_CALL,
            status=ExecutionStepStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        svc_step.set_output({
            'raw_output': {'number': 'CHG9999', 'sys_id': 'sid-999'},
            'extracted_output': {'change_number': 'CHG9999'},
            'status_context': {'status': 'COMPLETED'},
        })
        svc_step.save()

        gate_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=2,
            step_name='Gate Approval',
            config_step_id='gate-approval',
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
            started_at=timezone.now(),
        )
        gate_step.set_output({
            'gate_type': 'approval',
            'gate_conditions': [{'type': 'approval_granted'}],
        })
        gate_step.save()

        with override_settings(
            SIMULATE_EXECUTION_DEV=True,
            SIMULATE_EXECUTION_STEP_DURATION=0,
            SIMULATE_EXECUTION_FAILURE_RATE=0,
        ):
            with patch(
                'executions.container_workflow_runtime.ContainerWorkflowRuntime._run_child_execution'
            ) as mock_run:
                mock_run.side_effect = lambda child_exec: None
                result = resume_container_workflow_from_gate.run(
                    execution.id,
                    ['consume-change'],
                )

        assert result.get('outcome') == 'completed', (
            f"AC2 : resume doit retourner outcome='completed', reçu: {result}"
        )

        consume_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='consume-change',
        ).first()
        assert consume_step is not None, "Le step consommateur doit être créé après resume"

        child_id = consume_step.platform_job_id
        assert child_id, "Le platform step doit avoir un platform_job_id"

        child = Execution.objects.get(id=int(child_id))
        child_params = child.get_parameters() or {}
        assert child_params.get('change_number') == 'CHG9999', (
            f"AC2 : le step consommateur doit recevoir change_number='CHG9999' depuis extracted_output, "
            f"reçu: {child_params.get('change_number')!r}"
        )


# ---------------------------------------------------------------------------
# Task 4 — AC4 : artifacts platform dans step en aval (régression croisée 77.4)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAC4PlatformArtifactsDownstreamStep:
    """
    AC4 : extraction d'artifacts platform dans un step en aval.

    Régression croisée de 77.4 : vérifie que extracted_output et _step_outputs
    contiennent la valeur extraite via output_mapping depuis les artifacts du child.
    """

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_platform_artifact_extracted_and_accessible_downstream(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """
        AC4 (4.2) : platform step avec artifacts.health_report :
        - extracted_output['health_report'] == 'OK' sur le parent step
        - runtime._step_outputs['plat-1']['health_report'] == 'OK'
        """
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        output_mapping = {'health_report': '$.artifacts.health_report'}
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1,
                'name': 'Platform Step',
                'step_id': 'plat-1',
                'referenced_action_id': ref_action.id,
                'output_mapping': output_mapping,
            }],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            """Simule le polling : marque child_step COMPLETED avec artifacts réels."""
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({
                'platform_job_id': 'job-health-123',
                'job_status': 'COMPLETED',
                'artifacts': {'health_report': 'OK'},
            })
            child_step.save()

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        assert parent_step is not None, "Le parent step platform doit exister"

        stored = parent_step.get_output()
        assert stored is not None

        # AC4 : extracted_output contient health_report
        assert stored['extracted_output'].get('health_report') == 'OK', (
            f"AC4 : extracted_output['health_report'] doit être 'OK', "
            f"reçu: {stored['extracted_output'].get('health_report')!r}"
        )

        # AC4 : _step_outputs contient la valeur accessible au step suivant
        assert runtime._step_outputs.get('plat-1', {}).get('health_report') == 'OK', (
            f"AC4 : runtime._step_outputs['plat-1']['health_report'] doit être 'OK', "
            f"reçu: {runtime._step_outputs.get('plat-1', {}).get('health_report')!r}"
        )


# ---------------------------------------------------------------------------
# Task 5 — AC5 : rollback approve sans side effects (régression croisée 77.5)
# ---------------------------------------------------------------------------

def _make_approval_step_77_6(execution, step_name="request-approval-77-6", step_order=1):
    """Crée un step WAITING avec gate_conditions approval_granted."""
    step = ExecutionStep.objects.create(
        execution=execution,
        step_order=step_order,
        step_name=step_name,
        config_step_id=step_name,
        step_type=ExecutionStepType.GATE,
        status=ExecutionStepStatus.WAITING,
    )
    step.set_output({
        "gate_conditions": [{"type": "approval_granted", "timeout_hours": 72}],
        "context_from": [],
    })
    step.save()
    return step


@pytest.mark.django_db
class TestAC5RollbackApproveNoSideEffects(TestCase):
    """
    AC5 : absence d'émission d'événement avant commit en cas de rollback après approve.

    Régression croisée du fix 77.5 : vérifie que emit_approval_granted et
    RunnableStepService.delete ne sont PAS appelés avant le commit (pattern on_commit).
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = UserFactory(username="approver_77_6", profile="DBOPS")
        self.client.force_authenticate(user=self.admin)
        self.integration = IntegrationFactory(type="aap")
        self.action = ActionFactory(
            status="published",
            integration=self.integration,
            execution_steps=[{
                "step_id": "request-approval-77-6",
                "name": "request-approval-77-6",
                "step_type": "gate",
                "gate_type": "approval",
                "on_success_step_ids": [],
            }]
        )
        self.execution = ExecutionFactory(
            action=self.action,
            user=self.admin,
            status=ExecutionStatus.RUNNING,
        )
        self.step = _make_approval_step_77_6(self.execution)

    @patch('executions.views.approval_views._check_approver_permission', return_value=True)
    @patch('executions.services.workflow_events.WorkflowEventService.emit_approval_granted')
    @patch('executions.services.runnable_steps.RunnableStepService.delete')
    def test_approve_rollback_no_side_effects_77_6(
        self, mock_delete, mock_emit, mock_perm,
    ):
        """
        AC5 (5.2) : captureOnCommitCallbacks(execute=False) — callbacks enregistrés
        mais emit_approval_granted et delete non appelés (simulation rollback).

        Vérifie :
        1. Au moins un callback on_commit enregistré (pattern en place)
        2. emit_approval_granted non appelé avant commit
        3. RunnableStepService.delete non appelé avant commit
        """
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"/api/v1/executions/{self.execution.id}/steps/{self.step.id}/approve/",
                {"comment": "AC5 test approve rollback 77.6"},
                format='json',
            )

        self.assertEqual(response.status_code, 200)

        # Le callback on_commit a bien été enregistré (pattern on_commit actif)
        self.assertGreater(
            len(callbacks), 0,
            "AC5 : Au moins un callback on_commit doit être enregistré (pattern on_commit en place)"
        )

        # Les side effects durables ne sont PAS exécutés avant commit (= rollback safe)
        mock_emit.assert_not_called()
        mock_delete.assert_not_called()
