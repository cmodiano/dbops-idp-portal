"""
Story 31.6: Tests for ServiceNowService.create_change() (AC#9, AC#10).
Story 57.9: Tests for ServiceNowService.close_change() and cancel_change() (ADR-007 Phase 3).
Story 86.2: Tests for ServiceNowService.update_change() and get_change_status() (AC#6, AC#7).

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

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.create_change(short_description="Fail test")

        assert "500" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_timeout(self, mock_client_class):
        """5.3: Timeout raises ServiceUnavailableError."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

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

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.create_change(short_description="Network error")

        assert "indisponible" in exc_info.value.message.lower()


class TestServiceNowSyncClientReuse:
    """PERF-BE-01: httpx.Client instancié une seule fois par instance de service."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    @patch("services.servicenow_service.httpx.Client")
    def test_sync_client_created_once_across_multiple_calls(self, mock_client_class):
        """PERF-BE-01 : httpx.Client() appelé une seule fois même si create_change et
        close_change sont invoqués successivement sur la même instance."""
        mock_response_post = MagicMock()
        mock_response_post.json.return_value = {"result": {"number": "CHG001", "sys_id": "s1"}}
        mock_response_post.raise_for_status = MagicMock()

        mock_response_patch = MagicMock()
        mock_response_patch.json.return_value = {"result": {"sys_id": "s1"}}
        mock_response_patch.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response_post
        mock_client.patch.return_value = mock_response_patch
        mock_client_class.return_value = mock_client

        self.service.create_change(short_description="Test 1")
        self.service.close_change(change_id="CHG001")

        # httpx.Client() must be called exactly once regardless of how many methods were called
        mock_client_class.assert_called_once()

    @patch("services.servicenow_service.httpx.Client")
    def test_sync_client_instance_is_reused(self, mock_client_class):
        """PERF-BE-01 : le même objet client est retourné par _sync_client à chaque accès."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        client_first = self.service._sync_client
        client_second = self.service._sync_client

        assert client_first is client_second
        mock_client_class.assert_called_once()

    @patch("services.servicenow_service.httpx.Client")
    def test_close_resets_client_for_reinitialization(self, mock_client_class):
        """close() libère le client ; le prochain appel crée un nouveau client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        _ = self.service._sync_client
        self.service.close()
        mock_client.close.assert_called_once()

        # After close(), a new client should be created on next access
        _ = self.service._sync_client
        assert mock_client_class.call_count == 2

    def test_close_is_idempotent_when_no_client_created(self):
        """close() sans client lazily créé ne lève pas d'exception."""
        self.service.close()  # Should not raise


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


def _make_patch_mock_client(mock_client_class, response_json=None):
    """Helper partagé pour mocker httpx.Client avec PATCH (close_change, cancel_change)."""
    if response_json is None:
        response_json = {"result": {"sys_id": "abc123def456"}}
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.patch.return_value = mock_response

    mock_client_class.return_value = mock_client
    return mock_client


class TestServiceNowCloseChange:
    """Test ServiceNowService.close_change() (Story 57.9, AC#1, #4, #5, #6, #7)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    def _make_mock_client(self, mock_client_class, response_json=None):
        return _make_patch_mock_client(mock_client_class, response_json)

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_success(self, mock_client_class):
        """AC#1 : close_change retourne {closed: True, sys_id}."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001"}},
        )

        result = self.service.close_change(
            change_id="CHG001",
            close_code="successful",
        )

        assert result == {"closed": True, "sys_id": "abc123"}
        mock_client.patch.assert_called_once()
        call_url = mock_client.patch.call_args[0][0]
        assert call_url == "https://snow.example.com/api/now/table/change_request/CHG001"
        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "3"
        assert payload["close_code"] == "successful"

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_http_error(self, mock_client_class):
        """AC#4 : 500 → ServiceUnavailableError avec code HTTP dans message."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response,
        )
        mock_client = MagicMock()
        mock_client.patch.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.close_change(change_id="CHG001")

        assert "500" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_timeout(self, mock_client_class):
        """AC#5 : TimeoutException → ServiceUnavailableError SERVICENOW_TIMEOUT."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.close_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_TIMEOUT"
        assert "timeout" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_request_error(self, mock_client_class):
        """AC#6 : RequestError → ServiceUnavailableError SERVICENOW_UNAVAILABLE."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.RequestError("Connection refused")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.close_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_UNAVAILABLE"
        assert "indisponible" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=False)
    def test_close_change_tls_forced_production(self, mock_client_class):
        """AC#7 : DEBUG=False → verify=True même si SERVICENOW_VERIFY_TLS=False."""
        self._make_mock_client(mock_client_class)

        self.service.close_change(change_id="CHG001")

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["verify"] is True

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_payload_includes_close_code(self, mock_client_class):
        """AC#1 : payload contient state=3 et close_code."""
        mock_client = self._make_mock_client(mock_client_class)

        self.service.close_change(change_id="SYS123", close_code="unsuccessful")

        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "3"
        assert payload["close_code"] == "unsuccessful"

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_empty_sys_id_raises(self, mock_client_class):
        """HIGH-2 : 2xx sans sys_id → ServiceUnavailableError SERVICENOW_INVALID_RESPONSE."""
        self._make_mock_client(mock_client_class, {"result": {}})

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.close_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_INVALID_RESPONSE"
        assert "sys_id" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_close_change_extra_fields_via_kwargs(self, mock_client_class):
        """AC#3 : kwargs dynamiques sont passés dans le payload PATCH de close_change."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123"}},
        )

        self.service.close_change(
            change_id="CHG001",
            close_code="successful",
            u_work_notes="Clôture avec note",
        )

        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "3"
        assert payload["close_code"] == "successful"
        assert payload["u_work_notes"] == "Clôture avec note"


class TestServiceNowCancelChange:
    """Test ServiceNowService.cancel_change() (Story 57.9, AC#2, #4, #5, #6, #7)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    def _make_mock_client(self, mock_client_class, response_json=None):
        return _make_patch_mock_client(mock_client_class, response_json)

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_success(self, mock_client_class):
        """AC#2 : cancel_change retourne {cancelled: True, sys_id}."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001"}},
        )

        result = self.service.cancel_change(
            change_id="CHG001",
            reason="Annulé pour maintenance",
        )

        assert result == {"cancelled": True, "sys_id": "abc123"}
        mock_client.patch.assert_called_once()
        call_url = mock_client.patch.call_args[0][0]
        assert call_url == "https://snow.example.com/api/now/table/change_request/CHG001"
        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "4"
        assert payload["cancel_reason"] == "Annulé pour maintenance"

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_http_error(self, mock_client_class):
        """AC#4 : 500 → ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response,
        )
        mock_client = MagicMock()
        mock_client.patch.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.cancel_change(change_id="CHG001")

        assert "500" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_timeout(self, mock_client_class):
        """AC#5 : TimeoutException → ServiceUnavailableError SERVICENOW_TIMEOUT."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.cancel_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_TIMEOUT"
        assert "timeout" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=False)
    def test_cancel_change_tls_forced_production(self, mock_client_class):
        """AC#7 : DEBUG=False → verify=True pour cancel_change aussi."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "abc123"}}
        mock_response.raise_for_status = MagicMock()
        mock_client.patch.return_value = mock_response

        mock_client_class.return_value = mock_client

        self.service.cancel_change(change_id="CHG001")

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["verify"] is True

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_empty_sys_id_raises(self, mock_client_class):
        """HIGH-2 : 2xx sans sys_id → ServiceUnavailableError SERVICENOW_INVALID_RESPONSE."""
        self._make_mock_client(mock_client_class, {"result": {}})

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.cancel_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_INVALID_RESPONSE"
        assert "sys_id" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_extra_fields_via_kwargs(self, mock_client_class):
        """AC#3 : kwargs dynamiques sont passés dans le payload PATCH de cancel_change."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123"}},
        )

        self.service.cancel_change(
            change_id="CHG001",
            reason="Test",
            u_work_notes="Note additionnelle",
        )

        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "4"
        assert payload["cancel_reason"] == "Test"
        assert payload["u_work_notes"] == "Note additionnelle"

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_payload_state_4(self, mock_client_class):
        """AC#2 : payload contient state=4 et cancel_reason."""
        mock_client = self._make_mock_client(mock_client_class)

        self.service.cancel_change(change_id="SYS456", reason="Test annulation")

        payload = mock_client.patch.call_args[1]["json"]
        assert payload["state"] == "4"
        assert payload["cancel_reason"] == "Test annulation"

    @patch("services.servicenow_service.httpx.Client")
    def test_cancel_change_request_error(self, mock_client_class):
        """AC#6 : RequestError → ServiceUnavailableError SERVICENOW_UNAVAILABLE."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.RequestError("Connection refused")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.cancel_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_UNAVAILABLE"
        assert "indisponible" in exc_info.value.message.lower()


class TestServiceNowCreateChangeExtraFields:
    """Test ServiceNowService.create_change() avec kwargs dynamiques (Story 57.9, AC#3)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    @patch("services.servicenow_service.httpx.Client")
    def test_create_change_extra_fields_via_kwargs(self, mock_client_class):
        """AC#3 : kwargs dynamiques (cmdb_ci, u_patch_number) sont passés dans le payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"number": "CHG0009999", "sys_id": "sys999"}}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        mock_client_class.return_value = mock_client

        result = self.service.create_change(
            short_description="Patch Oracle",
            cmdb_ci="CI001",
            u_patch_number="PSU-24",
        )

        assert result == {"number": "CHG0009999", "sys_id": "sys999"}
        payload = mock_client.post.call_args[1]["json"]
        assert payload["cmdb_ci"] == "CI001"
        assert payload["u_patch_number"] == "PSU-24"


class TestServiceNowUpdateChange:
    """Test ServiceNowService.update_change() (Story 86.2, AC#1, #2, #6)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    def _make_mock_client(self, mock_client_class, response_json=None):
        return _make_patch_mock_client(mock_client_class, response_json)

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_success(self, mock_client_class):
        """AC#1 : update_change retourne {updated: True, sys_id}, URL et payload corrects."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001"}},
        )

        result = self.service.update_change(change_id="CHG001", work_notes="test note")

        assert result == {"updated": True, "sys_id": "abc123"}
        mock_client.patch.assert_called_once()
        call_url = mock_client.patch.call_args[0][0]
        assert call_url == "https://snow.example.com/api/now/table/change_request/CHG001"

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_http_error(self, mock_client_class):
        """AC#6 : HTTP 500 → ServiceUnavailableError avec '500' dans le message."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response,
        )
        mock_client = MagicMock()
        mock_client.patch.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.update_change(change_id="CHG001")

        assert "500" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_timeout(self, mock_client_class):
        """AC#6 : TimeoutException → ServiceUnavailableError(code='SERVICENOW_TIMEOUT')."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.update_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_TIMEOUT"

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_kwargs_in_payload(self, mock_client_class):
        """AC#6 : kwargs dynamiques inclus dans le payload PATCH."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123"}},
        )

        self.service.update_change(change_id="CHG001", work_notes="test", priority=2)

        payload = mock_client.patch.call_args[1]["json"]
        assert payload["work_notes"] == "test"
        assert payload["priority"] == "2"

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_empty_sys_id_raises(self, mock_client_class):
        """AC#6 : 2xx sans sys_id → ServiceUnavailableError SERVICENOW_INVALID_RESPONSE."""
        self._make_mock_client(mock_client_class, {"result": {}})

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.update_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_INVALID_RESPONSE"
        assert "sys_id" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_request_error(self, mock_client_class):
        """AC#2 : RequestError → ServiceUnavailableError SERVICENOW_UNAVAILABLE (même pattern que close/cancel)."""
        mock_client = MagicMock()
        mock_client.patch.side_effect = httpx.RequestError("Connection refused")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.update_change(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_UNAVAILABLE"
        assert "indisponible" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_update_change_no_kwargs_empty_payload(self, mock_client_class):
        """Edge case : update_change sans kwargs → payload vide envoyé, retourne {updated: True, sys_id}."""
        mock_client = self._make_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123"}},
        )

        result = self.service.update_change(change_id="CHG001")

        assert result == {"updated": True, "sys_id": "abc123"}
        payload = mock_client.patch.call_args[1]["json"]
        assert payload == {}


def _make_get_mock_client(mock_client_class, response_json=None):
    """Helper pour mocker httpx.Client avec GET (get_change_status)."""
    if response_json is None:
        response_json = {
            "result": {"sys_id": "abc123", "number": "CHG001", "state": "3", "priority": "2"}
        }
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.get.return_value = mock_response

    mock_client_class.return_value = mock_client
    return mock_client


class TestServiceNowGetChangeStatus:
    """Test ServiceNowService.get_change_status() (Story 86.2, AC#3, #4, #5, #7)."""

    def setup_method(self):
        self.service = ServiceNowService(
            base_url="https://snow.example.com",
            auth_headers={"Authorization": "Bearer test-token"},
        )

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_success_mapped_state(self, mock_client_class):
        """AC#3 : succès avec mapping état '3' → 'closed', change_id et number corrects."""
        _make_get_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001", "state": "3", "priority": "2"}},
        )

        result = self.service.get_change_status(change_id="CHG001")

        assert result["state"] == "closed"
        assert result["change_id"] == "CHG001"
        assert result["number"] == "CHG001"
        assert result["priority"] == 2

    @pytest.mark.parametrize("raw_state,expected", [
        ("-5", "pending"),
        ("1", "open"),
        ("2", "work_in_progress"),
        ("3", "closed"),
        ("4", "cancelled"),
        ("99", "99"),
    ])
    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_all_state_mappings(self, mock_client_class, raw_state, expected):
        """AC#4 : mapping complet des états ServiceNow."""
        _make_get_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001", "state": raw_state, "priority": "1"}},
        )

        result = self.service.get_change_status(change_id="CHG001")

        assert result["state"] == expected

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_unknown_state_returned_raw(self, mock_client_class):
        """AC#4 : état inconnu '99' retourné tel quel (pas d'erreur)."""
        _make_get_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001", "state": "99", "priority": "1"}},
        )

        result = self.service.get_change_status(change_id="CHG001")

        assert result["state"] == "99"

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_http_error(self, mock_client_class):
        """AC#5 : HTTP 404 → ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response,
        )
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.get_change_status(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_HTTP_ERROR"
        assert "404" in exc_info.value.message

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_timeout(self, mock_client_class):
        """AC#5 : TimeoutException → ServiceUnavailableError(code='SERVICENOW_TIMEOUT')."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.get_change_status(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_TIMEOUT"

    @patch("services.servicenow_service.httpx.Client")
    @override_settings(DEBUG=False, SERVICENOW_VERIFY_TLS=False)
    def test_get_change_status_tls_forced_production(self, mock_client_class):
        """AC#7 : DEBUG=False → verify=True même si SERVICENOW_VERIFY_TLS=False."""
        _make_get_mock_client(mock_client_class)

        self.service.get_change_status(change_id="CHG001")

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["verify"] is True

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_sysparm_fields_in_url(self, mock_client_class):
        """AC#3 : l'URL contient sysparm_fields=number,sys_id,state,priority,sys_updated_on."""
        mock_client = _make_get_mock_client(mock_client_class)

        self.service.get_change_status(change_id="CHG001")

        call_kwargs = mock_client.get.call_args[1]
        assert "sysparm_fields" in call_kwargs["params"]
        assert "number,sys_id,state,priority,sys_updated_on" in call_kwargs["params"]["sysparm_fields"]

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_empty_sys_id_raises(self, mock_client_class):
        """AC#5 : 2xx sans sys_id → ServiceUnavailableError SERVICENOW_INVALID_RESPONSE."""
        _make_get_mock_client(mock_client_class, {"result": {"number": "CHG001"}})

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.get_change_status(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_INVALID_RESPONSE"
        assert "sys_id" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_request_error(self, mock_client_class):
        """AC#5 : RequestError → ServiceUnavailableError SERVICENOW_UNAVAILABLE (même pattern que autres méthodes)."""
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")

        mock_client_class.return_value = mock_client

        with pytest.raises(ServiceUnavailableError) as exc_info:
            self.service.get_change_status(change_id="CHG001")

        assert exc_info.value.code == "SERVICENOW_UNAVAILABLE"
        assert "indisponible" in exc_info.value.message.lower()

    @patch("services.servicenow_service.httpx.Client")
    def test_get_change_status_priority_non_numeric_defaults_zero(self, mock_client_class):
        """M1 : priority non-numérique (ex: dict display value) → priority == 0 sans exception."""
        _make_get_mock_client(
            mock_client_class,
            {"result": {"sys_id": "abc123", "number": "CHG001", "state": "1",
                        "priority": {"value": "2", "display_value": "2 - High"}}},
        )

        result = self.service.get_change_status(change_id="CHG001")

        assert result["priority"] == 0
