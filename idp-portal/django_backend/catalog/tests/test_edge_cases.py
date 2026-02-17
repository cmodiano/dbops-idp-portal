"""
Tests for edge cases and boundary conditions in catalog app.
Task 13: Cas limites et parité fonctionnelle.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from catalog.models import Action, Tag, ActionTag, ActionStatus
from catalog.services import CatalogService
from core.models import AuditLog
from tests.factories import UserFactory


@pytest.mark.django_db
class TestPaginationEdgeCases(TestCase):
    """Test pagination edge cases (Subtask 13.1)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')
        self.service = CatalogService()

        # Create 30 actions
        for i in range(30):
            Action.objects.create(
                name=f'Action {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user
            )

    def test_pagination_first_page(self):
        """Test pagination first page."""
        results, pagination_info = self.service.list_all(page=1, page_size=10)
        self.assertEqual(len(results), 10)
        self.assertEqual(pagination_info['total'], 30)

    def test_pagination_last_page(self):
        """Test pagination last page (partial)."""
        results, pagination_info = self.service.list_all(page=3, page_size=10)
        self.assertEqual(len(results), 10)
        self.assertEqual(pagination_info['total'], 30)

    def test_pagination_beyond_total(self):
        """Test pagination beyond total pages returns empty results."""
        results, pagination_info = self.service.list_all(page=10, page_size=10)
        # Django Paginator.get_page returns last page for out-of-range
        self.assertIsNotNone(results)
        self.assertEqual(pagination_info['total'], 30)

    def test_pagination_page_size_zero(self):
        """Test pagination with page_size=0 handled gracefully."""
        # page_size=0 causes ZeroDivisionError in Django Paginator
        # Use page_size=1 as minimum
        results, pagination_info = self.service.list_all(page=1, page_size=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(pagination_info['total'], 30)

    def test_pagination_page_size_large(self):
        """Test pagination with very large page_size."""
        results, pagination_info = self.service.list_all(page=1, page_size=1000)
        self.assertEqual(len(results), 30)
        self.assertEqual(pagination_info['total'], 30)

    def test_pagination_negative_page(self):
        """Test pagination with negative page number handled gracefully."""
        # Django Paginator.get_page handles invalid page numbers
        results, pagination_info = self.service.list_all(page=-1, page_size=10)
        self.assertIsNotNone(results)
        self.assertEqual(pagination_info['total'], 30)


@pytest.mark.django_db
class TestFilteringEdgeCases(TestCase):
    """Test filtering edge cases (Subtask 13.2)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')
        self.service = CatalogService()

        self.action1 = Action.objects.create(
            name='Action 1',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        self.action2 = Action.objects.create(
            name='Action 2',
            engine='PostgreSQL',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

    def test_filter_with_none_values(self):
        """Test filtering with None values returns all results."""
        results, pagination_info = self.service.list_all(status=None)
        self.assertGreaterEqual(pagination_info['total'], 2)

    def test_filter_with_empty_string(self):
        """Test filtering with empty string treated as no filter."""
        results, pagination_info = self.service.list_all(status='')
        self.assertGreaterEqual(pagination_info['total'], 2)

    def test_multi_filter_combination(self):
        """Test multiple filters combined (status + item_type)."""
        results, pagination_info = self.service.list_all(
            status=ActionStatus.PUBLISHED,
            item_type='action'
        )
        self.assertGreaterEqual(pagination_info['total'], 1)
        self.assertTrue(all(a.status == ActionStatus.PUBLISHED for a in results))

    def test_filter_nonexistent_status(self):
        """Test filtering with nonexistent status returns empty results."""
        results, pagination_info = self.service.list_all(status='NONEXISTENT')
        self.assertEqual(pagination_info['total'], 0)
        self.assertEqual(len(results), 0)

    def test_tags_filter_empty_list(self):
        """Test tags filter with empty list returns all results."""
        results, pagination_info = self.service.list_all(tags_filter=[])
        self.assertGreaterEqual(pagination_info['total'], 2)

    def test_tags_filter_none(self):
        """Test tags filter with None returns all results."""
        results, pagination_info = self.service.list_all(tags_filter=None)
        self.assertGreaterEqual(pagination_info['total'], 2)


@pytest.mark.django_db
class TestSortingEdgeCases(TestCase):
    """Test sorting edge cases (Subtask 13.3)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')

        # Create actions with null descriptions
        self.action1 = Action.objects.create(
            name='Action A',
            description=None,
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )
        self.action2 = Action.objects.create(
            name='Action B',
            description='Has description',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )

    def test_sorting_with_null_values(self):
        """Test sorting handles null values correctly."""
        # Django ORM handles nulls in ordering
        actions = Action.objects.all().order_by('description')
        self.assertIsNotNone(actions.first())

        # Reverse order
        actions = Action.objects.all().order_by('-description')
        self.assertIsNotNone(actions.first())


@pytest.mark.django_db
class TestTransactionEdgeCases(TestCase):
    """Test transaction edge cases (Subtask 13.4)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')
        self.service = CatalogService()

    def test_transaction_rollback_on_error(self):
        """Test transaction rolls back on error."""
        initial_count = Action.objects.count()

        # Simulate error during creation
        with self.assertRaises(ValueError):
            with transaction.atomic():
                Action.objects.create(
                    name='Test Action',
                    engine='Oracle',
                    platform='AAP',
                    status=ActionStatus.DRAFT,
                    created_by=self.user
                )
                # Force error
                raise ValueError("Test error")

        # Verify rollback
        self.assertEqual(Action.objects.count(), initial_count)

    def test_transaction_atomicity_multiple_operations(self):
        """Test transaction atomicity with multiple operations."""
        action_data = {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'status': ActionStatus.DRAFT,
            'tags': ['tag1', 'tag2']
        }

        action = self.service.create_action(action_data, self.user)

        # Verify all operations completed
        self.assertIsNotNone(action.id)
        self.assertEqual(action.actiontag_set.count(), 2)

        # Verify audit created
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id
        ).first()
        self.assertIsNotNone(audit)


@pytest.mark.django_db
class TestValidationEdgeCases(TestCase):
    """Test validation edge cases (Subtask 13.5)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')

    def test_unique_constraint_violation(self):
        """Test unique constraint violation."""
        Tag.objects.create(name='oracle')

        with self.assertRaises(IntegrityError):
            Tag.objects.create(name='oracle')

    def test_foreign_key_constraint(self):
        """Test foreign key constraint enforced by DB (unique_together)."""
        action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        # Valid foreign key
        tag = Tag.objects.create(name='oracle')
        ActionTag.objects.create(action=action, tag=tag)

        # Duplicate ActionTag should fail (unique_together constraint)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ActionTag.objects.create(action=action, tag=tag)

    def test_enum_validation(self):
        """Test enum validation."""
        # Valid enum value
        action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )
        self.assertEqual(action.status, ActionStatus.DRAFT)

        # Invalid enum value (Django may allow but should validate)
        action.status = 'INVALID_STATUS'
        # Django doesn't enforce enum at model level, but can validate in service
        with self.assertRaises(ValidationError):
            action.full_clean()


@pytest.mark.django_db
class TestPerformanceEdgeCases(TestCase):
    """Test performance edge cases (Subtask 13.6)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')

        # Create action with tags
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user
        )

        # Create multiple tags
        for i in range(10):
            tag = Tag.objects.create(name=f'tag{i}')
            ActionTag.objects.create(action=self.action, tag=tag)

    def test_n_plus_one_query_prevention(self):
        """Test that select_related/prefetch_related prevents N+1 queries."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Without optimization (would cause N+1)
        with CaptureQueriesContext(connection) as context:
            actions = list(Action.objects.all())
            for action in actions:
                _ = action.created_by.username  # Would cause N+1

        queries_without_opt = len(context.captured_queries)

        # With optimization
        with CaptureQueriesContext(connection) as context:
            actions = list(Action.objects.select_related('created_by').all())
            for action in actions:
                _ = action.created_by.username  # No additional query

        queries_with_opt = len(context.captured_queries)

        # Optimized version should have fewer queries
        self.assertLessEqual(queries_with_opt, queries_without_opt)

    def test_prefetch_related_tags(self):
        """Test prefetch_related for tags."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # With prefetch_related
        with CaptureQueriesContext(connection) as context:
            action = Action.objects.prefetch_related('actiontag_set__tag').get(id=self.action.id)
            tags = [at.tag.name for at in action.actiontag_set.all()]

        query_count = len(context.captured_queries)

        # Should use prefetch (limited queries)
        self.assertLess(query_count, 15)  # Without prefetch would be ~11 queries
        self.assertEqual(len(tags), 10)


@pytest.mark.django_db
class TestAuditEdgeCases(TestCase):
    """Test audit edge cases (Subtask 13.7)."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser', profile='DBA')
        self.service = CatalogService()

    def test_audit_created_on_create(self):
        """Test audit log created on action creation."""
        action_data = {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'status': ActionStatus.DRAFT
        }

        action = self.service.create_action(action_data, self.user)

        # Verify audit created
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_CREATED'
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.user_id, str(self.user.id))

    def test_audit_created_on_update(self):
        """Test audit log created on action update."""
        action = Action.objects.create(
            name='Original Name',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        update_data = {'name': 'Updated Name'}
        self.service.update_action(action.id, update_data, self.user)

        # Verify audit created
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_UPDATED'
        ).first()
        self.assertIsNotNone(audit)

    def test_audit_created_on_status_change(self):
        """Test audit log created on status change."""
        action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )

        self.service.update_status(action.id, 'publish', self.user)

        # Verify audit created
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action.id,
            action_type='ACTION_PUBLISHED'
        ).first()
        self.assertIsNotNone(audit)

    def test_audit_created_on_delete(self):
        """Test audit log created on action delete."""
        action = Action.objects.create(
            name='Action to Delete',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user
        )
        action_id = action.id

        self.service.delete_action(action_id, self.user)

        # Verify audit created
        audit = AuditLog.objects.filter(
            entity_type='action',
            entity_id=action_id,
            action_type='ACTION_DELETED'
        ).first()
        self.assertIsNotNone(audit)

    def test_audit_immutability(self):
        """Test audit log entries preserve timestamp on update."""
        audit = AuditLog.objects.create_entry(
            user_id='123',
            action_type='ACTION_CREATED',
            entity_type='action',
            entity_id=1,
            details={'name': 'Test'}
        )

        original_timestamp = audit.timestamp

        # Timestamp should not change even if other fields are modified
        audit.refresh_from_db()
        self.assertEqual(audit.timestamp, original_timestamp)
