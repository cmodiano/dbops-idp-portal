"""Tests for profile target permission repository (Story 2.11, AC1–AC5)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.models.profile import (
    ProfileTargetPermissionsUpdate,
    ProfileTargetPermissionsResponse,
)
from app.repositories import profile_target_permission_repository as repo


@pytest.fixture
def perm_row_list():
    """DB row: LIST type, target_names."""
    return ("LIST", '["assurance-db01", "assurance-db02"]', None)


@pytest.fixture
def perm_row_pattern():
    """DB row: PATTERN type, target_patterns."""
    return ("PATTERN", None, '["assurance-*", "infra-*"]')


@pytest.fixture
def perm_row_all():
    return ("ALL", None, None)


class TestGetTargetPermissions:
    @pytest.mark.asyncio
    async def test_get_found_list(self, perm_row_list):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=perm_row_list)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_target_permissions(1)

        assert result is not None
        assert result.targets_type == "list"
        assert result.target_names == ["assurance-db01", "assurance-db02"]
        assert result.target_patterns == []

    @pytest.mark.asyncio
    async def test_get_found_pattern(self, perm_row_pattern):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=perm_row_pattern)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_target_permissions(1)

        assert result is not None
        assert result.targets_type == "pattern"
        assert result.target_patterns == ["assurance-*", "infra-*"]
        assert result.target_names == []

    @pytest.mark.asyncio
    async def test_get_malformed_json_returns_empty(self):
        malformed_row = ("LIST", "not valid json", "{ not array }")
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=malformed_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_target_permissions(1)

        assert result is not None
        assert result.targets_type == "list"
        assert result.target_names == []
        assert result.target_patterns == []

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_target_permissions(999)

        assert result is None


class TestSetTargetPermissions:
    @pytest.mark.asyncio
    async def test_set_list_success(self):
        payload = ProfileTargetPermissionsUpdate(
            targets_type="list",
            target_names=["assurance-db01", "assurance-db02"],
            target_patterns=[],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_target_permissions(1, payload)

        assert result.targets_type == "list"
        assert result.target_names == ["assurance-db01", "assurance-db02"]
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_pattern_success(self):
        payload = ProfileTargetPermissionsUpdate(
            targets_type="pattern",
            target_names=[],
            target_patterns=["assurance-*", "infra-*"],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_target_permissions(1, payload)

        assert result.targets_type == "pattern"
        assert result.target_patterns == ["assurance-*", "infra-*"]
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_all_success(self):
        payload = ProfileTargetPermissionsUpdate(
            targets_type="all",
            target_names=[],
            target_patterns=[],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_target_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_target_permissions(1, payload)

        assert result.targets_type == "all"
        mock_conn.execute.assert_called_once()


class TestMatchTargets:
    def test_all_returns_all_available(self):
        perms = [
            ProfileTargetPermissionsResponse(targets_type="all", target_names=[], target_patterns=[]),
        ]
        available = ["assurance-db01", "infra-prod"]
        assert repo.match_targets(perms, available) == ["assurance-db01", "infra-prod"]

    def test_list_filters_by_names_in_inventory(self):
        perms = [
            ProfileTargetPermissionsResponse(
                targets_type="list",
                target_names=["assurance-db01", "unknown-db"],
                target_patterns=[],
            ),
        ]
        available = ["assurance-db01", "assurance-db02", "infra-prod"]
        assert repo.match_targets(perms, available) == ["assurance-db01"]

    def test_pattern_fnmatch(self):
        perms = [
            ProfileTargetPermissionsResponse(
                targets_type="pattern",
                target_names=[],
                target_patterns=["assurance-*"],
            ),
        ]
        available = ["assurance-db01", "assurance-db02", "infra-oracle-prod"]
        assert repo.match_targets(perms, available) == ["assurance-db01", "assurance-db02"]

    def test_cumulate_multiple_profiles(self):
        perms = [
            ProfileTargetPermissionsResponse(
                targets_type="list",
                target_names=["assurance-db01"],
                target_patterns=[],
            ),
            ProfileTargetPermissionsResponse(
                targets_type="pattern",
                target_names=[],
                target_patterns=["infra-*"],
            ),
        ]
        available = ["assurance-db01", "assurance-db02", "infra-oracle-prod"]
        result = repo.match_targets(perms, available)
        assert sorted(result) == ["assurance-db01", "infra-oracle-prod"]

    def test_empty_permissions_returns_empty(self):
        assert repo.match_targets([], ["a", "b"]) == []
        perms = [
            ProfileTargetPermissionsResponse(targets_type="list", target_names=[], target_patterns=[]),
        ]
        assert repo.match_targets(perms, ["a", "b"]) == []
