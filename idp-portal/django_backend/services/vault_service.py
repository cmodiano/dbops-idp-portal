"""
VaultService — HashiCorp Vault client with retry, circuit breaker, and cache.

Story 27.6: Centralized Vault secret resolution for all platform adapters.
Supports Vault Open Source and Enterprise (namespaces).
Auth: Token or AppRole. Resilience: retry with exponential backoff,
circuit breaker, thread-safe TTL cache.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

import requests
import structlog
from cachetools import TTLCache

from core.exceptions import (
    VaultAccessDeniedError,
    VaultAuthError,
    VaultSecretNotFoundError,
    VaultUnavailableError,
)

logger = structlog.get_logger(__name__)

# Transient HTTP status codes that trigger retry
_TRANSIENT_STATUS_CODES = frozenset({500, 502, 503})

# Definitive HTTP status codes that must NOT trigger retry
_DEFINITIVE_STATUS_CODES = frozenset({400, 403, 404})

# Regex for parsing credential_ref format
# vault:secret/data/path#key  OR  vault:namespace/secret/data/path#key
_CREDENTIAL_REF_PATTERN = re.compile(
    r"^vault:(?:(?P<namespace>[^/]+)/)?(?P<mount>[^/]+)/data/(?P<path>.+?)(?:#(?P<key>.+))?$"
)


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state."""

    failures: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed | open | half-open
    lock: RLock = field(default_factory=RLock)


class CircuitBreaker:
    """Circuit breaker protecting Vault from cascading failures.

    States:
      - closed: normal operation
      - open: requests rejected immediately (VaultUnavailableError)
      - half-open: single probe request allowed; success → closed, failure → open
    """

    def __init__(self, failure_threshold: int = 5, timeout: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._state = CircuitBreakerState()

    @property
    def state(self) -> str:
        return self._state.state

    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute *func* through circuit breaker logic."""
        # CRIT-1 FIX: Check state WITHOUT holding lock to avoid thread pool exhaustion
        if self._state.state == "open":
            with self._state.lock:
                # Double-check under lock (state could have changed)
                if self._state.state == "open":
                    elapsed = time.monotonic() - self._state.last_failure_time
                    if elapsed > self.timeout:
                        self._state.state = "half-open"
                        logger.info("circuit_breaker_half_open", timeout_elapsed=elapsed)
                    else:
                        # MED-1 FIX: Ensure retry_after_s is never negative
                        retry_after = max(0, self.timeout - elapsed)
                        raise VaultUnavailableError(
                            message="Circuit breaker open — Vault unavailable",
                            details={"failures": self._state.failures, "retry_after_s": retry_after},
                        )

        try:
            result = func(*args, **kwargs)
        except (VaultSecretNotFoundError, VaultAccessDeniedError):
            # Definitive errors do NOT count toward circuit breaker
            raise
        except Exception:
            with self._state.lock:
                self._state.failures += 1
                self._state.last_failure_time = time.monotonic()
                if self._state.failures >= self.failure_threshold:
                    self._state.state = "open"
                    logger.warning(
                        "circuit_breaker_open",
                        failures=self._state.failures,
                        threshold=self.failure_threshold,
                    )
            raise
        else:
            with self._state.lock:
                if self._state.state == "half-open":
                    logger.info("circuit_breaker_closed", previous_failures=self._state.failures)
                self._state.state = "closed"
                self._state.failures = 0
            return result

    def reset(self) -> None:
        """Reset circuit breaker to closed state (for testing)."""
        with self._state.lock:
            self._state.failures = 0
            self._state.last_failure_time = 0.0
            self._state.state = "closed"


@dataclass
class ParsedCredentialRef:
    """Parsed components of a credential_ref."""

    namespace: str | None
    mount: str
    path: str
    key: str | None


class VaultService:
    """HashiCorp Vault client with retry, circuit breaker, and TTL cache.

    Configuration via environment variables:
      - VAULT_ADDR: Vault server URL (default: http://localhost:8200)
      - VAULT_TOKEN: Token auth (takes precedence over AppRole)
      - VAULT_ROLE_ID + VAULT_SECRET_ID: AppRole auth
      - VAULT_NAMESPACE: Default Vault Enterprise namespace (optional)
      - VAULT_CACHE_TTL: Cache TTL in seconds (default: 300)
      - VAULT_TIMEOUT: HTTP request timeout in seconds (default: 10)
      - VAULT_MAX_RETRIES: Max retry attempts (default: 3)
    """

    def __init__(
        self,
        vault_addr: str | None = None,
        vault_token: str | None = None,
        vault_namespace: str | None = None,
        cache_ttl: int | None = None,
        failure_threshold: int = 5,
        circuit_timeout: int = 60,
        instance_id: str | None = None,
    ) -> None:
        # Story 27.11: instance_id for multi-instance cache key isolation
        self.instance_id = instance_id
        _addr: str = vault_addr or os.getenv("VAULT_ADDR", "http://localhost:8200") or ""
        self.vault_addr = _addr.rstrip("/")
        self.vault_namespace = vault_namespace or os.getenv("VAULT_NAMESPACE") or None
        self._vault_token = vault_token or os.getenv("VAULT_TOKEN") or None
        self._token_renewable = False
        self._token_expire_time: float | None = None

        ttl = cache_ttl if cache_ttl is not None else int(os.getenv("VAULT_CACHE_TTL", "300"))
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=1000, ttl=ttl)
        self._cache_lock = RLock()

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            timeout=circuit_timeout,
        )

        self._timeout = int(os.getenv("VAULT_TIMEOUT", "10"))
        self._max_retries = int(os.getenv("VAULT_MAX_RETRIES", "3"))
        self._session = requests.Session()

        # Authenticate if no token provided
        if not self._vault_token:
            self._authenticate_approle()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_secret(self, credential_ref: str, correlation_id: str | None = None) -> Any:
        """Resolve a credential_ref to a Vault secret value.

        Args:
            credential_ref: Vault reference in format ``vault:mount/data/path#key``
                or ``vault:namespace/mount/data/path#key``.
            correlation_id: Request correlation ID for structured logging.

        Returns:
            Secret value (str) if ``#key`` specified, else full secret dict.

        Raises:
            VaultSecretNotFoundError: Secret path does not exist (404).
            VaultAccessDeniedError: Token lacks permissions (403).
            VaultUnavailableError: Vault unreachable or circuit breaker open.
            VaultAuthError: Authentication failure.
            ValueError: Invalid credential_ref format.
        """
        log = logger.bind(credential_ref=credential_ref, correlation_id=correlation_id)

        # HIGH-1 FIX: Renew token before fetching if close to expiry
        self._ensure_token_valid()

        parsed = self._parse_credential_ref(credential_ref)

        # HIGH-3 FIX: Include namespace in cache key to prevent collision
        cache_key = self._build_cache_key(parsed)

        # Check cache first
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                log.debug("vault_cache_hit")
                return cached

        log.debug("vault_cache_miss")

        # Fetch via circuit breaker
        secret_value = self.circuit_breaker.call(
            self._fetch_with_retry, parsed, correlation_id
        )

        # Store in cache
        with self._cache_lock:
            self._cache[cache_key] = secret_value

        log.debug("vault_secret_resolved")
        return secret_value

    def clear_cache(self) -> None:
        """Invalidate all cached secrets."""
        with self._cache_lock:
            self._cache.clear()
        logger.info("vault_cache_cleared")

    def clear_secret(self, credential_ref: str) -> None:
        """Invalidate a specific cached secret.

        HIGH-3 FIX: Parse credential_ref to build correct cache key.
        """
        try:
            parsed = self._parse_credential_ref(credential_ref)
            cache_key = self._build_cache_key(parsed)
            with self._cache_lock:
                self._cache.pop(cache_key, None)
            logger.debug("vault_cache_entry_cleared", credential_ref=credential_ref)
        except ValueError:
            # Invalid credential_ref format — clear by exact string as fallback
            with self._cache_lock:
                self._cache.pop(credential_ref, None)
            logger.warning("vault_cache_entry_cleared_fallback", credential_ref=credential_ref)

    # ------------------------------------------------------------------
    # Credential ref parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_credential_ref(credential_ref: str) -> ParsedCredentialRef:
        """Parse credential_ref into components.

        Supported formats:
          - ``vault:secret/data/path#key``
          - ``vault:secret/data/path`` (returns full secret dict)
          - ``vault:namespace/secret/data/path#key`` (Vault Enterprise)
        """
        match = _CREDENTIAL_REF_PATTERN.match(credential_ref)
        if not match:
            raise ValueError(
                f"Invalid credential_ref format: '{credential_ref}'. "
                "Expected: vault:mount/data/path[#key] or vault:namespace/mount/data/path[#key]"
            )
        return ParsedCredentialRef(
            namespace=match.group("namespace"),
            mount=match.group("mount"),
            path=match.group("path"),
            key=match.group("key"),
        )

    def _build_cache_key(self, parsed: ParsedCredentialRef) -> str:
        """Build cache key including namespace and instance_id to prevent collisions.

        HIGH-3 fix: namespace in key.
        Story 27.11: instance_id in key for multi-instance Vault support.
        """
        instance = self.instance_id or "default"
        ns = parsed.namespace or "__default__"
        key_suffix = f"#{parsed.key}" if parsed.key else ""
        return f"vault:{instance}:{ns}/{parsed.mount}/data/{parsed.path}{key_suffix}"

    # ------------------------------------------------------------------
    # HTTP communication with Vault
    # ------------------------------------------------------------------

    def _build_headers(self, namespace: str | None) -> dict[str, str]:
        """Build HTTP headers for Vault request."""
        if not self._vault_token:
            raise VaultAuthError(
                message="No Vault token available — configure VAULT_TOKEN or VAULT_ROLE_ID/VAULT_SECRET_ID",
            )

        headers = {"X-Vault-Token": self._vault_token}

        # Namespace: credential_ref namespace takes precedence, then global
        effective_namespace = namespace or self.vault_namespace
        if effective_namespace:
            headers["X-Vault-Namespace"] = effective_namespace

        return headers

    def _fetch_with_retry(
        self,
        parsed: ParsedCredentialRef,
        correlation_id: str | None = None,
    ) -> Any:
        """Fetch secret from Vault with exponential backoff retry."""
        url = f"{self.vault_addr}/v1/{parsed.mount}/data/{parsed.path}"
        headers = self._build_headers(parsed.namespace)
        log = logger.bind(
            vault_url=url,
            correlation_id=correlation_id,
            namespace=parsed.namespace or self.vault_namespace,
        )

        last_exception: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                log.debug("vault_request", attempt=attempt + 1, max_retries=self._max_retries)

                response = self._session.get(url, headers=headers, timeout=self._timeout)

                if response.status_code == 200:
                    data = response.json()["data"]["data"]
                    if parsed.key:
                        if parsed.key not in data:
                            raise VaultSecretNotFoundError(
                                message=f"Key '{parsed.key}' not found in secret at '{parsed.path}'",
                                details={"path": parsed.path, "key": parsed.key, "available_keys": list(data.keys())},
                            )
                        return data[parsed.key]
                    return data

                if response.status_code == 404:
                    # MED-2 FIX: Don't leak path/mount details to client (security)
                    raise VaultSecretNotFoundError(
                        message="Secret not found in Vault",
                        details={"credential_ref_format": "vault:mount/data/path#key"},
                    )

                if response.status_code == 403:
                    # MED-2 FIX: Don't leak path/mount details to client (security)
                    raise VaultAccessDeniedError(
                        message="Access denied to Vault secret",
                        details={"hint": "Check token permissions and Vault policy"},
                    )

                if response.status_code in _DEFINITIVE_STATUS_CODES:
                    raise VaultUnavailableError(
                        message=f"Vault returned HTTP {response.status_code}",
                        details={"status_code": response.status_code, "path": parsed.path},
                    )

                # Transient error — retry with backoff
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    last_exception = VaultUnavailableError(
                        message=f"Vault returned HTTP {response.status_code}",
                        details={"status_code": response.status_code, "attempt": attempt + 1},
                    )
                    if attempt < self._max_retries - 1:
                        backoff = 2**attempt
                        log.warning("vault_transient_error_retry", status_code=response.status_code, backoff=backoff)
                        time.sleep(backoff)
                        continue
                    raise last_exception

                # Unexpected status code — treat as transient
                last_exception = VaultUnavailableError(
                    message=f"Vault returned unexpected HTTP {response.status_code}",
                    details={"status_code": response.status_code},
                )
                if attempt < self._max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise last_exception

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exception = VaultUnavailableError(
                    message=f"Vault connection error: {type(exc).__name__}",
                    details={"attempt": attempt + 1, "error": str(exc)},
                )
                if attempt < self._max_retries - 1:
                    backoff = 2**attempt
                    log.warning("vault_connection_error_retry", error=str(exc), backoff=backoff)
                    time.sleep(backoff)
                    continue
                raise last_exception from exc

            except (VaultSecretNotFoundError, VaultAccessDeniedError):
                # Definitive errors — no retry
                raise

        # Should not reach here, but safety net
        raise last_exception or VaultUnavailableError(message="Vault max retries exceeded")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate_approle(self) -> None:
        """Authenticate via AppRole and store client_token."""
        role_id = os.getenv("VAULT_ROLE_ID")
        secret_id = os.getenv("VAULT_SECRET_ID")

        if not role_id or not secret_id:
            logger.debug("vault_no_auth_configured", hint="Set VAULT_TOKEN or VAULT_ROLE_ID+VAULT_SECRET_ID")
            return

        url = f"{self.vault_addr}/v1/auth/approle/login"
        payload = {"role_id": role_id, "secret_id": secret_id}

        try:
            response = self._session.post(url, json=payload, timeout=self._timeout)

            if response.status_code == 200:
                auth_data = response.json().get("auth", {})
                self._vault_token = auth_data.get("client_token")
                self._token_renewable = auth_data.get("renewable", False)
                lease_duration = auth_data.get("lease_duration", 0)
                if lease_duration > 0:
                    self._token_expire_time = time.monotonic() + lease_duration
                logger.info(
                    "vault_approle_auth_success",
                    renewable=self._token_renewable,
                    lease_duration=lease_duration,
                )
            elif response.status_code == 403:
                raise VaultAuthError(
                    message="AppRole authentication failed: access denied",
                    details={"status_code": 403},
                )
            else:
                raise VaultAuthError(
                    message=f"AppRole authentication failed: HTTP {response.status_code}",
                    details={"status_code": response.status_code},
                )

        except requests.exceptions.RequestException as exc:
            raise VaultAuthError(
                message=f"AppRole authentication failed: {exc}",
                details={"error": str(exc)},
            ) from exc

    def _ensure_token_valid(self) -> None:
        """Ensure Vault token is valid, renewing if necessary (HIGH-1 + CRIT-2 fix).

        Called automatically before each get_secret() call.
        Thread-safe token renewal with lock to prevent race conditions.
        """
        if not self._token_renewable or not self._token_expire_time:
            return

        # Renew if less than 30s remaining
        remaining = self._token_expire_time - time.monotonic()
        if remaining > 30:
            return

        # CRIT-2 FIX: Acquire lock for thread-safe token renewal
        with self._cache_lock:
            # Double-check under lock (another thread may have renewed already)
            remaining = self._token_expire_time - time.monotonic()
            if remaining > 30:
                return

            url = f"{self.vault_addr}/v1/auth/token/renew-self"
            headers = {"X-Vault-Token": self._vault_token or ""}

            try:
                response = self._session.post(url, headers=headers, timeout=self._timeout)
                if response.status_code == 200:
                    auth_data = response.json().get("auth", {})
                    self._vault_token = auth_data.get("client_token", self._vault_token)
                    lease_duration = auth_data.get("lease_duration", 0)
                    if lease_duration > 0:
                        self._token_expire_time = time.monotonic() + lease_duration
                    logger.info("vault_token_renewed", lease_duration=lease_duration)
                else:
                    logger.warning("vault_token_renewal_failed", status_code=response.status_code)
            except requests.exceptions.RequestException as exc:
                logger.warning("vault_token_renewal_error", error=str(exc))

    def renew_token(self) -> None:
        """Deprecated: Use _ensure_token_valid() instead.

        Kept for backward compatibility with tests.
        """
        self._ensure_token_valid()


# Module-level singleton
_vault_service: VaultService | None = None
_vault_service_lock = RLock()


def get_vault_service() -> VaultService:
    """Get or create the module-level VaultService singleton."""
    global _vault_service
    if _vault_service is None:
        with _vault_service_lock:
            if _vault_service is None:
                _vault_service = VaultService()
    return _vault_service
