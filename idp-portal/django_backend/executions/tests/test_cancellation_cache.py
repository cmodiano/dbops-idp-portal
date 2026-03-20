"""
Unit tests for cancellation cache — Story 20.3 AC5, Story 86.6

Tests the Redis-based cancellation cache that reduces database queries
for high-volume retry workflows.
Story 86.6: clé `cancellation:{execution_id}`, TTL 24h, tests multi-worker.
"""

import pytest
from unittest.mock import patch
from django.test import override_settings

from executions.cancellation_cache import is_cancelled, mark_cancelled
from executions.models import Execution, ExecutionStatus
from catalog.models import ActionStatus
from tests.factories import UserFactory, ActionFactory


@pytest.mark.django_db
class TestCancellationCacheDisabled:
    """Tests when WORKFLOW_RETRY_USE_CANCELLATION_CACHE = False (default)."""

    def setup_method(self):
        self.user = UserFactory(username="cache_disabled_user")
        self.action = ActionFactory(
            name="Cache Test Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    def test_is_cancelled_returns_true_for_cancelled_execution(self):
        """Direct DB check returns True for cancelled execution."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )
        assert is_cancelled(execution.id) is True

    def test_is_cancelled_returns_false_for_running_execution(self):
        """Direct DB check returns False for running execution."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        assert is_cancelled(execution.id) is False

    def test_is_cancelled_returns_false_for_nonexistent_execution(self):
        """Direct DB check returns False for non-existent execution."""
        assert is_cancelled(99999) is False

    def test_mark_cancelled_is_noop_when_disabled(self):
        """mark_cancelled does nothing when cache is disabled."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        # Should not raise, just no-op
        mark_cancelled(execution.id)


@pytest.mark.django_db
class TestCancellationCacheEnabled:
    """Tests when WORKFLOW_RETRY_USE_CANCELLATION_CACHE = True."""

    def setup_method(self):
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory(username="cache_enabled_user")
        self.action = ActionFactory(
            name="Cache Enabled Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_is_cancelled_caches_result(self):
        """First call queries DB, second call should use cache."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )

        # First call: DB hit
        result1 = is_cancelled(execution.id)
        assert result1 is True

        # Second call: should get from cache (we can verify by changing DB)
        execution.status = ExecutionStatus.RUNNING
        execution.save()

        result2 = is_cancelled(execution.id)
        # Still True because cached value is True (TTL 24h)
        assert result2 is True

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_mark_cancelled_updates_cache(self):
        """mark_cancelled sets cache to True immediately."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )

        # Before marking: should be False (from DB)
        assert is_cancelled(execution.id) is False

        # Mark as cancelled in cache
        mark_cancelled(execution.id)

        # Now should be True (from cache, even though DB still says RUNNING)
        assert is_cancelled(execution.id) is True

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_is_cancelled_caches_cancelled_result_with_24h_ttl(self):
        """is_cancelled popule le cache avec timeout=86400 pour une exécution annulée."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )
        with patch("executions.cancellation_cache.cache.set") as mock_set:
            with patch("executions.cancellation_cache.cache.get", return_value=None):
                is_cancelled(execution.id)
        mock_set.assert_called_once_with(f"cancellation:{execution.id}", True, timeout=86400)

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_mark_cancelled_logs_and_survives_redis_failure(self):
        """mark_cancelled log un warning sans propager l'exception Redis."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        with patch("executions.cancellation_cache.cache.set", side_effect=Exception("Redis down")):
            # Should not raise — Redis failure must be silent
            mark_cancelled(execution.id)

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_cache_fallback_on_error(self):
        """If cache raises exception, falls back to DB."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.CANCELLED,
        )

        with patch("executions.cancellation_cache.cache.get", side_effect=Exception("Redis down")):
            result = is_cancelled(execution.id)

        # Should still return True (from DB fallback)
        assert result is True


@pytest.mark.django_db
class TestCancellationCacheMultiWorker:
    """Tests du comportement multi-worker du cache d'annulation — Story 86.6."""

    def setup_method(self):
        from django.core.cache import cache
        cache.clear()
        self.user = UserFactory(username="multi_worker_user")
        self.action = ActionFactory(
            name="Multi Worker Test Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
        )

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_mark_in_worker1_visible_in_worker2(self):
        """Worker 1 marque annulé → Worker 2 lit depuis cache sans DB."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        # Worker 1: marque l'annulation
        mark_cancelled(execution.id)

        # Worker 2: lit le statut — doit venir du cache (pas de DB query)
        with patch("executions.cancellation_cache._check_db") as mock_db:
            result = is_cancelled(execution.id)

        assert result is True
        mock_db.assert_not_called()  # cache hit — aucune requête DB

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_cancel_persists_across_multiple_reads(self):
        """mark_cancelled + 3× is_cancelled → tous True, _check_db jamais appelée."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        mark_cancelled(execution.id)

        with patch("executions.cancellation_cache._check_db") as mock_db:
            results = [is_cancelled(execution.id) for _ in range(3)]

        assert all(r is True for r in results)
        mock_db.assert_not_called()  # cache hits — aucune requête DB après mark_cancelled

    @override_settings(WORKFLOW_RETRY_USE_CANCELLATION_CACHE=True)
    def test_ttl_is_24h(self):
        """cache.set est appelé avec timeout=86400."""
        execution = Execution.objects.create(
            action=self.action, user=self.user,
            environment="dev", status=ExecutionStatus.RUNNING,
        )
        with patch("executions.cancellation_cache.cache.set") as mock_set:
            mark_cancelled(execution.id)
        mock_set.assert_called_once_with(f"cancellation:{execution.id}", True, timeout=86400)
