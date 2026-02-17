"""
Tests d'intégration for BUG-BE-5: pagination + cache consistency.
Story 30.3 — Fixes CRIT-10.

Vérifie que:
- Cache hit retourne même format que cache miss
- Pagination réelle appliquée avant cache
- Pages différentes ont des données différentes
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action, ActionStatus
from catalog.views import _catalog_cache
from tests.factories import UserFactory


@pytest.mark.django_db
class TestCachePaginationIntegration(TestCase):
    """Tests d'intégration API pour cache + pagination."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(profile='dba')
        self.client.force_authenticate(user=self.user)

        # Create 25 published actions for multi-page testing
        for i in range(25):
            Action.objects.create(
                name=f'Action {i:02d}',
                description=f'Description {i}',
                category='Test',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user,
            )

        # Clear cache before each test
        _catalog_cache.clear()

    def tearDown(self):
        _catalog_cache.clear()

    def test_cache_miss_returns_paginated_format(self):
        """COLD: Cache miss should return DRF paginated format with count/next/previous."""
        response = self.client.get('/api/v1/catalog/actions?page=1&limit=10')

        assert response.status_code == status.HTTP_200_OK
        assert 'count' in response.data, "Paginated response must have 'count'"
        assert 'results' in response.data, "Paginated response must have 'results'"
        assert response.data['count'] == 25, "Should count all published actions"
        assert len(response.data['results']) == 10, "Should return 10 actions (limit)"

    def test_cache_hit_returns_same_format_as_miss(self):
        """HOT: Cache hit should return SAME format as cache miss (CRIT-1/CRIT-2 fix validation)."""
        # Cold request: cache miss
        response1 = self.client.get('/api/v1/catalog/actions?page=1&limit=10')
        assert response1.status_code == status.HTTP_200_OK
        format1 = set(response1.data.keys())

        # Hot request: cache hit
        response2 = self.client.get('/api/v1/catalog/actions?page=1&limit=10')
        assert response2.status_code == status.HTTP_200_OK
        format2 = set(response2.data.keys())

        # Format must be identical
        assert format1 == format2, f"Cache hit format {format2} != miss format {format1}"
        assert response1.data['count'] == response2.data['count']
        assert len(response1.data['results']) == len(response2.data['results'])

    def test_different_pages_have_different_data(self):
        """Page 1 and page 2 should contain different actions."""
        response1 = self.client.get('/api/v1/catalog/actions?page=1&limit=10')
        response2 = self.client.get('/api/v1/catalog/actions?page=2&limit=10')

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        ids_page1 = {a['id'] for a in response1.data['results']}
        ids_page2 = {a['id'] for a in response2.data['results']}

        # Pages should not overlap
        assert ids_page1.isdisjoint(ids_page2), "Page 1 and Page 2 should have different actions"

    def test_pagination_applied_before_cache(self):
        """Verify paginate_queryset() is called BEFORE caching."""
        # Request page 1 (cache miss)
        response1 = self.client.get('/api/v1/catalog/actions?page=1&limit=5')
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.data['results']) == 5

        # Request page 2 (different cache key)
        response2 = self.client.get('/api/v1/catalog/actions?page=2&limit=5')
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.data['results']) == 5

        # Verify results are different
        ids1 = {a['id'] for a in response1.data['results']}
        ids2 = {a['id'] for a in response2.data['results']}
        assert ids1 != ids2, "Page 1 and Page 2 must contain different actions"

    def test_cache_key_includes_page_and_limit(self):
        """Different page/limit combinations should produce different cache entries."""
        _catalog_cache.clear()

        # Create multiple cache entries
        self.client.get('/api/v1/catalog/actions?page=1&limit=10')
        self.client.get('/api/v1/catalog/actions?page=2&limit=10')
        self.client.get('/api/v1/catalog/actions?page=1&limit=20')

        # All should be cached separately
        assert len(_catalog_cache) == 3, "Should have 3 distinct cache entries"
