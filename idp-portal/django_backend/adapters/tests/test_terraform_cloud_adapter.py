"""
Tests for TerraformCloudAdapter — Story 27.5.

Covers:
- trigger(): POST /runs, auto_apply, success and errors (workspace locked, policy blocked)
- get_status(): mapping Terraform Cloud statuses (18+ states) → IDP Portal
- get_job_logs(): success, timeout, 404, log-read-url, run in progress (complete: False)
- cancel_execution(): success, 409 conflict, force-cancel, errors
- map_terraform_cloud_status(): status mapping utility
- Factory integration: get_platform_adapter("terraform_cloud")
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from adapters.terraform_cloud_adapter import (
    TerraformCloudAdapter,
    map_terraform_cloud_status,
    TERRAFORM_CLOUD_STATUS_MAP,
    TERRAFORM_CLOUD_TERMINAL_STATUSES,
)
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def adapter() -> TerraformCloudAdapter:
    return TerraformCloudAdapter(
        base_url="https://app.terraform.io/api/v2",
        auth_headers={"Authorization": "Bearer test-token-123"},
        organization="my-org",
        timeout=5.0,
    )


def _make_run_response(
    run_id: str = "run-abc123",
    status: str = "pending",
    workspace_id: str = "ws-test",
) -> dict:
    """Helper to build a Terraform Cloud JSON API run response."""
    return {
        "data": {
            "id": run_id,
            "type": "runs",
            "attributes": {
                "status": status,
                "created-at": "2026-02-14T10:00:00Z",
                "status-timestamps": {
                    status: "2026-02-14T10:00:00Z",
                },
                "message": "Test run",
            },
            "relationships": {
                "workspace": {
                    "data": {"type": "workspaces", "id": workspace_id}
                },
                "plan": {
                    "data": {"type": "plans", "id": "plan-abc123"}
                },
                "apply": {
                    "data": {"type": "applies", "id": "apply-abc123"}
                },
            },
        }
    }


def _make_resource_response(resource_id: str, log_read_url: str = "https://archivist.terraform.io/logs/abc") -> dict:
    """Helper to build a plan/apply resource response with log-read-url."""
    return {
        "data": {
            "id": resource_id,
            "type": "plans",
            "attributes": {
                "log-read-url": log_read_url,
                "status": "finished",
            },
        }
    }


def _mock_httpx_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# map_terraform_cloud_status
# ---------------------------------------------------------------------------

class TestMapTerraformCloudStatus:
    """Tests for status mapping utility."""

    def test_pending(self) -> None:
        assert map_terraform_cloud_status("pending") == "SUBMITTED"

    def test_plan_queued(self) -> None:
        assert map_terraform_cloud_status("plan_queued") == "SUBMITTED"

    def test_planning(self) -> None:
        assert map_terraform_cloud_status("planning") == "RUNNING"

    def test_planned(self) -> None:
        assert map_terraform_cloud_status("planned") == "SUBMITTED"

    def test_cost_estimating(self) -> None:
        assert map_terraform_cloud_status("cost_estimating") == "RUNNING"

    def test_cost_estimated(self) -> None:
        assert map_terraform_cloud_status("cost_estimated") == "SUBMITTED"

    def test_policy_checking(self) -> None:
        assert map_terraform_cloud_status("policy_checking") == "RUNNING"

    def test_policy_override(self) -> None:
        assert map_terraform_cloud_status("policy_override") == "SUBMITTED"

    def test_policy_checked(self) -> None:
        assert map_terraform_cloud_status("policy_checked") == "SUBMITTED"

    def test_fetching(self) -> None:
        """Test 'fetching' status mapping (early initialization phase)."""
        assert map_terraform_cloud_status("fetching") == "SUBMITTED"

    def test_applying(self) -> None:
        assert map_terraform_cloud_status("applying") == "RUNNING"

    def test_applied(self) -> None:
        assert map_terraform_cloud_status("applied") == "COMPLETED"

    def test_planned_and_finished(self) -> None:
        assert map_terraform_cloud_status("planned_and_finished") == "COMPLETED"

    def test_errored(self) -> None:
        assert map_terraform_cloud_status("errored") == "FAILED"

    def test_canceled(self) -> None:
        assert map_terraform_cloud_status("canceled") == "CANCELLED"

    def test_force_canceled(self) -> None:
        assert map_terraform_cloud_status("force_canceled") == "CANCELLED"

    def test_discarded(self) -> None:
        assert map_terraform_cloud_status("discarded") == "CANCELLED"

    def test_unknown_status_defaults_to_submitted(self) -> None:
        assert map_terraform_cloud_status("unknown_state") == "SUBMITTED"

    def test_all_map_entries_covered(self) -> None:
        """Every entry in the status map should return a valid IDP status."""
        valid_statuses = {"SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        for tc_status, idp_status in TERRAFORM_CLOUD_STATUS_MAP.items():
            assert idp_status in valid_statuses, f"{tc_status} maps to invalid {idp_status}"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    """Tests for TerraformCloudAdapter initialization."""

    def test_init_success(self) -> None:
        adapter = TerraformCloudAdapter(
            base_url="https://app.terraform.io/api/v2",
            auth_headers={"Authorization": "Bearer token"},
            organization="test-org",
        )
        assert adapter.base_url == "https://app.terraform.io/api/v2"
        assert adapter.organization == "test-org"
        assert "Content-Type" in adapter.auth_headers
        assert adapter.auth_headers["Content-Type"] == "application/vnd.api+json"

    def test_init_strips_trailing_slash(self) -> None:
        adapter = TerraformCloudAdapter(
            base_url="https://app.terraform.io/api/v2/",
            auth_headers={"Authorization": "Bearer token"},
            organization="test-org",
        )
        assert adapter.base_url == "https://app.terraform.io/api/v2"

    def test_init_requires_organization(self) -> None:
        with pytest.raises(ValueError, match="organization"):
            TerraformCloudAdapter(
                base_url="https://app.terraform.io/api/v2",
                auth_headers={"Authorization": "Bearer token"},
                organization="",
            )


# ---------------------------------------------------------------------------
# trigger
# ---------------------------------------------------------------------------

class TestTrigger:
    """Tests for TerraformCloudAdapter.trigger()."""

    @pytest.mark.asyncio
    async def test_trigger_success(self, adapter: TerraformCloudAdapter) -> None:
        """Success: POST /runs returns 201 with run object."""
        response = _mock_httpx_response(
            status_code=201,
            json_data=_make_run_response("run-xyz789", "pending"),
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(
                workspace_id="ws-test123",
                auto_apply=True,
                message="Test run",
                correlation_id="corr-123",
            )

        assert result["platform_job_id"] == "run-xyz789"
        assert result["status"] == "SUBMITTED"
        assert "run-xyz789" in result["url"]

        # Verify payload structure
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["data"]["type"] == "runs"
        assert payload["data"]["attributes"]["auto-apply"] is True
        assert payload["data"]["relationships"]["workspace"]["data"]["id"] == "ws-test123"

    @pytest.mark.asyncio
    async def test_trigger_with_target_addrs(self, adapter: TerraformCloudAdapter) -> None:
        """Trigger with target_addrs parameter."""
        response = _mock_httpx_response(
            status_code=201,
            json_data=_make_run_response("run-target1"),
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(
                workspace_id="ws-test",
                target_addrs=["module.vpc", "aws_instance.web"],
            )

        assert result["platform_job_id"] == "run-target1"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["data"]["attributes"]["target-addrs"] == ["module.vpc", "aws_instance.web"]

    @pytest.mark.asyncio
    async def test_trigger_missing_workspace_id(self, adapter: TerraformCloudAdapter) -> None:
        """Missing workspace_id should raise ServiceUnavailableError."""
        with pytest.raises(ServiceUnavailableError, match="workspace_id"):
            await adapter.trigger(workspace_id="")

    @pytest.mark.asyncio
    async def test_trigger_timeout(self, adapter: TerraformCloudAdapter) -> None:
        """Timeout should raise ServiceUnavailableError with TERRAFORM_TIMEOUT code."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
            assert exc_info.value.code == "TERRAFORM_TIMEOUT"

    @pytest.mark.asyncio
    async def test_trigger_workspace_locked(self, adapter: TerraformCloudAdapter) -> None:
        """409 with 'locked' in error detail should use TERRAFORM_WORKSPACE_LOCKED."""
        error_resp = _mock_httpx_response(
            status_code=409,
            json_data={"errors": [{"title": "Conflict", "detail": "Workspace is locked"}]},
            text='{"errors":[{"detail":"Workspace is locked"}]}',
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
            assert exc_info.value.code == "TERRAFORM_WORKSPACE_LOCKED"

    @pytest.mark.asyncio
    async def test_trigger_policy_blocked(self, adapter: TerraformCloudAdapter) -> None:
        """422 with 'policy' in error detail should use TERRAFORM_POLICY_FAILED."""
        error_resp = _mock_httpx_response(
            status_code=422,
            json_data={"errors": [{"detail": "Policy check failed"}]},
            text='{"errors":[{"detail":"Policy check failed"}]}',
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
            assert exc_info.value.code == "TERRAFORM_POLICY_FAILED"

    @pytest.mark.asyncio
    async def test_trigger_auth_failed(self, adapter: TerraformCloudAdapter) -> None:
        """401 should map to TERRAFORM_AUTH_FAILED."""
        error_resp = _mock_httpx_response(status_code=401, text="Unauthorized")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=error_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
            assert exc_info.value.code == "TERRAFORM_AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_trigger_connection_error(self, adapter: TerraformCloudAdapter) -> None:
        """Connection error should raise TERRAFORM_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
            assert exc_info.value.code == "TERRAFORM_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    """Tests for TerraformCloudAdapter.get_status()."""

    @pytest.mark.asyncio
    async def test_get_status_success_running(self, adapter: TerraformCloudAdapter) -> None:
        """Success: run is planning (RUNNING)."""
        response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "planning"),
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-abc", correlation_id="corr-1")

        assert result["status"] == "RUNNING"
        assert result["terraform_cloud_status"] == "planning"

    @pytest.mark.asyncio
    async def test_get_status_applied(self, adapter: TerraformCloudAdapter) -> None:
        """Applied run should map to COMPLETED."""
        response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "applied"),
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-abc")

        assert result["status"] == "COMPLETED"
        assert result["terraform_cloud_status"] == "applied"

    @pytest.mark.asyncio
    async def test_get_status_errored(self, adapter: TerraformCloudAdapter) -> None:
        """Errored run should map to FAILED."""
        response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "errored"),
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-abc")

        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, adapter: TerraformCloudAdapter) -> None:
        """404 should return SUBMITTED with not_found status."""
        response = _mock_httpx_response(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-nonexistent")

        assert result["status"] == "SUBMITTED"
        assert result["terraform_cloud_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_status_timeout(self, adapter: TerraformCloudAdapter) -> None:
        """Timeout should raise ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("run-abc")
            assert exc_info.value.code == "TERRAFORM_TIMEOUT"


# ---------------------------------------------------------------------------
# get_job_logs
# ---------------------------------------------------------------------------

class TestGetJobLogs:
    """Tests for TerraformCloudAdapter.get_job_logs()."""

    @pytest.mark.asyncio
    async def test_get_job_logs_success_applied(self, adapter: TerraformCloudAdapter) -> None:
        """Applied run with plan and apply logs."""
        run_response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "applied"),
        )
        plan_resource = _mock_httpx_response(
            json_data=_make_resource_response("plan-abc123", "https://logs.tf/plan"),
        )
        apply_resource = _mock_httpx_response(
            json_data=_make_resource_response("apply-abc123", "https://logs.tf/apply"),
        )
        plan_logs = _mock_httpx_response(text="Plan: 3 to add, 0 to change")
        plan_logs.text = "Plan: 3 to add, 0 to change"
        apply_logs = _mock_httpx_response(text="Apply complete! Resources: 3 added")
        apply_logs.text = "Apply complete! Resources: 3 added"

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-abc" in url and "/plans/" not in url and "/applies/" not in url:
                return run_response
            if "/plans/plan-abc123" in url:
                return plan_resource
            if "/applies/apply-abc123" in url:
                return apply_resource
            if "logs.tf/plan" in url:
                return plan_logs
            if "logs.tf/apply" in url:
                return apply_logs
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-abc", correlation_id="corr-1")

        assert result["complete"] is True
        assert result["job_status"] == "applied"
        assert "Plan: 3 to add" in result["content"]
        assert "Apply complete!" in result["content"]
        assert result["format"] == "text/plain"

    @pytest.mark.asyncio
    async def test_get_job_logs_planning_in_progress(self, adapter: TerraformCloudAdapter) -> None:
        """Run still planning: only plan logs, complete=False."""
        run_response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "planning"),
        )
        plan_resource = _mock_httpx_response(
            json_data=_make_resource_response("plan-abc123", "https://logs.tf/plan"),
        )
        plan_logs = MagicMock()
        plan_logs.text = "Initializing provider plugins..."
        plan_logs.raise_for_status = MagicMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-abc" in url and "/plans/" not in url and "/applies/" not in url:
                return run_response
            if "/plans/plan-abc123" in url:
                return plan_resource
            if "logs.tf/plan" in url:
                return plan_logs
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-abc")

        assert result["complete"] is False
        assert result["job_status"] == "planning"
        assert "Initializing provider" in result["content"]

    @pytest.mark.asyncio
    async def test_get_job_logs_not_found(self, adapter: TerraformCloudAdapter) -> None:
        """404 should return empty content."""
        response = _mock_httpx_response(status_code=404)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-nonexistent")

        assert result["content"] == ""
        assert result["complete"] is False
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout(self, adapter: TerraformCloudAdapter) -> None:
        """Timeout should raise ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("run-abc")
            assert exc_info.value.code == "TERRAFORM_LOGS_TIMEOUT"

    @pytest.mark.asyncio
    async def test_get_job_logs_pending_no_logs(self, adapter: TerraformCloudAdapter) -> None:
        """Pending run: plan logs resource has no log-read-url yet."""
        run_response = _mock_httpx_response(
            json_data=_make_run_response("run-abc", "pending"),
        )
        plan_resource = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "plan-abc",
                    "type": "plans",
                    "attributes": {"log-read-url": "", "status": "pending"},
                }
            },
        )

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-abc" in url and "/plan" not in url:
                return run_response
            if "/plans/plan-abc" in url:
                return plan_resource
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-abc")

        assert result["complete"] is False
        assert result["content"] == ""


# ---------------------------------------------------------------------------
# cancel_execution
# ---------------------------------------------------------------------------

class TestCancelExecution:
    """Tests for TerraformCloudAdapter.cancel_execution()."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: TerraformCloudAdapter) -> None:
        """Standard cancel succeeds."""
        response = _mock_httpx_response(status_code=202)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("run-abc", correlation_id="corr-1")

        # Verify cancel URL (not force-cancel)
        call_args = mock_client.post.call_args
        assert "/actions/cancel" in call_args[0][0]
        assert "/force-cancel" not in call_args[0][0]

    @pytest.mark.asyncio
    async def test_force_cancel(self, adapter: TerraformCloudAdapter) -> None:
        """Force cancel uses /actions/force-cancel endpoint."""
        response = _mock_httpx_response(status_code=202)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("run-abc", force=True)

        call_args = mock_client.post.call_args
        assert "/actions/force-cancel" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_cancel_conflict_409(self, adapter: TerraformCloudAdapter) -> None:
        """409 should raise TERRAFORM_CANCEL_CONFLICT."""
        response = _mock_httpx_response(status_code=409)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc")
            assert exc_info.value.code == "TERRAFORM_CANCEL_CONFLICT"

    @pytest.mark.asyncio
    async def test_cancel_not_found_404(self, adapter: TerraformCloudAdapter) -> None:
        """404 should raise TERRAFORM_RUN_NOT_FOUND."""
        response = _mock_httpx_response(status_code=404)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc")
            assert exc_info.value.code == "TERRAFORM_RUN_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_cancel_timeout(self, adapter: TerraformCloudAdapter) -> None:
        """Timeout should raise ServiceUnavailableError."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc")
            assert exc_info.value.code == "TERRAFORM_TIMEOUT"


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------

class TestFactory:
    """Tests for get_platform_adapter("terraform_cloud")."""

    def test_factory_creates_adapter(self) -> None:
        from adapters import get_platform_adapter
        adapter = get_platform_adapter(
            platform_type="terraform_cloud",
            base_url="https://app.terraform.io/api/v2",
            auth_headers={"Authorization": "Bearer token"},
            organization="test-org",
        )
        assert isinstance(adapter, TerraformCloudAdapter)
        assert adapter.organization == "test-org"

    def test_factory_requires_organization(self) -> None:
        from adapters import get_platform_adapter
        with pytest.raises(ValueError, match="organization"):
            get_platform_adapter(
                platform_type="terraform_cloud",
                base_url="https://app.terraform.io/api/v2",
                auth_headers={"Authorization": "Bearer token"},
                organization="",
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    """Tests for adapter helper methods."""

    def test_build_run_url(self, adapter: TerraformCloudAdapter) -> None:
        url = adapter._build_run_url("run-abc123")
        assert "my-org" in url
        assert "run-abc123" in url

    def test_build_run_url_empty(self, adapter: TerraformCloudAdapter) -> None:
        assert adapter._build_run_url("") == ""

    def test_extract_error_detail_json(self) -> None:
        resp = MagicMock()
        resp.json.return_value = {
            "errors": [{"detail": "Workspace is locked"}, {"title": "Conflict"}]
        }
        resp.text = "raw"
        detail = TerraformCloudAdapter._extract_error_detail(resp)
        assert "Workspace is locked" in detail
        assert "Conflict" in detail

    def test_extract_error_detail_text_fallback(self) -> None:
        resp = MagicMock()
        resp.json.side_effect = ValueError("Not JSON")
        resp.text = "Some error text"
        detail = TerraformCloudAdapter._extract_error_detail(resp)
        assert "Some error text" in detail

    def test_map_http_error_code_401(self) -> None:
        assert TerraformCloudAdapter._map_http_error_code(401, "") == "TERRAFORM_AUTH_FAILED"

    def test_map_http_error_code_409_locked(self) -> None:
        assert TerraformCloudAdapter._map_http_error_code(409, "workspace is locked") == "TERRAFORM_WORKSPACE_LOCKED"

    def test_map_http_error_code_422_policy(self) -> None:
        assert TerraformCloudAdapter._map_http_error_code(422, "policy check failed") == "TERRAFORM_POLICY_FAILED"

    def test_map_http_error_code_500(self) -> None:
        assert TerraformCloudAdapter._map_http_error_code(500, "") == "TERRAFORM_HTTP_ERROR"

    def test_terminal_statuses_are_subset_of_map(self) -> None:
        """All terminal statuses should be in the status map."""
        for status in TERRAFORM_CLOUD_TERMINAL_STATUSES:
            assert status in TERRAFORM_CLOUD_STATUS_MAP
