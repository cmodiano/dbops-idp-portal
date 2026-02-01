"""Tests for integration repository (Story 2.27, 4.9, 5.3)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import oracledb

from app.models.integration import IntegrationCreate, IntegrationUpdate, IntegrationResponse, AuthFlow
from app.repositories import integration_repository
from app.repositories.integration_repository import DuplicateNameError


def _row(*cols):
    """Build 11-column row: ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG, CREATED_AT, UPDATED_AT (Story 5.3)."""
    default_ts = (datetime(2026, 1, 29, 10, 0, 0), datetime(2026, 1, 29, 10, 0, 0))
    cols = list(cols)
    while len(cols) < 7:
        cols.append(None)
    # Pad to 11: token_url, config, created_at, updated_at
    cols.extend([None] * (11 - len(cols) - 2) + [default_ts[0], default_ts[1]])
    return tuple(cols[:11])


@pytest.fixture
def sample_integration_create():
    """Sample integration with free-form type and auth_flow (Story 4.9)."""
    return IntegrationCreate(
        type="aap",  # Story 4.9: type is now free-form string
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
        auth_flow=AuthFlow.TOKEN,
    )


@pytest.fixture
def sample_integration_response():
    """Sample response with free-form type and auth_flow (Story 4.9, 5.3)."""
    return IntegrationResponse(
        id=1,
        type="aap",  # Story 4.9: type is now string
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
        auth_flow=AuthFlow.TOKEN,
        token_url=None,
        config=None,
        created_at=datetime(2026, 1, 29, 10, 0, 0),
        updated_at=datetime(2026, 1, 29, 10, 0, 0),
    )


@pytest.fixture
def mock_integration_row():
    """Mock row with 11 columns including auth_flow, token_url, config (Story 4.9, 5.3)."""
    return _row(
        1,
        "aap",
        "AAP Production",
        "https://aap.example.com",
        "secret/idp/aap-prod",
        "aap",
        "token",  # auth_flow
    )


class TestRowConversions:
    def test_row_to_integration_response(self, mock_integration_row):
        """Story 4.9: Test row conversion with auth_flow."""
        r = integration_repository._row_to_integration_response(mock_integration_row)
        assert r.id == 1
        assert r.type == "aap"
        assert r.name == "AAP Production"
        assert r.base_url == "https://aap.example.com"
        assert r.credential_ref == "secret/idp/aap-prod"
        assert r.icon == "aap"
        assert r.auth_flow == AuthFlow.TOKEN

    def test_row_to_integration_response_null_optional_fields(self):
        """Story 4.9 AC5: Test row with NULL auth_flow (backward compatibility)."""
        row = _row(
            2,
            "servicenow",
            "ServiceNow Dev",
            "https://dev.servicenow.com",
            None,  # credential_ref
            None,  # icon
            None,  # auth_flow (nullable for backward compatibility)
        )
        r = integration_repository._row_to_integration_response(row)
        assert r.id == 2
        assert r.type == "servicenow"
        assert r.credential_ref is None
        assert r.icon is None
        assert r.auth_flow is None

    def test_row_to_integration_response_free_form_type(self):
        """Story 4.9 AC1: Test with free-form type (not in legacy enum)."""
        row = _row(
            3,
            "jenkins",  # Free-form type not in original enum
            "Jenkins CI",
            "https://jenkins.example.com",
            "secret/jenkins",
            None,
            "pat",  # PAT auth flow
        )
        r = integration_repository._row_to_integration_response(row)
        assert r.id == 3
        assert r.type == "jenkins"
        assert r.auth_flow == AuthFlow.PAT

    def test_row_to_integration_response_token_url_and_config(self):
        """Story 5.3: Test row with token_url and config (CONFIG as JSON string)."""
        row = _row(
            4,
            "aap",
            "AAP With Config",
            "https://aap.example.com",
            "secret/aap",
            None,
            "basic_then_token",
            "https://aap.example.com/api/v2/token/",  # token_url
            '{"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]}',  # config CLOB
        )
        r = integration_repository._row_to_integration_response(row)
        assert r.id == 4
        assert r.token_url == "https://aap.example.com/api/v2/token/"
        assert r.config == {"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]}


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
        row2 = _row(
            2,
            "servicenow",
            "ServiceNow Prod",
            "https://prod.servicenow.com",
            "secret/idp/snow-prod",
            "servicenow",
            "basic",  # auth_flow (Story 4.9)
        )
        row2 = (2, "servicenow", "ServiceNow Prod", "https://prod.servicenow.com",
                "secret/idp/snow-prod", "servicenow", "basic", None, None,
                datetime(2026, 1, 29, 11, 0, 0), datetime(2026, 1, 29, 11, 0, 0))
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
    async def test_create_with_token_url_and_config(self, sample_integration_response):
        """Story 5.3: Create integration with token_url and config (AC2, AC3)."""
        create = IntegrationCreate(
            type="aap",
            name="AAP With Flow",
            base_url="https://aap.example.com",
            credential_ref="secret/aap",
            icon=None,
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config={"auth_flow": [{"step": "obtain_token", "url_ref": "token_url", "credentials": {"keys": ["username", "password"]}}]},
        )
        response_with_config = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP With Flow",
            base_url="https://aap.example.com",
            credential_ref="secret/aap",
            icon=None,
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config={"auth_flow": [{"step": "obtain_token"}]},
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        with patch("app.repositories.integration_repository.get_connection") as mock_get_conn:
            mock_cursor = AsyncMock()
            mock_cursor.close = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock(return_value=mock_cursor)
            mock_var = MagicMock()
            mock_var.getvalue.return_value = [1]
            mock_conn.var = lambda _: mock_var
            mock_conn.commit = AsyncMock()
            mock_conn.rollback = AsyncMock()
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = response_with_config
                result = await integration_repository.create(create)
        assert result.token_url == "https://aap.example.com/api/v2/token/"
        assert result.config == {"auth_flow": [{"step": "obtain_token"}]}

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

    @pytest.mark.asyncio
    async def test_update_with_token_url_and_config(self, sample_integration_response):
        """Story 5.3: Update with token_url and config (code-review fix MED-3)."""
        updated_response = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP Production",
            base_url="https://aap.example.com",
            credential_ref="secret/idp/aap-prod",
            icon="aap",
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config={"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]},
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 12, 0, 0),
        )
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
                # First call returns existing, second call returns updated
                mock_get.side_effect = [sample_integration_response, updated_response]
                result = await integration_repository.update(
                    1,
                    IntegrationUpdate(
                        auth_flow=AuthFlow.BASIC_THEN_TOKEN,
                        token_url="https://aap.example.com/api/v2/token/",
                        config={"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]},
                    ),
                )

        assert result is not None
        assert result.token_url == "https://aap.example.com/api/v2/token/"
        assert result.config == {"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]}
        # Verify SQL includes TOKEN_URL and CONFIG
        execute_call = mock_conn.execute.call_args
        sql = execute_call[0][0]
        assert "TOKEN_URL" in sql
        assert "CONFIG" in sql

    @pytest.mark.asyncio
    async def test_update_config_null_clears_config(self, sample_integration_response):
        """Story 5.3: Update with config=None clears config (code-review fix MED-3)."""
        # Start with existing that has config
        existing_with_config = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP Production",
            base_url="https://aap.example.com",
            credential_ref="secret/idp/aap-prod",
            icon="aap",
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config={"auth_flow": [{"step": "obtain_token"}]},
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        updated_no_config = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP Production",
            base_url="https://aap.example.com",
            credential_ref="secret/idp/aap-prod",
            icon="aap",
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config=None,  # Cleared
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 12, 0, 0),
        )
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
                mock_get.side_effect = [existing_with_config, updated_no_config]
                # Use model_construct to set model_fields_set explicitly
                update = IntegrationUpdate.model_construct(config=None, _fields_set={"config"})
                result = await integration_repository.update(1, update)

        assert result is not None
        assert result.config is None
        # Verify CONFIG = :config with None value
        execute_call = mock_conn.execute.call_args
        params = execute_call[0][1]
        assert "config" in params
        assert params["config"] is None


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
