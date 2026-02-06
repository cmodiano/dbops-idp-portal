"""
Integration tests for action lifecycle.

Story M.9: Tests unitaires et d'intégration
Tests: création → publication → exécution → audit d'une action
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from idp_auth.models import User
from integrations.models import Integration
from catalog.models import Action, ActionStatus, Tag, ActionTag
from executions.models import Execution, ExecutionStatus
from core.models import AuditLog


@pytest.mark.django_db
@pytest.mark.integration
class TestActionLifecycle(TestCase):
    """Integration tests for complete action lifecycle."""

    def setUp(self):
        """Set up test data and API client."""
        self.user = User.objects.create(
            username='lifecycle_user',
            display_name='Lifecycle Test User',
            profile='DBOPS'
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Lifecycle AAP',
            base_url='https://aap.example.com'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_action_create_publish_execute_flow(self):
        """Test complete flow: create action → publish → execute → verify audit."""
        # Step 1: Create action (draft)
        action = Action.objects.create(
            name='Lifecycle Test Action',
            description='Action for lifecycle testing',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )
        self.assertEqual(action.status, ActionStatus.DRAFT)

        # Create audit entry for action creation
        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=action.id,
            details={'name': action.name}
        )

        # Step 2: Add tags to action
        tag = Tag.objects.create(name='lifecycle-test')
        ActionTag.objects.create(action=action, tag=tag)

        # Verify tag association
        action_tags = ActionTag.objects.filter(action=action)
        self.assertEqual(action_tags.count(), 1)

        # Step 3: Publish action
        action.status = ActionStatus.PUBLISHED
        action.save()

        # Create audit entry for publish
        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='ACTION_PUBLISHED',
            entity_type='action',
            entity_id=action.id,
            details={'previous_status': 'draft', 'new_status': 'published'}
        )

        # Verify action is now in catalog
        published_actions = Action.objects.list_published()
        self.assertIn(action.id, [a.id for a in published_actions])

        # Step 4: Execute action
        execution = Execution.objects.create(
            action=action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        execution.set_parameters({'target_host': 'db-test-01', 'database_name': 'TESTDB'})
        execution.save()

        # Create audit entry for execution
        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='EXECUTION_SUBMITTED',
            entity_type='execution',
            entity_id=execution.id,
            details={'action_id': action.id, 'environment': 'dev'}
        )

        # Verify execution is associated with action
        action_executions = Execution.objects.filter(action=action)
        self.assertEqual(action_executions.count(), 1)

        # Step 5: Complete execution
        execution.status = ExecutionStatus.COMPLETED
        execution.save()

        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='EXECUTION_COMPLETED',
            entity_type='execution',
            entity_id=execution.id,
            details={'final_status': 'COMPLETED'}
        )

        # Step 6: Verify audit trail
        audit_entries = AuditLog.objects.list_by_entity('action', action.id)
        self.assertGreaterEqual(audit_entries.count(), 2)

        execution_audit = AuditLog.objects.list_by_entity('execution', execution.id)
        self.assertGreaterEqual(execution_audit.count(), 2)

        # Verify all audit entries for this user
        user_audit = AuditLog.objects.list_by_user(str(self.user.id))
        self.assertGreaterEqual(user_audit.count(), 4)  # create, publish, submit, complete

    def test_action_disable_prevents_new_executions(self):
        """Test that disabled actions are not in published catalog."""
        action = Action.objects.create(
            name='Disable Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        # Verify action is in catalog
        self.assertIn(action.id, [a.id for a in Action.objects.list_published()])

        # Disable action
        action.status = ActionStatus.DISABLED
        action.save()

        # Verify action is no longer in published catalog
        self.assertNotIn(action.id, [a.id for a in Action.objects.list_published()])

    def test_action_update_with_audit_trail(self):
        """Test action update maintains complete audit trail."""
        action = Action.objects.create(
            name='Audit Trail Test',
            description='Original description',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )

        # Log creation
        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=action.id
        )

        # Update description
        action.description = 'Updated description'
        action.save()

        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=action.id,
            details={'field': 'description', 'old': 'Original description', 'new': 'Updated description'}
        )

        # Update category
        action.category = 'Patching'
        action.save()

        AuditLog.objects.create_entry(
            user_id=str(self.user.id),
            action_type='ACTION_UPDATED',
            entity_type='action',
            entity_id=action.id,
            details={'field': 'category', 'old': 'Provisioning', 'new': 'Patching'}
        )

        # Verify audit trail
        audit_entries = AuditLog.objects.list_by_entity('action', action.id)
        self.assertEqual(audit_entries.count(), 3)  # create + 2 updates

        # Verify chronological order (newest first)
        action_types = [e.action_type for e in audit_entries]
        self.assertEqual(action_types[0], 'ACTION_UPDATED')
        self.assertEqual(action_types[-1], 'ACTION_CREATED')
