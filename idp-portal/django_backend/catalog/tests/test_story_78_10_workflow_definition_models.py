"""
Story 78.10 — Tests for WorkflowDefinition, WorkflowStep, WorkflowStepEdge models.
AC1: ORM creation, FK constraints, unique_together, edge type validation.
"""
from django.db import IntegrityError
from django.test import TestCase

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
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole


class WorkflowDefinitionModelTests(TestCase):
    """Test WorkflowDefinition, WorkflowStep, WorkflowStepEdge ORM operations."""

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
        )
        self.ref_action = Action.objects.create(
            name='Referenced Action',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
        )

    def test_create_workflow_definition(self):
        """AC1: WorkflowDefinition can be created with FK to ActionsCatalog."""
        wf_def = WorkflowDefinition.objects.create(
            action=self.action,
            version=1,
        )
        self.assertEqual(wf_def.action_id, self.action.id)
        self.assertEqual(wf_def.version, 1)
        self.assertIsNotNone(wf_def.id)

    def test_create_workflow_step(self):
        """AC1: WorkflowStep can be created with FK to WorkflowDefinition."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step = WorkflowStep.objects.create(
            workflow_definition=wf_def,
            step_id='step-uuid-1',
            step_order=1,
            step_name='Step 1',
            step_type='platform',
            referenced_action=self.ref_action,
        )
        self.assertEqual(step.workflow_definition_id, wf_def.id)
        self.assertEqual(step.step_id, 'step-uuid-1')
        self.assertEqual(step.step_type, 'platform')
        self.assertEqual(step.referenced_action_id, self.ref_action.id)

    def test_create_workflow_step_edge(self):
        """AC1: WorkflowStepEdge can be created with success/error edge type."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step1 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        step2 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s2', step_order=2,
            step_name='Step 2', step_type='platform',
        )
        edge = WorkflowStepEdge.objects.create(
            from_step=step1, to_step=step2, edge_type='success',
        )
        self.assertEqual(edge.from_step_id, step1.id)
        self.assertEqual(edge.to_step_id, step2.id)
        self.assertEqual(edge.edge_type, 'success')

    def test_error_edge_type(self):
        """AC1: Error edge type is valid."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step1 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        step2 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s2', step_order=2,
            step_name='Step 2', step_type='platform',
        )
        edge = WorkflowStepEdge.objects.create(
            from_step=step1, to_step=step2, edge_type='error',
        )
        self.assertEqual(edge.edge_type, 'error')

    def test_unique_together_step_id_per_definition(self):
        """AC1: (workflow_definition, step_id) must be unique."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='dup-id', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        with self.assertRaises(IntegrityError):
            WorkflowStep.objects.create(
                workflow_definition=wf_def, step_id='dup-id', step_order=2,
                step_name='Step 2', step_type='platform',
            )

    def test_unique_together_edge(self):
        """AC1: (from_step, to_step, edge_type) must be unique."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step1 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        step2 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s2', step_order=2,
            step_name='Step 2', step_type='platform',
        )
        WorkflowStepEdge.objects.create(from_step=step1, to_step=step2, edge_type='success')
        with self.assertRaises(IntegrityError):
            WorkflowStepEdge.objects.create(from_step=step1, to_step=step2, edge_type='success')

    def test_cascade_delete_definition_deletes_steps(self):
        """AC1: Deleting a definition cascades to steps and edges."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step1 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        step2 = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s2', step_order=2,
            step_name='Step 2', step_type='platform',
        )
        WorkflowStepEdge.objects.create(from_step=step1, to_step=step2, edge_type='success')

        wf_def.delete()
        self.assertEqual(WorkflowStep.objects.count(), 0)
        self.assertEqual(WorkflowStepEdge.objects.count(), 0)

    def test_step_ordering(self):
        """Steps are ordered by step_order (Meta.ordering)."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s3', step_order=3,
            step_name='Step 3', step_type='platform',
        )
        WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        steps = list(wf_def.steps.values_list('step_order', flat=True))
        self.assertEqual(steps, [1, 3])

    def test_step_nullable_fields(self):
        """Nullable fields can be None."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step = WorkflowStep.objects.create(
            workflow_definition=wf_def, step_id='s1', step_order=1,
            step_name='Step 1', step_type='platform',
        )
        self.assertIsNone(step.referenced_action_id)
        self.assertIsNone(step.integration_type)
        self.assertIsNone(step.operation)
        self.assertIsNone(step.input_mapping)
        self.assertIsNone(step.output_mapping)
        self.assertIsNone(step.condition)
        self.assertFalse(step.retry_enabled)
        self.assertIsNone(step.retry_max_attempts)
        self.assertIsNone(step.join_policy)

    def test_step_with_all_fields(self):
        """All step fields can be populated."""
        wf_def = WorkflowDefinition.objects.create(action=self.action, version=1)
        step = WorkflowStep.objects.create(
            workflow_definition=wf_def,
            step_id='full-step',
            step_order=1,
            step_name='Full Step',
            step_type='service_call',
            referenced_action=self.ref_action,
            integration_type='servicenow',
            operation='create_change',
            input_mapping={'param': '{{ steps.prev.field }}'},
            output_mapping={'alias': '$.json.path'},
            condition='{{ environment == "prod" }}',
            retry_enabled=True,
            retry_max_attempts=3,
            retry_interval_seconds=60,
            retry_backoff_multiplier=2.0,
            join_policy='all_success',
        )
        step.refresh_from_db()
        self.assertEqual(step.step_type, 'service_call')
        self.assertEqual(step.integration_type, 'servicenow')
        self.assertTrue(step.retry_enabled)
        self.assertEqual(step.retry_max_attempts, 3)
        self.assertEqual(step.join_policy, 'all_success')
