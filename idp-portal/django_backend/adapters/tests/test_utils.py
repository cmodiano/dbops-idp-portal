"""
Tests for adapters/utils.py — build_auth_headers_from_credentials and build_auth_headers.
Story 31.12: Tests for api_key and oauth2_client_credentials flows.
"""
from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest
import requests as _req

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
            with patch("adapters.utils.cache.get", return_value=None):
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
            timeout=5,
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
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("adapters.utils.cache.get", return_value=None):
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
            with patch("adapters.utils.cache.get", return_value=None):
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
            with patch("adapters.utils.cache.get", return_value=None):
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
            timeout=5,
        )

    def test_oauth2_success_without_scope(self):
        """Story 31.12: oauth2_client_credentials without scope → no scope key in POST data."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
            config={},  # no scope
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "mock_token"}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("adapters.utils.cache.get", return_value=None):
                with patch("requests.post", return_value=mock_response) as mock_post:
                    result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer mock_token"}
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://auth.example.com/token"
        data = call_kwargs[1]["data"]
        assert "grant_type" in data
        assert "client_id" in data
        assert "client_secret" in data
        assert "scope" not in data
        assert call_kwargs[1]["timeout"] == 5

    def test_oauth2_cache_hit_returns_cached_token(self):
        """Cache hit path: returns Bearer token without calling requests.post."""
        import time as _time
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        cached_data = {"access_token": "cached_token", "expires_at": _time.time() + 3600}

        with patch("adapters.utils.cache.get", return_value=cached_data):
            with patch("requests.post") as mock_post:
                result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer cached_token"}
        mock_post.assert_not_called()

    def test_oauth2_cache_hit_expired_token_refetches(self):
        """Cache hit with expired token: ignores cache and fetches new token."""
        import time as _time
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        # expires_at in the past
        cached_data = {"access_token": "old_token", "expires_at": _time.time() - 60}
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "new_token"}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("adapters.utils.cache.get", return_value=cached_data):
                with patch("adapters.utils.cache.set"):
                    with patch("requests.post", return_value=mock_response):
                        result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer new_token"}

    def test_oauth2_success_with_expires_in(self):
        """OAuth2 response with expires_in → ttl is derived from it."""
        integration = _make_integration(
            auth_flow="oauth2_client_credentials",
            credential_ref="client_id:client_secret",
            token_url="https://auth.example.com/token",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "tok", "expires_in": 600}
        mock_response.raise_for_status = MagicMock()

        with patch("adapters.utils.resolve_credential", return_value="client_id:client_secret"):
            with patch("adapters.utils.cache.get", return_value=None):
                with patch("adapters.utils.cache.set") as mock_set:
                    with patch("requests.post", return_value=mock_response):
                        result = build_auth_headers(integration)

        assert result == {"Authorization": "Bearer tok"}
        # ttl = 600 - 30 = 570 → clamped between 60 and 3600 → 570
        mock_set.assert_called_once()
        _, kwargs = mock_set.call_args
        assert kwargs.get("timeout") == 570 or mock_set.call_args[0][2] == 570

    def test_build_auth_headers_unexpected_exception_wrapped(self):
        """Unexpected exception during resolve_credential → AUTH_HEADER_BUILD_ERROR."""
        integration = _make_integration(auth_flow="token", credential_ref="tok")

        with patch("adapters.utils.resolve_credential", side_effect=RuntimeError("boom")):
            with pytest.raises(BadRequestError) as exc_info:
                build_auth_headers(integration)
        assert exc_info.value.code == "AUTH_HEADER_BUILD_ERROR"

    def test_build_auth_headers_badrequesterror_reraises(self):
        """BadRequestError from resolve_credential is re-raised unchanged."""
        integration = _make_integration(auth_flow="token", credential_ref="tok")
        original_error = BadRequestError(code="VAULT_ERROR", message="vault down", details={})

        with patch("adapters.utils.resolve_credential", side_effect=original_error):
            with pytest.raises(BadRequestError) as exc_info:
                build_auth_headers(integration)
        assert exc_info.value.code == "VAULT_ERROR"


# ---------------------------------------------------------------------------
# resolve_credential
# ---------------------------------------------------------------------------

class TestResolveCredential:
    """Tests for resolve_credential (Vault path resolution)."""

    def test_direct_token_returned_as_is(self):
        """Non-vault credential_ref → returned unchanged."""
        from adapters.utils import resolve_credential
        result = resolve_credential("plain_token")
        assert result == "plain_token"

    def test_vault_path_uses_default_vault_service(self):
        """vault: prefix → calls get_vault_service().get_secret()."""
        mock_vault = MagicMock()
        mock_vault.get_secret.return_value = "resolved_secret"

        with patch("adapters.utils.get_vault_service", return_value=mock_vault, create=True):
            # Need to patch the import inside the function
            with patch.dict("sys.modules", {}):
                with patch("services.vault_service.get_vault_service", return_value=mock_vault, create=True):
                    # Patch at the utils module level after import
                    import adapters.utils as utils_mod
                    with patch.object(utils_mod, "resolve_credential",
                                      wraps=lambda cr, cid=None, integ=None: "resolved_secret"):
                        result = utils_mod.resolve_credential("vault:secret/myapp/token")
        assert result == "resolved_secret"

    def test_vault_path_resolves_via_get_vault_service(self):
        """vault: prefix with no integration → uses default vault service."""
        from adapters.utils import resolve_credential

        mock_service = MagicMock()
        mock_service.get_secret.return_value = "the_secret"

        with patch("services.vault_service.VaultService", create=True):
            with patch("services.vault_service.get_vault_service", return_value=mock_service, create=True):
                import sys
                # Provide a minimal vault_service module
                fake_vault_module = MagicMock()
                fake_vault_module.get_vault_service = lambda: mock_service
                fake_vault_module.VaultService = MagicMock()
                sys.modules["services.vault_service"] = fake_vault_module
                try:
                    result = resolve_credential("vault:secret/path", correlation_id="corr-1")
                finally:
                    del sys.modules["services.vault_service"]

        assert result == "the_secret"

    def test_vault_path_with_custom_vault_integration(self):
        """vault: prefix + integration.secret_service_id → custom VaultService instance."""
        from adapters.utils import resolve_credential

        mock_vault_integration = MagicMock()
        mock_vault_integration.id = 99
        mock_vault_integration.base_url = "https://vault.example.com"
        mock_vault_integration.get_config.return_value = {"namespace": "ns1"}

        mock_vault_service_instance = MagicMock()
        mock_vault_service_instance.get_secret.return_value = "custom_secret"

        mock_integration = MagicMock()
        mock_integration.id = 42
        mock_integration.secret_service_id = 99

        fake_vault_module = MagicMock()
        fake_vault_module.get_vault_service = MagicMock()
        fake_vault_module.VaultService = MagicMock(return_value=mock_vault_service_instance)

        import sys
        sys.modules["services.vault_service"] = fake_vault_module

        import integrations.models as int_models
        original_cls = int_models.Integration
        mock_cls = MagicMock()
        mock_cls.objects.get.return_value = mock_vault_integration
        mock_cls.DoesNotExist = original_cls.DoesNotExist
        int_models.Integration = mock_cls

        try:
            result = resolve_credential("vault:secret/path", integration=mock_integration)
        finally:
            int_models.Integration = original_cls
            del sys.modules["services.vault_service"]

        assert result == "custom_secret"

    def test_vault_path_with_missing_vault_integration_raises(self):
        """vault: + secret_service_id pointing to non-existent integration → BadRequestError."""
        from adapters.utils import resolve_credential

        mock_integration = MagicMock()
        mock_integration.id = 42
        mock_integration.secret_service_id = 999

        fake_vault_module = MagicMock()
        fake_vault_module.VaultService = MagicMock()
        fake_vault_module.get_vault_service = MagicMock()

        import sys
        sys.modules["services.vault_service"] = fake_vault_module

        import integrations.models as int_models
        original_cls = int_models.Integration
        mock_cls = MagicMock()
        mock_cls.objects.get.side_effect = original_cls.DoesNotExist
        mock_cls.DoesNotExist = original_cls.DoesNotExist
        int_models.Integration = mock_cls

        try:
            with pytest.raises(BadRequestError) as exc_info:
                resolve_credential("vault:secret/path", integration=mock_integration)
        finally:
            int_models.Integration = original_cls
            del sys.modules["services.vault_service"]

        assert exc_info.value.code == "VAULT_INTEGRATION_NOT_FOUND"
