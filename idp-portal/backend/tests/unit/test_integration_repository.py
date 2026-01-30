"""Tests for integration repository (Story 2.27, AC1-AC4)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import oracledb

from app.models.integration import IntegrationCreate, IntegrationUpdate, IntegrationResponse, IntegrationType
from app.repositories import integration_repository
from app.repositories.integration_repository import DuplicateNameError


@pytest.fixture
def sample_integration_create():
    return IntegrationCreate(
        type=IntegrationType.AAP,
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
    )


@pytest.fixture
def sample_integration_response():
    return IntegrationResponse(
        id=1,
        type=IntegrationType.AAP,
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
        created_at=datetime(2026, 1, 29, 10, 0, 0),
        updated_at=datetime(2026, 1, 29, 10, 0, 0),
    )


@pytest.fixture
def mock_integration_row():
    return (
        1,
        "aap",
        "AAP Production",
        "https://aap.example.com",
        "secret/idp/aap-prod",
        "aap",
        datetime(2026, 1, 29, 10, 0, 0),
        datetime(2026, 1, 29, 10, 0, 0),
    )


class TestRowConversions:
    def test_row_to_integration_response(self, mock_integration_row):
        r = integration_repository._row_to_integration_response(mock_integration_row)
        assert r.id == 1
        assert r.type == IntegrationType.AAP
        assert r.name == "AAP Production"
        assert r.base_url == "https://aap.example.com"
        assert r.credential_ref == "secret/idp/aap-prod"
        assert r.icon == "aap"

    def test_row_to_integration_response_null_optional_fields(self):
        row = (
            2,
            "servicenow",
            "ServiceNow Dev",
            "https://dev.servicenow.com",
            None,  # credential_ref
            None,  # icon
            datetime(2026, 1, 29, 10, 0, 0),
            datetime(2026, 1, 29, 10, 0, 0),
        )
        r = integration_repository._row_to_integration_response(row)
        assert r.id == 2
        assert r.type == IntegrationType.SERVICENOW
        assert r.credential_ref is None
        assert r.icon is None


class TestGetAll:
    @pytest.mark.asyncio
    async def test_get_all_empty(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_with_data(self, mock_integration_row):
        row2 = (
            2,
            "servicenow",
            "ServiceNow Prod",
            "https://prod.servicenow.com",
            "secret/idp/snow-prod",
            "servicenow",
            datetime(2026, 1, 29, 11, 0, 0),
            datetime(2026, 1, 29, 11, 0, 0),
        )
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_integration_row, row2])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_all()

        assert len(result) == 2
        assert result[0].name == "AAP Production"
        assert result[1].name == "ServiceNow Prod"


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_integration_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_integration_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "AAP Production"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_by_id(999)

        assert result is None


class TestGetByName:
    @pytest.mark.asyncio
    async def test_get_by_name_found(self, mock_integration_row):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_integration_row)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_by_name("AAP Production")

        assert result is not None
        assert result.name == "AAP Production"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.get_by_name("Unknown")

        assert result is None


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_success(self, sample_integration_create, sample_integration_response):
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_var = MagicMock()
        mock_var.getvalue.return_value = [1]
        mock_conn.var = lambda _: mock_var
        mock_conn.commit = AsyncMock()
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_integration_response
                result = await integration_repository.create(sample_integration_create)

        assert result.id == 1
        assert result.name == "AAP Production"
        mock_get.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_create_duplicate_name_raises(self, sample_integration_create):
        mock_conn = AsyncMock()
        mock_var = MagicMock()
        mock_var.getvalue.return_value = [1]
        mock_conn.var = lambda _: mock_var
        exc = oracledb.IntegrityError()
        exc.args = ("UK_INTEGRATIONS_NAME",)
        mock_conn.execute = AsyncMock(side_effect=exc)
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with pytest.raises(DuplicateNameError) as exc_info:
                await integration_repository.create(sample_integration_create)
        assert "AAP Production" in str(exc_info.value)


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_success(self, sample_integration_response):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_integration_response
                result = await integration_repository.update(
                    1,
                    IntegrationUpdate(name="AAP Production v2"),
                )

        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await integration_repository.update(999, IntegrationUpdate(name="X"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_duplicate_name_raises(self, sample_integration_response):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        exc = oracledb.IntegrityError()
        exc.args = ("UK_INTEGRATIONS_NAME",)
        mock_conn.execute = AsyncMock(side_effect=exc)
        mock_conn.rollback = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = sample_integration_response
                with pytest.raises(DuplicateNameError):
                    await integration_repository.update(1, IntegrationUpdate(name="Other"))

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_existing(self, sample_integration_response):
        """When no fields provided, return existing without DB update."""
        with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_integration_response
            result = await integration_repository.update(1, IntegrationUpdate())

        assert result is not None
        assert result.id == 1


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.delete(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        mock_cursor = AsyncMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await integration_repository.delete(999)

        assert result is False
