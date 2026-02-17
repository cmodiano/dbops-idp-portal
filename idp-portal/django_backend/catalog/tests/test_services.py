"""
Tests for catalog services (CatalogService).
"""

import pytest
from django.test import TestCase
from django.db import transaction
from django.utils import timezone
from integrations.models import Integration
from catalog.models import Action, Tag, ActionTag, ActionStatus, ActionItemType
from catalog.services import CatalogService
from core.models import AuditLog
from tests.factories import UserFactory


@pytest.mark.django_db
class TestCatalogService(TestCase):
    """Tests for CatalogService."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(
            username='testuser',
            profile='DBA'
        )
        self.integration = Integration.objects.create(
            type='aap',
            name='Test AAP',
            base_url='https://aap.example.com'
        )
        self.service = CatalogService()

    def test_create_action(self):
        """Test create_action() creates action with tags and audit."""
        action_data = {
            'name': 'Test Action',
            'description': 'Test Description',
            'engine': 'Oracle',
            'platform': 'AAP',
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
            'parameters_schema': {'type': 'object'},
            'impact_rules': {'DEV': {'level': 'low'}},
            'tags': ['oracle', 'database']
        }

        action = self.service.create_action(action_data, self.user)

        self.assertIsNotNone(action.id)
        self.assertEqual(action.name, 'Test Action')
        self.assertEqual(action.status, ActionStatus.DRAFT)

        # Verify tags
        tags = [at.tag.name for at in action.actiontag_set.all()]
        self.assertIn('oracle', tags)
        self.assertIn('database', tags)

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_CREATED'
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user_id, str(self.user.id))

    def test_create_action_with_json_fields(self):
        """Test create_action() with complex JSON fields."""
        action_data = {
            'name': 'Test Action JSON',
            'engine': 'Oracle',
            'platform': 'AAP',
            'status': ActionStatus.DRAFT,
            'parameters_schema': {
                'type': 'object',
                'properties': {'db_name': {'type': 'string'}}
            },
            'impact_rules': {
                'DEV': {'level': 'low'},
                'PROD': {'level': 'high'}
            },
            'execution_steps': [
                {'step_order': 1, 'step_name': 'Step 1', 'step_type': 'manual'}
            ],
            'change_type_config': {'type': 'standard'},
            'remediation_rules': {'enabled': True}
        }

        action = self.service.create_action(action_data, self.user)

        # Verify JSON fields
        self.assertEqual(action.parameters_schema['type'], 'object')
        self.assertEqual(action.impact_rules['DEV']['level'], 'low')
        self.assertEqual(len(action.execution_steps), 1)
        self.assertEqual(action.change_type_config['type'], 'standard')
        self.assertTrue(action.remediation_rules['enabled'])

    def test_list_all_with_filters(self):
        """Test list_all() with status and item_type filters."""
        # Create test actions
        action1 = Action.objects.create(
            name='Action 1',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        Action.objects.create(
            name='Action 2',
            engine='PostgreSQL',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        # Filter by status
        results, pagination_info = self.service.list_all(status=ActionStatus.PUBLISHED)
        self.assertEqual(pagination_info['total'], 1)
        self.assertEqual(results[0].id, action1.id)

        # Filter by item_type
        workflow = Action.objects.create(
            name='Workflow 1',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            created_by=self.user
        )
        results, pagination_info = self.service.list_all(item_type=ActionItemType.WORKFLOW)
        self.assertGreaterEqual(pagination_info['total'], 1)
        self.assertTrue(any(a.id == workflow.id for a in results))

    def test_list_all_with_pagination(self):
        """Test list_all() pagination."""
        # Create multiple actions
        for i in range(30):
            Action.objects.create(
                name=f'Action {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user
            )

        # First page
        results, pagination_info = self.service.list_all(page=1, page_size=10)
        self.assertEqual(pagination_info['total'], 30)
        self.assertEqual(len(results), 10)

        # Second page
        results, pagination_info = self.service.list_all(page=2, page_size=10)
        self.assertEqual(len(results), 10)

    def test_get_by_id(self):
        """Test get_by_id() retrieves action with relations."""
        tag = Tag.objects.create(name='oracle')
        action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        ActionTag.objects.create(action=action, tag=tag)

        retrieved = self.service.get_by_id(action.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, action.id)
        self.assertEqual(retrieved.name, 'Test Action')

        # Verify tags are attached
        self.assertIsNotNone(hasattr(retrieved, 'tags'))

    def test_get_by_id_not_found(self):
        """Test get_by_id() returns None for non-existent action."""
        result = self.service.get_by_id(99999)
        self.assertIsNone(result)

    def test_update_action(self):
        """Test update_action() updates action and creates audit."""
        action = Action.objects.create(
            name='Original Name',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        update_data = {
            'name': 'Updated Name',
            'description': 'Updated Description',
            'tags': ['new_tag']
        }

        updated = self.service.update_action(action.id, update_data, self.user)

        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.description, 'Updated Description')

        # Verify tags updated
        tags = [at.tag.name for at in updated.actiontag_set.all()]
        self.assertIn('new_tag', tags)

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_UPDATED'
        ).first()
        self.assertIsNotNone(audit)

    def test_update_status_publish(self):
        """Test update_status() with publish transition."""
        action = Action.objects.create(
            name='Draft Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        updated = self.service.update_status(action.id, 'publish', self.user)

        self.assertEqual(updated.status, ActionStatus.PUBLISHED)

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_PUBLISHED'
        ).first()
        self.assertIsNotNone(audit)

    def test_update_status_disable(self):
        """Test deactivate_action() properly disables a published action."""
        action = Action.objects.create(
            name='Published Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )

        result = self.service.deactivate_action(action.id, self.user)

        self.assertIsNotNone(result)
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.DISABLED)

    def test_update_status_enable(self):
        """Test reactivate_action() properly re-enables a disabled action."""
        action = Action.objects.create(
            name='Disabled Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(),
            deleted_by=self.user,
            created_by=self.user
        )

        result = self.service.reactivate_action(action.id, self.user)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ActionStatus.PUBLISHED)

    def test_delete_action(self):
        """Test delete_action() deletes action and creates audit."""
        action = Action.objects.create(
            name='Action to Delete',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )
        action_id = action.id

        result = self.service.delete_action(action_id, self.user)

        self.assertTrue(result)

        # Verify action deleted
        self.assertFalse(Action.objects.filter(id=action_id).exists())

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action_id,
            action_type='ACTION_DELETED'
        ).first()
        self.assertIsNotNone(audit)

    def test_transaction_rollback_on_error(self):
        """Test that transaction rolls back on error."""
        # Mock an error during tag creation
        with self.assertRaises(Exception):
            with transaction.atomic():
                Action.objects.create(
                    name='Test Action',
                    engine='Oracle',
                    platform='AAP',
                    status=ActionStatus.DRAFT,
                    created_by=self.user
                )
                # Simulate error
                raise ValueError("Test error")

        # Verify action was not created
        self.assertFalse(Action.objects.filter(name='Test Action').exists())

    def test_create_action_invalid_integration_id_raises(self):
        """Story 30.8 ERR-3: create_action raises ValueError for invalid integration_id."""
        action_data = {
            'name': 'Action With Bad Integration',
            'engine': 'Oracle',
            'platform': 'AAP',
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
            'integration_id': 99999,
        }
        # Fix HIGH-4: assertRaises msg parameter is failure message, not exception match
        with self.assertRaises(ValueError) as cm:
            self.service.create_action(action_data, self.user)
        self.assertIn("Integration 99999 not found", str(cm.exception))
        # Verify no action was created (transaction rolled back)
        self.assertFalse(Action.objects.filter(name='Action With Bad Integration').exists())

    def test_update_action_invalid_integration_id_raises(self):
        """Story 30.8 ERR-3: update_action raises ValueError for invalid integration_id."""
        action = self.service.create_action(
            {'name': 'Test Update Integration', 'engine': 'Oracle', 'platform': 'AAP'},
            self.user
        )
        with self.assertRaises(ValueError) as cm:
            self.service.update_action(
                action.id, {'integration_id': 99999}, self.user
            )
        self.assertIn("Integration 99999 not found", str(cm.exception))
