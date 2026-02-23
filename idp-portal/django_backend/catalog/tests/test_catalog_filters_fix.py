"""Tests for catalog filters fix — tags_filter now chains instead of replacing queryset (Story 30.1, AC3)."""
import pytest
from django.utils import timezone

from catalog.models import ActionStatus, Tag, ActionTag
from catalog.services import CatalogService
from tests.factories import UserFactory, IntegrationFactory, ActionFactory


@pytest.mark.django_db
class TestCatalogListAllFilters:
    """CatalogService.list_all() filter combination tests."""

    def setup_method(self):
        self.service = CatalogService()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')

        # Create tags
        self.tag_database = Tag.objects.create(name='database')
        self.tag_oracle = Tag.objects.create(name='oracle')
        self.tag_linux = Tag.objects.create(name='linux')

        # Action 1: published, action, tags=[database, oracle]
        self.action1 = ActionFactory.create(
            name='Oracle Patching',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            integration=self.integration,
            created_by=self.user,
        )
        ActionTag.objects.create(action=self.action1, tag=self.tag_database)
        ActionTag.objects.create(action=self.action1, tag=self.tag_oracle)

        # Action 2: published, action, tags=[linux]
        self.action2 = ActionFactory.create(
            name='Linux Restart',
            status=ActionStatus.PUBLISHED,
            item_type='action',
            integration=self.integration,
            created_by=self.user,
        )
        ActionTag.objects.create(action=self.action2, tag=self.tag_linux)

        # Action 3: published, workflow, tags=[database, oracle]
        self.action3 = ActionFactory.create(
            name='Oracle Workflow',
            status=ActionStatus.PUBLISHED,
            item_type='workflow',
            integration=self.integration,
            created_by=self.user,
        )
        ActionTag.objects.create(action=self.action3, tag=self.tag_database)
        ActionTag.objects.create(action=self.action3, tag=self.tag_oracle)

        # Action 4: disabled, action, tags=[database]
        # Note: disabled status requires deleted_at/deleted_by (ck_actions_soft_delete_consistency)
        self.action4 = ActionFactory.create(
            name='Disabled DB Action',
            status=ActionStatus.DISABLED,
            item_type='action',
            integration=self.integration,
            created_by=self.user,
            deleted_at=timezone.now(),
            deleted_by=self.user,
        )
        ActionTag.objects.create(action=self.action4, tag=self.tag_database)

    def test_filter_status_only(self):
        """list_all(status='published') returns only published actions."""
        actions, _ = self.service.list_all(status=ActionStatus.PUBLISHED)
        ids = {a.id for a in actions}
        assert self.action1.id in ids
        assert self.action2.id in ids
        assert self.action3.id in ids
        assert self.action4.id not in ids

    def test_filter_item_type_only(self):
        """list_all(item_type='action') returns only actions (not workflows)."""
        actions, _ = self.service.list_all(item_type='action')
        ids = {a.id for a in actions}
        assert self.action1.id in ids
        assert self.action2.id in ids
        assert self.action3.id not in ids  # workflow

    def test_filter_tags_only(self):
        """list_all(tags_filter=['database']) returns actions with tag 'database'."""
        actions, _ = self.service.list_all(tags_filter=['database'])
        ids = {a.id for a in actions}
        assert self.action1.id in ids
        assert self.action3.id in ids
        # action4 is disabled — search_by_tags filters status=PUBLISHED
        assert self.action4.id not in ids
        assert self.action2.id not in ids  # no database tag

    def test_combined_status_item_type_and_tags(self):
        """CRITICAL: list_all(status='published', item_type='action', tags_filter=['database', 'oracle'])
        returns the intersection — only published actions with both database AND oracle tags."""
        actions, _ = self.service.list_all(
            status=ActionStatus.PUBLISHED,
            item_type='action',
            tags_filter=['database', 'oracle'],
        )
        ids = {a.id for a in actions}
        # Only action1 matches all 3 criteria (published + action + both tags)
        assert ids == {self.action1.id}

    def test_no_regression_empty_filters(self):
        """list_all() with no filters returns all actions."""
        actions, _ = self.service.list_all()
        assert len(actions) >= 4
