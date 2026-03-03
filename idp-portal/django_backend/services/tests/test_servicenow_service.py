"""
Story 31.6: Tests for ServiceNowService.create_change() (AC#9, AC#10).

Tests:
- 5.1: create_change success — returns change number CHG0001234
- 5.2: create_change HTTP error — raises ServiceUnavailableError
- 5.3: create_change timeout — raises ServiceUnavailableError
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings

import httpx

from services.servicenow_service import ServiceNowService
from core.exceptions import ServiceUnavailableError


class TestServiceNowCreateChange:
    """Test ServiceNowService.create_change() (Story 31.6 AC#9)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_success(self, mock_client_class):
        """5.1: Successful change creation returns change number."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"number": "CHG0001234", "sys_id": "abc123"}
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = self.service.create_change(
            change_model_code="model123",
            change_type="normal",
            short_description="Test change",
            description="Test description",
        )

        assert result == {"number": "CHG0001234", "sys_id": "abc123"}
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://snow.example.com/api/now/table/change_request"
        payload = call_args[1]["json"]
        assert payload["short_description"] == "Test change"
        assert payload["description"] == "Test description"
        assert payload["type"] == "normal"
        assert payload["chg_model"] == "model123"

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_http_error(self, mock_client_class):
        """5.2: HTTP 500 raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.create_change(short_description="Fail test")

        assert "500" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_timeout(self, mock_client_class):
        """5.3: Timeout raises ServiceUnavailableError."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.create_change(short_description="Timeout test")

        assert "timeout" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_default_values(self, mock_client_class):
        """create_change uses default values when optional params omitted."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "CHG0005678"}}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        result = self.service.create_change()

        assert result == {"number": "CHG0005678", "sys_id": ""}
        payload = mock_client.post.call_args[1]["json"]
        assert payload["type"] == "normal"
        assert "chg_model" not in payload  # Not set when change_model_code is None

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_request_error(self, mock_client_class):
        """Request error (network) raises ServiceUnavailableError."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.create_change(short_description="Network error")

        assert "indisponible" in exc_info.value.message.lower()


class TestServiceNowTLSEnforcement:
    """SEC-13: TLS forced in production (Story 48.4)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    def _make_mock_client(self, mock_client_class):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "CHG0001"}}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client
        return mock_client

    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=False)
    def test_tls_forced_in_production(self, mock_client_class):
        """SEC-13: verify=True even when SERVICENOW_VERIFY_TLS=False in production (DEBUG=False)."""
        self._make_mock_client(mock_client_class)

        self.service.create_change(short_description="SEC-13 prod test")

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["verify"] is True, "TLS doit être forcé True en production"

    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=True, SERVICENOW_VERIFY_TLS=False)
    def test_tls_override_allowed_in_debug(self, mock_client_class):
        """SEC-13: verify=False respected in DEBUG=True (dev environment)."""
        self._make_mock_client(mock_client_class)

        self.service.create_change(short_description="SEC-13 dev test")

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["verify"] is False, "verify=False doit être respecté en DEBUG mode"

    @patch("services.servicenow_service.logger")
    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=False)
    def test_tls_override_logs_warning_in_production(self, mock_client_class, mock_logger):
        """SEC-13: A warning is logged when TLS override is ignored in production."""
        self._make_mock_client(mock_client_class)

        self.service.create_change(short_description="SEC-13 warning test")

        mock_logger.warning.assert_called_once_with(
            "servicenow_tls_override_ignored",
            reason="TLS verification forced True in production (DEBUG=False)",
            configured_value=False,
        )

    @patch("services.servicenow_service.logger")
    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=True)
    def test_tls_no_warning_when_already_true(self, mock_client_class, mock_logger):
        """SEC-13: No warning when TLS is already True in production."""
        self._make_mock_client(mock_client_class)

        self.service.create_change(short_description="SEC-13 no-warning test")

        mock_logger.warning.assert_not_called()
