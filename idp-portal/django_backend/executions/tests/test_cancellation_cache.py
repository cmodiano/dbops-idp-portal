"""
Unit tests for cancellation cache — Story 20.3 AC5

Tests the Redis-based cancellation cache that reduces database queries
for high-volume retry workflows.
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
        # Still True because cached value is True (TTL 60s)
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
