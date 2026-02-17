"""Tests for CatalogActionViewSet filter combinations (Story 30.14, AC1/AC2).

Verifies that search_by_tags() chains on the existing queryset instead of
recreating it, ensuring all filters (tags, category, q, engine, environment)
are applied cumulatively.
"""
import json

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import ActionStatus, Tag, ActionTag
from tests.factories import UserFactory, ActionFactory, IntegrationFactory


@pytest.mark.django_db
class TestCatalogViewSetFilterCombinations:
    """CatalogActionViewSet filter combination tests via API."""

    def setup_method(self) -> None:
        self.client = APIClient()
        self.user = UserFactory.create(profile='DBA')
        self.integration = IntegrationFactory.create(type='aap', name='Test AAP')

        # Tags
        self.tag_backup = Tag.objects.create(name='backup')
        self.tag_restore = Tag.objects.create(name='restore')
        self.tag_maintenance = Tag.objects.create(name='maintenance')

        # Action 1: published, Oracle, tags=[backup, restore], impact_rules with "prod"
        self.action1 = ActionFactory.create(
            name='Daily Backup Oracle',
            status=ActionStatus.PUBLISHED,
            engine='Oracle',
            integration=self.integration,
            created_by=self.user,
            impact_rules=json.dumps({'prod': {'requires_change': True}}),
        )
        ActionTag.objects.create(action=self.action1, tag=self.tag_backup)
        ActionTag.objects.create(action=self.action1, tag=self.tag_restore)

        # Action 2: published, SQL Server, tags=[backup, maintenance], impact_rules with "dev"
        self.action2 = ActionFactory.create(
            name='SQL Server Maintenance',
            status=ActionStatus.PUBLISHED,
            engine='SQL Server',
            integration=self.integration,
            created_by=self.user,
            impact_rules=json.dumps({'dev': {'requires_change': False}}),
        )
        ActionTag.objects.create(action=self.action2, tag=self.tag_backup)
        ActionTag.objects.create(action=self.action2, tag=self.tag_maintenance)

        # Action 3: published, Oracle, tags=[maintenance], impact_rules with "prod"
        self.action3 = ActionFactory.create(
            name='Oracle Patching',
            status=ActionStatus.PUBLISHED,
            engine='Oracle',
            integration=self.integration,
            created_by=self.user,
            impact_rules=json.dumps({'prod': {'requires_change': True}}),
        )
        ActionTag.objects.create(action=self.action3, tag=self.tag_maintenance)

        # Action 4: draft (should never appear in catalog)
        self.action4 = ActionFactory.create(
            name='Draft Action',
            status=ActionStatus.DRAFT,
            engine='Oracle',
            integration=self.integration,
            created_by=self.user,
        )
        ActionTag.objects.create(action=self.action4, tag=self.tag_backup)

    def _get_action_ids(self, response) -> set[int]:
        """Extract action IDs from paginated API response."""
        assert response.status_code == 200
        return {item['id'] for item in response.data['data']}

    # ---- AC2: Test 1 — tags seul ----

    def test_filter_by_tags_only(self) -> None:
        """GET /catalog/actions/?tags=backup,restore → actions with both tags."""
        response = self.client.get('/api/v1/catalog/actions/?tags=backup,restore')
        ids = self._get_action_ids(response)
        # Only action1 has both backup AND restore
        assert ids == {self.action1.id}

    # ---- AC2: Test 2 — category seul ----

    def test_filter_by_category_only(self) -> None:
        """GET /catalog/actions/?category=maintenance → actions tagged 'maintenance'."""
        response = self.client.get('/api/v1/catalog/actions/?category=maintenance')
        ids = self._get_action_ids(response)
        assert self.action2.id in ids
        assert self.action3.id in ids
        assert self.action1.id not in ids  # no maintenance tag

    # ---- AC2: Test 3 — tags + category combinés (AC1: chaînage correct) ----

    def test_filter_by_tags_and_category(self) -> None:
        """GET /catalog/actions/?tags=backup&category=maintenance → intersection."""
        response = self.client.get('/api/v1/catalog/actions/?tags=backup&category=maintenance')
        ids = self._get_action_ids(response)
        # action2 has both backup AND maintenance tags
        assert ids == {self.action2.id}

    # ---- AC2: Test 4 — tags + category + q (texte) ----

    def test_filter_by_tags_category_and_text(self) -> None:
        """GET /catalog/actions/?tags=backup&category=maintenance&q=SQL → all filters applied."""
        response = self.client.get(
            '/api/v1/catalog/actions/?tags=backup&category=maintenance&q=SQL'
        )
        ids = self._get_action_ids(response)
        # action2 matches: backup tag + maintenance tag + "SQL" in name
        assert ids == {self.action2.id}

    def test_filter_by_tags_category_and_text_no_match(self) -> None:
        """GET /catalog/actions/?tags=backup&category=maintenance&q=Oracle → empty."""
        response = self.client.get(
            '/api/v1/catalog/actions/?tags=backup&category=maintenance&q=Oracle'
        )
        ids = self._get_action_ids(response)
        assert ids == set()

    # ---- AC2: Test 5 — tags + engine ----

    def test_filter_by_tags_and_engine(self) -> None:
        """GET /catalog/actions/?tags=backup&engine=Oracle → combination."""
        response = self.client.get('/api/v1/catalog/actions/?tags=backup&engine=Oracle')
        ids = self._get_action_ids(response)
        # action1: backup + Oracle. action2: backup + SQL Server (excluded)
        assert ids == {self.action1.id}

    # ---- AC2: Test 6 — category + environment ----

    def test_filter_by_category_and_environment(self) -> None:
        """GET /catalog/actions/?category=maintenance&environment=prod → combination."""
        response = self.client.get(
            '/api/v1/catalog/actions/?category=maintenance&environment=prod'
        )
        ids = self._get_action_ids(response)
        # action3: maintenance + prod. action2: maintenance + dev (excluded)
        assert ids == {self.action3.id}

    # ---- Edge case: draft actions never returned ----

    def test_draft_actions_excluded(self) -> None:
        """Draft actions never appear regardless of filters."""
        response = self.client.get('/api/v1/catalog/actions/?tags=backup')
        ids = self._get_action_ids(response)
        assert self.action4.id not in ids

    # ---- Edge case: category=tout or category=all bypasses category filter ----

    def test_category_tout_no_filter(self) -> None:
        """category=tout should not apply category filter."""
        response = self.client.get('/api/v1/catalog/actions/?category=tout')
        ids = self._get_action_ids(response)
        # All published actions returned
        assert self.action1.id in ids
        assert self.action2.id in ids
        assert self.action3.id in ids
