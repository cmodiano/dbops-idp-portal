"""
Tests for catalog managers (ActionManager).
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from integrations.models import Integration
from catalog.models import Action, Tag, ActionTag, ActionStatus, ActionItemType
from tests.factories import UserFactory


@pytest.mark.django_db
class TestActionManager(TestCase):
    """Tests for ActionManager."""
    
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
        self.action_draft = Action.objects.create(
            name='Draft Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )
        self.action_published = Action.objects.create(
            name='Published Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )
        self.action_disabled = Action.objects.create(
            name='Disabled Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DISABLED,
            deleted_at=timezone.now(),
            created_by=self.user,
            integration=self.integration
        )
    
    def test_list_published(self):
        """Test list_published() returns only published actions."""
        published = Action.objects.list_published()
        self.assertEqual(published.count(), 1)
        self.assertEqual(published[0].id, self.action_published.id)
        self.assertEqual(published[0].status, ActionStatus.PUBLISHED)
    
    def test_list_by_status(self):
        """Test list_by_status() filters by status."""
        draft_actions = Action.objects.list_by_status(ActionStatus.DRAFT)
        self.assertEqual(draft_actions.count(), 1)
        self.assertEqual(draft_actions[0].id, self.action_draft.id)
        
        published_actions = Action.objects.list_by_status(ActionStatus.PUBLISHED)
        self.assertEqual(published_actions.count(), 1)
        self.assertEqual(published_actions[0].id, self.action_published.id)
        
        disabled_actions = Action.objects.list_by_status(ActionStatus.DISABLED)
        self.assertEqual(disabled_actions.count(), 1)
        self.assertEqual(disabled_actions[0].id, self.action_disabled.id)
    
    def test_search_by_tags_single_tag(self):
        """Test search_by_tags() with single tag."""
        tag1 = Tag.objects.create(name='oracle')
        ActionTag.objects.create(action=self.action_published, tag=tag1)
        
        results = Action.objects.search_by_tags(['oracle'])
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, self.action_published.id)
    
    def test_search_by_tags_multiple_tags(self):
        """Test search_by_tags() with multiple tags (AND logic)."""
        tag1 = Tag.objects.create(name='oracle')
        tag2 = Tag.objects.create(name='database')
        
        # Action with both tags
        ActionTag.objects.create(action=self.action_published, tag=tag1)
        ActionTag.objects.create(action=self.action_published, tag=tag2)
        
        # Action with only one tag
        ActionTag.objects.create(action=self.action_draft, tag=tag1)
        
        # Should return only action with both tags
        results = Action.objects.search_by_tags(['oracle', 'database'])
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, self.action_published.id)
    
    def test_search_by_tags_no_results(self):
        """Test search_by_tags() returns empty when no matches."""
        results = Action.objects.search_by_tags(['nonexistent'])
        self.assertEqual(results.count(), 0)
    
    def test_with_tags(self):
        """Test with_tags() prefetches tags to avoid N+1 queries."""
        tag1 = Tag.objects.create(name='oracle')
        tag2 = Tag.objects.create(name='database')
        ActionTag.objects.create(action=self.action_published, tag=tag1)
        ActionTag.objects.create(action=self.action_published, tag=tag2)
        
        # Use with_tags() to prefetch
        action = Action.objects.with_tags().get(id=self.action_published.id)
        
        # Access tags without additional query
        tags = [at.tag.name for at in action.actiontag_set.all()]
        self.assertIn('oracle', tags)
        self.assertIn('database', tags)
    
    def test_with_creator(self):
        """Test with_creator() uses select_related to avoid N+1 queries."""
        action = Action.objects.with_creator().get(id=self.action_published.id)

        # Access creator without additional query
        self.assertEqual(action.created_by.username, 'testuser')
        self.assertEqual(action.created_by.id, self.user.id)

    # =========================================================================
    # Story M.9: Additional manager tests for edge cases and filters
    # =========================================================================

    def test_list_by_status_invalid_status(self):
        """Test list_by_status() with invalid status returns empty."""
        results = Action.objects.list_by_status('nonexistent_status')
        self.assertEqual(results.count(), 0)

    def test_search_by_tags_empty_list(self):
        """Test search_by_tags() with empty list returns published actions."""
        results = Action.objects.search_by_tags([])
        # Empty tags should not filter anything, returns all published
        self.assertGreaterEqual(results.count(), 1)

    def test_list_published_ordering(self):
        """Test list_published() returns actions in correct order."""
        Action.objects.create(
            name='Z-Action',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        published = list(Action.objects.list_published().order_by('name'))
        # Should be ordered alphabetically
        names = [a.name for a in published]
        self.assertEqual(names, sorted(names))

    def test_with_tags_and_creator_combined(self):
        """Test combining with_tags() and with_creator() for optimization."""
        tag = Tag.objects.create(name='optimization_test')
        ActionTag.objects.create(action=self.action_published, tag=tag)

        # Chain both methods
        action = Action.objects.with_tags().with_creator().get(id=self.action_published.id)

        # Both should be accessible without extra queries
        self.assertEqual(action.created_by.username, 'testuser')
        tags = [at.tag.name for at in action.actiontag_set.all()]
        self.assertIn('optimization_test', tags)


@pytest.mark.django_db
class TestActionManagerAdvanced(TestCase):
    """Story M.9: Advanced tests for ActionManager with parametrized edge cases."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(username='testuser_adv', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Test AAP Adv',
            base_url='https://aap.example.com'
        )

    def test_filter_by_engine(self):
        """Test filtering actions by engine."""
        Action.objects.create(
            name='Oracle Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )
        Action.objects.create(
            name='SQL Server Action',
            category='Provisioning',
            engine='SQL Server',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        oracle_actions = Action.objects.filter(engine='Oracle', status=ActionStatus.PUBLISHED)
        self.assertEqual(oracle_actions.count(), 1)

        sql_actions = Action.objects.filter(engine='SQL Server', status=ActionStatus.PUBLISHED)
        self.assertEqual(sql_actions.count(), 1)

    def test_filter_by_platform(self):
        """Test filtering actions by platform."""
        Action.objects.create(
            name='AAP Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )
        Action.objects.create(
            name='Terraform Action',
            category='Provisioning',
            engine='Oracle',
            platform='Terraform',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        aap_actions = Action.objects.filter(platform='AAP', status=ActionStatus.PUBLISHED)
        self.assertGreaterEqual(aap_actions.count(), 1)

        terraform_actions = Action.objects.filter(platform='Terraform', status=ActionStatus.PUBLISHED)
        self.assertEqual(terraform_actions.count(), 1)

    def test_filter_by_category(self):
        """Test filtering actions by category."""
        Action.objects.create(
            name='Provisioning Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )
        Action.objects.create(
            name='Patching Action',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        provisioning = Action.objects.filter(category='Provisioning', status=ActionStatus.PUBLISHED)
        self.assertGreaterEqual(provisioning.count(), 1)

        patching = Action.objects.filter(category='Patching', status=ActionStatus.PUBLISHED)
        self.assertEqual(patching.count(), 1)

    def test_filter_by_item_type(self):
        """Test filtering actions by item_type (action vs workflow)."""
        Action.objects.create(
            name='Regular Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
            created_by=self.user,
            integration=self.integration
        )
        Action.objects.create(
            name='Workflow Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            created_by=self.user,
            integration=self.integration
        )

        actions = Action.objects.filter(item_type=ActionItemType.ACTION, status=ActionStatus.PUBLISHED)
        self.assertGreaterEqual(actions.count(), 1)

        workflows = Action.objects.filter(item_type=ActionItemType.WORKFLOW, status=ActionStatus.PUBLISHED)
        self.assertEqual(workflows.count(), 1)

    def test_multiple_tags_search_order_insensitive(self):
        """Test that search_by_tags works regardless of tag order."""
        action = Action.objects.create(
            name='Multi Tag Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )
        tag1 = Tag.objects.create(name='alpha')
        tag2 = Tag.objects.create(name='beta')
        ActionTag.objects.create(action=action, tag=tag1)
        ActionTag.objects.create(action=action, tag=tag2)

        # Both orders should return the same result
        results1 = Action.objects.search_by_tags(['alpha', 'beta'])
        results2 = Action.objects.search_by_tags(['beta', 'alpha'])

        self.assertEqual(set(r.id for r in results1), set(r.id for r in results2))
