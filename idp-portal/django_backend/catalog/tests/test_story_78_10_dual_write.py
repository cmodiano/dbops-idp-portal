"""
Story 78.10 — Tests for dual-write behavior in catalog/services.py.
AC3: When feature flag is True, JSON + normalized tables are written together.
"""
from django.test import TestCase, override_settings

from catalog.models import Action, ActionItemType, ActionStatus
from catalog.models_workflow_definition import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepEdge,
)
from catalog.services import CatalogService
from catalog.tests._workflow_definition_test_helpers import (
    create_unmanaged_tables,
    drop_unmanaged_tables,
)
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from tests.factories import UserFactory
from profiles.models import Profile


class DualWriteCreateActionTests(TestCase):
    """Test dual-write on create_action when feature flag is enabled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS', 'is_admin': 1, 'is_auditor': 0},
        )
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.user = UserFactory(username='testuser', profile='DBOPS')
        self.service = CatalogService()

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=True)
    def test_create_workflow_with_flag_true_writes_normalized(self):
        """When flag is True, create_action also writes to normalized tables."""
        steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform'},
            {'order': 2, 'step_id': 's2', 'name': 'Step 2', 'step_type': 'platform'},
        ]
        action = self.service.create_action(
            action_data={
                'name': 'DW Workflow',
                'engine': 'Oracle',
                'platform': 'AAP',
                'item_type': 'workflow',
                'execution_steps': steps,
            },
            created_by_user=self.user,
        )
        # JSON field written
        self.assertEqual(len(action.execution_steps), 2)
        # Normalized tables also written
        self.assertTrue(WorkflowDefinition.objects.filter(action=action).exists())
        self.assertEqual(
            WorkflowStep.objects.filter(workflow_definition__action=action).count(), 2,
        )

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=False)
    def test_create_workflow_with_flag_false_no_normalized(self):
        """When flag is False, create_action does NOT write to normalized tables."""
        steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform'},
        ]
        action = self.service.create_action(
            action_data={
                'name': 'No DW Workflow',
                'engine': 'Oracle',
                'platform': 'AAP',
                'item_type': 'workflow',
                'execution_steps': steps,
            },
            created_by_user=self.user,
        )
        self.assertFalse(WorkflowDefinition.objects.filter(action=action).exists())


class DualWriteUpdateExecutionStepsTests(TestCase):
    """Test dual-write on update_execution_steps when feature flag is enabled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS', 'is_admin': 1, 'is_auditor': 0},
        )
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.user = UserFactory(username='testuser', profile='DBOPS')
        self.service = CatalogService()
        self.ref_action = Action.objects.create(
            name='Ref Action',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
        )
        self.action = Action.objects.create(
            name='Update WF',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
            created_by=self.user,
        )

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=True)
    def test_update_steps_with_flag_true_syncs_normalized(self):
        """update_execution_steps syncs normalized tables when flag is True."""
        steps = [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform',
             'referenced_action_id': self.ref_action.id, 'on_success_step_ids': ['s2']},
            {'order': 2, 'step_id': 's2', 'name': 'Step 2', 'step_type': 'platform',
             'referenced_action_id': self.ref_action.id, 'on_success_step_ids': []},
        ]
        self.service.update_execution_steps(
            action_id=self.action.id,
            steps=steps,
            user=self.user,
        )
        wf_def = WorkflowDefinition.objects.get(action=self.action)
        self.assertEqual(wf_def.steps.count(), 2)
        self.assertEqual(
            WorkflowStepEdge.objects.filter(
                from_step__workflow_definition=wf_def, edge_type='success',
            ).count(), 1,
        )

    @override_settings(WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED=True)
    def test_update_steps_syncs_after_modification(self):
        """Updating steps a second time replaces normalized data correctly."""
        # First update
        self.service.update_execution_steps(
            action_id=self.action.id,
            steps=[{'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform',
                     'referenced_action_id': self.ref_action.id}],
            user=self.user,
        )
        self.assertEqual(WorkflowStep.objects.filter(
            workflow_definition__action=self.action,
        ).count(), 1)

        # Second update with different steps
        self.service.update_execution_steps(
            action_id=self.action.id,
            steps=[
                {'order': 1, 'step_id': 'new1', 'name': 'New 1', 'step_type': 'platform',
                 'referenced_action_id': self.ref_action.id},
                {'order': 2, 'step_id': 'new2', 'name': 'New 2', 'step_type': 'evaluation'},
            ],
            user=self.user,
        )
        self.assertEqual(WorkflowStep.objects.filter(
            workflow_definition__action=self.action,
        ).count(), 2)
        step_ids = list(WorkflowStep.objects.filter(
            workflow_definition__action=self.action,
        ).order_by('step_order').values_list('step_id', flat=True))
        self.assertEqual(step_ids, ['new1', 'new2'])
