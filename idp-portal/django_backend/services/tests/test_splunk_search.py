"""
Tests for SplunkService.search_platform_logs().
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.splunk_service import SplunkService


@pytest.fixture
def splunk_service() -> SplunkService:
    return SplunkService(
        base_url="https://splunk.example.com:8089",
        auth_headers={"Authorization": "Splunk test-token"},
        timeout=10.0,
    )


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(spec=httpx.Request),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestSearchPlatformLogs:

    @pytest.mark.asyncio
    async def test_success_returns_content(self, splunk_service):
        log_content = "PLAY [all] ***\nok: [host1]"
        raw_event = json.dumps({
            "event": "platform_log",
            "execution_id": 42,
            "content": log_content,
        })

        create_resp = _mock_response(200, {"sid": "search_123"})
        status_resp = _mock_response(200, {
            "entry": [{"content": {"dispatchState": "DONE"}}],
        })
        results_resp = _mock_response(200, {
            "results": [{"_raw": raw_event}],
        })

        mock_client = AsyncMock()
        mock_client.post.return_value = create_resp
        mock_client.get.side_effect = [status_resp, results_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await splunk_service.search_platform_logs(execution_id=42)

        assert result == log_content

    @pytest.mark.asyncio
    async def test_no_results_returns_none(self, splunk_service):
        create_resp = _mock_response(200, {"sid": "search_456"})
        status_resp = _mock_response(200, {
            "entry": [{"content": {"dispatchState": "DONE"}}],
        })
        results_resp = _mock_response(200, {"results": []})

        mock_client = AsyncMock()
        mock_client.post.return_value = create_resp
        mock_client.get.side_effect = [status_resp, results_resp]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await splunk_service.search_platform_logs(execution_id=42)

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, splunk_service):
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await splunk_service.search_platform_logs(execution_id=42)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_sid_returns_none(self, splunk_service):
        create_resp = _mock_response(200, {})  # no sid

        mock_client = AsyncMock()
        mock_client.post.return_value = create_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.splunk_service.httpx.AsyncClient", return_value=mock_client):
            result = await splunk_service.search_platform_logs(execution_id=42)

        assert result is None
