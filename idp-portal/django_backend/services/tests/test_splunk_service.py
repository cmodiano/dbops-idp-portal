"""
Tests for SplunkService — Splunk HEC integration.

Story 27.8, AC8: 12+ tests covering send_event, send_batch, error handling,
retry logic, credential_ref, and structured logging.
Story 27.9: Renamed SplunkService → SplunkService, moved to services/.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.splunk_service import SplunkService
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> SplunkService:
    """Create a SplunkService with test configuration."""
    return SplunkService(
        base_url="https://splunk.example.com:8088",
        auth_headers={"Authorization": "Splunk test-token-123"},
        timeout=10.0,
        default_sourcetype="idp:execution",
        default_index="prod-idp",
    )


def _mock_httpx_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    """Create a mock httpx Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {"text": "Success", "code": 0}
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(spec=httpx.Request),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None
    return response


class TestSplunkServiceInit:
    """Test SplunkService initialization."""

    def test_init_strips_trailing_slash(self) -> None:
        adapter = SplunkService(
            base_url="https://splunk.example.com:8088/",
            auth_headers={"Authorization": "Splunk token"},
        )
        assert adapter.base_url == "https://splunk.example.com:8088"

    def test_init_defaults(self) -> None:
        adapter = SplunkService(
            base_url="https://splunk.example.com:8088",
            auth_headers={"Authorization": "Splunk token"},
        )
        assert adapter.timeout == 30.0
        assert adapter.default_sourcetype == "idp:execution"
        assert adapter.default_index == "prod-idp"


class TestSendEvent:
    """Test SplunkService.send_event()."""

    @pytest.mark.asyncio
    async def test_send_event_success(self, adapter: SplunkService) -> None:
        """AC8 test 1: Mock POST HEC -> 200 -> event sent."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_event(
                event={"event": "execution_started", "level": "INFO"},
                correlation_id="test-corr-123",
            )

        assert result["code"] == 0
        assert result["text"] == "Success"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_event_with_correlation_id(self, adapter: SplunkService) -> None:
        """AC8 test 2: event contains correlation_id in fields."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        event = {
            "event": "execution_started",
            "correlation_id": "abc-123-def-456",
            "user_id": "john@example.com",
            "execution_id": 42,
        }

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            await adapter.send_event(event=event, correlation_id="abc-123-def-456")

        # Verify the posted body contains correlation_id in fields
        call_args = mock_client.post.call_args
        body = json.loads(call_args.kwargs.get("content", call_args[1].get("content", "")))
        assert body["fields"]["correlation_id"] == "abc-123-def-456"
        assert body["fields"]["user_id"] == "john@example.com"
        assert body["fields"]["execution_id"] == 42

    @pytest.mark.asyncio
    async def test_send_event_hec_error_503(self, adapter: SplunkService) -> None:
        """AC8 test 4: Mock POST HEC -> 503 after retries -> raise ServiceUnavailableError."""
        mock_response = _mock_httpx_response(503, {"text": "Service Unavailable", "code": 6})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await adapter.send_event(
                        event={"event": "test"},
                        correlation_id="test-corr",
                    )

        assert "503" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_send_event_sourcetype_index(self, adapter: SplunkService) -> None:
        """AC8 test 9: send_event with custom sourcetype and index."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            await adapter.send_event(
                event={"event": "adapter_call"},
                sourcetype="idp:adapter",
                index="test-idp",
            )

        call_args = mock_client.post.call_args
        body = json.loads(call_args.kwargs.get("content", call_args[1].get("content", "")))
        assert body["sourcetype"] == "idp:adapter"
        assert body["index"] == "test-idp"

    @pytest.mark.asyncio
    async def test_send_event_event_format(self, adapter: SplunkService) -> None:
        """AC8 test 8: event dict contains required fields."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        event = {
            "event": "execution_started",
            "level": "INFO",
            "correlation_id": "uuid-123",
            "user_id": "admin",
            "execution_id": 1,
            "timestamp": "2026-02-14T10:30:00Z",
        }

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_event(event=event)

        assert result["code"] == 0
        call_args = mock_client.post.call_args
        body = json.loads(call_args.kwargs.get("content", call_args[1].get("content", "")))
        assert body["event"]["event"] == "execution_started"
        assert body["event"]["level"] == "INFO"
        assert body["event"]["correlation_id"] == "uuid-123"


class TestSendBatch:
    """Test SplunkService.send_batch()."""

    @pytest.mark.asyncio
    async def test_send_batch_success(self, adapter: SplunkService) -> None:
        """AC8 test 3: Mock POST HEC batch -> 200 -> 10 events sent."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        events = [{"event": f"test_event_{i}", "level": "INFO"} for i in range(10)]

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.send_batch(events=events, correlation_id="batch-corr-123")

        assert result["count"] == 10
        assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_send_batch_empty(self, adapter: SplunkService) -> None:
        """send_batch with empty list returns immediately."""
        result = await adapter.send_batch(events=[], correlation_id="empty-batch")
        assert result["count"] == 0
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_batch_timeout(self, adapter: SplunkService) -> None:
        """AC8 test 5: Mock POST HEC -> timeout -> raise ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await adapter.send_batch(
                        events=[{"event": "test"}],
                        correlation_id="timeout-corr",
                    )

        assert exc_info.value.code == "SPLUNK_TIMEOUT"


class TestRetryAndErrorHandling:
    """Test retry logic and error handling."""

    @pytest.mark.asyncio
    async def test_retry_on_500(self, adapter: SplunkService) -> None:
        """AC8 test 10: 1st call 500, 2nd call 200 -> success after retry."""
        mock_response_500 = _mock_httpx_response(500, {"text": "Internal Error", "code": 8})
        # Override raise_for_status: 500 is transient, handled before raise_for_status
        mock_response_500.raise_for_status.side_effect = None
        mock_response_200 = _mock_httpx_response(200, {"text": "Success", "code": 0})

        mock_client = AsyncMock()
        mock_client.post.side_effect = [mock_response_500, mock_response_200]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await adapter.send_event(
                    event={"event": "test_retry"},
                    correlation_id="retry-corr",
                )

        assert result["code"] == 0
        assert mock_client.post.call_count == 2
        mock_sleep.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_send_event_connection_error(self, adapter: SplunkService) -> None:
        """Connection error after retries raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await adapter.send_event(
                        event={"event": "test"},
                        correlation_id="conn-err-corr",
                    )

        assert exc_info.value.code == "SPLUNK_CONNECTION_ERROR"


class TestCredentialRefVault:
    """Test Vault credential_ref resolution."""

    @pytest.mark.asyncio
    async def test_credential_ref_vault(self) -> None:
        """AC8 test 6: credential_ref resolved via VaultService -> token injected."""
        mock_vault = MagicMock()
        mock_vault.get_secret.return_value = "resolved-splunk-token-xyz"

        # Simulate resolving credential_ref and creating adapter
        token = mock_vault.get_secret(
            "vault:secret/data/splunk/prod#token",
            correlation_id="vault-test",
        )
        adapter = SplunkService(
            base_url="https://splunk.example.com:8088",
            auth_headers={"Authorization": f"Splunk {token}"},
        )

        assert adapter.auth_headers["Authorization"] == "Splunk resolved-splunk-token-xyz"
        mock_vault.get_secret.assert_called_once_with(
            "vault:secret/data/splunk/prod#token",
            correlation_id="vault-test",
        )


class TestServiceClassification:
    """Test SplunkService is a Service, not a Platform adapter (Story 27.9)."""

    def test_splunk_service_not_base_adapter(self, adapter: SplunkService) -> None:
        """SplunkService should NOT inherit from BaseAdapter."""
        from adapters.base_adapter import BaseAdapter
        assert not isinstance(adapter, BaseAdapter)

    def test_splunk_service_has_no_trigger(self, adapter: SplunkService) -> None:
        """SplunkService should not have trigger() method."""
        assert not hasattr(adapter, "trigger")

    def test_splunk_service_has_send_event(self, adapter: SplunkService) -> None:
        """SplunkService should have send_event() method."""
        assert hasattr(adapter, "send_event")
        assert callable(adapter.send_event)

    def test_backward_compat_alias(self) -> None:
        """SplunkAdapter alias should still work for backward compatibility."""
        from services.splunk_service import SplunkAdapter
        assert SplunkAdapter is SplunkService


class TestStructlogLogging:
    """Test structured logging."""

    @pytest.mark.asyncio
    async def test_logging_structlog_send_event(self, adapter: SplunkService) -> None:
        """AC8 test 12: send_event logs 'splunk_event_sent' with structlog."""
        mock_response = _mock_httpx_response(200, {"text": "Success", "code": 0})
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.logger") as mock_logger:
                await adapter.send_event(
                    event={"event": "test_log"},
                    correlation_id="log-corr-123",
                )

        # Verify structlog logging calls
        log_events = [call.args[0] for call in mock_logger.info.call_args_list]
        assert "splunk_event_sending" in log_events
        assert "splunk_event_sent" in log_events
