"""
Tests de performance et audit requêtes BD pour les endpoints catalogue.
Story 17.17: Optimisation requêtes BD — page Catalogue.

Audit baseline et tests de non-régression query count pour:
- GET /api/v1/catalog/actions/ (actions publiées avec cache)
- GET /api/v1/catalog/tags (tags avec action_count et RBAC)
- GET /api/v1/users/me/favorites/ (favoris utilisateur)
"""

import pytest
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient
from rest_framework import status
from idp_auth.models import User
from catalog.models import Action, Tag, ActionTag, ActionStatus, UserFavorite
from catalog.views import _catalog_cache, _tags_cache


def _log_queries(context, label=""):
    """Helper to print captured queries for audit purposes."""
    print(f"\n{'='*60}")
    print(f"AUDIT: {label}")
    print(f"Query count: {len(context.captured_queries)}")
    for i, q in enumerate(context.captured_queries, 1):
        sql = q['sql'][:200]
        time_s = q.get('time', '?')
        print(f"  [{i}] ({time_s}s) {sql}")
    print(f"{'='*60}\n")


@pytest.mark.django_db
class TestCatalogActionsPerformance(TestCase):
    """Audit et tests de performance pour GET /api/v1/catalog/actions/."""

    @classmethod
    def setUpTestData(cls):
        """Seed data: 20 actions publiées, 10 tags, associations variées."""
        cls.user = User.objects.create(username='perfuser', profile='DBA')

        # Create tags
        cls.tags = []
        for i in range(10):
            cls.tags.append(Tag.objects.create(name=f'perftag{i}'))

        # Create 20 published actions with tags
        cls.actions = []
        for i in range(20):
            action = Action.objects.create(
                name=f'PerfAction {i}',
                description=f'Description for action {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                default_impact_level='low',
                created_by=cls.user,
            )
            cls.actions.append(action)
            # Assign 2-3 tags per action
            for j in range(min(3, len(cls.tags))):
                tag_idx = (i + j) % len(cls.tags)
                ActionTag.objects.create(action=action, tag=cls.tags[tag_idx])

    def setUp(self):
        self.client = APIClient()
        # Clear catalog cache before each test
        _catalog_cache.clear()

    def test_catalog_actions_query_count_baseline(self):
        """
        Subtask 1.1: Instrumenter GET /api/v1/catalog/actions/ avec CaptureQueriesContext.
        Mesure le query count sur cache miss (sans auth = pas de RBAC).
        """
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data.get('data', [])), 0)

        _log_queries(ctx, "GET /catalog/actions/ (no auth, cache miss)")
        # Baseline: expect reasonable query count (no N+1)
        # Queries: 1 main + 1 prefetch tags + 1 select_related creator + 1 execution_count subquery
        # Actual count may vary; we assert it's bounded
        self.assertLessEqual(
            len(ctx.captured_queries), 10,
            f"Too many queries ({len(ctx.captured_queries)}) for catalog actions endpoint"
        )

    def test_catalog_actions_cache_hit_zero_queries(self):
        """Verify cache hit produces 0 DB queries."""
        # Prime the cache
        self.client.get('/api/v1/catalog/actions/')

        # Second request should use cache
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _log_queries(ctx, "GET /catalog/actions/ (cache hit)")
        self.assertEqual(
            len(ctx.captured_queries), 0,
            f"Cache hit should produce 0 queries, got {len(ctx.captured_queries)}"
        )

    def test_catalog_actions_with_filters_query_count(self):
        """
        Subtask 1.4: Tester avec filtres actifs.
        Mesure query count avec tags filter.
        """
        _catalog_cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/?tags=perftag0')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _log_queries(ctx, "GET /catalog/actions/?tags=perftag0 (cache miss)")
        self.assertLessEqual(
            len(ctx.captured_queries), 12,
            f"Too many queries ({len(ctx.captured_queries)}) for catalog actions with tag filter"
        )

    def test_catalog_actions_with_engine_filter_query_count(self):
        """Mesure query count avec filtre engine."""
        _catalog_cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/?engine=Oracle')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _log_queries(ctx, "GET /catalog/actions/?engine=Oracle (cache miss)")
        self.assertLessEqual(
            len(ctx.captured_queries), 10,
            f"Too many queries ({len(ctx.captured_queries)}) for catalog actions with engine filter"
        )

    def test_catalog_actions_with_text_search_query_count(self):
        """Mesure query count avec recherche texte."""
        _catalog_cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/?q=PerfAction')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _log_queries(ctx, "GET /catalog/actions/?q=PerfAction (cache miss)")
        self.assertLessEqual(
            len(ctx.captured_queries), 10,
            f"Too many queries ({len(ctx.captured_queries)}) for catalog actions with text search"
        )


@pytest.mark.django_db
class TestCatalogTagsPerformance(TestCase):
    """Audit et tests de performance pour GET /api/v1/catalog/tags."""

    @classmethod
    def setUpTestData(cls):
        """Seed data for tags endpoint audit."""
        cls.user = User.objects.create(username='tagsuser', profile='DBA')

        cls.tags = []
        for i in range(10):
            cls.tags.append(Tag.objects.create(name=f'tagperf{i}'))

        cls.actions = []
        for i in range(15):
            action = Action.objects.create(
                name=f'TagAction {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=cls.user,
            )
            cls.actions.append(action)
            for j in range(2):
                tag_idx = (i + j) % len(cls.tags)
                ActionTag.objects.create(action=action, tag=cls.tags[tag_idx])

    def setUp(self):
        self.client = APIClient()
        _tags_cache.clear()

    def test_catalog_tags_query_count_baseline(self):
        """
        Subtask 1.2: Instrumenter GET /api/v1/catalog/tags avec query logging.
        Mesure le query count on cache miss.
        """
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data.get('data', [])), 0)

        _log_queries(ctx, "GET /catalog/tags/ (no auth, cache miss)")
        # Tags endpoint: 1 query visible_action_ids + 1 query tags with annotate
        self.assertLessEqual(
            len(ctx.captured_queries), 6,
            f"Too many queries ({len(ctx.captured_queries)}) for catalog tags endpoint"
        )

    def test_catalog_tags_cache_hit_zero_queries(self):
        """Story 17.17: Verify tags cache hit produces 0 DB queries."""
        # Prime the cache
        self.client.get('/api/v1/catalog/tags/')

        # Second request should use cache
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        _log_queries(ctx, "GET /catalog/tags/ (cache hit)")
        self.assertEqual(
            len(ctx.captured_queries), 0,
            f"Tags cache hit should produce 0 queries, got {len(ctx.captured_queries)}"
        )


@pytest.mark.django_db
class TestFavoritesPerformance(TestCase):
    """Audit et tests de performance pour GET /api/v1/users/me/favorites/."""

    @classmethod
    def setUpTestData(cls):
        """Seed data for favorites endpoint audit."""
        cls.user = User.objects.create(username='favuser', profile='DBA')

        cls.actions = []
        for i in range(10):
            action = Action.objects.create(
                name=f'FavAction {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=cls.user,
            )
            cls.actions.append(action)
            # Add 5 favorites
            if i < 5:
                UserFavorite.objects.create(user=cls.user, action=action)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_favorites_query_count_baseline(self):
        """
        Subtask 1.3: Instrumenter GET /api/v1/users/me/favorites/ avec query logging.
        """
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/users/me/favorites/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        _log_queries(ctx, "GET /users/me/favorites/ (authenticated)")
        # Favorites: 1 query with select_related('action')
        self.assertLessEqual(
            len(ctx.captured_queries), 5,
            f"Too many queries ({len(ctx.captured_queries)}) for favorites endpoint"
        )


@pytest.mark.django_db
class TestIndexesCreated(TestCase):
    """Story 17.17 FIX#1: Verify Django indexes are created correctly."""

    def test_action_indexes_exist(self):
        """Verify Action model has the 3 performance indexes defined."""
        # Get index names from Action model Meta
        action_indexes = [idx.name for idx in Action._meta.indexes]

        self.assertIn('idx_actions_status', action_indexes,
                      "Missing index: idx_actions_status on Action.status")
        self.assertIn('idx_actions_status_engine', action_indexes,
                      "Missing index: idx_actions_status_engine on Action(status, engine)")
        self.assertIn('idx_actions_status_created', action_indexes,
                      "Missing index: idx_actions_status_created on Action(status, created_at)")

    def test_execution_indexes_exist(self):
        """Verify Execution model has the composite index for subquery."""
        from executions.models import Execution
        execution_indexes = [idx.name for idx in Execution._meta.indexes]

        self.assertIn('idx_exec_action_created', execution_indexes,
                      "Missing index: idx_exec_action_created on Execution(action, created_at)")


@pytest.mark.django_db
class TestNoPlusOneRegression(TestCase):
    """Tests de non-régression N+1 pour les endpoints catalogue."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username='n1user', profile='DBA')

        cls.tags = [Tag.objects.create(name=f'n1tag{i}') for i in range(5)]

        # Create actions with varying tag counts to detect N+1
        cls.actions = []
        for i in range(10):
            action = Action.objects.create(
                name=f'N1Action {i}',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=cls.user,
            )
            cls.actions.append(action)
            # Each action gets i % 5 + 1 tags
            for j in range(i % 5 + 1):
                ActionTag.objects.create(action=action, tag=cls.tags[j])

    def setUp(self):
        self.client = APIClient()
        _catalog_cache.clear()

    def test_no_n_plus_one_on_catalog_actions(self):
        """
        Verify query count does NOT scale with number of actions (N+1 detection).
        With 10 actions, if N+1 exists, we'd see 10+ additional queries.
        """
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/actions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        action_count = len(response.data.get('data', []))
        query_count = len(ctx.captured_queries)

        _log_queries(ctx, f"N+1 check: {action_count} actions, {query_count} queries")

        # With proper select_related/prefetch_related, query count should be
        # bounded regardless of action count (typically 3-5 queries)
        self.assertLessEqual(
            query_count, 10,
            f"Possible N+1: {query_count} queries for {action_count} actions"
        )

    def test_no_n_plus_one_on_catalog_tags(self):
        """Verify tags endpoint has no N+1."""
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/api/v1/catalog/tags/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tag_count = len(response.data.get('data', []))
        query_count = len(ctx.captured_queries)

        _log_queries(ctx, f"N+1 check tags: {tag_count} tags, {query_count} queries")

        self.assertLessEqual(
            query_count, 6,
            f"Possible N+1 on tags: {query_count} queries for {tag_count} tags"
        )
