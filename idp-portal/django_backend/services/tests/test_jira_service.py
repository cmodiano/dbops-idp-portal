"""
Tests for JiraService — Jira REST API integration.

Story 27.10, AC4: 10+ tests covering create_issue, update_issue, get_issue,
add_comment, error handling, retry logic, and correlation_id propagation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.exceptions import ServiceUnavailableError
from services.jira_service import JiraService, MAX_RETRIES, _TRANSIENT_STATUS_CODES


@pytest.fixture
def service() -> JiraService:
    """Create a JiraService with test configuration."""
    return JiraService(
        base_url="https://jira.example.com",
        auth_headers={"Authorization": "Basic dGVzdDp0ZXN0"},
        timeout=10.0,
    )


def _mock_client(response: httpx.Response) -> AsyncMock:
    """Create a mock httpx.AsyncClient returning the given response."""
    mock = AsyncMock()
    mock.get.return_value = response
    mock.post.return_value = response
    mock.put.return_value = response
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def _mock_response(status_code: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestJiraServiceInit:
    """Test JiraService initialization."""

    def test_strips_trailing_slash(self) -> None:
        svc = JiraService(
            base_url="https://jira.example.com/",
            auth_headers={"Authorization": "Basic x"},
        )
        assert svc.base_url == "https://jira.example.com"

    def test_default_timeout(self) -> None:
        svc = JiraService(
            base_url="https://jira.example.com",
            auth_headers={"Authorization": "Basic x"},
        )
        assert svc.timeout == 30.0


# ---------------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------------


class TestCreateIssue:
    """Test JiraService.create_issue()."""

    @pytest.mark.asyncio
    async def test_create_issue_success(self, service: JiraService) -> None:
        """AC4 test 1: create_issue with 201 Created."""
        resp = _mock_response(201, {
            "key": "PROJ-123",
            "id": "10001",
            "self": "https://jira.example.com/rest/api/3/issue/10001",
        })
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            result = await service.create_issue(
                project_key="PROJ",
                issue_type="Task",
                summary="Test issue",
                correlation_id="test-corr-123",
            )

        assert result["issue_key"] == "PROJ-123"
        assert result["issue_id"] == "10001"
        assert "jira.example.com" in result["url"]
        mock.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_issue_with_optional_fields(self, service: JiraService) -> None:
        """AC4 test 2: create_issue with assignee, labels, description."""
        resp = _mock_response(201, {
            "key": "PROJ-456",
            "id": "10002",
            "self": "https://jira.example.com/rest/api/3/issue/10002",
        })
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            result = await service.create_issue(
                project_key="PROJ",
                issue_type="Bug",
                summary="Bug with optional fields",
                description="Detailed description",
                assignee="john.doe",
                labels=["production", "urgent"],
                correlation_id="test-corr-456",
            )

        assert result["issue_key"] == "PROJ-456"
        # Verify payload includes optional fields
        call_args = mock.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        fields = payload["fields"]
        assert fields["assignee"] == {"name": "john.doe"}
        assert fields["labels"] == ["production", "urgent"]
        assert "description" in fields


# ---------------------------------------------------------------------------
# update_issue
# ---------------------------------------------------------------------------


class TestUpdateIssue:
    """Test JiraService.update_issue()."""

    @pytest.mark.asyncio
    async def test_update_issue_success(self, service: JiraService) -> None:
        """AC4 test 3: update_issue with 204 No Content."""
        resp = _mock_response(204)
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            result = await service.update_issue(
                "PROJ-123",
                status="Done",
                correlation_id="test-corr-789",
            )

        assert result["issue_key"] == "PROJ-123"
        assert result["status"] == "updated"
        mock.put.assert_called_once()


# ---------------------------------------------------------------------------
# get_issue
# ---------------------------------------------------------------------------


class TestGetIssue:
    """Test JiraService.get_issue()."""

    @pytest.mark.asyncio
    async def test_get_issue_success(self, service: JiraService) -> None:
        """AC4 test 4: get_issue with 200 OK."""
        issue_data = {
            "key": "PROJ-123",
            "id": "10001",
            "self": "https://jira.example.com/rest/api/3/issue/10001",
            "fields": {
                "summary": "Test issue",
                "status": {"name": "Open"},
            },
        }
        resp = _mock_response(200, issue_data)
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            result = await service.get_issue("PROJ-123", correlation_id="test-corr")

        assert result["key"] == "PROJ-123"
        assert result["fields"]["summary"] == "Test issue"
        mock.get.assert_called_once()


# ---------------------------------------------------------------------------
# add_comment
# ---------------------------------------------------------------------------


class TestAddComment:
    """Test JiraService.add_comment()."""

    @pytest.mark.asyncio
    async def test_add_comment_success(self, service: JiraService) -> None:
        """AC4 test 5: add_comment with 201 Created."""
        resp = _mock_response(201, {
            "id": "10042",
            "self": "https://jira.example.com/rest/api/3/issue/PROJ-123/comment/10042",
        })
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            result = await service.add_comment(
                "PROJ-123",
                "Patch applied successfully",
                correlation_id="test-corr",
            )

        assert result["comment_id"] == "10042"
        assert result["issue_key"] == "PROJ-123"
        mock.post.assert_called_once()


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Test retry logic on transient errors."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, service: JiraService) -> None:
        """AC4 test 6: retry on TimeoutException, then success."""
        success_resp = _mock_response(200, {"key": "PROJ-1", "id": "1", "fields": {}})

        mock = AsyncMock()
        mock.get.side_effect = [
            httpx.TimeoutException("timeout"),
            success_resp,
        ]
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("services.jira_service.httpx.AsyncClient", return_value=mock),
            patch("services.jira_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await service.get_issue("PROJ-1", correlation_id="retry-test")

        assert result["key"] == "PROJ-1"
        assert mock.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_503(self, service: JiraService) -> None:
        """AC4 test 7: retry on 503, then 200."""
        error_resp = _mock_response(503)
        success_resp = _mock_response(200, {"key": "PROJ-1", "id": "1", "fields": {}})

        mock = AsyncMock()
        mock.get.side_effect = [error_resp, success_resp]
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("services.jira_service.httpx.AsyncClient", return_value=mock),
            patch("services.jira_service.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await service.get_issue("PROJ-1", correlation_id="retry-503")

        assert result["key"] == "PROJ-1"
        assert mock.get.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_timeout(self, service: JiraService) -> None:
        """Timeout after MAX_RETRIES raises ServiceUnavailableError."""
        mock = AsyncMock()
        mock.get.side_effect = httpx.TimeoutException("timeout")
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("services.jira_service.httpx.AsyncClient", return_value=mock),
            patch("services.jira_service.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ServiceUnavailableError, match="did not respond"),
        ):
            await service.get_issue("PROJ-1")

        assert mock.get.call_count == MAX_RETRIES


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test error handling for various HTTP error codes."""

    @pytest.mark.asyncio
    async def test_error_401_unauthorized(self, service: JiraService) -> None:
        """AC4 test 8: 401 raises JIRA_AUTH_FAILED."""
        resp = _mock_response(401, text="Unauthorized")
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.get_issue("PROJ-1")
            assert exc_info.value.code == "JIRA_AUTH_FAILED"

    @pytest.mark.asyncio
    async def test_error_404_not_found(self, service: JiraService) -> None:
        """AC4 test 9: 404 raises JIRA_RESOURCE_NOT_FOUND."""
        resp = _mock_response(404, text="Issue does not exist")
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.get_issue("NONEXISTENT-1")
            assert exc_info.value.code == "JIRA_RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_403_forbidden(self, service: JiraService) -> None:
        """403 raises JIRA_PERMISSION_DENIED."""
        resp = _mock_response(403, text="Forbidden")
        mock = _mock_client(resp)

        with patch("services.jira_service.httpx.AsyncClient", return_value=mock):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.create_issue("PROJ", "Task", "Test")
            assert exc_info.value.code == "JIRA_PERMISSION_DENIED"


# ---------------------------------------------------------------------------
# Correlation ID propagation
# ---------------------------------------------------------------------------


class TestCorrelationId:
    """Test correlation_id propagation in structured logs."""

    @pytest.mark.asyncio
    async def test_correlation_id_in_logs(self, service: JiraService) -> None:
        """AC4 test 10: correlation_id propagated to structlog."""
        resp = _mock_response(200, {"key": "PROJ-1", "id": "1", "fields": {}})
        mock = _mock_client(resp)

        with (
            patch("services.jira_service.httpx.AsyncClient", return_value=mock),
            patch("services.jira_service.logger") as mock_logger,
        ):
            await service.get_issue("PROJ-1", correlation_id="corr-abc-123")

        # Verify logger was called with correlation_id
        calls = mock_logger.info.call_args_list
        assert len(calls) >= 2  # request + retrieved
        for call in calls:
            assert call.kwargs.get("correlation_id") == "corr-abc-123"
