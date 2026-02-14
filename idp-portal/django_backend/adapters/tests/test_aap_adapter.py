"""
Tests for AAPAdapter — Story 27.1.

Covers:
- get_job_logs(): success, timeout, 404, logs empty, workflow_job
- get_status(): success, timeout, error mapping
- trigger(): success, timeout, connection error
- cancel_execution(): success, timeout
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

import httpx

from adapters.aap_adapter import AAPAdapter, AAP_STATUS_MAP
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> AAPAdapter:
    return AAPAdapter(
        base_url="https://aap.example.com",
        auth_headers={"Authorization": "Bearer test-token"},
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# get_job_logs
# ---------------------------------------------------------------------------

class TestGetJobLogs:
    """Tests for AAPAdapter.get_job_logs() — Task 6.1."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success_job_template(self, adapter: AAPAdapter) -> None:
        """Success: mock stdout response for job_template."""
        stdout_response = MagicMock()
        stdout_response.status_code = 200
        stdout_response.text = "PLAY [all] ****\nTASK [setup] ****\nok: [host1]"
        stdout_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"status": "successful", "started": "2026-02-14T10:00:00Z"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[stdout_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("123", resource_type="job_template")

        assert result["content"] == "PLAY [all] ****\nTASK [setup] ****\nok: [host1]"
        assert result["format"] == "text/plain"
        assert result["complete"] is True
        assert result["job_status"] == "successful"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_job_logs_success_workflow_job(self, adapter: AAPAdapter) -> None:
        """Success: workflow_job uses correct endpoint."""
        stdout_response = MagicMock()
        stdout_response.status_code = 200
        stdout_response.text = "Workflow output"
        stdout_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
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
        assert result["job_status"] == "running"

        # Verify correct URL was called (workflow_jobs, not jobs)
        first_call = mock_client.get.call_args_list[0]
        assert "/workflow_jobs/456/stdout/" in str(first_call)

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: AAPAdapter) -> None:
        """Timeout raises ServiceUnavailableError with AAP_LOGS_TIMEOUT code."""
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
        """404 returns empty logs dict (job not found yet).

        MEDIUM-1 FIX: job_status="not_found" (was "unknown") to allow caller
        to distinguish "job not found yet (retry)" vs "job exists but logs empty".
        """
        response_404 = httpx.Response(404, request=httpx.Request("GET", "https://aap.example.com/api/v2/jobs/999/stdout/"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("Not Found", request=response_404.request, response=response_404))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("999")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "not_found"  # MEDIUM-1 FIX: was "unknown"

    @pytest.mark.asyncio
    async def test_get_job_logs_empty_content(self, adapter: AAPAdapter) -> None:
        """Job exists but stdout is empty (job just started)."""
        stdout_response = MagicMock()
        stdout_response.status_code = 200
        stdout_response.text = ""
        stdout_response.raise_for_status = MagicMock()

        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {"status": "pending"}
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[stdout_response, status_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("123")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: AAPAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for AAPAdapter.get_status()."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, adapter: AAPAdapter) -> None:
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
        assert result["started"] == "2026-02-14T10:00:00Z"

    @pytest.mark.asyncio
    async def test_get_status_workflow_job(self, adapter: AAPAdapter) -> None:
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
        # Verify correct URL
        mock_client.get.assert_called_once()
        call_url = str(mock_client.get.call_args)
        assert "workflow_jobs/456" in call_url

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: AAPAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123")

        assert exc_info.value.code == "AAP_TIMEOUT"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    """Tests for AAPAdapter.trigger()."""

    @pytest.mark.asyncio
    async def test_trigger_job_template_success(self, adapter: AAPAdapter) -> None:
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
        # Verify correct URL
        call_args = mock_client.post.call_args
        assert "workflow_job_templates/10/launch/" in str(call_args)

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: AAPAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "AAP_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Tests for AAPAdapter.cancel_execution()."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: AAPAdapter) -> None:
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("123")  # Should not raise

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: AAPAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.aap_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError):
                await adapter.cancel_execution("123")


# ---------------------------------------------------------------------------
# AAP_STATUS_MAP
# ---------------------------------------------------------------------------

class TestStatusMapping:
    """Test AAP status → IDP Portal mapping."""

    @pytest.mark.parametrize(
        "aap_status,expected",
        [
            ("pending", "SUBMITTED"),
            ("waiting", "SUBMITTED"),
            ("running", "RUNNING"),
            ("successful", "COMPLETED"),
            ("failed", "FAILED"),
            ("error", "FAILED"),
            ("canceled", "CANCELLED"),
        ],
    )
    def test_status_map(self, aap_status: str, expected: str) -> None:
        assert AAP_STATUS_MAP[aap_status] == expected
