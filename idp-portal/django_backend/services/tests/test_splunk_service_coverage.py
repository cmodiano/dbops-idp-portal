"""
Coverage tests for SplunkService — targeting missing lines to reach ≥90%.

Missing lines targeted:
- 279: SPLUNK_MAX_RETRIES safety net raise
- 350-353: poll loop timeout (asyncio.sleep + while/else)
- 387, 391-392: search_platform_logs with platform_job_id
- 405-406: search_platform_logs JSON parse and fallback
- 417-435: search_platform_logs_mapping
- 443-460: health_check
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.splunk_service import SplunkService, SPLUNK_MAX_RETRIES
from core.exceptions import ServiceUnavailableError


@pytest.fixture
def service() -> SplunkService:
    return SplunkService(
        base_url="https://splunk.example.com:8088",
        auth_headers={"Authorization": "Splunk test-token"},
        timeout=10.0,
    )


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> MagicMock:
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


# ---------------------------------------------------------------------------
# Lines 92-99: send_event success path (logger.info + return result)
# Lines 123-153: send_batch non-empty events
# Lines 167, 175: _build_hec_payload with fields
# Lines 203-214: transient error retry (_post_raw_with_retry)
# Lines 217-234: TimeoutException handling
# Lines 241-248: HTTPStatusError handling
# ---------------------------------------------------------------------------

class TestCorePathsCoverage:
    """Cover main send_event, send_batch, _build_hec_payload, and retry paths."""

    @pytest.mark.asyncio
    async def test_send_event_success_covers_return_path(self, service: SplunkService) -> None:
        """Lines 92-99: send_event success logs splunk_event_sent and returns result."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "Success", "code": 0}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.send_event(
                event={"event": "test_event", "level": "INFO"},
                correlation_id="cov-test-1",
            )

        assert result["code"] == 0
        assert result["text"] == "Success"

    @pytest.mark.asyncio
    async def test_send_batch_non_empty_covers_batch_path(self, service: SplunkService) -> None:
        """Lines 123-153: send_batch with non-empty events list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "Success", "code": 0}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        events = [
            {"event": "step_started", "execution_id": 1},
            {"event": "step_completed", "execution_id": 1},
        ]
        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.send_batch(events=events, correlation_id="batch-cov")

        assert result["count"] == 2
        assert result["code"] == 0

    def test_build_hec_payload_with_indexed_fields(self, service: SplunkService) -> None:
        """Lines 167, 175: _build_hec_payload extracts and sets fields from event dict."""
        event = {
            "event": "execution_completed",
            "correlation_id": "corr-abc",
            "user_id": "user-123",
            "execution_id": 42,
            "platform": "aws_batch",
            "other_field": "ignored_in_fields",
        }
        payload = service._build_hec_payload(event, sourcetype=None, index=None)

        assert "fields" in payload
        assert payload["fields"]["correlation_id"] == "corr-abc"
        assert payload["fields"]["user_id"] == "user-123"
        assert payload["fields"]["execution_id"] == 42
        assert payload["fields"]["platform"] == "aws_batch"
        assert "other_field" not in payload["fields"]

    @pytest.mark.asyncio
    async def test_send_batch_empty_returns_immediately(self, service: SplunkService) -> None:
        """Line 124: send_batch with empty list → immediate return (no HTTP call)."""
        result = await service.send_batch(events=[], correlation_id="empty-cov")
        assert result == {"status": "success", "count": 0, "code": 0, "text": "No events"}

    def test_build_hec_payload_without_indexed_fields(self, service: SplunkService) -> None:
        """_build_hec_payload with no indexed fields does not set 'fields' key."""
        event = {"event": "simple_event", "level": "INFO"}
        payload = service._build_hec_payload(event, sourcetype=None, index=None)

        assert "fields" not in payload

    @pytest.mark.asyncio
    async def test_transient_500_then_success_covers_retry_path(self, service: SplunkService) -> None:
        """Lines 203-214: 500 transient error → logs warning + sleep + retry → success."""
        # First response: 500 (transient)
        response_500 = MagicMock(spec=httpx.Response)
        response_500.status_code = 500
        response_500.raise_for_status.return_value = None  # transient, not raised

        # Second response: 200 (success)
        response_200 = MagicMock(spec=httpx.Response)
        response_200.status_code = 200
        response_200.raise_for_status.return_value = None
        response_200.json.return_value = {"text": "Success", "code": 0}

        mock_client = AsyncMock()
        mock_client.post.side_effect = [response_500, response_200]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await service._post_raw_with_retry(
                    "https://splunk.example.com:8088/services/collector/event",
                    '{"event": "test"}',
                    correlation_id="transient-test",
                )

        assert result["code"] == 0
        mock_sleep.assert_called_once_with(5.0)  # SPLUNK_RETRY_DELAY

    @pytest.mark.asyncio
    async def test_timeout_then_retry_then_success(self, service: SplunkService) -> None:
        """Lines 217-226: TimeoutException on first attempt → retry → success."""
        response_200 = MagicMock(spec=httpx.Response)
        response_200.status_code = 200
        response_200.raise_for_status.return_value = None
        response_200.json.return_value = {"text": "Success", "code": 0}

        mock_client = AsyncMock()
        mock_client.post.side_effect = [
            httpx.TimeoutException("Timeout"),
            response_200,
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                result = await service._post_raw_with_retry(
                    "https://splunk.example.com:8088/services/collector/event",
                    '{"event": "test"}',
                )

        assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_timeout_all_retries_exhausted_raises(self, service: SplunkService) -> None:
        """Lines 228-234: TimeoutException on ALL attempts → final raise SPLUNK_TIMEOUT."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Timeout on every attempt")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await service._post_raw_with_retry(
                        "https://splunk.example.com:8088/services/collector/event",
                        '{"event": "test"}',
                        correlation_id="timeout-all",
                    )

        assert exc_info.value.code == "SPLUNK_TIMEOUT"
        assert mock_client.post.call_count == SPLUNK_MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_http_status_error_raises_service_unavailable(self, service: SplunkService) -> None:
        """Lines 241-248: HTTPStatusError → raise ServiceUnavailableError(SPLUNK_HEC_ERROR)."""
        response_400 = MagicMock(spec=httpx.Response)
        response_400.status_code = 400
        response_400.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(spec=httpx.Request),
            response=response_400,
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = response_400
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service._post_raw_with_retry(
                    "https://splunk.example.com:8088/services/collector/event",
                    '{"event": "test"}',
                )

        assert exc_info.value.code == "SPLUNK_HEC_ERROR"
        assert "400" in exc_info.value.message


# ---------------------------------------------------------------------------
# Line 279: Safety net — max retries exceeded via HTTPError path
# ---------------------------------------------------------------------------

class TestMaxRetriesSafetyNet:
    """Cover line 279: safety net raise after exhausting all HTTPError retries."""

    @pytest.mark.asyncio
    async def test_max_retries_exceeded_http_error_safety_net(self, service: SplunkService) -> None:
        """HTTPError on every attempt → all retries exhausted → safety net ServiceUnavailableError."""
        mock_client = AsyncMock()
        # httpx.ConnectError is a subclass of httpx.HTTPError (not HTTPStatusError or TimeoutException)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await service.send_event(event={"event": "test"})

        # After SPLUNK_MAX_RETRIES+1 attempts with HTTPError, code should be CONNECTION_ERROR
        assert exc_info.value.code == "SPLUNK_CONNECTION_ERROR"
        # post was called max_retries+1 times
        assert mock_client.post.call_count == SPLUNK_MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_retry_then_connection_error_raises(self, service: SplunkService) -> None:
        """All retries exhausted via HTTPError: last attempt raises SPLUNK_CONNECTION_ERROR."""
        mock_client = AsyncMock()
        # ConnectTimeout is subclass of HTTPError (but not TimeoutException in older httpx)
        # Use a plain httpx.HTTPError to cover the generic HTTPError branch
        class _FakeHTTPError(httpx.HTTPError):
            def __init__(self):
                super().__init__("Network error")

        mock_client.post.side_effect = _FakeHTTPError()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await service._post_raw_with_retry(
                        "https://splunk.example.com:8088/services/collector/event",
                        '{"event": "test"}',
                    )

        assert exc_info.value.code == "SPLUNK_CONNECTION_ERROR"


# ---------------------------------------------------------------------------
# Lines 350-353: _run_splunk_search_job — poll loop timeout (while/else)
# ---------------------------------------------------------------------------

class TestRunSplunkSearchJobTimeout:
    """Cover lines 350-353: poll loop exhausted → while/else → return None."""

    @pytest.mark.asyncio
    async def test_poll_timeout_returns_none(self, service: SplunkService) -> None:
        """Search job never reaches DONE before deadline → sleep once then timeout.

        Patches time.monotonic so that:
        - call 1: initial time (deadline = 0.0 + poll_timeout_sec = 1.0)
        - call 2: 0.5 (still within deadline) → enters loop, gets RUNNING, sleeps (line 350)
        - call 3: 1000.0 (past deadline) → while condition fails → else clause (lines 351-353)
        """
        sid_response = MagicMock(spec=httpx.Response)
        sid_response.raise_for_status.return_value = None
        sid_response.json.return_value = {"sid": "12345"}

        # Status always returns RUNNING, never DONE
        status_response = MagicMock(spec=httpx.Response)
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            "entry": [{"content": {"dispatchState": "RUNNING"}}]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = sid_response
        mock_client.get.return_value = status_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # time is imported locally inside _run_splunk_search_job, so patch time.monotonic
        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                return 0.0  # initial: deadline = 0.0 + 1.0 = 1.0
            elif call_count[0] == 2:
                return 0.5  # within deadline → enter loop body
            else:
                return 1000.0  # past deadline → while exits via else

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch("time.monotonic", fake_monotonic):
                    result = await service._run_splunk_search_job(
                        spl='search sourcetype="test"',
                        execution_id=999,
                        poll_timeout_sec=1.0,
                    )

        assert result is None
        # Verify asyncio.sleep(1) was called (line 350)
        mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_run_search_job_no_sid_returns_none(self, service: SplunkService) -> None:
        """Search job creation returns no SID → return None (line 328-329)."""
        sid_response = MagicMock(spec=httpx.Response)
        sid_response.raise_for_status.return_value = None
        sid_response.json.return_value = {}  # no 'sid' key

        mock_client = AsyncMock()
        mock_client.post.return_value = sid_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._run_splunk_search_job(
                spl='search sourcetype="test"',
                execution_id=1,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_run_search_job_exception_returns_none(self, service: SplunkService) -> None:
        """Exception during search → return None (line 363-365 catch-all)."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Unexpected error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service._run_splunk_search_job(
                spl='search sourcetype="test"',
                execution_id=2,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_poll_job_done_immediately(self, service: SplunkService) -> None:
        """Search job reaches DONE on first poll → returns results."""
        sid_response = MagicMock(spec=httpx.Response)
        sid_response.raise_for_status.return_value = None
        sid_response.json.return_value = {"sid": "job-done-123"}

        status_response = MagicMock(spec=httpx.Response)
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            "entry": [{"content": {"dispatchState": "DONE"}}]
        }

        results_response = MagicMock(spec=httpx.Response)
        results_response.raise_for_status.return_value = None
        results_response.json.return_value = {
            "results": [{"_raw": '{"event": "test"}'}]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = sid_response
        mock_client.get.side_effect = [status_response, results_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            with patch("services.splunk_service.asyncio.sleep", new_callable=AsyncMock):
                result = await service._run_splunk_search_job(
                    spl='search sourcetype="test"',
                    execution_id=10,
                    poll_timeout_sec=30.0,
                )

        assert result == [{"_raw": '{"event": "test"}'}]


# ---------------------------------------------------------------------------
# Lines 387, 391-392: search_platform_logs with platform_job_id
# Lines 405-406: JSON parse result and fallback
# ---------------------------------------------------------------------------

class TestSearchPlatformLogs:
    """Cover search_platform_logs missing branches."""

    @pytest.mark.asyncio
    async def test_search_with_platform_job_id(self, service: SplunkService) -> None:
        """Lines 387, 391-392: platform_job_id causes SPL to include escaped pid filter."""
        raw_event = json.dumps({"content": "log output here", "platform_job_id": "job-abc"})

        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": raw_event}]
            result = await service.search_platform_logs(
                execution_id=42,
                platform_job_id="job-abc",
            )

        assert result == "log output here"
        # Verify SPL includes the platform_job_id filter
        call_spl = mock_search.call_args[0][0]
        assert 'platform_job_id="job-abc"' in call_spl

    @pytest.mark.asyncio
    async def test_search_platform_job_id_escapes_special_chars(self, service: SplunkService) -> None:
        """Backslash and double-quote in platform_job_id are escaped in SPL."""
        raw_event = json.dumps({"content": "some log", "platform_job_id": 'job"with"quotes'})

        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": raw_event}]
            _result = await service.search_platform_logs(
                execution_id=1,
                platform_job_id='job"with"quotes',
            )

        call_spl = mock_search.call_args[0][0]
        # Double quotes should be escaped with backslash
        assert '\\"' in call_spl

    @pytest.mark.asyncio
    async def test_search_platform_job_id_backslash_escape(self, service: SplunkService) -> None:
        """Backslash in platform_job_id is escaped."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": json.dumps({"content": "ok"})}]
            await service.search_platform_logs(
                execution_id=1,
                platform_job_id="job\\with\\backslash",
            )
        call_spl = mock_search.call_args[0][0]
        assert "\\\\" in call_spl

    @pytest.mark.asyncio
    async def test_search_returns_none_when_no_results(self, service: SplunkService) -> None:
        """Empty results list → log info → return None."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            result = await service.search_platform_logs(execution_id=5)

        assert result is None

    @pytest.mark.asyncio
    async def test_search_returns_none_when_search_fails(self, service: SplunkService) -> None:
        """_run_splunk_search_job returns None → search_platform_logs returns None."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = None
            result = await service.search_platform_logs(execution_id=99)

        assert result is None

    @pytest.mark.asyncio
    async def test_search_returns_content_from_valid_json(self, service: SplunkService) -> None:
        """Line 404-405: Valid JSON _raw → return event_data.get('content')."""
        raw_event = json.dumps({"content": "execution log line 1\nline 2", "execution_id": 42})

        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": raw_event}]
            result = await service.search_platform_logs(execution_id=42)

        assert result == "execution log line 1\nline 2"

    @pytest.mark.asyncio
    async def test_search_fallback_on_json_decode_error(self, service: SplunkService) -> None:
        """Line 405-406: Invalid JSON in _raw → return raw string."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": "not-valid-json"}]
            result = await service.search_platform_logs(execution_id=10)

        assert result == "not-valid-json"

    @pytest.mark.asyncio
    async def test_search_fallback_returns_none_when_raw_empty(self, service: SplunkService) -> None:
        """Line 406: Invalid JSON + empty raw → return None."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": ""}]
            result = await service.search_platform_logs(execution_id=10)

        # empty string is falsy, so `raw or None` returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_search_raw_is_dict_returns_content(self, service: SplunkService) -> None:
        """Line 403: _raw is already a dict (not str) → use directly."""
        raw_dict = {"content": "dict content", "execution_id": 1}

        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"_raw": raw_dict}]
            result = await service.search_platform_logs(execution_id=1)

        assert result == "dict content"


# ---------------------------------------------------------------------------
# Lines 417-435: search_platform_logs_mapping
# ---------------------------------------------------------------------------

class TestSearchPlatformLogsMapping:
    """Cover search_platform_logs_mapping (lines 417-435)."""

    @pytest.mark.asyncio
    async def test_mapping_returns_empty_on_none(self, service: SplunkService) -> None:
        """_run_splunk_search_job returns None → return empty dict."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = None
            result = await service.search_platform_logs_mapping(execution_id=1)

        assert result == {}

    @pytest.mark.asyncio
    async def test_mapping_builds_dict_from_results(self, service: SplunkService) -> None:
        """Valid results → mapping pid -> content."""
        results = [
            {"_raw": json.dumps({"platform_job_id": "job-1", "content": "log 1"})},
            {"_raw": json.dumps({"platform_job_id": "job-2", "content": "log 2"})},
        ]
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = results
            mapping = await service.search_platform_logs_mapping(execution_id=5)

        assert mapping == {"job-1": "log 1", "job-2": "log 2"}

    @pytest.mark.asyncio
    async def test_mapping_skips_entries_without_pid(self, service: SplunkService) -> None:
        """Entries missing platform_job_id are skipped."""
        results = [
            {"_raw": json.dumps({"content": "log without pid"})},
            {"_raw": json.dumps({"platform_job_id": "job-1", "content": "log 1"})},
        ]
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = results
            mapping = await service.search_platform_logs_mapping(execution_id=5)

        assert mapping == {"job-1": "log 1"}

    @pytest.mark.asyncio
    async def test_mapping_skips_entries_without_content(self, service: SplunkService) -> None:
        """Entries missing content are skipped."""
        results = [
            {"_raw": json.dumps({"platform_job_id": "job-1"})},  # no content
            {"_raw": json.dumps({"platform_job_id": "job-2", "content": "valid log"})},
        ]
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = results
            mapping = await service.search_platform_logs_mapping(execution_id=5)

        assert mapping == {"job-2": "valid log"}

    @pytest.mark.asyncio
    async def test_mapping_skips_invalid_json(self, service: SplunkService) -> None:
        """Invalid JSON in _raw → skipped (continue on exception)."""
        results = [
            {"_raw": "not-json"},
            {"_raw": json.dumps({"platform_job_id": "job-ok", "content": "ok log"})},
        ]
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = results
            mapping = await service.search_platform_logs_mapping(execution_id=3)

        assert mapping == {"job-ok": "ok log"}

    @pytest.mark.asyncio
    async def test_mapping_raw_is_dict(self, service: SplunkService) -> None:
        """_raw is already a dict → used directly."""
        results = [
            {"_raw": {"platform_job_id": "job-dict", "content": "dict log"}},
        ]
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = results
            mapping = await service.search_platform_logs_mapping(execution_id=7)

        assert mapping == {"job-dict": "dict log"}

    @pytest.mark.asyncio
    async def test_mapping_empty_results(self, service: SplunkService) -> None:
        """Empty results list → empty mapping."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            mapping = await service.search_platform_logs_mapping(execution_id=9)

        assert mapping == {}

    @pytest.mark.asyncio
    async def test_mapping_correct_spl_query(self, service: SplunkService) -> None:
        """search_platform_logs_mapping uses correct SPL query with execution_id."""
        with patch.object(service, "_run_splunk_search_job", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            await service.search_platform_logs_mapping(execution_id=42)

        call_spl = mock_search.call_args[0][0]
        assert "execution_id=42" in call_spl
        assert 'sourcetype="idp:platform_log"' in call_spl


# ---------------------------------------------------------------------------
# Lines 443-460: health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Cover health_check method (lines 443-460)."""

    @pytest.mark.asyncio
    async def test_health_check_ok(self, service: SplunkService) -> None:
        """Successful GET /services/server/info → HealthCheckStatus.OK."""
        from integrations.health_check import HealthCheckStatus

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.OK
        assert result.error_message is None
        mock_client.get.assert_called_once()
        call_url = mock_client.get.call_args[0][0]
        assert call_url.endswith("/services/server/info")

    @pytest.mark.asyncio
    async def test_health_check_error_on_http_exception(self, service: SplunkService) -> None:
        """Exception during GET → HealthCheckStatus.ERROR with error_message."""
        from integrations.health_check import HealthCheckStatus

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None
        assert "Connection refused" in result.error_message

    @pytest.mark.asyncio
    async def test_health_check_error_on_status_error(self, service: SplunkService) -> None:
        """HTTP 401 status → raise_for_status raises → HealthCheckStatus.ERROR."""
        from integrations.health_check import HealthCheckStatus

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(spec=httpx.Request),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.status == HealthCheckStatus.ERROR
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_health_check_result_has_checked_at(self, service: SplunkService) -> None:
        """health_check result includes checked_at timestamp."""

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await service.health_check()

        assert result.checked_at is not None

    @pytest.mark.asyncio
    async def test_health_check_uses_correct_url(self, service: SplunkService) -> None:
        """health_check calls /services/server/info on the configured base_url."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            await service.health_check()

        expected_url = "https://splunk.example.com:8088/services/server/info"
        mock_client.get.assert_called_once_with(expected_url)
