"""Tests for Vault service (Story 4.2bis, Task 4)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import hvac.exceptions

from app.services.vault_service import VaultService
from app.core.exceptions import VaultError, ServiceUnavailableError
from app.api.services import get_vault_service, VaultServiceDisabled


class TestVaultServiceInitialization:
    """Tests for VaultService.__init__ (Task 2.1)."""

    def test_init_with_token(self):
        """VaultService initializes with token authentication."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()

                mock_client_class.assert_called_once_with(url="http://vault:8200", timeout=30)
                assert mock_client.token == "test-token"
                assert service.client == mock_client

    def test_init_with_approle(self):
        """VaultService initializes with AppRole authentication."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.auth.approle.login.return_value = {"auth": {"client_token": "approle-token"}}
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = ""
                mock_settings.vault_role_id = "test-role-id"
                mock_settings.vault_secret_id = "test-secret-id"

                service = VaultService()

                mock_client_class.assert_called_once_with(url="http://vault:8200", timeout=30)
                mock_client.auth.approle.login.assert_called_once_with(
                    role_id="test-role-id",
                    secret_id="test-secret-id"
                )
                assert service.client == mock_client

    def test_init_connection_failed(self):
        """VaultService raises VaultError when connection fails."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client_class.side_effect = Exception("Connection failed")

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"

                with pytest.raises(VaultError) as exc_info:
                    VaultService()

                assert exc_info.value.code == "VAULT_CONNECTION_FAILED"


class TestVaultServiceGetSecret:
    """Tests for VaultService.get_secret (Task 2.2)."""

    @pytest.mark.asyncio
    async def test_get_secret_kv_v2_success(self):
        """get_secret() successfully retrieves secret from KV v2."""
        mock_secret_data = {
            "data": {
                "data": {
                    "username": "test-user",
                    "password": "test-pass"
                }
            }
        }

        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.secrets.kv.v2.read_secret_version.return_value = mock_secret_data
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()
                result = await service.get_secret("secret/data/idp/aap-prod")

                assert result == {"username": "test-user", "password": "test-pass"}
                mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
                    path="secret/data/idp/aap-prod",
                    version=None
                )

    @pytest.mark.asyncio
    async def test_get_secret_kv_v1_success(self):
        """get_secret() successfully retrieves secret from KV v1."""
        mock_secret_data = {
            "data": {
                "username": "test-user",
                "password": "test-pass"
            }
        }

        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            # Simulate KV v2 not available, fallback to v1
            mock_client.secrets.kv.v2.read_secret_version.side_effect = hvac.exceptions.InvalidPath("Not KV v2")
            mock_client.secrets.kv.v1.read_secret.return_value = mock_secret_data
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()
                result = await service.get_secret("secret/idp/aap-prod")

                assert result == {"username": "test-user", "password": "test-pass"}
                mock_client.secrets.kv.v1.read_secret.assert_called_once_with(path="secret/idp/aap-prod")

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self):
        """get_secret() raises VaultError when secret path does not exist."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.secrets.kv.v2.read_secret_version.side_effect = hvac.exceptions.InvalidPath("Secret not found")
            mock_client.secrets.kv.v1.read_secret.side_effect = hvac.exceptions.InvalidPath("Secret not found")
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()

                with pytest.raises(VaultError) as exc_info:
                    await service.get_secret("secret/data/nonexistent")

                assert exc_info.value.code == "SECRET_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_secret_vault_unavailable(self):
        """get_secret() raises VaultError when Vault is down."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.secrets.kv.v2.read_secret_version.side_effect = hvac.exceptions.VaultDown("Vault unavailable")
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "test-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()

                with pytest.raises(VaultError) as exc_info:
                    await service.get_secret("secret/data/idp/aap-prod")

                assert exc_info.value.code == "VAULT_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_get_secret_auth_failed(self):
        """get_secret() raises VaultError when token is expired."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.secrets.kv.v2.read_secret_version.side_effect = hvac.exceptions.Forbidden("Token expired")
            mock_client_class.return_value = mock_client

            with patch("app.services.vault_service.settings") as mock_settings:
                mock_settings.vault_addr = "http://vault:8200"
                mock_settings.vault_token = "expired-token"
                mock_settings.vault_role_id = ""
                mock_settings.vault_secret_id = ""

                service = VaultService()

                with pytest.raises(VaultError) as exc_info:
                    await service.get_secret("secret/data/idp/aap-prod")

                assert exc_info.value.code == "VAULT_AUTH_FAILED"


class TestGetVaultServiceFactory:
    """Tests for get_vault_service() factory function (MEDIUM-4 fix)."""

    def test_get_vault_service_disabled_when_no_vault_addr(self):
        """get_vault_service() returns VaultServiceDisabled when VAULT_ADDR not configured."""
        with patch("app.api.services.settings") as mock_settings:
            mock_settings.vault_addr = ""

            service = get_vault_service()

            assert isinstance(service, VaultServiceDisabled)

    def test_get_vault_service_returns_vault_service_when_configured(self):
        """get_vault_service() returns VaultService when VAULT_ADDR is configured."""
        with patch("app.services.vault_service.hvac.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            with patch("app.api.services.settings") as mock_settings_services:
                with patch("app.services.vault_service.settings") as mock_settings_vault:
                    mock_settings_services.vault_addr = "http://vault:8200"
                    mock_settings_vault.vault_addr = "http://vault:8200"
                    mock_settings_vault.vault_token = "test-token"
                    mock_settings_vault.vault_role_id = ""
                    mock_settings_vault.vault_secret_id = ""

                    service = get_vault_service()

                    assert isinstance(service, VaultService)

    @pytest.mark.asyncio
    async def test_vault_service_disabled_raises_service_unavailable(self):
        """VaultServiceDisabled.get_secret() raises ServiceUnavailableError."""
        service = VaultServiceDisabled()

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await service.get_secret("secret/data/test")

        assert exc_info.value.code == "VAULT_DISABLED"
        assert "VAULT_ADDR not configured" in exc_info.value.message
