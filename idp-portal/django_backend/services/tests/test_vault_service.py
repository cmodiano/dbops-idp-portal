"""
Tests for VaultService — Story 27.6.

Covers: get_secret success, retry, circuit breaker, cache, auth Token/AppRole,
Vault Enterprise namespaces, error handling (404, 403, 500, timeout),
credential_ref parsing, adapter integration via build_auth_headers.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from core.exceptions import (
    VaultAccessDeniedError,
    VaultAuthError,
    VaultSecretNotFoundError,
    VaultUnavailableError,
)
from services.vault_service import (
    CircuitBreaker,
    ParsedCredentialRef,
    VaultService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vault_response(status_code: int = 200, data: dict | None = None, auth: dict | None = None):
    """Create a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    body: dict = {}
    if data is not None:
        body = {"data": {"data": data, "metadata": {"version": 1}}}
    if auth is not None:
        body = {"auth": auth}
    resp.json.return_value = body
    return resp


# ---------------------------------------------------------------------------
# Credential ref parsing (AC2)
# ---------------------------------------------------------------------------

class TestParseCredentialRef:
    """Test credential_ref parsing."""

    def test_simple_kv_v2(self):
        parsed = VaultService._parse_credential_ref("vault:secret/data/myapp/db#password")
        assert parsed == ParsedCredentialRef(namespace=None, mount="secret", path="myapp/db", key="password")

    def test_kv_v2_no_key(self):
        parsed = VaultService._parse_credential_ref("vault:secret/data/myapp/db")
        assert parsed == ParsedCredentialRef(namespace=None, mount="secret", path="myapp/db", key=None)

    def test_enterprise_namespace(self):
        parsed = VaultService._parse_credential_ref("vault:team-a/secret/data/myapp/creds#token")
        assert parsed == ParsedCredentialRef(namespace="team-a", mount="secret", path="myapp/creds", key="token")

    def test_enterprise_namespace_no_key(self):
        parsed = VaultService._parse_credential_ref("vault:ns1/kv/data/path/to/secret")
        assert parsed == ParsedCredentialRef(namespace="ns1", mount="kv", path="path/to/secret", key=None)

    def test_invalid_format_no_prefix(self):
        with pytest.raises(ValueError, match="Invalid credential_ref format"):
            VaultService._parse_credential_ref("secret/data/path")

    def test_invalid_format_no_data_segment(self):
        with pytest.raises(ValueError, match="Invalid credential_ref format"):
            VaultService._parse_credential_ref("vault:secret/path")

    def test_invalid_format_empty(self):
        with pytest.raises(ValueError, match="Invalid credential_ref format"):
            VaultService._parse_credential_ref("")

    def test_nested_path(self):
        parsed = VaultService._parse_credential_ref("vault:secret/data/a/b/c/d#key")
        assert parsed.path == "a/b/c/d"
        assert parsed.key == "key"


# ---------------------------------------------------------------------------
# VaultService get_secret (AC2)
# ---------------------------------------------------------------------------

class TestGetSecret:
    """Test VaultService.get_secret() — success paths."""

    @patch("services.vault_service.requests.Session")
    def test_get_secret_with_key(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"password": "s3cret", "username": "admin"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="test-token")
        result = svc.get_secret("vault:secret/data/myapp/db#password", correlation_id="req-123")

        assert result == "s3cret"
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        assert "http://vault:8200/v1/secret/data/myapp/db" == call_args[0][0]
        assert call_args[1]["headers"]["X-Vault-Token"] == "test-token"

    @patch("services.vault_service.requests.Session")
    def test_get_secret_no_key_returns_dict(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        data = {"password": "s3cret", "username": "admin"}
        mock_session.get.return_value = _vault_response(200, data)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="test-token")
        result = svc.get_secret("vault:secret/data/myapp/db")

        assert result == data

    @patch("services.vault_service.requests.Session")
    def test_get_secret_key_not_in_data(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"username": "admin"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="test-token")
        with pytest.raises(VaultSecretNotFoundError, match="Key 'password' not found"):
            svc.get_secret("vault:secret/data/myapp/db#password")


# ---------------------------------------------------------------------------
# Retry with exponential backoff (AC3)
# ---------------------------------------------------------------------------

class TestRetry:
    """Test retry with exponential backoff."""

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_retry_transient_then_success(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = [
            _vault_response(500),
            _vault_response(500),
            _vault_response(200, {"token": "abc"}),
        ]

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        result = svc.get_secret("vault:secret/data/app#token")

        assert result == "abc"
        assert mock_session.get.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # 2^0
        mock_sleep.assert_any_call(2)  # 2^1

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_retry_all_fail_raises(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = [
            _vault_response(503),
            _vault_response(503),
            _vault_response(503),
        ]

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultUnavailableError, match="HTTP 503"):
            svc.get_secret("vault:secret/data/app#token")

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_timeout_retry(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = [
            requests.exceptions.Timeout("connect timeout"),
            _vault_response(200, {"token": "ok"}),
        ]

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        result = svc.get_secret("vault:secret/data/app#token")

        assert result == "ok"
        assert mock_sleep.call_count == 1

    @patch("services.vault_service.requests.Session")
    def test_no_retry_on_404(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(404)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultSecretNotFoundError):
            svc.get_secret("vault:secret/data/missing#key")

        assert mock_session.get.call_count == 1  # No retry

    @patch("services.vault_service.requests.Session")
    def test_no_retry_on_403(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(403)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultAccessDeniedError):
            svc.get_secret("vault:secret/data/forbidden#key")

        assert mock_session.get.call_count == 1  # No retry

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_connection_error_retry(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = [
            requests.exceptions.ConnectionError("refused"),
            _vault_response(200, {"val": "x"}),
        ]

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        result = svc.get_secret("vault:secret/data/app#val")

        assert result == "x"


# ---------------------------------------------------------------------------
# Circuit Breaker (AC4)
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """Test circuit breaker states and transitions."""

    def test_closed_to_open_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        assert cb.state == "closed"

        def failing_func():
            raise VaultUnavailableError("fail")

        for _ in range(3):
            with pytest.raises(VaultUnavailableError):
                cb.call(failing_func)

        assert cb.state == "open"

    def test_open_rejects_immediately(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing_func():
            raise VaultUnavailableError("fail")

        for _ in range(2):
            with pytest.raises(VaultUnavailableError):
                cb.call(failing_func)

        assert cb.state == "open"

        # Next call should be rejected immediately without calling func
        call_count = 0
        def counting_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        with pytest.raises(VaultUnavailableError, match="Circuit breaker open"):
            cb.call(counting_func)

        assert call_count == 0  # func was NOT called

    @patch("services.vault_service.time.monotonic")
    def test_half_open_success_closes(self, mock_monotonic):
        cb = CircuitBreaker(failure_threshold=2, timeout=10)

        def failing_func():
            raise VaultUnavailableError("fail")

        # Start at t=0
        mock_monotonic.return_value = 0.0
        for _ in range(2):
            with pytest.raises(VaultUnavailableError):
                cb.call(failing_func)
        assert cb.state == "open"

        # Jump past timeout (t=11)
        mock_monotonic.return_value = 11.0

        # Successful call should close the circuit
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == "closed"
        assert cb._state.failures == 0

    @patch("services.vault_service.time.monotonic")
    def test_half_open_failure_reopens(self, mock_monotonic):
        cb = CircuitBreaker(failure_threshold=2, timeout=10)

        def failing_func():
            raise VaultUnavailableError("fail")

        mock_monotonic.return_value = 0.0
        for _ in range(2):
            with pytest.raises(VaultUnavailableError):
                cb.call(failing_func)
        assert cb.state == "open"

        mock_monotonic.return_value = 11.0
        with pytest.raises(VaultUnavailableError):
            cb.call(failing_func)

        assert cb.state == "open"

    def test_definitive_errors_dont_trip_breaker(self):
        cb = CircuitBreaker(failure_threshold=3, timeout=60)

        def not_found():
            raise VaultSecretNotFoundError("nope")

        for _ in range(5):
            with pytest.raises(VaultSecretNotFoundError):
                cb.call(not_found)

        # Circuit should still be closed — 404/403 are definitive, not transient
        assert cb.state == "closed"
        assert cb._state.failures == 0

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=60)

        def failing():
            raise VaultUnavailableError("fail")

        for _ in range(2):
            with pytest.raises(VaultUnavailableError):
                cb.call(failing)
        assert cb.state == "open"

        cb.reset()
        assert cb.state == "closed"
        assert cb._state.failures == 0


# ---------------------------------------------------------------------------
# Cache with TTL (AC5)
# ---------------------------------------------------------------------------

class TestCache:
    """Test cache hit, miss, invalidation."""

    @patch("services.vault_service.requests.Session")
    def test_cache_hit_no_vault_call(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "cached-val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t", cache_ttl=300)

        # First call — cache miss
        result1 = svc.get_secret("vault:secret/data/app#token")
        assert result1 == "cached-val"
        assert mock_session.get.call_count == 1

        # Second call — cache hit
        result2 = svc.get_secret("vault:secret/data/app#token")
        assert result2 == "cached-val"
        assert mock_session.get.call_count == 1  # Still 1 — no new Vault call

    @patch("services.vault_service.requests.Session")
    def test_clear_cache(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t", cache_ttl=300)

        svc.get_secret("vault:secret/data/app#token")
        assert mock_session.get.call_count == 1

        svc.clear_cache()

        svc.get_secret("vault:secret/data/app#token")
        assert mock_session.get.call_count == 2  # New Vault call after cache clear

    @patch("services.vault_service.requests.Session")
    def test_clear_secret_specific(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"a": "1", "b": "2"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t", cache_ttl=300)

        svc.get_secret("vault:secret/data/app#a")
        svc.get_secret("vault:secret/data/app#b")
        assert mock_session.get.call_count == 2

        # Clear only one entry
        svc.clear_secret("vault:secret/data/app#a")

        svc.get_secret("vault:secret/data/app#a")  # cache miss → new call
        svc.get_secret("vault:secret/data/app#b")  # still cached

        assert mock_session.get.call_count == 3


# ---------------------------------------------------------------------------
# Auth Token (AC6)
# ---------------------------------------------------------------------------

class TestAuthToken:
    """Test Token authentication."""

    @patch("services.vault_service.requests.Session")
    def test_token_from_constructor(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"key": "val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="my-token")
        svc.get_secret("vault:secret/data/test#key")

        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Token"] == "my-token"

    @patch.dict("os.environ", {"VAULT_TOKEN": "env-token"}, clear=False)
    @patch("services.vault_service.requests.Session")
    def test_token_from_env(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"key": "val"})

        svc = VaultService(vault_addr="http://vault:8200")
        svc.get_secret("vault:secret/data/test#key")

        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Token"] == "env-token"

    @patch("services.vault_service.requests.Session")
    def test_no_token_raises_auth_error(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        # No token, no AppRole env vars → no auth
        with patch.dict("os.environ", {}, clear=True):
            svc = VaultService(vault_addr="http://vault:8200")

        with pytest.raises(VaultAuthError, match="No Vault token"):
            svc.get_secret("vault:secret/data/test#key")


# ---------------------------------------------------------------------------
# Auth AppRole (AC6)
# ---------------------------------------------------------------------------

class TestAuthAppRole:
    """Test AppRole authentication."""

    @patch.dict("os.environ", {"VAULT_ROLE_ID": "role-123", "VAULT_SECRET_ID": "secret-456"}, clear=False)
    @patch("services.vault_service.requests.Session")
    def test_approle_login_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = _vault_response(
            200, auth={"client_token": "approle-token", "renewable": True, "lease_duration": 3600}
        )
        mock_session.get.return_value = _vault_response(200, {"key": "val"})

        svc = VaultService(vault_addr="http://vault:8200")

        # Verify AppRole login was called
        mock_session.post.assert_called_once()
        login_url = mock_session.post.call_args[0][0]
        assert login_url == "http://vault:8200/v1/auth/approle/login"
        payload = mock_session.post.call_args[1]["json"]
        assert payload == {"role_id": "role-123", "secret_id": "secret-456"}

        # Verify token is used for subsequent requests
        result = svc.get_secret("vault:secret/data/app#key")
        assert result == "val"
        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Token"] == "approle-token"

    @patch.dict("os.environ", {"VAULT_ROLE_ID": "role-123", "VAULT_SECRET_ID": "bad-secret"}, clear=False)
    @patch("services.vault_service.requests.Session")
    def test_approle_login_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.return_value = _vault_response(403)

        with pytest.raises(VaultAuthError, match="access denied"):
            VaultService(vault_addr="http://vault:8200")

    @patch.dict("os.environ", {"VAULT_ROLE_ID": "role-123", "VAULT_SECRET_ID": "secret-456"}, clear=False)
    @patch("services.vault_service.requests.Session")
    def test_approle_connection_error(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.post.side_effect = requests.exceptions.ConnectionError("refused")

        with pytest.raises(VaultAuthError, match="refused"):
            VaultService(vault_addr="http://vault:8200")


# ---------------------------------------------------------------------------
# Token Renewal (AC6)
# ---------------------------------------------------------------------------

class TestTokenRenewal:
    """Test token auto-renewal."""

    @patch("services.vault_service.time.monotonic")
    @patch("services.vault_service.requests.Session")
    def test_renew_token_when_close_to_expiry(self, mock_session_cls, mock_monotonic):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        svc = VaultService(vault_addr="http://vault:8200", vault_token="old-token")
        svc._token_renewable = True
        svc._token_expire_time = 100.0  # expires at t=100

        mock_monotonic.return_value = 85.0  # 15s remaining — should renew (< 30s)
        mock_session.post.return_value = _vault_response(
            200, auth={"client_token": "new-token", "lease_duration": 3600}
        )

        svc.renew_token()

        mock_session.post.assert_called_once()
        assert svc._vault_token == "new-token"

    @patch("services.vault_service.time.monotonic")
    @patch("services.vault_service.requests.Session")
    def test_no_renewal_when_plenty_of_time(self, mock_session_cls, mock_monotonic):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        svc = VaultService(vault_addr="http://vault:8200", vault_token="token")
        svc._token_renewable = True
        svc._token_expire_time = 100.0

        mock_monotonic.return_value = 50.0  # 50s remaining — no renewal needed
        svc.renew_token()

        mock_session.post.assert_not_called()


# ---------------------------------------------------------------------------
# Vault Enterprise namespaces (AC7)
# ---------------------------------------------------------------------------

class TestVaultEnterprise:
    """Test Vault Enterprise namespace support."""

    @patch("services.vault_service.requests.Session")
    def test_namespace_from_credential_ref(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "ns-secret"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        result = svc.get_secret("vault:team-a/secret/data/app#token")

        assert result == "ns-secret"
        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Namespace"] == "team-a"

    @patch("services.vault_service.requests.Session")
    def test_global_namespace_env(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t", vault_namespace="global-ns")
        svc.get_secret("vault:secret/data/app#token")

        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Namespace"] == "global-ns"

    @patch("services.vault_service.requests.Session")
    def test_credential_ref_namespace_overrides_global(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t", vault_namespace="global-ns")
        svc.get_secret("vault:override-ns/secret/data/app#token")

        headers = mock_session.get.call_args[1]["headers"]
        assert headers["X-Vault-Namespace"] == "override-ns"

    @patch("services.vault_service.requests.Session")
    def test_no_namespace_header_for_open_source(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "val"})

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        svc.get_secret("vault:secret/data/app#token")

        headers = mock_session.get.call_args[1]["headers"]
        assert "X-Vault-Namespace" not in headers


# ---------------------------------------------------------------------------
# Error handling (AC8)
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Test error scenarios."""

    @patch("services.vault_service.requests.Session")
    def test_404_not_found(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(404)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultSecretNotFoundError, match="Secret not found"):
            svc.get_secret("vault:secret/data/missing#key")

    @patch("services.vault_service.requests.Session")
    def test_403_forbidden(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(403)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultAccessDeniedError, match="Access denied"):
            svc.get_secret("vault:secret/data/forbidden#key")

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_500_internal_error(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(500)

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultUnavailableError, match="HTTP 500"):
            svc.get_secret("vault:secret/data/app#key")

        assert mock_session.get.call_count == 3  # 3 retries

    @patch("services.vault_service.time.sleep")
    @patch("services.vault_service.requests.Session")
    def test_timeout_exhausted(self, mock_session_cls, mock_sleep):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.Timeout("timeout")

        svc = VaultService(vault_addr="http://vault:8200", vault_token="t")
        with pytest.raises(VaultUnavailableError, match="connection error"):
            svc.get_secret("vault:secret/data/app#key")

        assert mock_session.get.call_count == 3


# ---------------------------------------------------------------------------
# Integration: build_auth_headers with VaultService (AC2, Task 7)
# ---------------------------------------------------------------------------

class TestAdapterIntegration:
    """Test adapters/utils.py Vault resolution."""

    def test_build_auth_headers_vault_ref(self):
        """Vault credential_ref is resolved via VaultService."""
        from adapters.utils import build_auth_headers

        integration = MagicMock()
        integration.auth_flow = "token"
        integration.credential_ref = "vault:secret/data/platform/aap#token"
        integration.id = 1
        integration.secret_service_id = None

        with patch("services.vault_service.get_vault_service") as mock_get:
            mock_svc = MagicMock()
            mock_get.return_value = mock_svc
            mock_svc.get_secret.return_value = "resolved-token-abc"

            headers = build_auth_headers(integration, correlation_id="req-1")

        assert headers == {"Authorization": "Bearer resolved-token-abc"}
        mock_svc.get_secret.assert_called_once_with("vault:secret/data/platform/aap#token", "req-1")

    def test_build_auth_headers_direct_token(self):
        """Non-Vault credential_ref is used directly (backward compat)."""
        from adapters.utils import build_auth_headers

        integration = MagicMock()
        integration.auth_flow = "pat"
        integration.credential_ref = "direct-token-xyz"
        integration.id = 2
        integration.secret_service_id = None

        headers = build_auth_headers(integration)
        assert headers == {"Authorization": "Bearer direct-token-xyz"}

    def test_build_auth_headers_vault_basic(self):
        """Vault resolved credential used with basic auth."""
        from adapters.utils import build_auth_headers

        integration = MagicMock()
        integration.auth_flow = "basic"
        integration.credential_ref = "vault:secret/data/platform/tower#creds"
        integration.id = 3
        integration.secret_service_id = None

        with patch("services.vault_service.get_vault_service") as mock_get:
            mock_svc = MagicMock()
            mock_get.return_value = mock_svc
            mock_svc.get_secret.return_value = "admin:password123"

            headers = build_auth_headers(integration, correlation_id="req-2")

        import base64
        expected = base64.b64encode(b"admin:password123").decode()
        assert headers == {"Authorization": f"Basic {expected}"}


# ---------------------------------------------------------------------------
# Singleton (get_vault_service)
# ---------------------------------------------------------------------------

class TestSingleton:
    """Test module-level singleton."""

    @patch("services.vault_service.requests.Session")
    def test_get_vault_service_returns_same_instance(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        import services.vault_service as vs
        vs._vault_service = None  # Reset singleton

        with patch.dict("os.environ", {"VAULT_TOKEN": "test"}, clear=False):
            svc1 = vs.get_vault_service()
            svc2 = vs.get_vault_service()

        assert svc1 is svc2

        vs._vault_service = None  # Clean up


# ---------------------------------------------------------------------------
# Multi-instance registry (get_vault_service_for_integration)
# ---------------------------------------------------------------------------

class TestVaultServiceRegistry:
    """Test multi-instance VaultService registry."""

    @patch("services.vault_service.requests.Session")
    def test_registry_returns_same_instance_for_same_id(self, mock_session_cls):
        mock_session_cls.return_value = MagicMock()

        import services.vault_service as vs
        vs._vault_service_registry.clear()

        with patch.dict("os.environ", {"VAULT_TOKEN": "test"}, clear=False):
            svc1 = vs.get_vault_service_for_integration(
                vault_addr="http://vault:8200",
                instance_id="42",
            )
            svc2 = vs.get_vault_service_for_integration(
                vault_addr="http://vault:8200",
                instance_id="42",
            )

        assert svc1 is svc2
        vs._vault_service_registry.clear()

    @patch("services.vault_service.requests.Session")
    def test_registry_creates_different_instance_for_different_id(self, mock_session_cls):
        mock_session_cls.return_value = MagicMock()

        import services.vault_service as vs
        vs._vault_service_registry.clear()

        with patch.dict("os.environ", {"VAULT_TOKEN": "test"}, clear=False):
            svc1 = vs.get_vault_service_for_integration(
                vault_addr="http://vault-a:8200",
                instance_id="1",
            )
            svc2 = vs.get_vault_service_for_integration(
                vault_addr="http://vault-b:8200",
                instance_id="2",
            )

        assert svc1 is not svc2
        assert svc1.instance_id == "1"
        assert svc2.instance_id == "2"
        vs._vault_service_registry.clear()

    @patch("services.vault_service.requests.Session")
    def test_registry_cache_persists_across_calls(self, mock_session_cls):
        """Verify the bug fix: cache entries persist because VaultService is reused."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.return_value = _vault_response(200, {"token": "cached-val"})

        import services.vault_service as vs
        vs._vault_service_registry.clear()

        with patch.dict("os.environ", {"VAULT_TOKEN": "test"}, clear=False):
            svc = vs.get_vault_service_for_integration(
                vault_addr="http://vault:8200",
                instance_id="99",
            )
            # First call: cache miss → Vault call
            svc.get_secret("vault:secret/data/app#token")
            assert mock_session.get.call_count == 1

            # Get same instance again (simulates next request)
            svc2 = vs.get_vault_service_for_integration(
                vault_addr="http://vault:8200",
                instance_id="99",
            )
            # Second call: cache hit → no Vault call
            svc2.get_secret("vault:secret/data/app#token")
            assert mock_session.get.call_count == 1  # Still 1

        vs._vault_service_registry.clear()


# ---------------------------------------------------------------------------
# warmup_vault_cache
# ---------------------------------------------------------------------------

class TestWarmupVaultCache:
    """Test warmup_vault_cache pre-loading."""

    @staticmethod
    def _make_mock_qs(rows: list) -> MagicMock:
        """Crée un mock QuerySet supportant .count() et __iter__ (VAULT-LOW-02)."""
        mock_qs = MagicMock()
        mock_qs.count.return_value = len(rows)
        mock_qs.__iter__ = MagicMock(return_value=iter(rows))
        return mock_qs

    @patch("adapters.utils.resolve_credential")
    def test_warmup_resolves_vault_credentials(self, mock_resolve):
        """warmup_vault_cache calls resolve_credential for each vault: integration."""
        from collections import namedtuple

        Row = namedtuple("Row", ["id", "credential_ref", "secret_service_id"])
        rows = [
            Row(id=1, credential_ref="vault:secret/data/app1#token", secret_service_id=None),
            Row(id=2, credential_ref="vault:secret/data/app2#password", secret_service_id=None),
        ]

        with patch("integrations.models.Integration") as MockIntegration:
            MockIntegration.objects.filter.return_value.exclude.return_value.values_list.return_value = self._make_mock_qs(rows)

            from services.vault_service import warmup_vault_cache
            stats = warmup_vault_cache()

        assert stats["total"] == 2
        assert stats["ok"] == 2
        assert stats["errors"] == 0
        assert mock_resolve.call_count == 2

    @patch("adapters.utils.resolve_credential")
    def test_warmup_deduplicates_same_credential_ref(self, mock_resolve):
        """Duplicate credential_ref + secret_service_id are skipped."""
        from collections import namedtuple

        Row = namedtuple("Row", ["id", "credential_ref", "secret_service_id"])
        rows = [
            Row(id=1, credential_ref="vault:secret/data/shared#token", secret_service_id=None),
            Row(id=2, credential_ref="vault:secret/data/shared#token", secret_service_id=None),
            Row(id=3, credential_ref="vault:secret/data/other#key", secret_service_id=None),
        ]

        with patch("integrations.models.Integration") as MockIntegration:
            MockIntegration.objects.filter.return_value.exclude.return_value.values_list.return_value = self._make_mock_qs(rows)

            from services.vault_service import warmup_vault_cache
            stats = warmup_vault_cache()

        assert stats["total"] == 3
        assert stats["ok"] == 2
        assert stats["skipped"] == 1
        assert mock_resolve.call_count == 2

    @patch("adapters.utils.resolve_credential", side_effect=Exception("vault down"))
    def test_warmup_continues_on_error(self, mock_resolve):
        """Warmup is best-effort: errors are counted but don't stop processing."""
        from collections import namedtuple

        Row = namedtuple("Row", ["id", "credential_ref", "secret_service_id"])
        rows = [
            Row(id=1, credential_ref="vault:secret/data/app1#token", secret_service_id=None),
            Row(id=2, credential_ref="vault:secret/data/app2#token", secret_service_id=None),
        ]

        with patch("integrations.models.Integration") as MockIntegration:
            MockIntegration.objects.filter.return_value.exclude.return_value.values_list.return_value = self._make_mock_qs(rows)

            from services.vault_service import warmup_vault_cache
            stats = warmup_vault_cache()

        assert stats["total"] == 2
        assert stats["errors"] == 2
        assert stats["ok"] == 0

    def test_warmup_no_integrations(self):
        """No vault integrations → early return with zero counts."""
        with patch("integrations.models.Integration") as MockIntegration:
            MockIntegration.objects.filter.return_value.exclude.return_value.values_list.return_value = self._make_mock_qs([])

            from services.vault_service import warmup_vault_cache
            stats = warmup_vault_cache()

        assert stats["total"] == 0
