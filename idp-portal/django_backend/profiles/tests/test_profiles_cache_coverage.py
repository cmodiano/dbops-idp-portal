"""
Tests de couverture pour profiles/cache.py (Story 55).
Couvre les lignes manquantes 40-42 (bloc except de invalidate_permissions_cache).
"""
from unittest.mock import patch


class TestInvalidatePermissionsCache:
    """Tests pour profiles.cache.invalidate_permissions_cache."""

    def test_invalidate_success(self):
        """Cas nominal : cache.delete est appelé et le logger.info est déclenché."""
        with patch("profiles.cache.cache") as mock_cache, \
             patch("profiles.cache.logger") as mock_logger:
            from profiles.cache import invalidate_permissions_cache, RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL
            invalidate_permissions_cache()
            mock_cache.delete.assert_called_once_with(RBAC_CACHE_VERSION_KEY)
            mock_logger.info.assert_called_once_with(
                'rbac_permissions_cache_invalidated',
                cache_key=RBAC_CACHE_VERSION_KEY,
                ttl_seconds=RBAC_CACHE_TTL,
            )

    def test_invalidate_cache_exception_does_not_raise(self):
        """Lignes 40-42 : une exception levée par cache.delete doit être avalée et logger.warning appelé."""
        with patch("profiles.cache.cache") as mock_cache, \
             patch("profiles.cache.logger") as mock_logger:
            mock_cache.delete.side_effect = Exception("Redis indisponible")
            from profiles.cache import invalidate_permissions_cache
            # Ne doit pas lever
            invalidate_permissions_cache()
            mock_logger.warning.assert_called_once_with(
                'rbac_permissions_cache_invalidation_failed',
                exc_info=True,
            )

    def test_invalidate_cache_connection_error_does_not_raise(self):
        """Variante : ConnectionError avalée sans propager."""
        with patch("profiles.cache.cache") as mock_cache, \
             patch("profiles.cache.logger"):
            mock_cache.delete.side_effect = ConnectionError("timeout")
            from profiles.cache import invalidate_permissions_cache
            invalidate_permissions_cache()  # ne doit pas lever
