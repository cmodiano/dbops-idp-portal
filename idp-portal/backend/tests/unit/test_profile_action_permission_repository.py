"""Tests for profile action permission repository (Story 2.10, AC2–AC5)."""

import pytest
from unittest.mock import AsyncMock, patch

from app.models.profile import (
    ProfileActionPermissionsUpdate,
    ProfileActionPermissionsResponse,
)
from app.repositories import profile_action_permission_repository as repo


@pytest.fixture
def perm_row_list():
    """DB row: LIST type, action_ids [1,2], envs [DEV,STAGING]."""
    return ("LIST", "[1, 2]", None, '["DEV", "STAGING"]')


@pytest.fixture
def perm_row_pattern():
    """DB row: PATTERN type, tag_patterns."""
    return ("PATTERN", None, '["oracle", "provisioning"]', "[]")


@pytest.fixture
def perm_row_all():
    return ("ALL", None, None, None)


class TestGetActionsPermissions:
    @pytest.mark.asyncio
    async def test_get_found_list(self, perm_row_list):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=perm_row_list)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_actions_permissions(1)

        assert result is not None
        assert result.actions_type == "list"
        assert result.action_ids == [1, 2]
        assert result.tag_patterns == []
        assert result.environments == ["DEV", "STAGING"]

    @pytest.mark.asyncio
    async def test_get_found_pattern(self, perm_row_pattern):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=perm_row_pattern)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_actions_permissions(1)

        assert result is not None
        assert result.actions_type == "pattern"
        assert result.tag_patterns == ["oracle", "provisioning"]

    @pytest.mark.asyncio
    async def test_get_malformed_json_returns_empty(self):
        """Malformed JSON in DB should return empty lists (defensive coding)."""
        malformed_row = ("LIST", "not valid json", '["oracle", 123]', '{"not": "array"}')
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=malformed_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_actions_permissions(1)

        assert result is not None
        assert result.actions_type == "list"
        assert result.action_ids == []  # malformed JSON → empty
        assert result.tag_patterns == []  # mixed types → empty (validation fix)
        assert result.environments == []  # not an array → empty

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.get_actions_permissions(999)

        assert result is None


class TestSetActionsPermissions:
    @pytest.mark.asyncio
    async def test_set_list_success(self):
        payload = ProfileActionPermissionsUpdate(
            actions_type="list",
            action_ids=[1, 2],
            tag_patterns=[],
            environments=["DEV", "STAGING"],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_actions_permissions(1, payload)

        assert result.actions_type == "list"
        assert result.action_ids == [1, 2]
        assert result.environments == ["DEV", "STAGING"]
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_pattern_success(self):
        payload = ProfileActionPermissionsUpdate(
            actions_type="pattern",
            action_ids=[],
            tag_patterns=["oracle", "provisioning"],
            environments=[],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_actions_permissions(1, payload)

        assert result.actions_type == "pattern"
        assert result.tag_patterns == ["oracle", "provisioning"]
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_all_success(self):
        payload = ProfileActionPermissionsUpdate(
            actions_type="all",
            action_ids=[],
            tag_patterns=[],
            environments=[],
        )
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_action_permission_repository.get_connection") as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await repo.set_actions_permissions(1, payload)

        assert result.actions_type == "all"
        mock_conn.execute.assert_called_once()
