"""Tests for RBAC service: navigation permissions and cache behavior."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.rbac_service import (
    get_user_navigation_permissions,
    can_execute,
    invalidate_cache,
    _permission_cache,
)


class TestNavigationPermissions:
    """Tests for get_user_navigation_permissions."""

    def test_dbops_gets_four_tabs(self):
        """DBOPS profile gets catalog, executions, dashboard, admin."""
        tabs = get_user_navigation_permissions("dbops")
        assert tabs == ["catalog", "executions", "dashboard", "admin"]

    def test_dbops_case_insensitive(self):
        """Profile matching is case-insensitive."""
        tabs = get_user_navigation_permissions("DBOPS")
        assert tabs == ["catalog", "executions", "dashboard", "admin"]

    def test_dba_applicatif_gets_three_tabs(self):
        """DBA Applicatif profile gets catalog, executions, dashboard (no admin)."""
        tabs = get_user_navigation_permissions("dba_applicatif")
        assert tabs == ["catalog", "executions", "dashboard"]
        assert "admin" not in tabs

    def test_dba_infrastructure_gets_three_tabs(self):
        """DBA Infrastructure profile gets catalog, executions, dashboard (no admin)."""
        tabs = get_user_navigation_permissions("dba_infrastructure")
        assert tabs == ["catalog", "executions", "dashboard"]
        assert "admin" not in tabs

    def test_unknown_profile_gets_default_tabs(self):
        """Unknown profile gets default tabs (no admin)."""
        tabs = get_user_navigation_permissions("unknown_profile")
        assert tabs == ["catalog", "executions", "dashboard"]
        assert "admin" not in tabs


class TestCanExecute:
    """Tests for can_execute with caching."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear permission cache before each test."""
        _permission_cache.clear()
        yield
        _permission_cache.clear()

    async def test_can_execute_queries_repository(self):
        """First call queries user_repository.has_permission."""
        with patch("app.services.rbac_service.user_repository") as mock_repo:
            mock_repo.has_permission = AsyncMock(return_value=True)
            result = await can_execute(1, 10, "PROD")
            assert result is True
            mock_repo.has_permission.assert_awaited_once_with(1, 10, "PROD")

    async def test_can_execute_caches_result(self):
        """Second call uses cache, not repository."""
        with patch("app.services.rbac_service.user_repository") as mock_repo:
            mock_repo.has_permission = AsyncMock(return_value=True)
            await can_execute(1, 10, "PROD")
            await can_execute(1, 10, "PROD")
            # Only one call — second hit cache
            assert mock_repo.has_permission.await_count == 1

    async def test_can_execute_returns_false(self):
        """Returns False when permission not found."""
        with patch("app.services.rbac_service.user_repository") as mock_repo:
            mock_repo.has_permission = AsyncMock(return_value=False)
            result = await can_execute(2, 20, "DEV")
            assert result is False


class TestInvalidateCache:
    """Tests for cache invalidation."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _permission_cache.clear()
        yield
        _permission_cache.clear()

    async def test_invalidate_removes_user_entries(self):
        """invalidate_cache removes all entries for a user."""
        with patch("app.services.rbac_service.user_repository") as mock_repo:
            mock_repo.has_permission = AsyncMock(return_value=True)
            await can_execute(1, 10, "PROD")
            await can_execute(1, 20, "DEV")
            assert len(_permission_cache) == 2

            invalidate_cache(1)
            assert len(_permission_cache) == 0

    async def test_invalidate_preserves_other_users(self):
        """invalidate_cache only removes specified user's entries."""
        with patch("app.services.rbac_service.user_repository") as mock_repo:
            mock_repo.has_permission = AsyncMock(return_value=True)
            await can_execute(1, 10, "PROD")
            await can_execute(2, 10, "PROD")
            assert len(_permission_cache) == 2

            invalidate_cache(1)
            assert len(_permission_cache) == 1
            assert "2:10:PROD" in _permission_cache
