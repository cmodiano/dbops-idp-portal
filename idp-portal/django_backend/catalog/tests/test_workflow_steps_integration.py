"""
Integration tests for workflow steps with branches and retry.
Story 16.2: Test PUT /admin/actions/{id}/execution-steps/ with workflow branches and retry.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionItemType, ActionStatus
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from profiles.models import Profile
from tests.factories import UserFactory


class WorkflowStepsIntegrationTests(TestCase):
    """Integration tests for workflow steps API with branches and retry."""

    def setUp(self):
        """Set up test data."""
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.user = UserFactory(
            username='testuser',
            profile='DBOPS'
        )
        self.client.force_authenticate(user=self.user)

        # Create reference data
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True)

        # Create test actions for workflow references
        self.action1 = Action.objects.create(
            name='Action 1',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        self.action2 = Action.objects.create(
            name='Action 2',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        self.action3 = Action.objects.create(
            name='Action 3',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )

        # Create a draft workflow for testing
        self.workflow = Action.objects.create(
            name='Test Workflow',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

    def test_update_workflow_steps_with_branches_success(self):
        """Test updating workflow steps with valid branch configuration."""
        steps = [
            {
                'order': 1,
                'name': 'First Step',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': 'step-2',
                'on_error_step_id': 'step-3',
            },
            {
                'order': 2,
                'name': 'Success Path',
                'referenced_action_id': self.action2.id,
                'step_id': 'step-2',
                'on_success_step_id': None,  # Exit on success
            },
            {
                'order': 3,
                'name': 'Error Handler',
                'referenced_action_id': self.action3.id,
                'step_id': 'step-3',
                'on_error_step_id': None,  # Exit on error
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify workflow_steps in response
        workflow_steps = response.data['data']['workflow_steps']
        self.assertEqual(len(workflow_steps), 3)
        self.assertEqual(workflow_steps[0]['step_id'], 'step-1')
        self.assertEqual(workflow_steps[0]['on_success_step_id'], 'step-2')
        self.assertEqual(workflow_steps[0]['on_error_step_id'], 'step-3')

    def test_update_workflow_steps_with_retry_success(self):
        """Test updating workflow steps with valid retry configuration."""
        steps = [
            {
                'order': 1,
                'name': 'Retryable Step',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': None,
                'retry_enabled': True,
                'retry_max_attempts': 5,
                'retry_interval_seconds': 30,
                'retry_backoff_multiplier': 1.5,
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify retry config in response
        workflow_steps = response.data['data']['workflow_steps']
        self.assertEqual(len(workflow_steps), 1)
        self.assertTrue(workflow_steps[0]['retry_enabled'])
        self.assertEqual(workflow_steps[0]['retry_max_attempts'], 5)
        self.assertEqual(workflow_steps[0]['retry_interval_seconds'], 30)
        self.assertEqual(workflow_steps[0]['retry_backoff_multiplier'], 1.5)

    def test_update_workflow_steps_invalid_reference_fails(self):
        """Test that invalid step reference fails validation."""
        steps = [
            {
                'order': 1,
                'name': 'First Step',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': 'nonexistent-step',  # Invalid reference
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('does not reference a valid step_id', str(response.data))

    def test_update_workflow_steps_cycle_fails(self):
        """Test that workflow with cycle fails validation."""
        steps = [
            {
                'order': 1,
                'name': 'Step 1',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': 'step-2',
                'on_error_step_id': None,  # Exit point so cycle validation is reached
            },
            {
                'order': 2,
                'name': 'Step 2',
                'referenced_action_id': self.action2.id,
                'step_id': 'step-2',
                'on_success_step_id': 'step-1',  # Creates cycle
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Infinite loop detected', str(response.data))

    def test_update_workflow_steps_no_exit_point_fails(self):
        """Test that workflow without exit point fails validation."""
        steps = [
            {
                'order': 1,
                'name': 'Step 1',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': 'step-2',
                'on_error_step_id': 'step-2',
            },
            {
                'order': 2,
                'name': 'Step 2',
                'referenced_action_id': self.action2.id,
                'step_id': 'step-2',
                'on_success_step_id': 'step-1',
                'on_error_step_id': 'step-1',
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least one exit point', str(response.data))

    def test_update_workflow_steps_retry_constraints_fail(self):
        """Test that invalid retry constraints fail validation."""
        steps = [
            {
                'order': 1,
                'name': 'Step 1',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': None,
                'retry_enabled': True,
                'retry_max_attempts': 0,  # Invalid: must be >= 1
                'retry_interval_seconds': 60,
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('retry_max_attempts must be >= 1', str(response.data))

    def test_update_workflow_steps_backward_compatibility(self):
        """Test that workflows without branch/retry fields still work (backward compatibility)."""
        steps = [
            {
                'order': 1,
                'name': 'Simple Step',
                'referenced_action_id': self.action1.id,
            },
            {
                'order': 2,
                'name': 'Another Step',
                'referenced_action_id': self.action2.id,
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify workflow_steps in response
        workflow_steps = response.data['data']['workflow_steps']
        self.assertEqual(len(workflow_steps), 2)

    def test_update_workflow_steps_published_workflow_fails(self):
        """Test that published workflow cannot have steps updated."""
        # Publish the workflow
        self.workflow.status = ActionStatus.PUBLISHED
        self.workflow.save()

        steps = [
            {
                'order': 1,
                'name': 'Step 1',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': None,
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('brouillon ou désactivée', str(response.data))

    def test_update_workflow_steps_complex_diamond_structure(self):
        """Test complex diamond workflow structure (convergence, not a cycle)."""
        steps = [
            {
                'order': 1,
                'name': 'Start',
                'referenced_action_id': self.action1.id,
                'step_id': 'step-1',
                'on_success_step_id': 'step-2',
                'on_error_step_id': 'step-3',
            },
            {
                'order': 2,
                'name': 'Success Path',
                'referenced_action_id': self.action2.id,
                'step_id': 'step-2',
                'on_success_step_id': 'final',
            },
            {
                'order': 3,
                'name': 'Error Handler',
                'referenced_action_id': self.action3.id,
                'step_id': 'step-3',
                'on_success_step_id': 'final',
            },
            {
                'order': 4,
                'name': 'Final Step',
                'referenced_action_id': self.action1.id,
                'step_id': 'final',
                'on_success_step_id': None,  # Exit
            },
        ]

        response = self.client.put(
            f'/api/v1/admin/actions/{self.workflow.id}/execution-steps/',
            {'steps': steps},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify complex structure
        workflow_steps = response.data['data']['workflow_steps']
        self.assertEqual(len(workflow_steps), 4)
        self.assertEqual(workflow_steps[0]['on_success_step_id'], 'step-2')
        self.assertEqual(workflow_steps[0]['on_error_step_id'], 'step-3')
        self.assertEqual(workflow_steps[1]['on_success_step_id'], 'final')
        self.assertEqual(workflow_steps[2]['on_success_step_id'], 'final')
        self.assertEqual(workflow_steps[3]['on_success_step_id'], None)
