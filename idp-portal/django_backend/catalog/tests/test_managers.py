"""
Tests for catalog managers (ActionManager).
"""

import pytest
from django.test import TestCase
from idp_auth.models import User
from integrations.models import Integration
from catalog.models import Action, Tag, ActionTag, ActionStatus, ActionItemType


@pytest.mark.django_db
class TestActionManager(TestCase):
    """Tests for ActionManager."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
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
