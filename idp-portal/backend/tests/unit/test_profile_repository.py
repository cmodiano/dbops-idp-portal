"""Tests for profile repository (Story 2.9, AC #5)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import oracledb

from app.models.profile import ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem
from app.repositories import profile_repository
from app.core.exceptions import InvalidStateError


@pytest.fixture
def sample_profile_create():
    return ProfileCreate(
        name="Assurance",
        description="Profil Assurance",
        ad_group="GRP-IDP-ASSURANCE",
        is_admin=False,
        is_auditor=True,
    )


@pytest.fixture
def sample_profile_response():
    return ProfileResponse(
        id=1,
        name="Assurance",
        description="Profil Assurance",
        ad_group="GRP-IDP-ASSURANCE",
        is_admin=False,
        is_auditor=True,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=datetime(2026, 1, 28, 10, 0, 0),
    )


@pytest.fixture
def mock_profile_row():
    return (
        1,
        "Assurance",
        "Profil Assurance",
        "GRP-IDP-ASSURANCE",
        0,
        1,
        datetime(2026, 1, 28, 10, 0, 0),
        datetime(2026, 1, 28, 10, 0, 0),
    )


@pytest.fixture
def mock_list_row():
    return (1, "Assurance", "GRP-IDP-ASSURANCE", datetime(2026, 1, 28, 10, 0, 0))


class TestRowConversions:
    def test_row_to_response(self, mock_profile_row):
        r = profile_repository._row_to_response(mock_profile_row)
        assert r.id == 1
        assert r.name == "Assurance"
        assert r.ad_group == "GRP-IDP-ASSURANCE"
        assert r.is_admin is False
        assert r.is_auditor is True

    def test_row_to_list_item(self, mock_list_row):
        r = profile_repository._row_to_list_item(mock_list_row)
        assert r.id == 1
        assert r.name == "Assurance"
        assert r.ad_group == "GRP-IDP-ASSURANCE"
        assert r.permission_count == 0


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_success(self, sample_profile_create, sample_profile_response):
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_var = MagicMock()
        mock_var.getvalue.return_value = [1]
        mock_conn.var = lambda _: mock_var
        mock_conn.commit = AsyncMock()
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_profile_response
                result = await profile_repository.create(sample_profile_create)

        assert result.id == 1
        assert result.name == "Assurance"
        mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_create_duplicate_name_raises(self, sample_profile_create):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=oracledb.IntegrityError())
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with pytest.raises(InvalidStateError) as exc_info:
                await profile_repository.create(sample_profile_create)
        assert exc_info.value.code == "DUPLICATE_NAME"


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_profile_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_profile_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "Assurance"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_by_id(999)

        assert result is None


class TestGetByName:
    """Story 2.13 — get_by_name for import upsert."""

    @pytest.mark.asyncio
    async def test_get_by_name_found(self, mock_profile_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_profile_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_by_name("Assurance")

        assert result is not None
        assert result.id == 1
        assert result.name == "Assurance"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_by_name("Unknown")

        assert result is None


class TestGetAll:
    @pytest.mark.asyncio
    async def test_get_all_empty(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_one(self, mock_list_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_list_row])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.get_all()

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].permission_count == 0


class TestFindByAdGroups:
    """Story 2.12: resolve profiles by AD groups."""

    @pytest.mark.asyncio
    async def test_find_by_ad_groups_empty_list_returns_empty(self):
        result = await profile_repository.find_by_ad_groups([])
        assert result == []

    @pytest.mark.asyncio
    async def test_find_by_ad_groups_one_match(self, mock_profile_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_profile_row])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.find_by_ad_groups(["GRP-IDP-ASSURANCE"])

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].ad_group == "GRP-IDP-ASSURANCE"

    @pytest.mark.asyncio
    async def test_find_by_ad_groups_two_groups_two_profiles(self, mock_profile_row):
        row2 = (
            2,
            "DBA App",
            "DBA Applicatif",
            "GRP-IDP-DBA-APP",
            0,
            0,
            datetime(2026, 1, 28, 10, 0, 0),
            datetime(2026, 1, 28, 10, 0, 0),
        )
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_profile_row, row2])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.find_by_ad_groups(
                ["GRP-IDP-ASSURANCE", "GRP-IDP-DBA-APP"]
            )

        assert len(result) == 2
        assert result[0].ad_group == "GRP-IDP-ASSURANCE"
        assert result[1].ad_group == "GRP-IDP-DBA-APP"


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_success(self, sample_profile_response):
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_profile_response
                result = await profile_repository.update(
                    1,
                    ProfileUpdate(ad_group="GRP-IDP-ASSURANCE-V2"),
                )

        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        with patch("app.repositories.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await profile_repository.update(999, ProfileUpdate(name="X"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_duplicate_name_raises(self, sample_profile_response):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=oracledb.IntegrityError())
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_profile_response
                with pytest.raises(InvalidStateError) as exc_info:
                    await profile_repository.update(1, ProfileUpdate(name="Other"))
        assert exc_info.value.code == "DUPLICATE_NAME"


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.delete(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.profile_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await profile_repository.delete(999)

        assert result is False
