"""
Coverage tests for TerraformCloudAdapter — targeting missing lines to reach >=90%.

This file is self-sufficient: it covers both the previously untested lines
AND enough happy-path code so this file alone achieves >=90% on terraform_cloud_adapter.py.

Missing lines targeted:
- Line 139: variables in trigger() payload
- Lines 286-308: Non-404 HTTPStatusError and HTTPError in get_status()
- Line 405->407: Branch — apply logs with no plan logs (no separator)
- Lines 437-459: Non-404 HTTPStatusError and HTTPError in get_job_logs()
- Line 505: no resource_id branch in _fetch_resource_logs()
- Lines 539-554: HTTPStatusError (404 and non-404) + HTTPError in _fetch_resource_logs()
- Lines 632-654: Generic HTTPError in cancel_execution()
- Lines 698, 702, 706: _map_http_error_code() — 404, 409-non-locked, 422-non-policy
- Lines 721-737: health_check() — success and error paths
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
from integrations.health_check import HealthCheckStatus


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
    return {
        "data": {
            "id": run_id,
            "type": "runs",
            "attributes": {
                "status": status,
                "created-at": "2026-02-14T10:00:00Z",
                "status-timestamps": {status: "2026-02-14T10:00:00Z"},
                "message": "Test run",
            },
            "relationships": {
                "workspace": {"data": {"type": "workspaces", "id": workspace_id}},
                "plan": {"data": {"type": "plans", "id": "plan-abc123"}},
                "apply": {"data": {"type": "applies", "id": "apply-abc123"}},
            },
        }
    }


def _mock_httpx_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> MagicMock:
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
# trigger() — variables payload (line 139)
# ---------------------------------------------------------------------------

class TestTriggerCoverage:
    """Additional trigger() coverage tests."""

    @pytest.mark.asyncio
    async def test_trigger_with_variables(self, adapter: TerraformCloudAdapter) -> None:
        """Line 139: variables are added to payload attributes."""
        response = _mock_httpx_response(
            status_code=201,
            json_data=_make_run_response("run-vars1", "pending"),
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        variables = [{"key": "ENV", "value": "prod", "category": "terraform"}]

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(
                workspace_id="ws-test",
                variables=variables,
            )

        assert result["platform_job_id"] == "run-vars1"
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["data"]["attributes"]["variables"] == variables


# ---------------------------------------------------------------------------
# get_status() — Non-404 HTTPStatusError and HTTPError (lines 286-308)
# ---------------------------------------------------------------------------

class TestGetStatusCoverage:
    """Additional get_status() coverage tests for missing error paths."""

    @pytest.mark.asyncio
    async def test_get_status_http_status_error_non_404(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 286-300: Non-404 HTTPStatusError raises ServiceUnavailableError."""
        mock_response = _mock_httpx_response(status_code=500)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("run-abc", correlation_id="corr-1")

        assert exc_info.value.code == "TERRAFORM_HTTP_ERROR"
        assert exc_info.value.details["status_code"] == 500

    @pytest.mark.asyncio
    async def test_get_status_http_status_error_403(self, adapter: TerraformCloudAdapter) -> None:
        """Non-404 HTTPStatusError (403 forbidden) raises TERRAFORM_HTTP_ERROR."""
        mock_response = _mock_httpx_response(status_code=403)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("run-abc")

        assert exc_info.value.code == "TERRAFORM_HTTP_ERROR"
        assert "platform_job_id" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_get_status_connection_error(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 301-308: HTTPError (connection) raises TERRAFORM_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_status("run-abc", correlation_id="corr-1")

        assert exc_info.value.code == "TERRAFORM_CONNECTION_ERROR"
        assert "Cannot connect to Terraform Cloud" in exc_info.value.message


# ---------------------------------------------------------------------------
# get_job_logs() — separator branch (405->407), Non-404 errors (437-459)
# ---------------------------------------------------------------------------

class TestGetJobLogsCoverage:
    """Additional get_job_logs() coverage tests."""

    @pytest.mark.asyncio
    async def test_get_job_logs_plan_and_apply_logs_separator(self, adapter: TerraformCloudAdapter) -> None:
        """Line 405->407: separator '\n\n' is added when both plan and apply logs exist.

        This exercises the 'if parts:' branch inside the apply logs combination section.
        _make_run_response uses plan-abc123 and apply-abc123 as resource IDs.
        """
        # Use the standard _make_run_response which has plan-abc123 and apply-abc123
        run_response = _mock_httpx_response(
            json_data=_make_run_response("run-sep1", "applied"),
        )
        plan_resource = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "plan-abc123",
                    "type": "plans",
                    "attributes": {"log-read-url": "https://logs.tf/plan-sep1", "status": "finished"},
                }
            },
        )
        apply_resource = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "apply-abc123",
                    "type": "applies",
                    "attributes": {"log-read-url": "https://logs.tf/apply-sep1", "status": "finished"},
                }
            },
        )
        plan_log_resp = MagicMock()
        plan_log_resp.text = "Plan output here"
        plan_log_resp.raise_for_status = MagicMock()

        apply_log_resp = MagicMock()
        apply_log_resp.text = "Apply output here"
        apply_log_resp.raise_for_status = MagicMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-sep1" in url and "/plans/" not in url and "/applies/" not in url:
                return run_response
            if "/plans/plan-abc123" in url:
                return plan_resource
            if "/applies/apply-abc123" in url:
                return apply_resource
            if "logs.tf/plan-sep1" in url:
                return plan_log_resp
            if "logs.tf/apply-sep1" in url:
                return apply_log_resp
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-sep1")

        # Both plan and apply logs present — separator '\n\n' should be between them
        assert "Plan output here" in result["content"]
        assert "Apply output here" in result["content"]
        assert "\n\n" in result["content"]
        assert result["complete"] is True

    @pytest.mark.asyncio
    async def test_get_job_logs_apply_only_no_separator(self, adapter: TerraformCloudAdapter) -> None:
        """Branch 405->407: apply logs exist but plan logs are empty — no separator added.

        When plan logs are empty (parts is []) but apply logs exist,
        the 'if parts:' check is False so separator is NOT added.
        """
        run_response = _mock_httpx_response(
            json_data=_make_run_response("run-applyonly", "applied"),
        )
        # Plan resource returns empty log-read-url (so plan_logs == "")
        plan_resource_no_url = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "plan-abc123",
                    "type": "plans",
                    "attributes": {"log-read-url": "", "status": "finished"},
                }
            },
        )
        # Apply resource has real log URL
        apply_resource = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "apply-abc123",
                    "type": "applies",
                    "attributes": {"log-read-url": "https://logs.tf/apply-only", "status": "finished"},
                }
            },
        )
        apply_log_resp = MagicMock()
        apply_log_resp.text = "Apply only output"
        apply_log_resp.raise_for_status = MagicMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-applyonly" in url and "/plans/" not in url and "/applies/" not in url:
                return run_response
            if "/plans/plan-abc123" in url:
                return plan_resource_no_url
            if "/applies/apply-abc123" in url:
                return apply_resource
            if "logs.tf/apply-only" in url:
                return apply_log_resp
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-applyonly")

        # Only apply logs — no plan section, no separator
        assert "Apply only output" in result["content"]
        assert "=== Plan Logs ===" not in result["content"]
        assert result["complete"] is True

    @pytest.mark.asyncio
    async def test_get_job_logs_http_status_error_non_404(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 437-451: Non-404 HTTPStatusError raises TERRAFORM_LOGS_UNAVAILABLE."""
        mock_response = _mock_httpx_response(status_code=503)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("run-abc", correlation_id="corr-1")

        assert exc_info.value.code == "TERRAFORM_LOGS_UNAVAILABLE"
        assert exc_info.value.details["status_code"] == 503

    @pytest.mark.asyncio
    async def test_get_job_logs_connection_error(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 452-463: HTTPError raises TERRAFORM_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("run-abc")

        assert exc_info.value.code == "TERRAFORM_CONNECTION_ERROR"
        assert "Cannot connect to Terraform Cloud for log retrieval" in exc_info.value.message


# ---------------------------------------------------------------------------
# _fetch_resource_logs() — no resource_id (line 505), exception handlers (539-554)
# ---------------------------------------------------------------------------

class TestFetchResourceLogs:
    """Tests for TerraformCloudAdapter._fetch_resource_logs()."""

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_no_resource_id(self, adapter: TerraformCloudAdapter) -> None:
        """Line 505: returns empty string when resource_id is missing."""
        mock_client = AsyncMock()
        # relationships dict with no 'plan' entry
        relationships = {}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "plan", "corr-1"
        )
        assert result == ""
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_resource_id_empty_string(self, adapter: TerraformCloudAdapter) -> None:
        """Line 505: returns empty string when resource 'id' is empty string."""
        mock_client = AsyncMock()
        relationships = {"plan": {"data": {"id": ""}}}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "plan", "corr-1"
        )
        assert result == ""
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_404_returns_empty(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 539-546: 404 HTTPStatusError returns empty string (not available yet)."""
        mock_response = _mock_httpx_response(status_code=404)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        relationships = {"plan": {"data": {"id": "plan-test1"}}}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "plan", "corr-1"
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_non_404_http_status_error_reraises(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 539-547: Non-404 HTTPStatusError is re-raised."""
        mock_response = _mock_httpx_response(status_code=500)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        relationships = {"plan": {"data": {"id": "plan-test2"}}}

        with pytest.raises(httpx.HTTPStatusError):
            await adapter._fetch_resource_logs(
                mock_client, relationships, "plan", "corr-1"
            )

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_http_error_returns_empty(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 548-554: Generic HTTPError returns empty string with warning log."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        relationships = {"plan": {"data": {"id": "plan-test3"}}}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "plan", "corr-1"
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_resource_logs_no_log_read_url_returns_empty(self, adapter: TerraformCloudAdapter) -> None:
        """Returns empty string when resource has no log-read-url."""
        resource_resp = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "plan-no-url",
                    "attributes": {"log-read-url": "", "status": "pending"},
                }
            }
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=resource_resp)

        relationships = {"plan": {"data": {"id": "plan-no-url"}}}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "plan", "corr-1"
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_apply_uses_applies_plural(self, adapter: TerraformCloudAdapter) -> None:
        """Verify 'apply' resource type uses '/applies/' (not '/applys/')."""
        resource_resp = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "apply-test1",
                    "attributes": {"log-read-url": "https://logs.tf/apply1", "status": "finished"},
                }
            }
        )
        log_resp = MagicMock()
        log_resp.text = "Apply log content"
        log_resp.raise_for_status = MagicMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/applies/apply-test1" in url:
                return resource_resp
            if "logs.tf/apply1" in url:
                return log_resp
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)

        relationships = {"apply": {"data": {"id": "apply-test1"}}}

        result = await adapter._fetch_resource_logs(
            mock_client, relationships, "apply", "corr-1"
        )
        assert result == "Apply log content"


# ---------------------------------------------------------------------------
# cancel_execution() — generic HTTPError (lines 632-654)
# ---------------------------------------------------------------------------

class TestCancelExecutionCoverage:
    """Additional cancel_execution() tests for missing HTTPError path."""

    @pytest.mark.asyncio
    async def test_cancel_connection_error_raises(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 647-658: Generic HTTPError raises TERRAFORM_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc", correlation_id="corr-1")

        assert exc_info.value.code == "TERRAFORM_CONNECTION_ERROR"
        assert "Cannot connect to Terraform Cloud for cancellation" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_cancel_generic_http_status_error(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 632-646: Non-409/non-404 HTTPStatusError raises TERRAFORM_HTTP_ERROR."""
        mock_response = _mock_httpx_response(status_code=500)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc", correlation_id="corr-1")

        assert exc_info.value.code == "TERRAFORM_HTTP_ERROR"
        assert exc_info.value.details["status_code"] == 500


# ---------------------------------------------------------------------------
# _map_http_error_code() — 404, 409-non-locked, 422-non-policy (lines 698, 702, 706)
# ---------------------------------------------------------------------------

class TestMapHttpErrorCodeCoverage:
    """Tests for _map_http_error_code() branches not covered by existing tests."""

    def test_map_http_error_code_404(self) -> None:
        """Line 698: 404 maps to TERRAFORM_RUN_NOT_FOUND."""
        result = TerraformCloudAdapter._map_http_error_code(404, "not found")
        assert result == "TERRAFORM_RUN_NOT_FOUND"

    def test_map_http_error_code_409_not_locked(self) -> None:
        """Line 702: 409 without 'locked' maps to TERRAFORM_CANCEL_CONFLICT."""
        result = TerraformCloudAdapter._map_http_error_code(409, "run already completed")
        assert result == "TERRAFORM_CANCEL_CONFLICT"

    def test_map_http_error_code_422_not_policy(self) -> None:
        """Line 706: 422 without 'policy' maps to TERRAFORM_VALIDATION_ERROR."""
        result = TerraformCloudAdapter._map_http_error_code(422, "invalid attribute value")
        assert result == "TERRAFORM_VALIDATION_ERROR"

    def test_map_http_error_code_500_fallback(self) -> None:
        """Any other status code returns TERRAFORM_HTTP_ERROR."""
        result = TerraformCloudAdapter._map_http_error_code(503, "service unavailable")
        assert result == "TERRAFORM_HTTP_ERROR"


# ---------------------------------------------------------------------------
# health_check() — success and error paths (lines 721-737)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for TerraformCloudAdapter.health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 721-734: health_check() returns OK when account/details responds 200."""
        response = MagicMock()
        response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None
        assert result.checked_at is not None

        # Verify the authenticated endpoint was called (not /ping)
        call_url = str(mock_client.get.call_args)
        assert "/account/details" in call_url

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, adapter: TerraformCloudAdapter) -> None:
        """Lines 735-741: health_check() returns ERROR on connection failure."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None
        assert "Connection refused" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, adapter: TerraformCloudAdapter) -> None:
        """health_check() returns ERROR on timeout."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_auth_failure(self, adapter: TerraformCloudAdapter) -> None:
        """health_check() returns ERROR on HTTP 401 (invalid token)."""
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

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

# ---------------------------------------------------------------------------
# Happy-path tests to make this file self-sufficient at >=90% coverage
# ---------------------------------------------------------------------------

class TestInitCoverage:
    """Init tests for standalone coverage."""

    def test_init_success(self) -> None:
        adapter = TerraformCloudAdapter(
            base_url="https://app.terraform.io/api/v2",
            auth_headers={"Authorization": "Bearer token"},
            organization="test-org",
        )
        assert adapter.base_url == "https://app.terraform.io/api/v2"
        assert adapter.organization == "test-org"
        assert adapter.auth_headers["Content-Type"] == "application/vnd.api+json"

    def test_init_strips_trailing_slash(self) -> None:
        adapter = TerraformCloudAdapter(
            base_url="https://app.terraform.io/api/v2/",
            auth_headers={},
            organization="test-org",
        )
        assert adapter.base_url == "https://app.terraform.io/api/v2"

    def test_init_requires_organization(self) -> None:
        with pytest.raises(ValueError, match="organization"):
            TerraformCloudAdapter(
                base_url="https://app.terraform.io/api/v2",
                auth_headers={},
                organization="",
            )


class TestTriggerHappyPath:
    """Happy-path trigger() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_trigger_success(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(
            status_code=201,
            json_data=_make_run_response("run-xyz789", "pending"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(workspace_id="ws-test", message="Test run")

        assert result["platform_job_id"] == "run-xyz789"
        assert result["status"] == "SUBMITTED"
        assert "run-xyz789" in result["url"]

    @pytest.mark.asyncio
    async def test_trigger_with_target_addrs(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(
            status_code=201,
            json_data=_make_run_response("run-target1"),
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.trigger(workspace_id="ws-test", target_addrs=["module.vpc"])

        assert result["platform_job_id"] == "run-target1"

    @pytest.mark.asyncio
    async def test_trigger_missing_workspace_raises(self, adapter: TerraformCloudAdapter) -> None:
        with pytest.raises(ServiceUnavailableError, match="workspace_id"):
            await adapter.trigger(workspace_id="")

    @pytest.mark.asyncio
    async def test_trigger_timeout(self, adapter: TerraformCloudAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        from core.exceptions import AdapterTimeoutError
        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
        assert exc_info.value.code == "ADAPTER_TIMEOUT"

    @pytest.mark.asyncio
    async def test_trigger_workspace_locked(self, adapter: TerraformCloudAdapter) -> None:
        error_resp = _mock_httpx_response(
            status_code=409,
            json_data={"errors": [{"detail": "Workspace is locked"}]},
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
    async def test_trigger_auth_failed(self, adapter: TerraformCloudAdapter) -> None:
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
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.trigger(workspace_id="ws-test")
        assert exc_info.value.code == "TERRAFORM_CONNECTION_ERROR"


class TestGetStatusHappyPath:
    """Happy-path get_status() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_get_status_planning(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(json_data=_make_run_response("run-abc", "planning"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-abc")

        assert result["status"] == "RUNNING"
        assert result["terraform_cloud_status"] == "planning"

    @pytest.mark.asyncio
    async def test_get_status_applied(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(json_data=_make_run_response("run-abc", "applied"))
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_status("run-abc")

        assert result["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, adapter: TerraformCloudAdapter) -> None:
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
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        from core.exceptions import AdapterTimeoutError
        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AdapterTimeoutError) as exc_info:
                await adapter.get_status("run-abc")
        assert exc_info.value.code == "ADAPTER_TIMEOUT"


class TestGetJobLogsHappyPath:
    """Happy-path get_job_logs() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_get_job_logs_planning_with_plan_logs(self, adapter: TerraformCloudAdapter) -> None:
        run_response = _mock_httpx_response(json_data=_make_run_response("run-plan1", "planning"))
        plan_resource = _mock_httpx_response(
            json_data={
                "data": {
                    "id": "plan-abc123",
                    "type": "plans",
                    "attributes": {"log-read-url": "https://logs.tf/plan1", "status": "running"},
                }
            },
        )
        plan_log_resp = MagicMock()
        plan_log_resp.text = "Initializing provider plugins..."
        plan_log_resp.raise_for_status = MagicMock()

        async def mock_get(url: str, **kwargs: object) -> MagicMock:
            if "/runs/run-plan1" in url and "/plans/" not in url and "/applies/" not in url:
                return run_response
            if "/plans/plan-abc123" in url:
                return plan_resource
            if "logs.tf/plan1" in url:
                return plan_log_resp
            return _mock_httpx_response()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-plan1")

        assert result["complete"] is False
        assert "Initializing provider" in result["content"]

    @pytest.mark.asyncio
    async def test_get_job_logs_not_found_standalone(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(status_code=404)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            result = await adapter.get_job_logs("run-nonexistent")

        assert result["content"] == ""
        assert result["job_status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_job_logs_timeout_standalone(self, adapter: TerraformCloudAdapter) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.get_job_logs("run-abc")
        assert exc_info.value.code == "TERRAFORM_LOGS_TIMEOUT"


class TestCancelExecutionHappyPath:
    """Happy-path cancel_execution() tests for standalone coverage."""

    @pytest.mark.asyncio
    async def test_cancel_success(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(status_code=202)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("run-abc")

        assert "/actions/cancel" in str(mock_client.post.call_args)

    @pytest.mark.asyncio
    async def test_force_cancel(self, adapter: TerraformCloudAdapter) -> None:
        response = _mock_httpx_response(status_code=202)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            await adapter.cancel_execution("run-abc", force=True)

        assert "/actions/force-cancel" in str(mock_client.post.call_args)

    @pytest.mark.asyncio
    async def test_cancel_conflict_409(self, adapter: TerraformCloudAdapter) -> None:
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
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("adapters.terraform_cloud_adapter.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await adapter.cancel_execution("run-abc")
        assert exc_info.value.code == "TERRAFORM_TIMEOUT"


class TestHelpersHappyPath:
    """Helper method tests for standalone coverage."""

    def test_build_run_url(self, adapter: TerraformCloudAdapter) -> None:
        url = adapter._build_run_url("run-abc123")
        assert "my-org" in url
        assert "run-abc123" in url

    def test_build_run_url_empty(self, adapter: TerraformCloudAdapter) -> None:
        assert adapter._build_run_url("") == ""

    def test_extract_error_detail_json(self) -> None:
        resp = MagicMock()
        resp.json.return_value = {"errors": [{"detail": "Workspace is locked"}, {"title": "Conflict"}]}
        resp.text = "raw"
        detail = TerraformCloudAdapter._extract_error_detail(resp)
        assert "Workspace is locked" in detail

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


class TestStatusMappingHappyPath:
    """Status mapping tests for standalone coverage."""

    def test_pending(self) -> None:
        assert map_terraform_cloud_status("pending") == "SUBMITTED"

    def test_planning(self) -> None:
        assert map_terraform_cloud_status("planning") == "RUNNING"

    def test_applied(self) -> None:
        assert map_terraform_cloud_status("applied") == "COMPLETED"

    def test_errored(self) -> None:
        assert map_terraform_cloud_status("errored") == "FAILED"

    def test_canceled(self) -> None:
        assert map_terraform_cloud_status("canceled") == "CANCELLED"

    def test_unknown_defaults_submitted(self) -> None:
        assert map_terraform_cloud_status("unknown_xyz") == "SUBMITTED"

    def test_all_terminal_statuses_in_map(self) -> None:
        for status in TERRAFORM_CLOUD_TERMINAL_STATUSES:
            assert status in TERRAFORM_CLOUD_STATUS_MAP
