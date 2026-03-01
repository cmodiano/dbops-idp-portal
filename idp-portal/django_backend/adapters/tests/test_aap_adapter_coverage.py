"""
Coverage tests for AAPAdapter — targeting missing lines to reach >=90%.

This file is self-sufficient: it covers both the previously untested lines
AND enough happy-path code so this file alone achieves >=90% on aap_adapter.py.

Missing lines targeted:
- Line 47: ssl_verify=False warning in __init__
- Line 90: limit payload in trigger()
- Lines 110-116: TimeoutException in trigger()
- Lines 122-129: HTTPStatusError in trigger()
- Lines 213-218: HTTPStatusError and HTTPError in get_status()
- Lines 329-336: Non-404 HTTP error in get_job_logs()
- Line 484: workflow_job URL in cancel_execution()
- Lines 506-511: HTTPStatusError and HTTPError in cancel_execution()
- Lines 529-545: health_check() success and error paths
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from adapters.aap_adapter import AAPAdapter, AAP_STATUS_MAP
from core.exceptions import ServiceUnavailableError
from integrations.health_check import HealthCheckStatus


@pytest.fixture
def adapter() -> AAPAdapter:
    return AAPAdapter(
        base_url="https://aap.example.com",
        auth_headers={"Authorization": "Bearer test-token"},
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# __init__ — ssl_verify=False warning (line 47)
# ---------------------------------------------------------------------------

class TestInit:
    """Tests for AAPAdapter.__init__ edge cases."""

    def test_init_ssl_verify_false_logs_warning(self) -> None:
        """Line 47: logger.warning is called when ssl_verify=False."""
        with patch("adapters.aap_adapter.logger") as mock_logger:
            adapter = AAPAdapter(
                base_url="https://aap.example.com",
                auth_headers={"Authorization": "Bearer token"},
                ssl_verify=False,
            )
            mock_logger.warning.assert_called_once_with(
                "aap_adapter_ssl_verify_disabled",
                base_url="https://aap.example.com",
                message="SSL verification is disabled for this AAP integration; connection is not verified.",
            )
        assert adapter._verify is False

    def test_init_ca_bundle_overrides_ssl_verify(self) -> None:
        """CA bundle path takes precedence over ssl_verify."""
        adapter = AAPAdapter(
            base_url="https://aap.example.com",
            auth_headers={},
            ssl_verify=False,
            ca_bundle_path="/etc/ssl/ca.pem",
        )
        assert adapter._verify == "/etc/ssl/ca.pem"

    def test_init_strips_trailing_slash(self) -> None:
        """base_url trailing slash is stripped."""
        adapter = AAPAdapter(
            base_url="https://aap.example.com/",
            auth_headers={},
        )
        assert adapter.base_url == "https://aap.example.com"


# ---------------------------------------------------------------------------
# trigger() — limit payload (line 90) + error paths (lines 110-129)
# ---------------------------------------------------------------------------

class TestTriggerCoverage:
    """Additional trigger() tests for missing lines."""

    @pytest.mark.asyncio
    async def test_trigger_with_limit_param(self, adapter: AAPAdapter) -> None:
        """Line 90: limit is added to payload when provided."""
        response = MagicMock()
        response.json.return_value = {"id": 99, "status": "pending", "url": "/api/v2/jobs/99/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(
                "42",
                resource_type="job_template",
                limit="host1",
                correlation_id="corr-1",
            )

        assert result["platform_job_id"] == "99"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["limit"] == "host1"

    @pytest.mark.asyncio
    async def test_trigger_timeout_raises_service_unavailable(self, adapter: AAPAdapter) -> None:
        """Lines 110-116: TimeoutException in trigger() raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42", correlation_id="corr-1")

        assert exc_info.value.code == "AAP_TIMEOUT"
        assert "AAP did not respond in time" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_trigger_http_status_error_raises_service_unavailable(self, adapter: AAPAdapter) -> None:
        """Lines 122-129: HTTPStatusError in trigger() raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        error = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42", correlation_id="corr-1")

        assert exc_info.value.code == "AAP_HTTP_ERROR"
        assert "403" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_trigger_http_status_error_500(self, adapter: AAPAdapter) -> None:
        """HTTPStatusError 500 in trigger() raises ServiceUnavailableError with status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "AAP_HTTP_ERROR"
        assert exc_info.value.details["status_code"] == 500


# ---------------------------------------------------------------------------
# get_status() — HTTPStatusError and HTTPError (lines 213-218)
# ---------------------------------------------------------------------------

class TestGetStatusCoverage:
    """Additional get_status() tests for missing error paths."""

    @pytest.mark.asyncio
    async def test_get_status_http_status_error(self, adapter: AAPAdapter) -> None:
        """Lines 213-215: HTTPStatusError in get_status() raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123", correlation_id="corr-1")

        assert exc_info.value.code == "AAP_HTTP_ERROR"
        assert exc_info.value.details["status_code"] == 500

    @pytest.mark.asyncio
    async def test_get_status_connection_error(self, adapter: AAPAdapter) -> None:
        """Lines 216-218: HTTPError in get_status() raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"
        assert "Cannot connect to AAP" in exc_info.value.message


# ---------------------------------------------------------------------------
# get_job_logs() — Non-404 HTTP error (lines 329-336)
# ---------------------------------------------------------------------------

class TestGetJobLogsCoverage:
    """Additional get_job_logs() tests for missing lines."""

    @pytest.mark.asyncio
    async def test_get_job_logs_non_404_http_error_raises(self, adapter: AAPAdapter) -> None:
        """Lines 329-336: Non-404 HTTPStatusError raises ServiceUnavailableError."""
        mock_response = httpx.Response(
            503,
            request=httpx.Request("GET", "https://aap.example.com/api/v2/jobs/123/stdout/"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable",
                request=mock_response.request,
                response=mock_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123", correlation_id="corr-1")

        assert exc_info.value.code == "AAP_LOGS_UNAVAILABLE"
        assert exc_info.value.details["status_code"] == 503

    @pytest.mark.asyncio
    async def test_get_job_logs_non_404_500_error(self, adapter: AAPAdapter) -> None:
        """Non-404 HTTPStatusError (500) raises with correct details."""
        mock_response = httpx.Response(
            500,
            request=httpx.Request("GET", "https://aap.example.com/api/v2/jobs/456/stdout/"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=mock_response.request,
                response=mock_response,
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("456")

        assert exc_info.value.code == "AAP_LOGS_UNAVAILABLE"
        assert "500" in exc_info.value.message


# ---------------------------------------------------------------------------
# cancel_execution() — workflow_job URL (line 484) + errors (lines 506-511)
# ---------------------------------------------------------------------------

class TestCancelExecutionCoverage:
    """Additional cancel_execution() tests for missing lines."""

    @pytest.mark.asyncio
    async def test_cancel_workflow_job_uses_correct_url(self, adapter: AAPAdapter) -> None:
        """Line 484: workflow_job resource_type uses workflow_jobs URL."""
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("456", resource_type="workflow_job")

        call_url = str(mock_client.post.call_args)
        assert "workflow_jobs/456/cancel/" in call_url

    @pytest.mark.asyncio
    async def test_cancel_http_status_error_raises(self, adapter: AAPAdapter) -> None:
        """Lines 506-508: HTTPStatusError in cancel_execution() raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        error = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("123", correlation_id="corr-1")

        assert exc_info.value.code == "AAP_HTTP_ERROR"
        assert exc_info.value.details["status_code"] == 403

    @pytest.mark.asyncio
    async def test_cancel_connection_error_raises(self, adapter: AAPAdapter) -> None:
        """Lines 509-511: HTTPError in cancel_execution() raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("123")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"
        assert "Cannot connect to AAP for cancellation" in exc_info.value.message


# ---------------------------------------------------------------------------
# health_check() — success and error paths (lines 529-545)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for AAPAdapter.health_check() — lines 529-545."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter: AAPAdapter) -> None:
        """Lines 529-542: health_check() returns OK when ping succeeds."""
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None
        assert result.checked_at is not None

        # Verify correct ping URL was called
        call_url = str(mock_client.get.call_args)
        assert "/api/v2/ping/" in call_url

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, adapter: AAPAdapter) -> None:
        """Lines 543-549: health_check() returns ERROR on connection failure."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None
        assert "Connection refused" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, adapter: AAPAdapter) -> None:
        """health_check() returns ERROR on timeout."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_http_error(self, adapter: AAPAdapter) -> None:
        """health_check() returns ERROR on HTTP 401 (auth failure)."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None


# ---------------------------------------------------------------------------
# Happy-path tests to make this file self-sufficient at >=90% coverage
# ---------------------------------------------------------------------------

class TestTriggerHappyPath:
    """Happy-path trigger() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_trigger_job_template_success(self, adapter: AAPAdapter) -> None:
        """trigger() job_template happy path."""
        response = MagicMock()
        response.json.return_value = {"id": 789, "status": "pending", "url": "/api/v2/jobs/789/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("42", resource_type="job_template", extra_vars={"db": "mydb"})

        assert result["platform_job_id"] == "789"
        assert result["status"] == "SUBMITTED"
        assert result["aap_status"] == "pending"

    @pytest.mark.asyncio
    async def test_trigger_workflow_job_success(self, adapter: AAPAdapter) -> None:
        """trigger() workflow_job uses correct URL."""
        response = MagicMock()
        response.json.return_value = {"id": 101, "status": "pending", "url": "/api/v2/workflow_jobs/101/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("10", resource_type="workflow_job")

        assert result["platform_job_id"] == "101"
        call_args = mock_client.post.call_args
        assert "workflow_job_templates/10/launch/" in str(call_args)

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: AAPAdapter) -> None:
        """trigger() connection error maps to AAP_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"


class TestGetStatusHappyPath:
    """Happy-path get_status() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_get_status_success_job_template(self, adapter: AAPAdapter) -> None:
        """get_status() success with job_template."""
        response = MagicMock()
        response.json.return_value = {
            "status": "running",
            "started": "2026-02-14T10:00:00Z",
            "finished": None,
            "elapsed": 45.2,
        }
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("123", resource_type="job_template")

        assert result["status"] == "RUNNING"
        assert result["aap_status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_workflow_job(self, adapter: AAPAdapter) -> None:
        """get_status() success with workflow_job."""
        response = MagicMock()
        response.json.return_value = {"status": "successful", "started": "x", "finished": "y", "elapsed": 10}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("456", resource_type="workflow_job")

        assert result["status"] == "COMPLETED"
        assert "workflow_jobs/456" in str(mock_client.get.call_args)

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: AAPAdapter) -> None:
        """get_status() timeout raises AAP_TIMEOUT."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123")

        assert exc_info.value.code == "AAP_TIMEOUT"


class TestGetJobLogsHappyPath:
    """Happy-path get_job_logs() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success_job_template(self, adapter: AAPAdapter) -> None:
        """get_job_logs() success with job_template."""
        stdout_response = MagicMock()
        stdout_response.text = "PLAY [all] ****\nok: [host1]"
        stdout_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.json.return_value = {"status": "successful"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[stdout_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("123", resource_type="job_template")

        assert result["content"] == "PLAY [all] ****\nok: [host1]"
        assert result["complete"] is True
        assert result["job_status"] == "successful"

    @pytest.mark.asyncio
    async def test_get_job_logs_workflow_job(self, adapter: AAPAdapter) -> None:
        """get_job_logs() success with workflow_job."""
        stdout_response = MagicMock()
        stdout_response.text = "Workflow output"
        stdout_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.json.return_value = {"status": "running"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[stdout_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("456", resource_type="workflow_job")

        assert result["content"] == "Workflow output"
        assert result["complete"] is False
        assert "/workflow_jobs/456/stdout/" in str(mock_client.get.call_args_list[0])

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: AAPAdapter) -> None:
        """get_job_logs() timeout raises AAP_LOGS_TIMEOUT."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("read timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "AAP_LOGS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_job_logs_404_returns_empty(self, adapter: AAPAdapter) -> None:
        """get_job_logs() 404 returns empty content with job_status=not_found."""
        response_404 = httpx.Response(
            404,
            request=httpx.Request("GET", "https://aap.example.com/api/v2/jobs/999/stdout/"),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("Not Found", request=response_404.request, response=response_404)
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("999")

        assert result["content"] == ""
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: AAPAdapter) -> None:
        """get_job_logs() connection error raises AAP_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"


class TestCancelExecutionHappyPath:
    """Happy-path cancel_execution() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_cancel_success_job_template(self, adapter: AAPAdapter) -> None:
        """cancel_execution() success with job_template."""
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("123")  # Should not raise

        call_url = str(mock_client.post.call_args)
        assert "jobs/123/cancel/" in call_url

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: AAPAdapter) -> None:
        """cancel_execution() timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("123")

        assert exc_info.value.code == "AAP_TIMEOUT"


class TestListTemplatesHappyPath:
    """Happy-path list_templates() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_list_templates_job_template(self, adapter: AAPAdapter) -> None:
        """list_templates() success with job_template."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "count": 2,
            "results": [
                {"id": 10, "name": "Deploy DB", "description": "Deploy database"},
                {"id": 20, "name": "Patch OS", "description": ""},
            ],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.list_templates(resource_type="job_template")

        assert len(result) == 2
        assert result[0]["name"] == "Deploy DB"

    @pytest.mark.asyncio
    async def test_list_templates_workflow_job(self, adapter: AAPAdapter) -> None:
        """list_templates() success with workflow_job uses correct endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "count": 1,
            "results": [{"id": 42, "name": "Full Provision", "description": "Full provisioning"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.list_templates(resource_type="workflow_job")

        assert len(result) == 1
        assert "/api/v2/workflow_job_templates/" in str(mock_client.get.call_args)

    @pytest.mark.asyncio
    async def test_list_templates_with_search(self, adapter: AAPAdapter) -> None:
        """list_templates() passes search parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"count": 0, "results": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.list_templates(resource_type="job_template", search="deploy")

        assert mock_client.get.call_args.kwargs["params"]["search"] == "deploy"

    @pytest.mark.asyncio
    async def test_list_templates_invalid_resource_type(self, adapter: AAPAdapter) -> None:
        """list_templates() raises ValueError for invalid resource_type."""
        with pytest.raises(ValueError, match="resource_type invalide"):
            await adapter.list_templates(resource_type="invalid")

    @pytest.mark.asyncio
    async def test_list_templates_timeout(self, adapter: AAPAdapter) -> None:
        """list_templates() timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.list_templates()

        assert exc_info.value.code == "AAP_TIMEOUT"

    @pytest.mark.asyncio
    async def test_list_templates_http_error(self, adapter: AAPAdapter) -> None:
        """list_templates() HTTP 500 raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.list_templates()

        assert exc_info.value.code == "AAP_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_list_templates_connection_error(self, adapter: AAPAdapter) -> None:
        """list_templates() connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.list_templates()

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"


class TestStatusMapping:
    """AAP status mapping tests for standalone coverage."""

    @pytest.mark.parametrize(
        "aap_status,expected",
        [
            ("pending", "SUBMITTED"),
            ("running", "RUNNING"),
            ("successful", "COMPLETED"),
            ("failed", "FAILED"),
            ("canceled", "CANCELLED"),
        ],
    )
    def test_status_map(self, aap_status: str, expected: str) -> None:
        assert AAP_STATUS_MAP[aap_status] == expected
