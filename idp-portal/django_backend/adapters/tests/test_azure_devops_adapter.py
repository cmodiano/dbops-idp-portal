"""
Tests for AzureDevOpsAdapter — Story 27.3.

Covers:
- trigger(): launch pipeline run, success and errors
- get_status(): mapping Azure DevOps state+result → IDP Portal status
- get_job_logs(): success, timeout, 404, logs empty
- cancel_execution(): success and errors
- map_azure_devops_status(): status mapping utility
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from adapters.azure_devops_adapter import (
    AzureDevOpsAdapter,
    map_azure_devops_status,
)
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> AzureDevOpsAdapter:
    return AzureDevOpsAdapter(
        base_url="https://dev.azure.com/myorg/myproject",
        auth_headers={"Authorization": "Basic dGVzdC1wYXQ="},
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# map_azure_devops_status
# ---------------------------------------------------------------------------

class TestMapAzureDevOpsStatus:
    """Tests for status mapping utility."""

    def test_in_progress(self) -> None:
        assert map_azure_devops_status("inProgress", None) == "RUNNING"

    def test_canceling(self) -> None:
        assert map_azure_devops_status("canceling", None) == "RUNNING"

    def test_completed_succeeded(self) -> None:
        assert map_azure_devops_status("completed", "succeeded") == "COMPLETED"

    def test_completed_failed(self) -> None:
        assert map_azure_devops_status("completed", "failed") == "FAILED"

    def test_completed_canceled(self) -> None:
        assert map_azure_devops_status("completed", "canceled") == "CANCELLED"

    def test_unknown_state(self) -> None:
        assert map_azure_devops_status("unknown", None) == "SUBMITTED"

    def test_completed_unknown_result(self) -> None:
        assert map_azure_devops_status("completed", "unknown") == "FAILED"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    """Tests for AzureDevOpsAdapter.trigger()."""

    @pytest.mark.asyncio
    async def test_trigger_success_minimal(self, adapter: AzureDevOpsAdapter) -> None:
        """Success: launch pipeline run with no extra parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 42,
            "state": "inProgress",
            "result": None,
            "url": "https://dev.azure.com/myorg/myproject/_apis/pipelines/1/runs/42",
            "pipeline": {"id": 1, "name": "CI Pipeline"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("1", correlation_id="corr-123")

        assert result["platform_job_id"] == "42"
        assert result["status"] == "RUNNING"
        assert result["azure_devops_state"] == "inProgress"
        assert result["pipeline_id"] == "1"

    @pytest.mark.asyncio
    async def test_trigger_success_with_parameters(self, adapter: AzureDevOpsAdapter) -> None:
        """Success: launch with template parameters, variables, and branch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 43,
            "state": "inProgress",
            "result": None,
            "pipeline": {"id": 5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(
                "5",
                template_parameters={"env": "prod"},
                variables={"debug": {"value": "true"}},
                branch="refs/heads/main",
            )

        assert result["platform_job_id"] == "43"
        # Verify payload was passed correctly
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["templateParameters"] == {"env": "prod"}
        assert payload["variables"] == {"debug": {"value": "true"}}
        assert payload["resources"]["repositories"]["self"]["refName"] == "refs/heads/main"

    @pytest.mark.asyncio
    async def test_trigger_timeout(self, adapter: AzureDevOpsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        from core.exceptions import AdapterTimeoutError
        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.trigger("1")
            assert exc_info.value.code == "ADAPTER_TIMEOUT"

    @pytest.mark.asyncio
    async def test_trigger_http_error(self, adapter: AzureDevOpsAdapter) -> None:
        """HTTP error raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Forbidden",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("1")
            assert exc_info.value.code == "AZURE_DEVOPS_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: AzureDevOpsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("1")
            assert exc_info.value.code == "AZURE_DEVOPS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for AzureDevOpsAdapter.get_status()."""

    @pytest.mark.asyncio
    async def test_get_status_in_progress(self, adapter: AzureDevOpsAdapter) -> None:
        """Running run returns RUNNING status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "inProgress",
            "result": None,
            "createdDate": "2026-02-14T10:00:00Z",
            "finishedDate": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("42", pipeline_id="1")

        assert result["status"] == "RUNNING"
        assert result["azure_devops_state"] == "inProgress"
        assert result["azure_devops_result"] is None

    @pytest.mark.asyncio
    async def test_get_status_completed_succeeded(self, adapter: AzureDevOpsAdapter) -> None:
        """Completed+succeeded maps to COMPLETED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "completed",
            "result": "succeeded",
            "createdDate": "2026-02-14T10:00:00Z",
            "finishedDate": "2026-02-14T10:05:00Z",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("42", pipeline_id="1")

        assert result["status"] == "COMPLETED"
        assert result["azure_devops_state"] == "completed"
        assert result["azure_devops_result"] == "succeeded"

    @pytest.mark.asyncio
    async def test_get_status_completed_failed(self, adapter: AzureDevOpsAdapter) -> None:
        """Completed+failed maps to FAILED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "completed",
            "result": "failed",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("42", pipeline_id="1")

        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_get_status_completed_canceled(self, adapter: AzureDevOpsAdapter) -> None:
        """Completed+canceled maps to CANCELLED."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "completed",
            "result": "canceled",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("42", pipeline_id="1")

        assert result["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_get_status_404_not_found(self, adapter: AzureDevOpsAdapter) -> None:
        """404 returns not_found state (run not ready yet)."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("999", pipeline_id="1")

        assert result["status"] == "SUBMITTED"
        assert result["azure_devops_state"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: AzureDevOpsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        from core.exceptions import AdapterTimeoutError
        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.get_status("42", pipeline_id="1")
            assert exc_info.value.code == "ADAPTER_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_status_connection_error(self, adapter: AzureDevOpsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_job_logs
# ---------------------------------------------------------------------------

class TestGetJobLogs:
    """Tests for AzureDevOpsAdapter.get_job_logs()."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success(self, adapter: AzureDevOpsAdapter) -> None:
        """Success: retrieve logs from multiple log entries."""
        # Step 1: logs listing response
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {
            "logs": [
                {"id": 1, "lineCount": 10},
                {"id": 2, "lineCount": 5},
            ]
        }
        logs_list_response.raise_for_status = MagicMock()

        # Step 2: individual log responses
        log1_response = MagicMock()
        log1_response.status_code = 200
        log1_response.text = "Step 1: Checkout\nStep 1: Complete"

        log2_response = MagicMock()
        log2_response.status_code = 200
        log2_response.text = "Step 2: Build\nStep 2: Complete"

        # Step 3: status response
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "state": "completed",
            "result": "succeeded",
        }
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[logs_list_response, log1_response, log2_response, status_response]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("42", pipeline_id="1")

        assert "Step 1: Checkout" in result["content"]
        assert "Step 2: Build" in result["content"]
        assert result["format"] == "text/plain"
        assert result["complete"] is True
        assert result["job_status"] == "completed"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_job_logs_empty(self, adapter: AzureDevOpsAdapter) -> None:
        """Success with empty log listing."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {"logs": []}
        logs_list_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "inProgress", "result": None}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[logs_list_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("42", pipeline_id="1")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "inProgress"

    @pytest.mark.asyncio
    async def test_get_job_logs_still_running(self, adapter: AzureDevOpsAdapter) -> None:
        """Logs retrieved while run is still in progress."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {
            "logs": [{"id": 1, "lineCount": 3}]
        }
        logs_list_response.raise_for_status = MagicMock()

        log1_response = MagicMock()
        log1_response.status_code = 200
        log1_response.text = "Running task..."

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "inProgress", "result": None}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[logs_list_response, log1_response, status_response]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("42", pipeline_id="1")

        assert result["complete"] is False
        assert result["job_status"] == "inProgress"

    @pytest.mark.asyncio
    async def test_get_job_logs_404(self, adapter: AzureDevOpsAdapter) -> None:
        """404 returns empty content with not_found status."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("999", pipeline_id="1")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: AzureDevOpsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_LOGS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_job_logs_http_500(self, adapter: AzureDevOpsAdapter) -> None:
        """Non-404 HTTP error raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_LOGS_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: AzureDevOpsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Tests for AzureDevOpsAdapter.cancel_execution()."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: AzureDevOpsAdapter) -> None:
        """Success: PATCH build with status=cancelling."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.patch = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("42", pipeline_id="1")

        # Verify PATCH was called with correct URL and payload
        call_args = mock_client.patch.call_args
        assert "build/builds/42" in call_args.args[0]
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload == {"status": "cancelling"}

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: AzureDevOpsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.patch = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_cancel_http_error(self, adapter: AzureDevOpsAdapter) -> None:
        """HTTP error raises ServiceUnavailableError."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Conflict",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.patch = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_cancel_connection_error(self, adapter: AzureDevOpsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.patch = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------

class TestFactory:
    """Tests for adapter factory integration."""

    def test_factory_azure_devops(self) -> None:
        """Factory returns AzureDevOpsAdapter for 'azure_devops' platform_type."""
        from adapters import get_platform_adapter

        adapter = get_platform_adapter(
            platform_type="azure_devops",
            base_url="https://dev.azure.com/org/proj",
            auth_headers={"Authorization": "Basic abc"},
        )
        assert isinstance(adapter, AzureDevOpsAdapter)

    def test_factory_azure_devops_default_verify_ssl_true(self) -> None:
        """ADP-HIGH-01: AzureDevOpsAdapter factory default verify_ssl=True (cloud public service)."""
        from adapters import get_platform_adapter

        adapter = get_platform_adapter(
            platform_type="azure_devops",
            base_url="https://dev.azure.com/org/proj",
            auth_headers={"Authorization": "Basic abc"},
        )
        assert isinstance(adapter, AzureDevOpsAdapter)
        assert adapter.verify_ssl is True

    def test_factory_azure_devops_can_override_verify_ssl_false(self) -> None:
        """AzureDevOpsAdapter factory can set verify_ssl=False for on-prem Azure DevOps Server."""
        from adapters import get_platform_adapter

        adapter = get_platform_adapter(
            platform_type="azure_devops",
            base_url="https://ado.internal.example.com/org/proj",
            auth_headers={"Authorization": "Basic abc"},
            verify_ssl=False,
        )
        assert isinstance(adapter, AzureDevOpsAdapter)
        assert adapter.verify_ssl is False

    def test_factory_aap_still_works(self) -> None:
        """Factory still returns AAPAdapter for 'aap' (non-regression)."""
        from adapters import get_platform_adapter
        from adapters.aap_adapter import AAPAdapter

        adapter = get_platform_adapter(
            platform_type="aap",
            base_url="https://aap.example.com",
            auth_headers={"Authorization": "Bearer tok"},
        )
        assert isinstance(adapter, AAPAdapter)

    def test_factory_tower_still_works(self) -> None:
        """Factory still returns TowerAdapter for 'tower' (non-regression)."""
        from adapters import get_platform_adapter
        from adapters.tower_adapter import TowerAdapter

        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer tok"},
        )
        assert isinstance(adapter, TowerAdapter)

    def test_factory_unsupported(self) -> None:
        """Factory raises ValueError for unsupported platform_type."""
        from adapters import get_platform_adapter

        with pytest.raises(ValueError, match="Unsupported platform_type"):
            get_platform_adapter(
                platform_type="jenkins",
                base_url="https://jenkins.example.com",
                auth_headers={},
            )


# ---------------------------------------------------------------------------
# trigger — non-numeric pipeline_id (line 97)
# ---------------------------------------------------------------------------

class TestTriggerValidation:
    """Tests for trigger() input validation."""

    @pytest.mark.asyncio
    async def test_trigger_non_numeric_pipeline_id_raises_value_error(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """Non-numeric pipeline_id raises ValueError before any HTTP call."""
        with pytest.raises(ValueError, match="must be numeric"):
            await adapter.trigger("my-pipeline-name")


# ---------------------------------------------------------------------------
# get_status — non-404 HTTP error (lines 272-279)
# ---------------------------------------------------------------------------

class TestGetStatusHttpErrors:
    """Tests for get_status() HTTP error branches."""

    @pytest.mark.asyncio
    async def test_get_status_non_404_http_error_raises(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """Non-404 HTTPStatusError raises ServiceUnavailableError with AZURE_DEVOPS_HTTP_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("42", pipeline_id="1")
        assert exc_info.value.code == "AZURE_DEVOPS_HTTP_ERROR"


# ---------------------------------------------------------------------------
# get_job_logs — fetch_log edge cases (lines 395, 409-433, 441->440)
# ---------------------------------------------------------------------------

class TestGetJobLogsFetchLogEdgeCases:
    """Tests for fetch_log() internal retry and edge-case branches."""

    @pytest.mark.asyncio
    async def test_fetch_log_with_null_id_is_skipped(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """Log entry with null id returns empty string and is not written to buffer."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        # Entry without 'id' key → log_id will be None
        logs_list_response.json.return_value = {"logs": [{"lineCount": 5}]}
        logs_list_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "completed", "result": "succeeded"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[logs_list_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("42", pipeline_id="1")

        # Null id log is skipped — content should be empty
        assert result["content"] == ""
        assert result["complete"] is True

    @pytest.mark.asyncio
    async def test_fetch_log_retries_on_5xx_then_succeeds(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """fetch_log retries once on 5xx error and returns content on second attempt."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {"logs": [{"id": 1, "lineCount": 3}]}
        logs_list_response.raise_for_status = MagicMock()

        # First call: 500 error (triggers retry)
        log_retry_fail = MagicMock()
        log_retry_fail.status_code = 500

        # Second call (retry): 200 success
        log_retry_ok = MagicMock()
        log_retry_ok.status_code = 200
        log_retry_ok.text = "retried successfully"

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "completed", "result": "succeeded"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[logs_list_response, log_retry_fail, log_retry_ok, status_response]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", return_value=None):
                result = await adapter.get_job_logs("42", pipeline_id="1")

        assert "retried successfully" in result["content"]

    @pytest.mark.asyncio
    async def test_fetch_log_non_retryable_4xx_returns_empty(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """fetch_log with a non-retryable 4xx status code returns empty string for that log."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {"logs": [{"id": 7, "lineCount": 2}]}
        logs_list_response.raise_for_status = MagicMock()

        # 403 is non-retryable (not 5xx, not 200)
        log_403 = MagicMock()
        log_403.status_code = 403

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "completed", "result": "succeeded"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=[logs_list_response, log_403, status_response]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("42", pipeline_id="1")

        # Non-retryable 4xx → empty content for that log
        assert result["content"] == ""
        assert result["complete"] is True

    @pytest.mark.asyncio
    async def test_fetch_log_http_error_on_first_attempt_retries(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """fetch_log swallows HTTPError on first attempt, retries, succeeds on second."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {"logs": [{"id": 9, "lineCount": 1}]}
        logs_list_response.raise_for_status = MagicMock()

        log_ok = MagicMock()
        log_ok.status_code = 200
        log_ok.text = "recovered log"

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "completed", "result": "succeeded"}
        status_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return logs_list_response
            if call_count == 2:
                raise httpx.ConnectError("transient error")
            if call_count == 3:
                return log_ok
            return status_response

        mock_client = MagicMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", return_value=None):
                result = await adapter.get_job_logs("42", pipeline_id="1")

        assert "recovered log" in result["content"]

    @pytest.mark.asyncio
    async def test_fetch_log_http_error_on_both_attempts_returns_empty(
        self, adapter: AzureDevOpsAdapter
    ) -> None:
        """fetch_log with HTTPError on both attempts returns empty string for that log."""
        logs_list_response = MagicMock()
        logs_list_response.status_code = 200
        logs_list_response.json.return_value = {"logs": [{"id": 11, "lineCount": 1}]}
        logs_list_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"state": "completed", "result": "succeeded"}
        status_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_get(url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return logs_list_response
            if call_count in (2, 3):
                raise httpx.ConnectError("persistent error")
            return status_response

        mock_client = MagicMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with patch("asyncio.sleep", return_value=None):
                result = await adapter.get_job_logs("42", pipeline_id="1")

        assert result["content"] == ""
        assert result["complete"] is True


# ---------------------------------------------------------------------------
# health_check (lines 632-648)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for AzureDevOpsAdapter.health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_ok(self, adapter: AzureDevOpsAdapter) -> None:
        """Successful ping returns HealthCheckStatus.OK."""
        from integrations.health_check import HealthCheckStatus

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_health_check_error_on_timeout(self, adapter: AzureDevOpsAdapter) -> None:
        """Timeout exception returns HealthCheckStatus.ERROR with error_message."""
        from integrations.health_check import HealthCheckStatus

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None
        assert "timeout" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_health_check_error_on_http_error(self, adapter: AzureDevOpsAdapter) -> None:
        """HTTPStatusError (e.g. 401 Unauthorized) returns HealthCheckStatus.ERROR."""
        from integrations.health_check import HealthCheckStatus

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None
