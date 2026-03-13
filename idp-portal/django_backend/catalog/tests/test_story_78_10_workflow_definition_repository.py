"""
Story 78.10 — Tests for WorkflowDefinitionRepository.
AC3: get_steps_from_json, get_steps_from_normalized, get_steps dispatch, sync_from_json.
"""

from django.test import TestCase, override_settings

from catalog.models import Action, ActionItemType, ActionStatus
from catalog.models_workflow_definition import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepEdge,
)
from catalog.tests._workflow_definition_test_helpers import (
    create_unmanaged_tables,
    drop_unmanaged_tables,
)
from catalog.workflow_definition_repository import (
    get_steps,
    get_steps_from_json,
    get_steps_from_normalized,
    sync_from_json,
)
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole


SAMPLE_STEPS_LINEAR = [
    {
        'order': 1,
        'step_id': 'step-uuid-1',
        'name': 'Step 1',
        'step_type': 'platform',
        'referenced_action_id': None,  # Will be set in setUp
    },
    {
        'order': 2,
        'step_id': 'step-uuid-2',
        'name': 'Step 2',
        'step_type': 'platform',
        'referenced_action_id': None,
    },
]

SAMPLE_STEPS_BRANCHED = [
    {
        'order': 1,
        'step_id': 'step-a',
        'name': 'Step A',
        'step_type': 'platform',
        'referenced_action_id': None,
        'on_success_step_ids': ['step-b'],
        'on_error_step_ids': ['step-c'],
        'retry_enabled': False,
    },
    {
        'order': 2,
        'step_id': 'step-b',
        'name': 'Step B',
        'step_type': 'service_call',
        'referenced_action_id': None,
        'integration_type': 'servicenow',
        'operation': 'create_change',
        'retry_enabled': True,
        'retry_max_attempts': 3,
        'retry_interval_seconds': 60,
        'retry_backoff_multiplier': 2.0,
    },
    {
        'order': 3,
        'step_id': 'step-c',
        'name': 'Step C (Error Handler)',
        'step_type': 'evaluation',
        'referenced_action_id': None,
        'input_mapping': {'param': '{{ steps.step_a.output }}'},
        'output_mapping': {'result': '$.data.value'},
        'condition': '{{ environment == "prod" }}',
        'join_policy': 'all_success',
    },
]


class GetStepsFromJsonTests(TestCase):
    """Test get_steps_from_json returns execution_steps as-is."""

    def setUp(self):
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.action = Action.objects.create(
            name='Test Workflow',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
        )

    def test_returns_json_steps(self):
        steps = [{'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform'}]
        self.action.execution_steps = steps
        self.action.save()
        result = get_steps_from_json(self.action)
        self.assertEqual(result, steps)

    def test_returns_empty_for_null(self):
        self.action.execution_steps = None
        self.action.save()
        result = get_steps_from_json(self.action)
        self.assertEqual(result, [])

    def test_returns_empty_for_non_list(self):
        self.action.execution_steps = {'not': 'a list'}
        self.action.save()
        result = get_steps_from_json(self.action)
        self.assertEqual(result, [])


class GetStepsFromNormalizedTests(TestCase):
    """Test get_steps_from_normalized reconstructs JSON format from tables."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.ref_action = Action.objects.create(
            name='Referenced Action',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name='Test Workflow',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
        )

    def test_returns_empty_for_no_definition(self):
        result = get_steps_from_normalized(self.action.id)
        self.assertEqual(result, [])

    def test_linear_workflow_reconstruction(self):
        """Linear workflow (no edges) reconstructed correctly."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
            referenced_action=self.ref_action,
        )
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s2', step_order=2,
            step_name='Step 2', step_type='platform',
            referenced_action=self.ref_action,
        )
        result = get_steps_from_normalized(self.action.id)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['order'], 1)
        self.assertEqual(result[0]['step_id'], 's1')
        self.assertEqual(result[0]['name'], 'Step 1')
        self.assertEqual(result[0]['step_type'], 'platform')
        self.assertEqual(result[0]['referenced_action_id'], self.ref_action.id)
        self.assertEqual(result[1]['order'], 2)

    def test_branched_workflow_with_edges(self):
        """Branched workflow with success/error edges reconstructed correctly."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step_a = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='sa', step_order=1,
            step_name='Step A', step_type='platform',
        )
        step_b = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='sb', step_order=2,
            step_name='Step B', step_type='platform',
        )
        step_c = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='sc', step_order=3,
            step_name='Step C', step_type='evaluation',
        )
        WorkflowStepEdge.objects.create(from_step=step_a, to_step=step_b, edge_type='success')
        WorkflowStepEdge.objects.create(from_step=step_a, to_step=step_c, edge_type='error')

        result = get_steps_from_normalized(self.action.id)
        step_a_dict = result[0]
        self.assertEqual(step_a_dict['on_success_step_ids'], ['sb'])
        self.assertEqual(step_a_dict['on_error_step_ids'], ['sc'])
        # Steps without edges should not have on_success/on_error keys
        self.assertNotIn('on_success_step_ids', result[1])
        self.assertNotIn('on_error_step_ids', result[1])

    def test_step_with_retry_and_mappings(self):
        """Step with retry, input/output mapping, condition reconstructed correctly."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Full Step', step_type='service_call',
            integration_type='servicenow',
            operation='create_change',
            input_mapping={'param': '{{ prev.output }}'},
            output_mapping={'alias': '$.data'},
            condition='{{ env == "prod" }}',
            retry_enabled=True,
            retry_max_attempts=3,
            retry_interval_seconds=60,
            retry_backoff_multiplier=2.0,
            join_policy='all_success',
        )
        result = get_steps_from_normalized(self.action.id)
        step = result[0]
        self.assertEqual(step['integration_type'], 'servicenow')
        self.assertEqual(step['operation'], 'create_change')
        self.assertEqual(step['input_mapping'], {'param': '{{ prev.output }}'})
        self.assertEqual(step['output_mapping'], {'alias': '$.data'})
        self.assertEqual(step['condition'], '{{ env == "prod" }}')
        self.assertTrue(step['retry_enabled'])
        self.assertEqual(step['retry_max_attempts'], 3)
        self.assertEqual(step['retry_interval_seconds'], 60)
        self.assertEqual(step['retry_backoff_multiplier'], 2.0)
        self.assertEqual(step['join_policy'], 'all_success')


class GetStepsDispatchTests(TestCase):
    """Test get_steps dispatches based on feature flag."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.action = Action.objects.create(
            name='Test Workflow',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
            execution_steps=[{'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform'}],
        )

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=False)
    def test_dispatch_reads_from_json_when_disabled(self):
        result = get_steps(self.action)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['step_id'], 's1')

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=True)
    def test_dispatch_reads_from_normalized_when_enabled(self):
        # No normalized data → empty
        result = get_steps(self.action)
        self.assertEqual(result, [])

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=True)
    def test_dispatch_reads_from_normalized_with_data(self):
        sync_from_json(self.action)
        result = get_steps(self.action)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['step_id'], 's1')


class SyncFromJsonTests(TestCase):
    """Test sync_from_json creates/updates normalized tables from JSON."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.ref_action = Action.objects.create(
            name='Referenced Action',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
        )
        self.action = Action.objects.create(
            name='Test Workflow',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
        )

    def test_sync_creates_definition_and_steps(self):
        self.action.execution_steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform',
             'referenced_action_id': self.ref_action.id},
        ]
        self.action.save()
        sync_from_json(self.action)

        self.assertEqual(WorkflowDefinition.objects.filter(action=self.action).count(), 1)
        self.assertEqual(WorkflowStep.objects.filter(
            workflow_definition__action=self.action
        ).count(), 1)

    def test_sync_creates_edges(self):
        self.action.execution_steps = [
            {'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform',
             'on_success_step_ids': ['s2'], 'on_error_step_ids': ['s3']},
            {'order': 2, 'step_id': 's2', 'name': 'S2', 'step_type': 'platform'},
            {'order': 3, 'step_id': 's3', 'name': 'S3', 'step_type': 'evaluation'},
        ]
        self.action.save()
        sync_from_json(self.action)

        edges = WorkflowStepEdge.objects.filter(
            from_step__workflow_definition__action=self.action,
        )
        self.assertEqual(edges.count(), 2)
        self.assertEqual(edges.filter(edge_type='success').count(), 1)
        self.assertEqual(edges.filter(edge_type='error').count(), 1)

    def test_sync_idempotent(self):
        """Double sync_from_json produces no duplicates."""
        self.action.execution_steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform'},
            {'order': 2, 'step_id': 's2', 'name': 'Step 2', 'step_type': 'platform'},
        ]
        self.action.save()
        sync_from_json(self.action)
        sync_from_json(self.action)

        self.assertEqual(WorkflowDefinition.objects.filter(action=self.action).count(), 1)
        self.assertEqual(WorkflowStep.objects.filter(
            workflow_definition__action=self.action,
        ).count(), 2)

    def test_sync_updates_version(self):
        """Second sync increments version."""
        self.action.execution_steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform'},
        ]
        self.action.save()
        sync_from_json(self.action)
        wf_def = WorkflowDefinition.objects.get(action=self.action)
        self.assertEqual(wf_def.version, 1)

        sync_from_json(self.action)
        wf_def.refresh_from_db()
        self.assertEqual(wf_def.version, 2)

    def test_sync_cleans_up_for_empty_steps(self):
        """sync_from_json with no steps removes existing definition."""
        self.action.execution_steps = [
            {'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform'},
        ]
        self.action.save()
        sync_from_json(self.action)
        self.assertEqual(WorkflowDefinition.objects.filter(action=self.action).count(), 1)

        self.action.execution_steps = None
        self.action.save()
        sync_from_json(self.action)
        self.assertEqual(WorkflowDefinition.objects.filter(action=self.action).count(), 0)

    def test_sync_with_retry_fields(self):
        self.action.execution_steps = [
            {
                'order': 1, 'step_id': 's1', 'name': 'Retry Step', 'step_type': 'platform',
                'retry_enabled': True, 'retry_max_attempts': 5,
                'retry_interval_seconds': 30, 'retry_backoff_multiplier': 1.5,
            },
        ]
        self.action.save()
        sync_from_json(self.action)

        step = WorkflowStep.objects.get(
            workflow_definition__action=self.action, step_id='s1',
        )
        self.assertTrue(step.retry_enabled)
        self.assertEqual(step.retry_max_attempts, 5)
        self.assertEqual(step.retry_interval_seconds, 30)
        self.assertEqual(float(step.retry_backoff_multiplier), 1.5)
