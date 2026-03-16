"""
Tests for GitHubActionsAdapter — Story 27.4.

Covers:
- trigger(): workflow_dispatch, polling run_id, success and errors
- get_status(): mapping GitHub Actions status+conclusion → IDP Portal status
- get_job_logs(): success, timeout, 404, logs ZIP, run in progress (complete: False)
- cancel_execution(): success, 409 conflict, errors
- _map_github_actions_status(): status mapping utility
- _extract_logs_from_zip(): ZIP extraction utility
"""
from __future__ import annotations

import io
import zipfile

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from adapters.github_actions_adapter import (
    GitHubActionsAdapter,
    _map_github_actions_status,
)
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> GitHubActionsAdapter:
    return GitHubActionsAdapter(
        base_url="https://api.github.com",
        auth_headers={"Authorization": "Bearer ghp_test123"},
        owner="my-org",
        repo="my-repo",
        timeout=5.0,
    )


def _make_zip_content(*files: tuple[str, str]) -> bytes:
    """Helper to create a ZIP archive in memory with given files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _map_github_actions_status
# ---------------------------------------------------------------------------

class TestMapGitHubActionsStatus:
    """Tests for status mapping utility."""

    def test_queued(self) -> None:
        assert _map_github_actions_status("queued", None) == "SUBMITTED"

    def test_in_progress(self) -> None:
        assert _map_github_actions_status("in_progress", None) == "RUNNING"

    def test_completed_success(self) -> None:
        assert _map_github_actions_status("completed", "success") == "COMPLETED"

    def test_completed_failure(self) -> None:
        assert _map_github_actions_status("completed", "failure") == "FAILED"

    def test_completed_cancelled(self) -> None:
        assert _map_github_actions_status("completed", "cancelled") == "CANCELLED"

    def test_completed_timed_out(self) -> None:
        assert _map_github_actions_status("completed", "timed_out") == "FAILED"

    def test_completed_action_required(self) -> None:
        assert _map_github_actions_status("completed", "action_required") == "SUBMITTED"

    def test_completed_skipped(self) -> None:
        assert _map_github_actions_status("completed", "skipped") == "CANCELLED"

    def test_unknown_state(self) -> None:
        assert _map_github_actions_status("unknown", None) == "SUBMITTED"

    def test_completed_unknown_result(self) -> None:
        assert _map_github_actions_status("completed", "unknown") == "FAILED"


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    """Tests for GitHubActionsAdapter.trigger()."""

    @pytest.mark.asyncio
    async def test_trigger_success(self, adapter: GitHubActionsAdapter) -> None:
        """Success: dispatch workflow and recover run_id via polling."""
        # Dispatch response: 204 No Content
        dispatch_response = MagicMock()
        dispatch_response.status_code = 204
        dispatch_response.raise_for_status = MagicMock()

        # Poll response: run found
        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {
            "workflow_runs": [{"id": 12345}]
        }
        poll_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=dispatch_response)
        mock_client.get = AsyncMock(return_value=poll_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client), \
             patch("adapters.github_actions_adapter.asyncio.sleep", new_callable=AsyncMock):
            result = await adapter.trigger(
                workflow_id="deploy.yaml",
                ref="main",
                inputs={"environment": "prod"},
                correlation_id="corr-001",
            )

        assert result["platform_job_id"] == "12345"
        assert result["status"] == "SUBMITTED"
        assert "actions/runs/12345" in result["url"]

        # Verify dispatch POST was called
        call_args = mock_client.post.call_args
        assert "workflows/deploy.yaml/dispatches" in call_args.args[0]
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["ref"] == "main"
        assert payload["inputs"] == {"environment": "prod"}

    @pytest.mark.asyncio
    async def test_trigger_run_id_not_found(self, adapter: GitHubActionsAdapter) -> None:
        """Run_id not found after max polling attempts raises error."""
        dispatch_response = MagicMock()
        dispatch_response.status_code = 204
        dispatch_response.raise_for_status = MagicMock()

        poll_response = MagicMock()
        poll_response.status_code = 200
        poll_response.json.return_value = {"workflow_runs": []}
        poll_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=dispatch_response)
        mock_client.get = AsyncMock(return_value=poll_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client), \
             patch("adapters.github_actions_adapter.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workflow_id="deploy.yaml")
            assert exc_info.value.code == "GITHUB_ACTIONS_RUN_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_trigger_timeout(self, adapter: GitHubActionsAdapter) -> None:
        """Timeout raises AdapterTimeoutError (Story 86.1)."""
        from core.exceptions import AdapterTimeoutError
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.trigger(workflow_id="deploy.yaml")
            assert exc_info.value.code == "ADAPTER_TIMEOUT"
            assert exc_info.value.details.get("adapter_type") == "github_actions"

    @pytest.mark.asyncio
    async def test_trigger_http_error(self, adapter: GitHubActionsAdapter) -> None:
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

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workflow_id="deploy.yaml")
            assert exc_info.value.code == "GITHUB_ACTIONS_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: GitHubActionsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workflow_id="deploy.yaml")
            assert exc_info.value.code == "GITHUB_ACTIONS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for GitHubActionsAdapter.get_status()."""

    @pytest.mark.asyncio
    async def test_get_status_queued(self, adapter: GitHubActionsAdapter) -> None:
        """Queued run returns SUBMITTED status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "queued",
            "conclusion": None,
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:00:01Z",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("12345")

        assert result["status"] == "SUBMITTED"
        assert result["github_actions_status"] == "queued"
        assert result["github_actions_conclusion"] is None
        assert result["outputs"] == {}
        assert result["artifacts"] == []
        assert result["job_conclusion"] is None

    @pytest.mark.asyncio
    async def test_get_status_in_progress(self, adapter: GitHubActionsAdapter) -> None:
        """Running run returns RUNNING status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "in_progress",
            "conclusion": None,
            "created_at": "2026-02-14T10:00:00Z",
            "updated_at": "2026-02-14T10:02:00Z",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("12345")

        assert result["status"] == "RUNNING"
        assert result["github_actions_status"] == "in_progress"
        assert result["outputs"] == {}
        assert result["artifacts"] == []
        assert result["job_conclusion"] is None

    @pytest.mark.asyncio
    async def test_get_status_completed_success(self, adapter: GitHubActionsAdapter) -> None:
        """Completed+success maps to COMPLETED (3 clients: main+jobs+artifacts)."""
        main_response = MagicMock()
        main_response.status_code = 200
        main_response.json.return_value = {"status": "completed", "conclusion": "success"}
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {"total_count": 0, "jobs": []}
        jobs_response.raise_for_status = MagicMock()

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {"total_count": 0, "artifacts": []}
        artifacts_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("12345")

        assert result["status"] == "COMPLETED"
        assert result["job_conclusion"] == "success"
        assert "outputs" in result
        assert "artifacts" in result

    @pytest.mark.asyncio
    async def test_get_status_completed_failure(self, adapter: GitHubActionsAdapter) -> None:
        """Completed+failure maps to FAILED (3 clients: main+jobs+artifacts)."""
        main_response = MagicMock()
        main_response.status_code = 200
        main_response.json.return_value = {"status": "completed", "conclusion": "failure"}
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {"total_count": 0, "jobs": []}
        jobs_response.raise_for_status = MagicMock()

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {"total_count": 0, "artifacts": []}
        artifacts_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("12345")

        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_get_status_completed_cancelled(self, adapter: GitHubActionsAdapter) -> None:
        """Completed+cancelled maps to CANCELLED (3 clients: main+jobs+artifacts)."""
        main_response = MagicMock()
        main_response.status_code = 200
        main_response.json.return_value = {"status": "completed", "conclusion": "cancelled"}
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {"total_count": 0, "jobs": []}
        jobs_response.raise_for_status = MagicMock()

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {"total_count": 0, "artifacts": []}
        artifacts_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("12345")

        assert result["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_get_status_404_not_found(self, adapter: GitHubActionsAdapter) -> None:
        """404 returns not_found state."""
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

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("999")

        assert result["status"] == "SUBMITTED"
        assert result["github_actions_status"] == "not_found"
        assert result["outputs"] == {}
        assert result["artifacts"] == []
        assert result["job_conclusion"] is None

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: GitHubActionsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            from core.exceptions import AdapterTimeoutError
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.get_status("12345")
            assert exc_info.value.code == "ADAPTER_TIMEOUT"
            assert exc_info.value.details["adapter_type"] == "github_actions"

    @pytest.mark.asyncio
    async def test_get_status_connection_error(self, adapter: GitHubActionsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_job_logs
# ---------------------------------------------------------------------------

class TestGetJobLogs:
    """Tests for GitHubActionsAdapter.get_job_logs()."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success_completed(self, adapter: GitHubActionsAdapter) -> None:
        """Success: retrieve logs ZIP from completed run."""
        # Status response: completed
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "status": "completed",
            "conclusion": "success",
        }
        status_response.raise_for_status = MagicMock()

        # Logs response: ZIP content
        zip_content = _make_zip_content(
            ("job1/step1.txt", "Step 1: Checkout\nDone"),
            ("job1/step2.txt", "Step 2: Build\nDone"),
        )
        logs_response = MagicMock()
        logs_response.status_code = 200
        logs_response.content = zip_content
        logs_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[status_response, logs_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("12345")

        assert "Step 1: Checkout" in result["content"]
        assert "Step 2: Build" in result["content"]
        assert result["format"] == "text/plain"
        assert result["complete"] is True
        assert result["job_status"] == "completed"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_job_logs_in_progress(self, adapter: GitHubActionsAdapter) -> None:
        """Run in progress returns empty content with complete=False."""
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "status": "in_progress",
            "conclusion": None,
        }
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=status_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("12345")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_get_job_logs_queued(self, adapter: GitHubActionsAdapter) -> None:
        """Queued run returns empty content with complete=False."""
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "status": "queued",
            "conclusion": None,
        }
        status_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=status_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("12345")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_job_logs_404(self, adapter: GitHubActionsAdapter) -> None:
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

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("999")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: GitHubActionsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_LOGS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_job_logs_http_500(self, adapter: GitHubActionsAdapter) -> None:
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

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_LOGS_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: GitHubActionsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_CONNECTION_ERROR"

    @pytest.mark.asyncio
    async def test_get_job_logs_bad_zip(self, adapter: GitHubActionsAdapter) -> None:
        """Bad ZIP content returns empty content."""
        status_response = MagicMock()
        status_response.status_code = 200
        status_response.json.return_value = {
            "status": "completed",
            "conclusion": "success",
        }
        status_response.raise_for_status = MagicMock()

        logs_response = MagicMock()
        logs_response.status_code = 200
        logs_response.content = b"not-a-zip-file"
        logs_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[status_response, logs_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("12345")

        assert result["content"] == ""
        assert result["complete"] is True


# ---------------------------------------------------------------------------
# _extract_logs_from_zip
# ---------------------------------------------------------------------------

class TestExtractLogsFromZip:
    """Tests for ZIP extraction utility."""

    def test_extract_multiple_files(self) -> None:
        """Extract and concatenate multiple files from ZIP."""
        zip_content = _make_zip_content(
            ("job1/1_step.txt", "Hello"),
            ("job1/2_step.txt", "World"),
        )
        result = GitHubActionsAdapter._extract_logs_from_zip(zip_content)
        assert "Hello" in result
        assert "World" in result
        assert "=== job1/1_step.txt ===" in result
        assert "=== job1/2_step.txt ===" in result

    def test_extract_empty_zip(self) -> None:
        """Empty ZIP returns empty string."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        result = GitHubActionsAdapter._extract_logs_from_zip(buf.getvalue())
        assert result == ""

    def test_extract_bad_zip(self) -> None:
        """Bad ZIP returns empty string."""
        result = GitHubActionsAdapter._extract_logs_from_zip(b"not-a-zip")
        assert result == ""

    def test_extract_skips_directories(self) -> None:
        """Directories in ZIP are skipped."""
        zip_content = _make_zip_content(
            ("job1/step.txt", "content"),
        )
        result = GitHubActionsAdapter._extract_logs_from_zip(zip_content)
        assert "content" in result


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Tests for GitHubActionsAdapter.cancel_execution()."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: GitHubActionsAdapter) -> None:
        """Success: POST /cancel returns 202."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("12345")

        # Verify POST was called with correct URL
        call_args = mock_client.post.call_args
        assert "actions/runs/12345/cancel" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_cancel_conflict_409(self, adapter: GitHubActionsAdapter) -> None:
        """409 Conflict (already completed) raises ServiceUnavailableError."""
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
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_CANCEL_CONFLICT"

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: GitHubActionsAdapter) -> None:
        """Timeout raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_cancel_http_error(self, adapter: GitHubActionsAdapter) -> None:
        """HTTP error raises ServiceUnavailableError."""
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
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_HTTP_ERROR"

    @pytest.mark.asyncio
    async def test_cancel_connection_error(self, adapter: GitHubActionsAdapter) -> None:
        """Connection error raises ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.github_actions_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("12345")
            assert exc_info.value.code == "GITHUB_ACTIONS_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------

class TestFactory:
    """Tests for adapter factory integration."""

    def test_factory_github_actions(self) -> None:
        """Factory returns GitHubActionsAdapter for 'github_actions' platform_type."""
        from adapters import get_platform_adapter

        adapter = get_platform_adapter(
            platform_type="github_actions",
            base_url="https://api.github.com",
            auth_headers={"Authorization": "Bearer ghp_test"},
            owner="my-org",
            repo="my-repo",
        )
        assert isinstance(adapter, GitHubActionsAdapter)

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

    def test_factory_azure_devops_still_works(self) -> None:
        """Factory still returns AzureDevOpsAdapter for 'azure_devops' (non-regression)."""
        from adapters import get_platform_adapter
        from adapters.azure_devops_adapter import AzureDevOpsAdapter

        adapter = get_platform_adapter(
            platform_type="azure_devops",
            base_url="https://dev.azure.com/org/proj",
            auth_headers={"Authorization": "Basic abc"},
        )
        assert isinstance(adapter, AzureDevOpsAdapter)

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
# Auth headers verification
# ---------------------------------------------------------------------------

class TestAuthHeaders:
    """Tests for GitHub API headers."""

    def test_adapter_includes_github_headers(self) -> None:
        """Adapter adds Accept and X-GitHub-Api-Version headers."""
        adapter = GitHubActionsAdapter(
            base_url="https://api.github.com",
            auth_headers={"Authorization": "Bearer ghp_test"},
            owner="org",
            repo="repo",
        )
        assert adapter.auth_headers["Accept"] == "application/vnd.github+json"
        assert adapter.auth_headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert adapter.auth_headers["Authorization"] == "Bearer ghp_test"
        assert adapter.verify_ssl is True  # Default SSL verification

    def test_repos_url(self) -> None:
        """_repos_url builds correct URL."""
        adapter = GitHubActionsAdapter(
            base_url="https://api.github.com",
            auth_headers={},
            owner="my-org",
            repo="my-repo",
        )
        assert adapter._repos_url() == "https://api.github.com/repos/my-org/my-repo"

    def test_adapter_requires_owner_and_repo(self) -> None:
        """Adapter raises ValueError if owner or repo is empty."""
        with pytest.raises(ValueError, match="requires non-empty 'owner' and 'repo'"):
            GitHubActionsAdapter(
                base_url="https://api.github.com",
                auth_headers={},
                owner="",
                repo="my-repo",
            )

        with pytest.raises(ValueError, match="requires non-empty 'owner' and 'repo'"):
            GitHubActionsAdapter(
                base_url="https://api.github.com",
                auth_headers={},
                owner="my-org",
                repo="",
            )


# ---------------------------------------------------------------------------
# get_status outputs & artifacts (Story 63.10)
# ---------------------------------------------------------------------------

class TestGetStatusOutputsArtifacts:
    """Tests for get_status() outputs and artifacts retrieval (Story 63.10)."""

    @pytest.mark.asyncio
    async def test_get_status_completed_returns_outputs(self, adapter: GitHubActionsAdapter) -> None:
        """AC1: get_status() completed → outputs = {job_name: conclusion}."""
        main_response = MagicMock()
        main_response.json.return_value = {
            "status": "completed", "conclusion": "success",
            "created_at": "2026-03-08T10:00:00Z", "updated_at": "2026-03-08T10:05:00Z",
        }
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {
            "total_count": 2,
            "jobs": [
                {"name": "build", "conclusion": "success"},
                {"name": "test", "conclusion": "failure"},
            ],
        }
        jobs_response.raise_for_status = MagicMock()

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {"total_count": 0, "artifacts": []}
        artifacts_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("run-123")

        assert result["outputs"] == {"build": "success", "test": "failure"}
        assert result["artifacts"] == []
        assert result["status"] == "COMPLETED"
        assert result["job_conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_get_status_completed_returns_artifacts(self, adapter: GitHubActionsAdapter) -> None:
        """AC2: get_status() completed → artifacts list from artifacts endpoint."""
        main_response = MagicMock()
        main_response.json.return_value = {
            "status": "completed", "conclusion": "success",
            "created_at": "2026-03-08T10:00:00Z", "updated_at": "2026-03-08T10:05:00Z",
        }
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {"total_count": 0, "jobs": []}
        jobs_response.raise_for_status = MagicMock()

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {
            "total_count": 1,
            "artifacts": [
                {
                    "name": "dist-package",
                    "archive_download_url": "https://api.github.com/repos/org/repo/actions/artifacts/5001/zip",
                    "size_in_bytes": 102400,
                    "expired": False,
                }
            ],
        }
        artifacts_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("run-456")

        assert len(result["artifacts"]) == 1
        artifact = result["artifacts"][0]
        assert artifact["name"] == "dist-package"
        assert "archive_download_url" in artifact
        assert artifact["size_in_bytes"] == 102400
        assert artifact["expired"] is False
        assert result["job_conclusion"] == "success"

    @pytest.mark.asyncio
    async def test_get_status_in_progress_no_additional_calls(self, adapter: GitHubActionsAdapter) -> None:
        """AC1+AC2: run in_progress → outputs={}, artifacts=[], UN SEUL appel API."""
        main_response = MagicMock()
        main_response.json.return_value = {
            "status": "in_progress", "conclusion": None,
            "created_at": "2026-03-08T10:00:00Z", "updated_at": "2026-03-08T10:01:00Z",
        }
        main_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=main_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await adapter.get_status("run-789")

        assert result["outputs"] == {}
        assert result["artifacts"] == []
        assert result["status"] == "RUNNING"
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_jobs_failure_is_resilient(self, adapter: GitHubActionsAdapter) -> None:
        """AC1: Échec appel jobs → outputs={}, pas d'exception."""
        main_response = MagicMock()
        main_response.json.return_value = {
            "status": "completed", "conclusion": "success",
            "created_at": "x", "updated_at": "y",
        }
        main_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        artifacts_response = MagicMock()
        artifacts_response.json.return_value = {"total_count": 0, "artifacts": []}
        artifacts_response.raise_for_status = MagicMock()
        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(return_value=artifacts_response)
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("run-999")

        assert result["outputs"] == {}
        assert result["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_status_artifacts_failure_is_resilient(self, adapter: GitHubActionsAdapter) -> None:
        """AC2: Échec appel artifacts → artifacts=[], pas d'exception."""
        main_response = MagicMock()
        main_response.json.return_value = {
            "status": "completed", "conclusion": "success",
            "created_at": "x", "updated_at": "y",
        }
        main_response.raise_for_status = MagicMock()

        jobs_response = MagicMock()
        jobs_response.json.return_value = {"total_count": 0, "jobs": []}
        jobs_response.raise_for_status = MagicMock()

        mock_main = AsyncMock()
        mock_main.get = AsyncMock(return_value=main_response)
        mock_main.__aenter__ = AsyncMock(return_value=mock_main)
        mock_main.__aexit__ = AsyncMock(return_value=False)

        mock_jobs = AsyncMock()
        mock_jobs.get = AsyncMock(return_value=jobs_response)
        mock_jobs.__aenter__ = AsyncMock(return_value=mock_jobs)
        mock_jobs.__aexit__ = AsyncMock(return_value=False)

        mock_artifacts = AsyncMock()
        mock_artifacts.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_artifacts.__aenter__ = AsyncMock(return_value=mock_artifacts)
        mock_artifacts.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "adapters.github_actions_adapter.httpx.AsyncClient",
            side_effect=[mock_main, mock_jobs, mock_artifacts],
        ):
            result = await adapter.get_status("run-888")

        assert result["artifacts"] == []
        assert result["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Story 86.1 — GitHubActionsAdapter timeout tests
# ---------------------------------------------------------------------------

class TestGitHubActionsAdapterTimeout:
    """Story 86.1 — Tests timeout settings."""

    def test_init_uses_settings_timeout(self) -> None:
        """override_settings(GITHUB_ACTIONS_SOCKET_TIMEOUT=10) → adapter uses timeout=10."""
        from django.test import override_settings
        from adapters.github_actions_adapter import GitHubActionsAdapter
        with override_settings(GITHUB_ACTIONS_SOCKET_TIMEOUT=10.0):
            a = GitHubActionsAdapter(
                base_url="https://api.github.com",
                auth_headers={"Authorization": "Bearer token"},
                owner="myorg",
                repo="myrepo",
            )
        assert a.timeout == 10.0
