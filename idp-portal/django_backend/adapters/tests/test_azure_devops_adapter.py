"""
Tests for AzureDevOpsAdapter — Story 27.3.

Covers:
- trigger(): launch pipeline run, success and errors
- get_status(): mapping Azure DevOps state+result → IDP Portal status
- get_job_logs(): success, timeout, 404, logs empty
- cancel_execution(): success and errors
- _map_azure_devops_status(): status mapping utility
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from adapters.azure_devops_adapter import (
    AzureDevOpsAdapter,
    _map_azure_devops_status,
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
# _map_azure_devops_status
# ---------------------------------------------------------------------------

class TestMapAzureDevOpsStatus:
    """Tests for status mapping utility."""

    def test_in_progress(self) -> None:
        assert _map_azure_devops_status("inProgress", None) == "RUNNING"

    def test_canceling(self) -> None:
        assert _map_azure_devops_status("canceling", None) == "RUNNING"

    def test_completed_succeeded(self) -> None:
        assert _map_azure_devops_status("completed", "succeeded") == "COMPLETED"

    def test_completed_failed(self) -> None:
        assert _map_azure_devops_status("completed", "failed") == "FAILED"

    def test_completed_canceled(self) -> None:
        assert _map_azure_devops_status("completed", "canceled") == "CANCELLED"

    def test_unknown_state(self) -> None:
        assert _map_azure_devops_status("unknown", None) == "SUBMITTED"

    def test_completed_unknown_result(self) -> None:
        assert _map_azure_devops_status("completed", "unknown") == "FAILED"


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

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("1")
            assert exc_info.value.code == "AZURE_DEVOPS_TIMEOUT"

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

        with patch("adapters.azure_devops_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("42", pipeline_id="1")
            assert exc_info.value.code == "AZURE_DEVOPS_TIMEOUT"

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
