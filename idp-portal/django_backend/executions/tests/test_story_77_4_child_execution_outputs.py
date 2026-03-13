"""
Tests Story 77.4 — Extraction des outputs/artifacts réels des child executions

AC1 : raw_output du parent step contient les artifacts réels du child (artifacts, job_status, etc.)
AC2 : output_mapping peut extraire des champs platform réels ($.artifacts.health_report)
AC3 : fallback propre — pas de child platform step (workflow imbriqué ou simulation)
AC4 : child platform step avec output null/vide → raw_output metadata only, pas d'erreur
"""
import pytest
from unittest.mock import patch
from django.test import override_settings
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
from tests.factories import UserFactory, ActionFactory, IntegrationFactory

TEST_ENVIRONMENT = 'developpement'


def _make_platform_step_config(ref_action_id, step_id='plat-1', **kwargs):
    """Construit un step platform référençant une action donnée."""
    step = {
        'order': 1,
        'name': 'Platform Step',
        'step_id': step_id,
        'referenced_action_id': ref_action_id,
    }
    step.update(kwargs)
    return step


# ---------------------------------------------------------------------------
# AC1 — raw_output enrichi avec les artifacts réels du child
# ---------------------------------------------------------------------------

class TestAC1RawOutputEnrichedWithArtifacts:
    """AC1 : raw_output du parent step contient les artifacts réels du child."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_raw_output_contains_artifacts(self, mock_queue, mock_trigger, mock_audit):
        """AC1 : raw_output contient artifacts et job_status du child platform step."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            """Simule polling.py : marque child_step COMPLETED avec artifacts réels."""
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({
                'platform_job_id': 'job-123',
                'job_status': 'COMPLETED',
                'artifacts': {'health_report': 'OK', 'patched_count': 5},
                'platform_logs': 'All tasks succeeded.',
                'failed_tasks': [],
                'changed_hosts': ['host1', 'host2'],
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
        assert parent_step is not None

        stored = parent_step.get_output()
        assert stored is not None
        assert 'raw_output' in stored

        raw = stored['raw_output']

        # AC1 : artifacts réels présents
        assert 'artifacts' in raw, "artifacts absents de raw_output"
        assert raw['artifacts'] == {'health_report': 'OK', 'patched_count': 5}
        assert raw.get('job_status') == 'COMPLETED'
        assert raw.get('platform_job_id') == 'job-123'
        assert raw.get('platform_logs') == 'All tasks succeeded.'

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_metadata_preserved_alongside_artifacts(self, mock_queue, mock_trigger, mock_audit):
        """AC1 : les métadonnées sont préservées avec les artifacts."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({'artifacts': {'health_report': 'OK'}})
            child_step.save()

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        raw = parent_step.get_output()['raw_output']

        # Métadonnées toujours présentes
        assert 'child_execution_id' in raw
        assert 'referenced_action_id' in raw
        assert raw['referenced_action_name'] == ref_action.name
        assert raw['child_status'] == ExecutionStatus.COMPLETED
        assert 'parameters_injected' in raw

        # Artifacts aussi présents
        assert raw['artifacts'] == {'health_report': 'OK'}


# ---------------------------------------------------------------------------
# AC2 — output_mapping peut extraire des champs platform réels
# ---------------------------------------------------------------------------

class TestAC2OutputMappingExtractsRealFields:
    """AC2 : output_mapping avec $.artifacts.health_report fonctionne."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_output_mapping_extracts_artifact_field(self, mock_queue, mock_trigger, mock_audit):
        """AC2 : extracted_output['health_report'] == 'OK' via $.artifacts.health_report."""
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
            execution_steps=[_make_platform_step_config(
                ref_action.id, output_mapping=output_mapping,
            )],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({
                'artifacts': {'health_report': 'OK'},
                'job_status': 'COMPLETED',
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
        stored = parent_step.get_output()

        # AC2 : extracted_output contient le champ mappé
        assert stored['extracted_output'].get('health_report') == 'OK'

        # AC2 : _step_outputs accessible aux steps en aval
        assert runtime._step_outputs.get('plat-1', {}).get('health_report') == 'OK'


# ---------------------------------------------------------------------------
# AC3 — Fallback propre : pas de child platform step (workflow imbriqué)
# ---------------------------------------------------------------------------

class TestAC3FallbackNoChildPlatformStep:
    """AC3 : workflow imbriqué → raw_output metadata only, aucune exception."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    def test_nested_workflow_no_child_platform_step(self, mock_audit):
        """AC3 : step platform sur workflow imbriqué → raw_output metadata only."""
        user = UserFactory()
        # Action de type WORKFLOW (pas ACTION) → pas de trigger_platform_job
        inner_workflow = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[],  # Workflow vide → COMPLETED immédiat
            created_by=user,
        )
        outer_workflow = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(inner_workflow.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=outer_workflow,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()  # Ne doit pas lever d'exception

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        assert parent_step is not None

        stored = parent_step.get_output()
        assert stored is not None
        raw = stored['raw_output']

        # AC3 : metadata présente
        assert 'child_execution_id' in raw
        assert 'referenced_action_id' in raw
        assert 'child_status' in raw

        # AC3 : pas de clés platform (pas d'artifacts, job_status, etc.)
        assert 'artifacts' not in raw
        assert 'job_status' not in raw
        assert 'platform_job_id' not in raw

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_nested_workflow_with_inner_platform_step_does_not_pollute(
        self, mock_queue, mock_trigger, mock_audit,
    ):
        """AC3 (régression C1) : workflow imbriqué non-vide avec platform step interne →
        raw_output de l'outer step ne contient PAS les clés du step interne."""
        user = UserFactory()
        integration = IntegrationFactory()
        # Action inner (platform) référencée par le workflow interne
        inner_ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        # Workflow interne avec un platform step
        inner_workflow = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(inner_ref_action.id, step_id='inner-plat-1')],
            created_by=user,
        )
        outer_workflow = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(inner_workflow.id, step_id='outer-plat-1')],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=outer_workflow,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            """Marque le inner platform step COMPLETED avec des artifacts."""
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({
                'platform_job_id': 'inner-job-999',
                'job_status': 'COMPLETED',
                'artifacts': {'inner_result': 'should_not_leak'},
            })
            child_step.save()

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()

        # L'outer parent_step (sur l'outer execution) est le step de type PLATFORM
        # qui référence le inner_workflow
        outer_parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        assert outer_parent_step is not None

        stored = outer_parent_step.get_output()
        assert stored is not None
        raw = stored['raw_output']

        # AC3 : l'outer raw_output ne doit PAS contenir les artifacts du inner step
        assert 'artifacts' not in raw, (
            "Les artifacts du step interne ne doivent pas polluer le raw_output outer"
        )
        assert 'platform_job_id' not in raw
        assert 'inner_result' not in str(raw)

        # AC3 : metadata outer présente
        assert 'child_execution_id' in raw
        assert 'referenced_action_id' in raw
        assert raw['referenced_action_id'] == inner_workflow.id

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_action_without_integration_metadata_only(self, mock_queue, mock_trigger, mock_audit):
        """M2 : action sans intégration → child FAILED, raw_output metadata only, pas d'erreur."""
        user = UserFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=None,  # Pas d'intégration
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()  # Ne doit pas lever d'exception

        # apply_async ne doit PAS être appelé
        assert not mock_trigger.apply_async.called

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        assert parent_step is not None

        stored = parent_step.get_output()
        assert stored is not None
        raw = stored['raw_output']

        # Metadata présente
        assert 'child_execution_id' in raw
        assert 'referenced_action_id' in raw
        assert raw['child_status'] == ExecutionStatus.FAILED

        # Aucune clé platform (pas de child_platform_step créé)
        assert 'artifacts' not in raw
        assert 'job_status' not in raw
        assert 'platform_job_id' not in raw


# ---------------------------------------------------------------------------
# AC4 — Child platform step avec output null/vide
# ---------------------------------------------------------------------------

class TestAC4EmptyChildPlatformOutput:
    """AC4 : child platform step existe mais output null ou {} → raw_output metadata only."""

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_empty_output_dict_metadata_only(self, mock_queue, mock_trigger, mock_audit):
        """AC4 : child_step.get_output() == {} → raw_output metadata only."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            child_step.set_output({})  # Output vide
            child_step.save()

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()  # Ne doit pas lever d'exception

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        stored = parent_step.get_output()
        assert stored is not None
        raw = stored['raw_output']

        # AC4 : metadata présente, pas de clés platform supplémentaires
        assert 'child_execution_id' in raw
        assert 'child_status' in raw
        assert raw['child_status'] == ExecutionStatus.COMPLETED

    @pytest.mark.django_db
    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.trigger_platform_job')
    @patch('executions.container_workflow_runtime.get_platform_queue', return_value='default')
    def test_null_output_metadata_only(self, mock_queue, mock_trigger, mock_audit):
        """AC4 : child_step.get_output() == None → raw_output metadata only, pas d'erreur."""
        user = UserFactory()
        integration = IntegrationFactory()
        ref_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            integration=integration,
            created_by=user,
        )
        workflow_action = ActionFactory(
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[_make_platform_step_config(ref_action.id)],
            created_by=user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        def _trigger_side_effect(kwargs, queue):
            exec_step_id = kwargs['execution_step_id']
            child_step = ExecutionStep.objects.get(id=exec_step_id)
            child_step.status = ExecutionStepStatus.COMPLETED
            child_step.completed_at = timezone.now()
            # Ne pas appeler set_output → output reste None
            child_step.save()

        mock_trigger.apply_async.side_effect = _trigger_side_effect

        with override_settings(SIMULATE_EXECUTION_DEV=False):
            runtime = ContainerWorkflowRuntime(execution)
            runtime.run_sync()  # Ne doit pas lever d'exception

        parent_step = ExecutionStep.objects.filter(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
        ).first()
        stored = parent_step.get_output()
        assert stored is not None
        raw = stored['raw_output']

        # AC4 : metadata présente uniquement
        assert 'child_execution_id' in raw
        assert 'child_status' in raw
        assert 'artifacts' not in raw
