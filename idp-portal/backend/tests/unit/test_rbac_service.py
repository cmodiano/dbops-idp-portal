"""Tests for RBAC service: navigation permissions and cache behavior (Story 2.12 cumulative)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.profile import (
    CumulativePermissionsResponse,
    ProfileActionPermissionsResponse,
    ProfileTargetPermissionsResponse,
)
from app.services.rbac_service import (
    get_user_navigation_permissions,
    can_execute,
    invalidate_cache,
    invalidate_permissions_cache,
    get_cumulative_permissions,
    get_cumulative_permissions_cached,
    _permission_cache,
    _cumulative_permissions_cache,
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
    """Tests for can_execute with granular RBAC (Story 7.3)."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear permission cache before each test."""
        _permission_cache.clear()
        _cumulative_permissions_cache.clear()
        yield
        _permission_cache.clear()
        _cumulative_permissions_cache.clear()

    async def test_can_execute_with_actions_type_all(self):
        """User with actions_type=all can execute any action in allowed env."""
        perms = CumulativePermissionsResponse(
            actions_type="all",
            action_ids=[],
            tag_patterns=[],
            environments=["DEV", "PROD"],
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dbops"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            result = await can_execute(1, 10, "PROD")
            assert result is True

    async def test_can_execute_with_action_id_in_list(self):
        """User with action_id in action_ids list can execute that action."""
        perms = CumulativePermissionsResponse(
            actions_type="list",
            action_ids=[10, 20, 30],
            tag_patterns=[],
            environments=["DEV", "STAGING"],
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dba"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            result = await can_execute(1, 10, "DEV")
            assert result is True

    async def test_can_execute_with_tag_pattern_match(self):
        """User with tag_pattern matching action tags can execute."""
        perms = CumulativePermissionsResponse(
            actions_type="pattern",
            action_ids=[],
            tag_patterns=["provisioning", "patching"],
            environments=["DEV", "PROD"],
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch("app.services.rbac_service.catalog_repository") as mock_catalog_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dba"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            mock_catalog_repo.get_tags_for_action = AsyncMock(return_value=["provisioning", "oracle"])
            result = await can_execute(1, 10, "DEV")
            assert result is True

    async def test_can_execute_denied_wrong_environment(self):
        """Returns False when environment not in allowed list."""
        perms = CumulativePermissionsResponse(
            actions_type="all",
            action_ids=[],
            tag_patterns=[],
            environments=["DEV"],  # Only DEV allowed
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dba"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            result = await can_execute(1, 10, "PROD")  # PROD not allowed
            assert result is False

    async def test_can_execute_denied_no_action_permission(self):
        """Returns False when action not in allowed actions and no tag match."""
        perms = CumulativePermissionsResponse(
            actions_type="list",
            action_ids=[20, 30],  # Action 10 not in list
            tag_patterns=["monitoring"],
            environments=["DEV", "PROD"],
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch("app.services.rbac_service.catalog_repository") as mock_catalog_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dba"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            mock_catalog_repo.get_tags_for_action = AsyncMock(return_value=["provisioning"])  # No match
            result = await can_execute(1, 10, "DEV")
            assert result is False

    async def test_can_execute_caches_result(self):
        """Second call uses cache, not repository."""
        perms = CumulativePermissionsResponse(
            actions_type="all",
            action_ids=[],
            tag_patterns=[],
            environments=["DEV", "PROD"],
            targets_type="list",
            target_names=[],
            target_patterns=[],
        )
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
            patch(
                "app.services.rbac_service.get_cumulative_permissions_cached",
                new_callable=AsyncMock,
                return_value=perms,
            ),
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "dbops"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(
                return_value=[type("Profile", (), {"id": 1})()]
            )
            await can_execute(1, 10, "PROD")
            await can_execute(1, 10, "PROD")
            # Only one call to get_by_id — second hit cache
            assert mock_user_repo.get_by_id.await_count == 1

    async def test_can_execute_returns_false_when_user_not_found(self):
        """Returns False when user does not exist in database."""
        with patch("app.services.rbac_service.user_repository") as mock_user_repo:
            mock_user_repo.get_by_id = AsyncMock(return_value=None)
            result = await can_execute(999, 10, "DEV")
            assert result is False

    async def test_can_execute_returns_false_when_user_has_no_profile(self):
        """Returns False when user exists but has no profile."""
        with patch("app.services.rbac_service.user_repository") as mock_user_repo:
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": None})
            result = await can_execute(1, 10, "DEV")
            assert result is False

    async def test_can_execute_returns_false_when_no_profile_ids_found(self):
        """Returns False when user profile doesn't map to any profile IDs."""
        with (
            patch("app.services.rbac_service.user_repository") as mock_user_repo,
            patch("app.services.rbac_service.profile_repository") as mock_profile_repo,
        ):
            mock_user_repo.get_by_id = AsyncMock(return_value={"id": 1, "profile": "unknown_profile"})
            mock_profile_repo.find_by_ad_groups = AsyncMock(return_value=[])  # No profiles found
            result = await can_execute(1, 10, "DEV")
            assert result is False


class TestInvalidateCache:
    """Tests for cache invalidation."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _permission_cache.clear()
        _cumulative_permissions_cache.clear()
        yield
        _permission_cache.clear()
        _cumulative_permissions_cache.clear()

    async def test_invalidate_removes_user_entries(self):
        """invalidate_cache removes all entries for a user."""
        # Manually populate cache to test invalidation
        _permission_cache["1:10:PROD"] = True
        _permission_cache["1:20:DEV"] = True
        assert len(_permission_cache) == 2

        invalidate_cache(1)
        assert len(_permission_cache) == 0

    async def test_invalidate_preserves_other_users(self):
        """invalidate_cache only removes specified user's entries."""
        # Manually populate cache to test invalidation
        _permission_cache["1:10:PROD"] = True
        _permission_cache["2:10:PROD"] = True
        assert len(_permission_cache) == 2

        invalidate_cache(1)
        assert len(_permission_cache) == 1
        assert "2:10:PROD" in _permission_cache


class TestGetCumulativePermissions:
    """Story 2.12: union of permissions across profiles."""

    @pytest.mark.asyncio
    async def test_empty_profile_ids_returns_deny_all(self):
        result = await get_cumulative_permissions([])
        assert result.actions_type == "list"
        assert result.targets_type == "list"
        assert result.action_ids == []
        assert result.tag_patterns == []
        assert result.environments == []
        assert result.target_names == []
        assert result.target_patterns == []

    @pytest.mark.asyncio
    async def test_one_profile_list_union(self):
        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                return_value=ProfileActionPermissionsResponse(
                    actions_type="list",
                    action_ids=[1, 2],
                    tag_patterns=[],
                    environments=["DEV"],
                ),
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                return_value=ProfileTargetPermissionsResponse(
                    targets_type="list",
                    target_names=["t1"],
                    target_patterns=[],
                ),
            ),
        ):
            result = await get_cumulative_permissions([1])
        assert result.actions_type == "list"
        assert result.action_ids == [1, 2]
        assert result.environments == ["DEV"]
        assert result.targets_type == "list"
        assert result.target_names == ["t1"]

    @pytest.mark.asyncio
    async def test_two_profiles_union(self):
        async def actions_side_effect(profile_id):
            if profile_id == 1:
                return ProfileActionPermissionsResponse(
                    actions_type="list",
                    action_ids=[1],
                    tag_patterns=[],
                    environments=["DEV"],
                )
            return ProfileActionPermissionsResponse(
                actions_type="list",
                action_ids=[2, 3],
                tag_patterns=[],
                environments=["STAGING"],
            )

        async def targets_side_effect(profile_id):
            if profile_id == 1:
                return ProfileTargetPermissionsResponse(
                    targets_type="pattern",
                    target_names=[],
                    target_patterns=["assurance-*"],
                )
            return ProfileTargetPermissionsResponse(
                targets_type="list",
                target_names=["t2"],
                target_patterns=[],
            )

        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                side_effect=actions_side_effect,
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                side_effect=targets_side_effect,
            ),
        ):
            result = await get_cumulative_permissions([1, 2])
        assert result.actions_type == "list"
        assert set(result.action_ids) == {1, 2, 3}
        assert set(result.environments) == {"DEV", "STAGING"}
        assert result.targets_type == "pattern"
        assert "t2" in result.target_names
        assert "assurance-*" in result.target_patterns

    @pytest.mark.asyncio
    async def test_any_profile_all_actions_gives_all(self):
        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                return_value=ProfileActionPermissionsResponse(
                    actions_type="all",
                    action_ids=[],
                    tag_patterns=[],
                    environments=[],
                ),
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                return_value=ProfileTargetPermissionsResponse(
                    targets_type="list",
                    target_names=[],
                    target_patterns=[],
                ),
            ),
        ):
            result = await get_cumulative_permissions([1])
        assert result.actions_type == "all"
        assert result.targets_type == "list"


class TestGetCumulativePermissionsCached:
    @pytest.fixture(autouse=True)
    def clear_cumulative_cache(self):
        _cumulative_permissions_cache.clear()
        yield
        _cumulative_permissions_cache.clear()

    @pytest.mark.asyncio
    async def test_caches_result(self):
        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                return_value=ProfileActionPermissionsResponse(
                    actions_type="all",
                    action_ids=[],
                    tag_patterns=[],
                    environments=[],
                ),
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                return_value=ProfileTargetPermissionsResponse(
                    targets_type="all",
                    target_names=[],
                    target_patterns=[],
                ),
            ),
        ):
            await get_cumulative_permissions_cached(1, [1])
            await get_cumulative_permissions_cached(1, [1])
        assert len(_cumulative_permissions_cache) == 1

    @pytest.mark.asyncio
    async def test_invalidate_permissions_cache_clears_all(self):
        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                return_value=ProfileActionPermissionsResponse(
                    actions_type="all",
                    action_ids=[],
                    tag_patterns=[],
                    environments=[],
                ),
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                return_value=ProfileTargetPermissionsResponse(
                    targets_type="all",
                    target_names=[],
                    target_patterns=[],
                ),
            ),
        ):
            await get_cumulative_permissions_cached(1, [1])
        assert len(_cumulative_permissions_cache) == 1
        # Also populate permission cache
        _permission_cache["1:10:PROD"] = True
        assert len(_permission_cache) == 1
        invalidate_permissions_cache()
        assert len(_cumulative_permissions_cache) == 0
        assert len(_permission_cache) == 0  # Both caches should be cleared

    @pytest.mark.asyncio
    async def test_cache_invalidation_forces_refetch(self):
        """Task 5.3: After invalidation, next call refetches fresh data from repositories."""
        call_count = {"actions": 0, "targets": 0}

        async def actions_mock(profile_id):
            call_count["actions"] += 1
            return ProfileActionPermissionsResponse(
                actions_type="list",
                action_ids=[call_count["actions"]],  # Different each call
                tag_patterns=[],
                environments=[],
            )

        async def targets_mock(profile_id):
            call_count["targets"] += 1
            return ProfileTargetPermissionsResponse(
                targets_type="list",
                target_names=[f"target-{call_count['targets']}"],
                target_patterns=[],
            )

        with (
            patch(
                "app.services.rbac_service.profile_action_permission_repository.get_actions_permissions",
                new_callable=AsyncMock,
                side_effect=actions_mock,
            ),
            patch(
                "app.services.rbac_service.profile_target_permission_repository.get_target_permissions",
                new_callable=AsyncMock,
                side_effect=targets_mock,
            ),
        ):
            # First call: fetches from repository
            result1 = await get_cumulative_permissions_cached(1, [1])
            assert result1.action_ids == [1]
            assert call_count["actions"] == 1

            # Second call: uses cache, no new fetch
            result2 = await get_cumulative_permissions_cached(1, [1])
            assert result2.action_ids == [1]  # Same cached value
            assert call_count["actions"] == 1  # No additional call

            # Invalidate cache (simulates admin profile update)
            invalidate_permissions_cache()

            # Third call: must refetch (cache was cleared)
            result3 = await get_cumulative_permissions_cached(1, [1])
            assert result3.action_ids == [2]  # New value from fresh fetch
            assert call_count["actions"] == 2  # Repository was called again
