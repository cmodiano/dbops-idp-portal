"""Tests for RBAC permissions cache invalidation (Story 30.14, AC3; Story 34.3, NEW-3).

Verifies that invalidate_permissions_cache() clears the cache version key,
causing CatalogRBACService.get_permissions() to re-fetch from the database.

Story 34.3 - NEW-3: Function moved to profiles/cache.py. Both import paths tested.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache

from catalog.rbac_service import CatalogRBACService
from profiles.cache import RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL
from profiles.views import invalidate_permissions_cache
from tests.factories import UserFactory


@pytest.mark.django_db
class TestRBACCacheInvalidation:
    """Test that RBAC cache is properly invalidated on profile changes."""

    def setup_method(self) -> None:
        cache.clear()
        self.user = UserFactory.create(profile='DBA')
        self.service = CatalogRBACService()

    def teardown_method(self) -> None:
        cache.clear()

    def test_invalidate_permissions_cache_deletes_version_key(self) -> None:
        """invalidate_permissions_cache() deletes the RBAC cache version key."""
        cache.set(RBAC_CACHE_VERSION_KEY, '12345', RBAC_CACHE_TTL)
        assert cache.get(RBAC_CACHE_VERSION_KEY) == '12345'

        invalidate_permissions_cache()

        assert cache.get(RBAC_CACHE_VERSION_KEY) is None

    @patch('catalog.rbac_service.get_user_ad_groups', return_value=['DBA-Team'])
    @patch('catalog.rbac_service.ProfileService')
    def test_get_permissions_caches_result(self, mock_profile_cls, mock_ad_groups) -> None:
        """get_permissions() caches the result and serves from cache on second call."""
        mock_service = MagicMock()
        mock_service.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {'actions_type': 'all', 'environments': ['dev', 'prod']}
            ],
        }
        mock_profile_cls.return_value = mock_service

        # First call — should hit ProfileService
        result1 = self.service.get_permissions(self.user)
        assert result1 is not None
        assert result1['actions_type'] == 'all'
        assert mock_service.get_cumulative_permissions.call_count == 1

        # Second call — should serve from cache
        result2 = self.service.get_permissions(self.user)
        assert result2 == result1
        # ProfileService should NOT be called again
        assert mock_service.get_cumulative_permissions.call_count == 1

    @patch('catalog.rbac_service.get_user_ad_groups', return_value=['DBA-Team'])
    @patch('catalog.rbac_service.ProfileService')
    def test_invalidation_forces_refetch(self, mock_profile_cls, mock_ad_groups) -> None:
        """After invalidation, get_permissions() re-fetches from database."""
        mock_service = MagicMock()
        mock_service.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {'actions_type': 'all', 'environments': ['dev']}
            ],
        }
        mock_profile_cls.return_value = mock_service

        # First call populates cache
        self.service.get_permissions(self.user)
        assert mock_service.get_cumulative_permissions.call_count == 1

        # Invalidate cache (simulates profile update)
        invalidate_permissions_cache()

        # Second call should re-fetch since version key was deleted
        self.service.get_permissions(self.user)
        assert mock_service.get_cumulative_permissions.call_count == 2

    @patch('catalog.rbac_service.get_user_ad_groups', return_value=['DBA-Team'])
    @patch('catalog.rbac_service.ProfileService')
    def test_cache_resilient_to_cache_failure(self, mock_profile_cls, mock_ad_groups) -> None:
        """get_permissions() works even when cache is unavailable."""
        mock_service = MagicMock()
        mock_service.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {'actions_type': 'list', 'action_ids': [1, 2], 'environments': ['dev']}
            ],
        }
        mock_profile_cls.return_value = mock_service

        # Simulate cache failure
        with patch('catalog.rbac_service.cache') as mock_cache:
            mock_cache.get.side_effect = Exception('Cache down')
            mock_cache.set.side_effect = Exception('Cache down')

            result = self.service.get_permissions(self.user)
            assert result is not None
            assert result['actions_type'] == 'list'


class TestInvalidatePermissionsCacheFromCacheModule:
    """Story 34.3 - NEW-3: invalidate_permissions_cache() is importable from profiles.cache."""

    def test_invalidate_permissions_cache_from_cache_module(self) -> None:
        """AC6: importable from profiles.cache, calls cache.delete(RBAC_CACHE_VERSION_KEY)."""
        from profiles.cache import invalidate_permissions_cache as fn_from_cache

        with patch('profiles.cache.cache') as mock_cache:
            fn_from_cache()
            mock_cache.delete.assert_called_once_with(RBAC_CACHE_VERSION_KEY)

    def test_invalidate_permissions_cache_backward_compat_via_views(self) -> None:
        """profiles.views.invalidate_permissions_cache is the same function as profiles.cache."""
        from profiles.cache import invalidate_permissions_cache as fn_cache
        from profiles.views import invalidate_permissions_cache as fn_views

        assert fn_cache is fn_views, (
            "profiles.views.invalidate_permissions_cache must re-export profiles.cache version"
        )
