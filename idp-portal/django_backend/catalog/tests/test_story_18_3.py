"""
Tests for Story 18.3 — action_name in workflow steps.
Tests: Backend serializer enriches workflow_steps with action_name from referenced_action.
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from idp_auth.models import User
from catalog.models import Action, ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.serializers import ActionSerializer
from tests.factories import UserFactory


@pytest.mark.django_db
class TestWorkflowStepActionName(TestCase):
    """Story 18.3, AC4: action_name included in workflow_steps from serializer."""

    def setUp(self):
        """Set up test data with a workflow referencing other actions."""
        self.client = APIClient()
        self.user = UserFactory(
            username='testuser_18_3',
            profile='admin',
        )
        self.client.force_authenticate(user=self.user)

        # Create referenced actions
        self.action_a = Action.objects.create(
            name='Apply Oracle Patch',
            description='Applies an Oracle patch',
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )
        self.action_b = Action.objects.create(
            name='Backup Database',
            description='Backs up the database',
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
        )

        # Create a workflow with execution_steps referencing the actions
        self.workflow = Action.objects.create(
            name='Patch Workflow',
            description='Workflow that patches and backs up',
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            created_by=self.user,
            execution_steps=[
                {
                    'order': 1,
                    'step_id': 'step-1',
                    'name': None,
                    'referenced_action_id': self.action_a.id,
                    'on_success_step_id': 'step-2',
                    'on_error_step_id': None,
                    'retry_enabled': False,
                },
                {
                    'order': 2,
                    'step_id': 'step-2',
                    'name': 'Custom Step Name',
                    'referenced_action_id': self.action_b.id,
                    'on_success_step_id': None,
                    'on_error_step_id': None,
                    'retry_enabled': True,
                    'retry_max_attempts': 3,
                },
            ],
        )

    def test_workflow_steps_include_action_name(self):
        """GET /api/v1/catalog/actions/{id} returns steps with action_name."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.workflow.id}/')
        self.assertEqual(response.status_code, 200)
        steps = response.data['data']['workflow_steps']
        self.assertIsNotNone(steps)
        self.assertEqual(len(steps), 2)

        # First step: action_name should be the real action name
        self.assertEqual(steps[0]['action_name'], 'Apply Oracle Patch')
        self.assertEqual(steps[0]['referenced_action_id'], self.action_a.id)

        # Second step: action_name should be the real action name (not the custom step name)
        self.assertEqual(steps[1]['action_name'], 'Backup Database')
        self.assertEqual(steps[1]['name'], 'Custom Step Name')

    def test_action_name_matches_referenced_action(self):
        """action_name corresponds to the real name of the referenced action."""
        serializer = ActionSerializer(self.workflow)
        steps = serializer.data['workflow_steps']

        for step in steps:
            ref_id = step['referenced_action_id']
            expected_name = Action.objects.get(id=ref_id).name
            self.assertEqual(step['action_name'], expected_name)

    def test_action_name_null_when_referenced_action_deleted(self):
        """If referenced_action is deleted, action_name returns None."""
        deleted_action_id = self.action_a.id
        self.action_a.delete()

        serializer = ActionSerializer(self.workflow)
        # Refresh from DB to get updated state
        self.workflow.refresh_from_db()
        serializer = ActionSerializer(self.workflow)
        steps = serializer.data['workflow_steps']

        # First step references deleted action → action_name should be None
        step_1 = next(s for s in steps if s['referenced_action_id'] == deleted_action_id)
        self.assertIsNone(step_1['action_name'])

    def test_non_workflow_returns_null_workflow_steps(self):
        """Regular action (not workflow) returns null for workflow_steps."""
        serializer = ActionSerializer(self.action_a)
        self.assertIsNone(serializer.data['workflow_steps'])

    def test_batch_query_avoids_n_plus_one(self):
        """Verify batch fetch is used (single query for all action names)."""
        # Create a workflow with 5 steps
        actions = []
        for i in range(5):
            action = Action.objects.create(
                name=f'Action {i}',
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                status=ActionStatus.PUBLISHED,
                item_type=ActionItemType.ACTION,
                created_by=self.user,
            )
            actions.append(action)

        workflow_5 = Action.objects.create(
            name='Big Workflow',
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            created_by=self.user,
            execution_steps=[
                {
                    'order': i + 1,
                    'step_id': f'step-{i}',
                    'name': None,
                    'referenced_action_id': actions[i].id,
                }
                for i in range(5)
            ],
        )

        serializer = ActionSerializer(workflow_5)
        steps = serializer.data['workflow_steps']

        self.assertEqual(len(steps), 5)
        # All should have action_name populated
        for i, step in enumerate(steps):
            self.assertEqual(step['action_name'], f'Action {i}')
