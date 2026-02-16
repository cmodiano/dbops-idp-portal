"""
Tests for BUG-BE-5: cache catalogue applies pagination systematically.
Story 30.3 — AC4.

Verifies that:
- Cache key includes page and page_size parameters
- Different pages produce different cache keys
- Pagination is applied before caching
"""

import pytest
from django.test import TestCase

from catalog.views import _get_cache_key, _catalog_cache


class TestCacheKeyIncludesPagination(TestCase):
    """Tests that _get_cache_key includes page and page_size."""

    def test_cache_key_contains_page_and_limit(self):
        """Cache key should include page and limit values."""
        key = _get_cache_key(
            user_id=1,
            tags_filter=None,
            page='1',
            page_size='20',
        )
        assert 'page_1' in key
        assert 'limit_20' in key

    def test_different_pages_different_cache_keys(self):
        """page=1 and page=2 should produce different cache keys."""
        key1 = _get_cache_key(user_id=1, tags_filter=None, page='1', page_size='20')
        key2 = _get_cache_key(user_id=1, tags_filter=None, page='2', page_size='20')
        assert key1 != key2

    def test_different_page_sizes_different_cache_keys(self):
        """limit=20 and limit=50 should produce different cache keys."""
        key1 = _get_cache_key(user_id=1, tags_filter=None, page='1', page_size='20')
        key2 = _get_cache_key(user_id=1, tags_filter=None, page='1', page_size='50')
        assert key1 != key2

    def test_default_page_values(self):
        """When no page/page_size, defaults to page_1:limit_20."""
        key = _get_cache_key(user_id=1, tags_filter=None)
        assert 'page_1' in key
        assert 'limit_20' in key

    def test_same_params_same_cache_key(self):
        """Same parameters should produce identical cache keys."""
        key1 = _get_cache_key(user_id=1, tags_filter=['db'], page='1', page_size='20')
        key2 = _get_cache_key(user_id=1, tags_filter=['db'], page='1', page_size='20')
        assert key1 == key2
