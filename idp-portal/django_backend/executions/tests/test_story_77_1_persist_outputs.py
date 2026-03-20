"""
Tests Story 77.1 — Persister les outputs de tous les handlers de steps

AC1 : raw_output + extracted_output + status_context persistés dans ExecutionStep.output
AC2 : resume reconstruit _step_outputs depuis extracted_output (si présent)
AC3 : test end-to-end service_call → gate → step consommateur
"""
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone

from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionStepType,
)
from executions.container_workflow_runtime import ContainerWorkflowRuntime
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


TEST_ENVIRONMENT = 'developpement'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler_step(step_id, step_type='service_call', output_mapping=None, **kwargs):
    """Build a handler step config (service_call / http_request / evaluation)."""
    step = {
        'order': 1,
        'name': f'Step {step_id}',
        'step_id': step_id,
        'step_type': step_type,
        'integration_type': 'servicenow',
        'operation': 'create_change',
    }
    if output_mapping is not None:
        step['output_mapping'] = output_mapping
    step.update(kwargs)
    return step


def _make_platform_step(step_id, referenced_action_id, output_mapping=None, **kwargs):
    """Build a platform (referenced action) step config."""
    step = {
        'order': 1,
        'name': f'Platform {step_id}',
        'step_id': step_id,
        'referenced_action_id': referenced_action_id,
    }
    if output_mapping is not None:
        step['output_mapping'] = output_mapping
    step.update(kwargs)
    return step


# ---------------------------------------------------------------------------
# AC1 — Tests de persistance dans ExecutionStep.output
# ---------------------------------------------------------------------------

class TestAC1FinalizeHandlerStepPersistsOutput:
    """
    AC1 : _finalize_handler_step persiste raw_output + extracted_output + status_context
    dans ExecutionStep.output avant de sauvegarder.
    """

    @pytest.mark.django_db
    def test_finalize_handler_step_persists_standard_format(self):
        """AC1 : set_output() appelé avec structure standard {raw_output, extracted_output, status_context}."""
        user = UserFactory()
        workflow_action = ActionFactory(
            name="Test Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )
        parent_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='service-call-step',
            config_step_id='svc-step',
            step_type=ExecutionStepType.SERVICE_CALL,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        runtime = ContainerWorkflowRuntime(execution)
        output_mapping = {'change_number': '$.number', 'sys_id': '$.sys_id'}
        raw_handler_result = {
            'status': ExecutionStatus.COMPLETED,
            'raw_output': {'number': 'CHG001', 'sys_id': 'abc123', 'extra': 'data'},
        }

        runtime._finalize_handler_step(
            result=raw_handler_result,
            parent_step=parent_step,
            step_id='svc-step',
            output_mapping=output_mapping,
        )

        # Recharger depuis la BD
        parent_step.refresh_from_db()
        stored = parent_step.get_output()

        assert stored is not None, "ExecutionStep.output doit être persisté"
        assert 'raw_output' in stored, "raw_output manquant"
        assert 'extracted_output' in stored, "extracted_output manquant"
        assert 'status_context' in stored, "status_context manquant"

        assert stored['raw_output'] == {'number': 'CHG001', 'sys_id': 'abc123', 'extra': 'data'}
        assert stored['extracted_output'] == {'change_number': 'CHG001', 'sys_id': 'abc123'}
        assert stored['status_context']['status'] == ExecutionStepStatus.COMPLETED

    @pytest.mark.django_db
    def test_finalize_handler_step_raw_result_not_wrapped(self):
        """AC1 : si le résultat n'a pas de clé 'raw_output', tout le résultat devient raw_output."""
        user = UserFactory()
        workflow_action = ActionFactory(
            name="Test Workflow2",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )
        parent_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='eval-step',
            config_step_id='eval-1',
            step_type=ExecutionStepType.EVALUATION,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        runtime = ContainerWorkflowRuntime(execution)
        flat_result = {
            'status': ExecutionStatus.COMPLETED,
            'result_value': True,
            'score': 95,
        }
        output_mapping = {'passed': '$.result_value', 'score': '$.score'}

        runtime._finalize_handler_step(
            result=flat_result,
            parent_step=parent_step,
            step_id='eval-1',
            output_mapping=output_mapping,
        )

        parent_step.refresh_from_db()
        stored = parent_step.get_output()

        assert stored is not None
        assert stored['raw_output'] == flat_result
        assert stored['extracted_output'] == {'passed': True, 'score': 95}

    @pytest.mark.django_db
    def test_finalize_handler_step_http_request_persists_standard_format(self):
        """AC1 : _finalize_handler_step persiste le format standard pour http_request (comme service_call)."""
        user = UserFactory()
        workflow_action = ActionFactory(
            name="Test Workflow HTTP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )
        parent_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='http-step',
            config_step_id='http-1',
            step_type=ExecutionStepType.HTTP_REQUEST,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        runtime = ContainerWorkflowRuntime(execution)
        # Structure typique retournée par HttpRequestHandler
        http_result = {
            'status': ExecutionStatus.COMPLETED,
            'raw_output': {'id': 42, 'token': 'abc-xyz', 'expires_in': 3600},
        }
        output_mapping = {'token': '$.token', 'expires_in': '$.expires_in'}

        runtime._finalize_handler_step(
            result=http_result,
            parent_step=parent_step,
            step_id='http-1',
            output_mapping=output_mapping,
        )

        parent_step.refresh_from_db()
        stored = parent_step.get_output()

        assert stored is not None
        assert 'raw_output' in stored
        assert 'extracted_output' in stored
        assert 'status_context' in stored
        assert stored['raw_output'] == {'id': 42, 'token': 'abc-xyz', 'expires_in': 3600}
        assert stored['extracted_output'] == {'token': 'abc-xyz', 'expires_in': 3600}

    @pytest.mark.django_db
    def test_finalize_handler_step_step_id_none_no_output_set(self):
        """AC1 : sans step_id, la structure standard est quand même persistée (extracted_output vide)."""
        user = UserFactory()
        workflow_action = ActionFactory(
            name="Test Workflow3",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.RUNNING,
        )
        parent_step = ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='no-id-step',
            step_type=ExecutionStepType.SERVICE_CALL,
            status=ExecutionStepStatus.RUNNING,
            started_at=timezone.now(),
        )

        runtime = ContainerWorkflowRuntime(execution)
        result = {'status': ExecutionStatus.COMPLETED, 'data': 'value'}

        runtime._finalize_handler_step(
            result=result,
            parent_step=parent_step,
            step_id=None,
            output_mapping={},
        )

        parent_step.refresh_from_db()
        stored = parent_step.get_output()

        # _finalize_handler_step persiste toujours le format standard
        assert stored is not None, "Le format standard doit être persisté même sans step_id"
        assert 'raw_output' in stored
        assert 'extracted_output' in stored
        assert 'status_context' in stored
        assert stored['raw_output'] == result
        assert stored['extracted_output'] == {}  # output_mapping vide


# ---------------------------------------------------------------------------
# AC1 — Tests de persistance dans _execute_platform_step
# ---------------------------------------------------------------------------

class TestAC1PlatformStepPersistsStandardFormat:
    """AC1 : _execute_platform_step persiste la structure standard."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    def test_platform_step_output_has_standard_keys(self, mock_audit):
        """AC1 : après exécution d'un platform step, ExecutionStep.output a raw_output + extracted_output."""
        user = UserFactory()
        ref_action = ActionFactory(
            name="Ref Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=user,
        )
        workflow_action = ActionFactory(
            name="Platform Test Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[{
                'order': 1,
                'name': 'Platform Step',
                'step_id': 'plat-1',
                'referenced_action_id': ref_action.id,
                'output_mapping': {'child_id': '$.child_execution_id'},
            }],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        from django.test import override_settings
        with override_settings(
            SIMULATE_EXECUTION_DEV=True,
            SIMULATE_EXECUTION_STEP_DURATION=0,
            SIMULATE_EXECUTION_FAILURE_RATE=0,
        ):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # Récupérer le step platform créé
        platform_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='plat-1',
        ).first()

        assert platform_step is not None, "Le platform step doit exister en BD"
        stored = platform_step.get_output()

        assert stored is not None, "Le platform step doit avoir un output persisté"
        assert 'raw_output' in stored, "raw_output manquant dans le platform step output"
        assert 'extracted_output' in stored, "extracted_output manquant dans le platform step output"
        assert 'child_execution_id' in stored['raw_output'], "child_execution_id absent de raw_output"


# ---------------------------------------------------------------------------
# AC2 — Tests de reconstruction _step_outputs au resume
# ---------------------------------------------------------------------------

class TestAC2ResumeUsesExtractedOutput:
    """AC2 : resume_container_workflow_from_gate utilise extracted_output si présent."""

    def test_resume_prefers_extracted_output_over_recalculation(self):
        """AC2 : si extracted_output présent dans get_output(), l'utiliser directement."""
        from executions.tasks.gates import _build_step_outputs_from_completed

        # Simuler un db_step avec le format standard
        db_step = MagicMock()
        db_step.config_step_id = 'svc-step'
        db_step.step_name = 'Service Call'
        db_step.get_output.return_value = {
            'raw_output': {'number': 'CHG001', 'sys_id': 'abc123'},
            'extracted_output': {'change_number': 'CHG001', 'sys_id': 'abc123'},
            'status_context': {'status': 'COMPLETED'},
        }

        step_config = {
            'step_id': 'svc-step',
            'output_mapping': {'change_number': '$.number', 'sys_id': '$.sys_id'},
        }
        step_config_by_id = {'svc-step': step_config}
        step_name_to_id = {'Service Call': 'svc-step'}

        step_outputs = {}
        _build_step_outputs_from_completed(
            completed_steps=[db_step],
            step_config_by_id=step_config_by_id,
            step_name_to_id=step_name_to_id,
            step_outputs=step_outputs,
        )

        assert 'svc-step' in step_outputs
        # Doit utiliser extracted_output directement
        assert step_outputs['svc-step'] == {'change_number': 'CHG001', 'sys_id': 'abc123'}

    def test_resume_fallback_when_no_extracted_output(self):
        """AC2 : si extracted_output absent (ancien format), recalculer via OutputExtractor."""
        from executions.tasks.gates import _build_step_outputs_from_completed

        db_step = MagicMock()
        db_step.config_step_id = 'svc-step'
        db_step.step_name = 'Service Call'
        # Ancien format : juste le raw output sans structure standard
        db_step.get_output.return_value = {
            'number': 'CHG001',
            'sys_id': 'abc123',
            'extra': 'data',
        }

        step_config = {
            'step_id': 'svc-step',
            'output_mapping': {'change_number': '$.number', 'sys_id': '$.sys_id'},
        }
        step_config_by_id = {'svc-step': step_config}
        step_name_to_id = {}

        step_outputs = {}
        _build_step_outputs_from_completed(
            completed_steps=[db_step],
            step_config_by_id=step_config_by_id,
            step_name_to_id=step_name_to_id,
            step_outputs=step_outputs,
        )

        assert 'svc-step' in step_outputs
        # Doit recalculer depuis raw via OutputExtractor
        assert step_outputs['svc-step'] == {'change_number': 'CHG001', 'sys_id': 'abc123'}

    def test_resume_fallback_without_output_mapping(self):
        """AC2 : sans output_mapping, utiliser raw_output tel quel (comportement actuel)."""
        from executions.tasks.gates import _build_step_outputs_from_completed

        db_step = MagicMock()
        db_step.config_step_id = 'plat-step'
        db_step.step_name = 'Platform Step'
        db_step.get_output.return_value = {
            'raw_output': {'child_execution_id': 42, 'child_status': 'COMPLETED'},
            'extracted_output': {},
            'status_context': {'status': 'COMPLETED'},
        }

        step_config = {
            'step_id': 'plat-step',
            # Pas d'output_mapping
        }
        step_config_by_id = {'plat-step': step_config}
        step_name_to_id = {}

        step_outputs = {}
        _build_step_outputs_from_completed(
            completed_steps=[db_step],
            step_config_by_id=step_config_by_id,
            step_name_to_id=step_name_to_id,
            step_outputs=step_outputs,
        )

        # Sans output_mapping, extracted_output est vide → utiliser extracted_output {}
        assert 'plat-step' in step_outputs
        assert step_outputs['plat-step'] == {}


# ---------------------------------------------------------------------------
# AC3 — Test end-to-end service_call → gate → step consommateur
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAC3EndToEndServiceCallGateConsumer:
    """
    AC3 : Workflow avec service_call (output_mapping) → gate approval → step qui consomme l'output.
    Vérifie que le step en aval reçoit correctement les données du service_call après resume.
    """

    def setup_method(self):
        self.user = UserFactory()

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.tasks.gates.AuditService')
    def test_service_call_output_persisted_before_gate(self, mock_gate_audit, mock_runtime_audit):
        """AC3 : le service_call step a raw_output + extracted_output persistés avant la gate WAITING."""
        from django.test import override_settings

        consumer_action = ActionFactory(
            name="Consumer Action",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="E2E Durability Workflow",
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
                    'output_mapping': {
                        'change_number': '$.number',
                        'sys_id': '$.sys_id',
                    },
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
            status=ExecutionStatus.SUBMITTED,
        )

        # Mock le service_call handler pour retourner un résultat réaliste
        mock_svc_result = {
            'status': ExecutionStatus.COMPLETED,
            'raw_output': {'number': 'CHG0012345', 'sys_id': 'abc-sys-id-123', 'state': 1},
        }

        with override_settings(
            SIMULATE_EXECUTION_DEV=False,
            SIMULATE_EXECUTION_STEP_DURATION=0,
        ):
            with patch('executions.step_handlers.service_call_handler.ServiceCallHandler.execute',
                       return_value=mock_svc_result):
                runtime = ContainerWorkflowRuntime(execution)
                runtime.run_sync()

        # Vérifier que le service_call step a raw_output + extracted_output persistés
        svc_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='create-change',
        ).first()

        assert svc_step is not None, "Le step service_call doit être créé"
        assert svc_step.status == ExecutionStepStatus.COMPLETED

        stored = svc_step.get_output()
        assert stored is not None, "ExecutionStep.output doit être persisté pour service_call"
        assert 'raw_output' in stored
        assert 'extracted_output' in stored
        assert stored['raw_output'] == {'number': 'CHG0012345', 'sys_id': 'abc-sys-id-123', 'state': 1}
        assert stored['extracted_output']['change_number'] == 'CHG0012345'
        assert stored['extracted_output']['sys_id'] == 'abc-sys-id-123'

        # Vérifier que la gate est en WAITING
        gate_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='gate-approval',
        ).first()
        assert gate_step is not None
        assert gate_step.status == ExecutionStepStatus.WAITING

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.tasks.gates.AuditService')
    def test_resume_after_gate_uses_extracted_output(self, mock_gate_audit, mock_runtime_audit):
        """AC3 : après resume de la gate, le step consommateur reçoit les outputs du service_call."""
        from django.test import override_settings
        from executions.tasks.gates import resume_container_workflow_from_gate

        consumer_action = ActionFactory(
            name="Consumer Action 2",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="E2E Resume Durability Workflow",
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
                    'output_mapping': {
                        'change_number': '$.number',
                    },
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

        # Simuler l'état après exécution service_call + gate WAITING
        # Créer le service_call step avec le format standard persisté
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

        # Créer la gate en WAITING
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
            with patch('executions.platform_step_executor.PlatformStepExecutor._run_child_execution') as mock_run:
                mock_run.side_effect = lambda *args, **kwargs: None

                result = resume_container_workflow_from_gate.run(
                    execution.id,  # execution_id
                    ['consume-change'],  # on_success_step_ids
                )

        assert result.get('outcome') != 'step_not_found', f"Resume a échoué : {result}"

        # AC3 : vérifier que le step consommateur a reçu change_number depuis extracted_output
        consume_step = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='consume-change',
        ).first()
        assert consume_step is not None, "Le step consommateur doit être créé après resume"

        # Le child execution est créé avec les paramètres résolus (input_mapping)
        child_id = consume_step.platform_job_id
        assert child_id, "Le platform step doit avoir un platform_job_id (child execution)"
        child = Execution.objects.get(id=int(child_id))
        child_params = child.get_parameters() or {}
        assert child_params.get('change_number') == 'CHG9999', (
            f"AC3 : le step consommateur doit recevoir change_number='CHG9999' depuis extracted_output, "
            f"reçu: {child_params.get('change_number')!r}"
        )
