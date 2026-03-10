"""
Tests for TowerAdapter — Story 27.2.

Covers:
- get_job_logs(): success, timeout, 404, logs empty, workflow_job
- get_status(): success, timeout, error mapping, workflow_job
- trigger(): success job_template, workflow_job, timeout, connection error
- cancel_execution(): success, timeout
- TOWER_STATUS_MAP: all status mappings
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from adapters.tower_adapter import TowerAdapter, TOWER_STATUS_MAP
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> TowerAdapter:
    return TowerAdapter(
        base_url="https://tower.example.com",
        auth_headers={"Authorization": "Bearer test-token"},
        timeout=5.0,
    )


# ---------------------------------------------------------------------------
# get_job_logs
# ---------------------------------------------------------------------------

class TestGetJobLogs:
    """Tests for TowerAdapter.get_job_logs()."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success_job_template(self, adapter: TowerAdapter) -> None:
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

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("123", resource_type="job_template")

        assert result["content"] == "PLAY [all] ****\nTASK [setup] ****\nok: [host1]"
        assert result["format"] == "text/plain"
        assert result["complete"] is True
        assert result["job_status"] == "successful"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_job_logs_success_workflow_job(self, adapter: TowerAdapter) -> None:
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

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("456", resource_type="workflow_job")

        assert result["content"] == "Workflow output"
        assert result["complete"] is False
        assert result["job_status"] == "running"

        first_call = mock_client.get.call_args_list[0]
        assert "/workflow_jobs/456/stdout/" in str(first_call)

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("read timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "TOWER_LOGS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_job_logs_404_returns_empty(self, adapter: TowerAdapter) -> None:
        response_404 = httpx.Response(404, request=httpx.Request("GET", "https://tower.example.com/api/v2/jobs/999/stdout/"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("Not Found", request=response_404.request, response=response_404))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("999")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_empty_content(self, adapter: TowerAdapter) -> None:
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

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("123")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "TOWER_CONNECTION_ERROR"

    @pytest.mark.asyncio
    async def test_get_job_logs_http_500_raises(self, adapter: TowerAdapter) -> None:
        response_500 = httpx.Response(500, request=httpx.Request("GET", "https://tower.example.com/api/v2/jobs/123/stdout/"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("Server Error", request=response_500.request, response=response_500))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("123")

        assert exc_info.value.code == "TOWER_LOGS_UNAVAILABLE"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for TowerAdapter.get_status()."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, adapter: TowerAdapter) -> None:
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

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("123", resource_type="job_template")

        assert result["status"] == "RUNNING"
        assert result["tower_status"] == "running"
        assert result["started"] == "2026-02-14T10:00:00Z"

    @pytest.mark.asyncio
    async def test_get_status_workflow_job(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.json.return_value = {"status": "successful", "started": "x", "finished": "y", "elapsed": 10}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("456", resource_type="workflow_job")

        assert result["status"] == "COMPLETED"
        mock_client.get.assert_called_once()
        call_url = str(mock_client.get.call_args)
        assert "workflow_jobs/456" in call_url

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123")

        assert exc_info.value.code == "TOWER_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_status_http_error(self, adapter: TowerAdapter) -> None:
        response_500 = httpx.Response(500, request=httpx.Request("GET", "https://tower.example.com/api/v2/jobs/123/"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=response_500.request, response=response_500))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("123")

        assert exc_info.value.code == "TOWER_HTTP_ERROR"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    """Tests for TowerAdapter.trigger()."""

    @pytest.mark.asyncio
    async def test_trigger_job_template_success(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.json.return_value = {"id": 789, "status": "pending", "url": "/api/v2/jobs/789/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("42", resource_type="job_template", extra_vars={"db": "mydb"})

        assert result["platform_job_id"] == "789"
        assert result["status"] == "SUBMITTED"
        assert result["tower_status"] == "pending"

    @pytest.mark.asyncio
    async def test_trigger_workflow_job_success(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.json.return_value = {"id": 101, "status": "pending", "url": "/api/v2/workflow_jobs/101/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("10", resource_type="workflow_job")

        assert result["platform_job_id"] == "101"
        call_args = mock_client.post.call_args
        assert "workflow_job_templates/10/launch/" in str(call_args)

    @pytest.mark.asyncio
    async def test_trigger_with_limit(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.json.return_value = {"id": 200, "status": "pending", "url": "/api/v2/jobs/200/"}
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger("42", limit="host1,host2")

        assert result["platform_job_id"] == "200"
        # Verify limit was passed in payload
        call_kwargs = mock_client.post.call_args
        assert "limit" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_trigger_timeout(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "TOWER_TIMEOUT"

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "TOWER_CONNECTION_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_http_error(self, adapter: TowerAdapter) -> None:
        response_403 = httpx.Response(403, request=httpx.Request("POST", "https://tower.example.com/api/v2/job_templates/42/launch/"))
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("Forbidden", request=response_403.request, response=response_403))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger("42")

        assert exc_info.value.code == "TOWER_HTTP_ERROR"


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Tests for TowerAdapter.cancel_execution()."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("123")

    @pytest.mark.asyncio
    async def test_cancel_workflow_job(self, adapter: TowerAdapter) -> None:
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("456", resource_type="workflow_job")

        call_url = str(mock_client.post.call_args)
        assert "workflow_jobs/456/cancel/" in call_url

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: TowerAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError):
                await adapter.cancel_execution("123")

    @pytest.mark.asyncio
    async def test_cancel_http_error(self, adapter: TowerAdapter) -> None:
        response_500 = httpx.Response(500, request=httpx.Request("POST", "https://tower.example.com/api/v2/jobs/123/cancel/"))
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=response_500.request, response=response_500))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.tower_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("123")

        assert exc_info.value.code == "TOWER_HTTP_ERROR"


# ---------------------------------------------------------------------------
# TOWER_STATUS_MAP
# ---------------------------------------------------------------------------

class TestStatusMapping:
    """Test Tower status → IDP Portal mapping."""

    @pytest.mark.parametrize(
        "tower_status,expected",
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
    def test_status_map(self, tower_status: str, expected: str) -> None:
        assert TOWER_STATUS_MAP[tower_status] == expected

    def test_unknown_status_defaults_to_submitted(self, adapter: TowerAdapter) -> None:
        """Unknown status should map to SUBMITTED via dict.get() default."""
        assert TOWER_STATUS_MAP.get("new_status", "SUBMITTED") == "SUBMITTED"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestAdapterFactory:
    """Test get_platform_adapter factory."""

    def test_factory_returns_tower_adapter(self) -> None:
        from adapters import get_platform_adapter
        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, TowerAdapter)

    def test_factory_returns_aap_adapter(self) -> None:
        from adapters import get_platform_adapter
        from adapters.aap_adapter import AAPAdapter
        adapter = get_platform_adapter(
            platform_type="aap",
            base_url="https://aap.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, AAPAdapter)

    def test_factory_unsupported_platform_raises(self) -> None:
        from adapters import get_platform_adapter
        with pytest.raises(ValueError, match="Unsupported platform_type"):
            get_platform_adapter(
                platform_type="unknown",
                base_url="https://example.com",
                auth_headers={},
            )

    def test_factory_with_custom_timeout(self) -> None:
        from adapters import get_platform_adapter
        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
            timeout=10.0,
        )
        assert isinstance(adapter, TowerAdapter)
        assert adapter.timeout == 10.0

    def test_factory_default_ssl_verify_false_for_backward_compat(self) -> None:
        """ADP-MED-01: TowerAdapter factory default ssl_verify=False (Tower/AWX on-prem backward compat)."""
        from adapters import get_platform_adapter
        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
        )
        assert isinstance(adapter, TowerAdapter)
        assert adapter._verify is False

    def test_factory_can_override_ssl_verify_true(self) -> None:
        """ADP-MED-01: TowerAdapter factory can set ssl_verify=True for environments with valid certs."""
        from adapters import get_platform_adapter
        adapter = get_platform_adapter(
            platform_type="tower",
            base_url="https://tower.example.com",
            auth_headers={"Authorization": "Bearer token"},
            ssl_verify=True,
        )
        assert isinstance(adapter, TowerAdapter)
        assert adapter._verify is True
