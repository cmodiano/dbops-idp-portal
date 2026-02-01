"""Unit tests for ServiceNowService (Story 4.5, Task 8.1).

Tests ServiceNow change request creation with:
- Approved (pre-approved change model)
- Pending approval (normal change)
- Timeout and retry
- Authentication errors
- Invalid response handling
- Vault credential retrieval
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import ServiceNowError
from app.services.servicenow_service import ServiceNowService


@pytest.fixture
def mock_vault_service():
    """Create a mock VaultService."""
    vault_service = MagicMock()
    vault_service.get_secret = AsyncMock(return_value={
        "username": "servicenow_user",
        "password": "servicenow_pass",
    })
    return vault_service


@pytest.fixture
def servicenow_service(mock_vault_service):
    """Create a ServiceNowService with mocked dependencies."""
    return ServiceNowService(mock_vault_service)


@pytest.fixture
def mock_settings():
    """Mock settings for ServiceNow configuration."""
    with patch("app.services.servicenow_service.settings") as mock:
        mock.servicenow_base_url = "https://test.service-now.com"
        mock.servicenow_credential_ref = "secret/data/idp/servicenow"
        yield mock


@pytest.fixture
def mock_integration_repo():
    """Mock integration repository."""
    with patch("app.services.servicenow_service.integration_repository") as mock:
        mock.get_by_type = AsyncMock(return_value=None)
        yield mock


class TestServiceNowServiceCreateChange:
    """Tests for create_change method."""

    @pytest.mark.asyncio
    async def test_create_change_approved(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test creating a pre-approved change (Standard Change)."""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123def456",
                "number": "CHG0030123",
                "approval": "approved",
                "state": "2",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await servicenow_service.create_change(
                execution_id=1,
                action_name="Create PDB",
                environment="prod",
                parameters={"pdb_name": "NEWPDB"},
                user="marc.dupont",
                correlation_id="corr-123",
                change_model_code="STD-DB-CREATE-PDB",
            )

            assert result["change_id"] == "abc123def456"
            assert result["change_number"] == "CHG0030123"
            assert result["status"] == "approved"

            # Verify API call
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "change_request" in call_args[0][0]
            payload = call_args[1]["json"]
            assert payload["u_change_model"] == "STD-DB-CREATE-PDB"
            assert payload["u_correlation_id"] == "corr-123"

    @pytest.mark.asyncio
    async def test_create_change_pending_approval(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test creating a change requiring CAB approval (Normal Change)."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "xyz789abc123",
                "number": "CHG0030124",
                "approval": "not requested",
                "state": "-5",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await servicenow_service.create_change(
                execution_id=1,
                action_name="Major Schema Migration",
                environment="prod",
                parameters={"migration_id": 42},
                user="marc.dupont",
                correlation_id="corr-456",
            )

            assert result["change_id"] == "xyz789abc123"
            assert result["change_number"] == "CHG0030124"
            assert result["status"] == "pending_approval"

    @pytest.mark.asyncio
    async def test_create_change_timeout_with_retry(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test timeout with retry behavior (AC4)."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceNowError) as exc_info:
                    await servicenow_service.create_change(
                        execution_id=1,
                        action_name="Test Action",
                        environment="prod",
                        parameters={},
                        user="test_user",
                        correlation_id="corr-789",
                    )

                assert exc_info.value.code == "SERVICENOW_TIMEOUT"
                assert "timeout" in exc_info.value.message.lower()

                # Verify retry was attempted (2 calls = 1 initial + 1 retry)
                assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_create_change_auth_error_401(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test 401 Unauthorized error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ServiceNowError) as exc_info:
                await servicenow_service.create_change(
                    execution_id=1,
                    action_name="Test Action",
                    environment="prod",
                    parameters={},
                    user="test_user",
                    correlation_id="corr-auth",
                )

            assert exc_info.value.code == "SERVICENOW_AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_create_change_invalid_response_missing_sys_id(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test invalid response handling when sys_id is missing."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "number": "CHG0030123",
                # Missing sys_id
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ServiceNowError) as exc_info:
                await servicenow_service.create_change(
                    execution_id=1,
                    action_name="Test Action",
                    environment="prod",
                    parameters={},
                    user="test_user",
                    correlation_id="corr-invalid",
                )

            assert exc_info.value.code == "SERVICENOW_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_create_change_server_error_503(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test 503 Service Unavailable error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ServiceNowError) as exc_info:
                await servicenow_service.create_change(
                    execution_id=1,
                    action_name="Test Action",
                    environment="prod",
                    parameters={},
                    user="test_user",
                    correlation_id="corr-503",
                )

            assert exc_info.value.code == "SERVICENOW_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_create_change_not_configured(
        self,
        servicenow_service,
        mock_integration_repo,
    ):
        """Test error when ServiceNow is not configured."""
        with patch("app.services.servicenow_service.settings") as mock_settings:
            mock_settings.servicenow_base_url = ""
            mock_settings.servicenow_credential_ref = ""

            with pytest.raises(ServiceNowError) as exc_info:
                await servicenow_service.create_change(
                    execution_id=1,
                    action_name="Test Action",
                    environment="prod",
                    parameters={},
                    user="test_user",
                    correlation_id="corr-not-configured",
                )

            assert exc_info.value.code == "SERVICENOW_NOT_CONFIGURED"


class TestServiceNowServiceCredentials:
    """Tests for credential retrieval."""

    @pytest.mark.asyncio
    async def test_credentials_from_vault(
        self,
        servicenow_service,
        mock_vault_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test credentials are retrieved from Vault."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "number": "CHG0030123",
                "approval": "approved",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await servicenow_service.create_change(
                execution_id=1,
                action_name="Test",
                environment="prod",
                parameters={},
                user="user",
                correlation_id="corr",
                credential_ref="secret/data/test/creds",
            )

            mock_vault_service.get_secret.assert_called_once_with(
                "secret/data/test/creds", "corr"
            )

    @pytest.mark.asyncio
    async def test_credentials_invalid_structure(
        self,
        servicenow_service,
        mock_vault_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test error when credentials are missing username/password."""
        mock_vault_service.get_secret = AsyncMock(return_value={
            "api_key": "some_key",  # Missing username/password
        })

        with pytest.raises(ServiceNowError) as exc_info:
            await servicenow_service.create_change(
                execution_id=1,
                action_name="Test",
                environment="prod",
                parameters={},
                user="user",
                correlation_id="corr",
            )

        assert exc_info.value.code == "SERVICENOW_AUTH_ERROR"
        assert "username/password" in exc_info.value.message


class TestServiceNowServicePayload:
    """Tests for change request payload building."""

    @pytest.mark.asyncio
    async def test_payload_includes_correlation_id(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test payload includes correlation_id in u_correlation_id field."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "number": "CHG0030123",
                "approval": "approved",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await servicenow_service.create_change(
                execution_id=1,
                action_name="Test Action",
                environment="prod",
                parameters={"key": "value"},
                user="test_user",
                correlation_id="unique-correlation-id",
            )

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]

            assert payload["u_correlation_id"] == "unique-correlation-id"
            assert "[IDP] Test Action - prod" in payload["short_description"]
            assert "unique-correlation-id" in payload["description"]

    @pytest.mark.asyncio
    async def test_payload_headers_include_correlation_id(
        self,
        servicenow_service,
        mock_settings,
        mock_integration_repo,
    ):
        """Test X-Request-ID header includes correlation_id."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "result": {
                "sys_id": "abc123",
                "number": "CHG0030123",
                "approval": "approved",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            await servicenow_service.create_change(
                execution_id=1,
                action_name="Test",
                environment="prod",
                parameters={},
                user="user",
                correlation_id="header-correlation-id",
            )

            call_args = mock_client.post.call_args
            headers = call_args[1]["headers"]

            assert headers["X-Request-ID"] == "header-correlation-id"
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")
