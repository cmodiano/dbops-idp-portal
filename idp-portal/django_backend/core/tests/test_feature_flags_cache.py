"""
Story 22.16: Feature flags cache tests.

Tests cover:
- MED-3: Anti-thundering herd lock (concurrent access, only 1 DB load)
- MED-4: Cache key includes source (env/database), source change invalidation
- Lock timeout behaviour
"""

import threading
import time
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from core import feature_flags


# ============================================================================
# Task 4: Anti-thundering herd lock tests (AC: #1, #4, #5, #6)
# ============================================================================

@pytest.mark.django_db
class TestThunderingHerdPrevention:
    """Tests for MED-3: anti-thundering herd lock in _get_all_flags()."""

    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_thundering_herd_prevention(self):
        """AC #4, #6: 20 concurrent requests → exactly 1 DB load."""
        call_count = {'value': 0}
        original_flags = {'test_flag': {'enabled': True, 'rollout_percent': 100}}

        def slow_db_load():
            call_count['value'] += 1
            time.sleep(0.05)  # Simulate DB latency
            return original_flags

        results = []
        errors = []

        def worker():
            try:
                result = feature_flags._get_all_flags()
                results.append(result)
            except Exception as e:
                errors.append(e)

        with patch('core.feature_flags._load_flags_from_database', side_effect=slow_db_load):
            threads = [threading.Thread(target=worker) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        assert not errors, f"Worker errors: {errors}"
        assert len(results) == 20, f"Expected 20 results, got {len(results)}"
        # Only 1 DB load (the lock holder). A second load may happen if
        # timeout is hit, but with 50ms DB latency and 5s timeout, that
        # should not occur.
        assert call_count['value'] == 1, (
            f"Expected exactly 1 DB call, got {call_count['value']}"
        )

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_concurrent_requests_same_result(self):
        """AC #4: All 20 concurrent requests receive the same result."""
        original_flags = {'shared_flag': {'enabled': True, 'rollout_percent': 50}}

        def slow_db_load():
            time.sleep(0.05)
            return original_flags

        results = []

        def worker():
            results.append(feature_flags._get_all_flags())

        with patch('core.feature_flags._load_flags_from_database', side_effect=slow_db_load):
            threads = [threading.Thread(target=worker) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        assert len(results) == 20
        for r in results:
            assert r == original_flags, f"Expected {original_flags}, got {r}"

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_timeout(self):
        """AC #5: Lock timeout emits WARNING and loads anyway."""
        # Manually hold the lock to simulate a stuck loader
        source = 'database'
        lock_key = f'feature_flags:all:{source}:lock'
        cache.add(lock_key, True, 10)  # Hold lock for 10s

        fallback_flags = {'timeout_flag': {'enabled': True}}

        with patch('core.feature_flags._load_flags_from_database', return_value=fallback_flags) as mock_load, \
             patch('core.feature_flags.logger') as mock_logger:
            result = feature_flags._get_all_flags()

        # Should have hit timeout and loaded anyway
        mock_load.assert_called_once()
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == 'feature_flag_lock_timeout'
        assert result == fallback_flags

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"env_flag":{"enabled":true,"rollout_percent":100}}',
        FEATURE_FLAGS_LOCK_TIMEOUT=1,
    )
    def test_lock_timeout_env_source(self):
        """AC #5: Lock timeout with env source also falls back."""
        source = 'env'
        lock_key = f'feature_flags:all:{source}:lock'
        cache.add(lock_key, True, 10)

        with patch('core.feature_flags.logger') as mock_logger:
            result = feature_flags._get_all_flags()

        mock_logger.warning.assert_called_once()
        assert 'env_flag' in result

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_lock_released_after_load(self):
        """Lock is released after successful load, allowing future loads."""
        flags = {'test': {'enabled': True}}

        with patch('core.feature_flags._load_flags_from_database', return_value=flags):
            feature_flags._get_all_flags()

        # Lock should be released
        source = 'database'
        lock_key = f'feature_flags:all:{source}:lock'
        assert cache.get(lock_key) is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_lock_released_on_exception(self):
        """Lock is released even if load raises an exception."""
        with patch('core.feature_flags._load_flags_from_database', side_effect=RuntimeError("DB down")):
            with pytest.raises(RuntimeError):
                feature_flags._get_all_flags()

        source = 'database'
        lock_key = f'feature_flags:all:{source}:lock'
        assert cache.get(lock_key) is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_cache_hit_skips_lock(self):
        """When cache is populated, no lock is acquired."""
        source = 'database'
        cache_key = f'feature_flags:all:{source}'
        cached_flags = {'cached': {'enabled': True}}
        cache.set(cache_key, cached_flags, 300)

        with patch('core.feature_flags._load_flags_from_database') as mock_load:
            result = feature_flags._get_all_flags()

        mock_load.assert_not_called()
        assert result == cached_flags


# ============================================================================
# Task 5: Cache key includes source tests (AC: #2, #3, #7)
# ============================================================================

@pytest.mark.django_db
class TestCacheKeyIncludesSource:
    """Tests for MED-4: cache key includes source."""

    def setup_method(self):
        cache.clear()

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"env_flag":{"enabled":true,"rollout_percent":100}}',
    )
    def test_cache_key_includes_source_env(self):
        """AC #2: Cache key is 'feature_flags:all:env' when source=env."""
        feature_flags._get_all_flags()
        assert cache.get('feature_flags:all:env') is not None
        assert cache.get('feature_flags:all:database') is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_cache_key_includes_source_database(self):
        """AC #2: Cache key is 'feature_flags:all:database' when source=database."""
        db_flags = {'db_flag': {'enabled': True, 'rollout_percent': 100}}

        with patch('core.feature_flags._load_flags_from_database', return_value=db_flags):
            feature_flags._get_all_flags()

        assert cache.get('feature_flags:all:database') is not None
        assert cache.get('feature_flags:all:env') is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='database',
        FEATURE_FLAGS_ENABLED=True,
    )
    def test_per_flag_cache_key_includes_source(self):
        """AC #2: Per-flag cache key is 'feature_flag:{key}:{source}'."""
        db_flags = {'my_flag': {'enabled': True, 'rollout_percent': 100}}

        with patch('core.feature_flags._load_flags_from_database', return_value=db_flags):
            feature_flags._get_flag_config('my_flag')

        assert cache.get('feature_flag:my_flag:database') is not None
        assert cache.get('feature_flag:my_flag:env') is None

    def test_source_change_invalidates_old_cache(self):
        """AC #3, #7: Changing source returns new flags, old source cache ignored."""
        db_flags = {'db_only': {'enabled': True, 'rollout_percent': 100}}
        env_flags_str = '{"env_only":{"enabled":true,"rollout_percent":100}}'

        # Step 1: Load with source=database
        with override_settings(
            FEATURE_FLAGS_SOURCE='database',
            FEATURE_FLAGS_ENABLED=True,
        ):
            with patch('core.feature_flags._load_flags_from_database', return_value=db_flags):
                result_db = feature_flags._get_all_flags()

        assert result_db == db_flags
        assert cache.get('feature_flags:all:database') is not None

        # Step 2: Change source to env
        with override_settings(
            FEATURE_FLAGS_SOURCE='env',
            FEATURE_FLAGS_ENABLED=True,
            FEATURE_FLAGS=env_flags_str,
        ):
            result_env = feature_flags._get_all_flags()

        # Must get env flags, NOT database flags
        assert 'env_only' in result_env
        assert 'db_only' not in result_env
        assert cache.get('feature_flags:all:env') is not None

    def test_source_change_database_to_env(self):
        """AC #7: After source change from database→env, old DB flags not returned."""
        db_flags = {'feature_a': {'enabled': True, 'rollout_percent': 100}}
        env_flags_str = '{"feature_b":{"enabled":true,"rollout_percent":50}}'

        # Load database flags into cache
        with override_settings(
            FEATURE_FLAGS_SOURCE='database',
            FEATURE_FLAGS_ENABLED=True,
        ):
            with patch('core.feature_flags._load_flags_from_database', return_value=db_flags):
                feature_flags._get_all_flags()

        assert cache.get('feature_flags:all:database') == db_flags

        # Switch to env source
        with override_settings(
            FEATURE_FLAGS_SOURCE='env',
            FEATURE_FLAGS_ENABLED=True,
            FEATURE_FLAGS=env_flags_str,
        ):
            result = feature_flags._get_all_flags()

        assert 'feature_b' in result
        assert 'feature_a' not in result

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"flag_x":{"enabled":true}}',
    )
    def test_invalidate_cache_clears_both_sources(self):
        """invalidate_cache() clears cache for both env and database sources."""
        # Populate caches for both sources
        cache.set('feature_flags:all:env', {'flag_x': {'enabled': True}}, 300)
        cache.set('feature_flags:all:database', {'flag_y': {'enabled': True}}, 300)
        cache.set('feature_flag:flag_x:env', {'enabled': True}, 300)
        cache.set('feature_flag:flag_x:database', {'enabled': True}, 300)

        feature_flags.invalidate_cache('flag_x')

        assert cache.get('feature_flags:all:env') is None
        assert cache.get('feature_flags:all:database') is None
        assert cache.get('feature_flag:flag_x:env') is None
        assert cache.get('feature_flag:flag_x:database') is None

    @override_settings(
        FEATURE_FLAGS_SOURCE='env',
        FEATURE_FLAGS_ENABLED=True,
        FEATURE_FLAGS='{"flag_a":{"enabled":true}}',
    )
    def test_invalidate_all_clears_both_sources(self):
        """invalidate_cache(flag_key=None) clears all-flags cache for both sources."""
        cache.set('feature_flags:all:env', {'flag_a': {'enabled': True}}, 300)
        cache.set('feature_flags:all:database', {'flag_b': {'enabled': True}}, 300)

        feature_flags.invalidate_cache()

        assert cache.get('feature_flags:all:env') is None
        assert cache.get('feature_flags:all:database') is None
