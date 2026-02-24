"""
Tests for adapters/utils.py — build_auth_headers_from_credentials and build_auth_headers.
Story 31.12: Tests for api_key and oauth2_client_credentials flows.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from adapters.utils import build_auth_headers_from_credentials, build_auth_headers
from core.exceptions import BadRequestError


# ---------------------------------------------------------------------------
# build_auth_headers_from_credentials
# ---------------------------------------------------------------------------

class TestBuildAuthHeadersFromCredentials:
    """Tests for the simple credential-based header builder (no Vault resolution)."""

    def test_token_flow(self):
        result = build_auth_headers_from_credentials("mytoken", "token")
        assert result == {"Authorization": "Bearer mytoken"}

    def test_default_flow_is_token(self):
        result = build_auth_headers_from_credentials("mytoken")
        assert result == {"Authorization": "Bearer mytoken"}

    def test_pat_flow(self):
        result = build_auth_headers_from_credentials("mypattoken", "pat")
        assert result == {"Authorization": "Bearer mypattoken"}

    def test_basic_flow(self):
        encoded = base64.b64encode("user:pass".encode()).decode()
        result = build_auth_headers_from_credentials("user:pass", "basic")
        assert result == {"Authorization": f"Basic {encoded}"}

    def test_api_key_flow(self):
        """Story 31.12: api_key → X-API-Key header with credential as value."""
        result = build_auth_headers_from_credentials("mykey", "api_key")
        assert result == {"X-API-Key": "mykey"}

    def test_basic_then_token_falls_through_to_bearer(self):
        result = build_auth_headers_from_credentials("mytoken", "basic_then_token")
        assert result == {"Authorization": "Bearer mytoken"}


# ---------------------------------------------------------------------------
# build_auth_headers (with Integration mock)
# ---------------------------------------------------------------------------

def _make_integration(
    auth_flow: str = "token",
    credential_ref: str = "mytoken",
    token_url: str | None = None,
    config: dict | None = None,
    integration_id: int = 1,
    secret_service_id: int | None = None,
) -> MagicMock:
    """Build a minimal Integration mock."""
    m = MagicMock()
    m.auth_flow = auth_flow
    m.credential_ref = credential_ref
    m.token_url = token_url
    m.id = integration_id
    m.secret_service_id = secret_service_id
    m.get_config = MagicMock(return_value=config or {})
    return m


class TestBuildAuthHeaders:
    """Tests for build_auth_headers (with credential resolution)."""

    def test_empty_credential_raises(self):
        integration = _make_integration(credential_ref="")
        with pytest.raises(BadRequestError) as exc_info:
            build_auth_headers(integration)
        assert exc_info.value.code == "EMPTY_CREDENTIAL"

    def test_token_flow(self):
        integration = _make_integration(auth_flow="token", credential_ref="tok123")
        with patch("adapters.utils.resolve_credential", return_value="tok123"):
            result = build_auth_headers(integration)
        assert result == {"Authorization": "Bearer tok123"}

    # --- api_key ---

    def test_api_key_with_custom_header_name(self):
        """Story 31.12: api_key + config.header_name → custom header."""
        integration = _make_integration(
            auth_flow="api_key",
            credential_ref="apikey123",
            config={"header_name": "X-Auth-Token"},
        )
        with patch("adapters.utils.resolve_credential", return_value="apikey123"):
            result = build_auth_headers(integration)
        assert result == {"X-Auth-Token": "apikey123"}

    def test_api_key_without_header_name_defaults_to_x_api_key(self):
        """Story 31.12: api_key + no header_name → default X-API-Key."""
        integration = _make_integration(
            auth_flow="api_key",
            credential_ref="apikey123",
            config={},
        )
        with patch("adapters.utils.resolve_credential", return_value="apikey123"):
            result = build_auth_headers(integration)
        assert result == {"X-API-Key": "apikey123"}

    # --- oauth2_client_credentials ---

    def test_oauth2_success(self):
        """Story 31.12: oauth2_client_credentials → POST to token_url → Bearer token."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
            config={"scope": "api:read"},
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "mock_token"}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("requests.post", return_value=mock_response) as mock_post:
                result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer mock_token"}
        mock_post.assert_called_once_with(
            "https://auth.example.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "client_id",
                "client_secret": "client_secret",
                "scope": "api:read",
            },
            timeout=10,
        )

    def test_oauth2_missing_token_url_raises(self):
        """Story 31.12: oauth2_client_credentials without token_url → BadRequestError."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url=None,
        )
        with pytest.raises(BadRequestError) as exc_info:
            build_auth_headers(integration)
        assert exc_info.value.code == "MISSING_TOKEN_URL"

    def test_oauth2_token_request_failure_raises(self):
        """Story 31.12: oauth2_client_credentials + requests.post fails → BadRequestError."""
        import requests as _req
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("requests.post", side_effect=_req.RequestException("Connection refused")):
                with pytest.raises(BadRequestError) as exc_info:
                    build_auth_headers(integration)
        assert exc_info.value.code == "OAUTH2_TOKEN_REQUEST_FAILED"

    def test_oauth2_no_access_token_in_response_raises(self):
        """Story 31.12: oauth2_client_credentials + empty access_token → BadRequestError."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # no access_token
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("requests.post", return_value=mock_response):
                with pytest.raises(BadRequestError) as exc_info:
                    build_auth_headers(integration)
        assert exc_info.value.code == "OAUTH2_NO_ACCESS_TOKEN"

    def test_oauth2_credential_without_colon_uses_empty_secret(self):
        """Story 31.12: credential_ref without ':' → client_id=resolved, client_secret=''."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="just_client_id",
            token_url="https://auth.example.com/token",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "mock_token"}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="just_client_id"):
            with patch("requests.post", return_value=mock_response) as mock_post:
                result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer mock_token"}
        mock_post.assert_called_once_with(
            "https://auth.example.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "just_client_id",
                "client_secret": "",
            },
            timeout=10,
        )
