"""
Custom exceptions and exception handler for DRF.
Story M.8 - Task 5: Enhanced error handling with structured logging.
"""

from __future__ import annotations

from typing import Any, Union, cast

import structlog

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class NotFoundError(Exception):
    """Exception for 404 Not Found errors."""
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class BadRequestError(Exception):
    """Exception for 400 Bad Request errors."""
    def __init__(self, code: str = "BAD_REQUEST", message: str = "Bad request", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class InvalidStateError(Exception):
    """Exception for 400 Invalid State errors."""
    def __init__(self, code: str = "INVALID_STATE", message: str = "Invalid state", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class UnauthorizedError(Exception):
    """Exception for 401 Unauthorized errors."""
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "Unauthorized", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ForbiddenError(Exception):
    """Exception for 403 Forbidden errors."""
    def __init__(self, code: str = "FORBIDDEN", message: str = "Forbidden", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ServiceUnavailableError(Exception):
    """Exception for 503 Service Unavailable errors (Story 21.6)."""
    def __init__(self, code: str = "SERVICE_UNAVAILABLE", message: str = "Service unavailable", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConflictError(Exception):
    """Exception for 409 Conflict errors (Story 18.1)."""
    def __init__(self, code: str = "CONFLICT", message: str = "Conflict", details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


# Story 27.6: Vault-specific exceptions
class VaultError(ServiceUnavailableError):
    """Base exception for Vault-related errors."""
    def __init__(self, code: str = "VAULT_ERROR", message: str = "Vault error", details: dict | None = None) -> None:
        super().__init__(code=code, message=message, details=details)


class VaultUnavailableError(VaultError):
    """Vault is unavailable (timeout, 500, 503, circuit breaker open)."""
    def __init__(self, message: str = "Vault unavailable", details: dict | None = None) -> None:
        super().__init__(code="VAULT_UNAVAILABLE", message=message, details=details)


class VaultAuthError(VaultError):
    """Vault authentication failed (invalid token, AppRole login failure)."""
    def __init__(self, message: str = "Vault authentication failed", details: dict | None = None) -> None:
        super().__init__(code="VAULT_AUTH_ERROR", message=message, details=details)


class VaultSecretNotFoundError(VaultError):
    """Secret not found in Vault (404)."""
    def __init__(self, message: str = "Vault secret not found", details: dict | None = None) -> None:
        super().__init__(code="VAULT_SECRET_NOT_FOUND", message=message, details=details)


class VaultAccessDeniedError(VaultError):
    """Access denied to Vault secret (403)."""
    def __init__(self, message: str = "Vault access denied", details: dict | None = None) -> None:
        super().__init__(code="VAULT_ACCESS_DENIED", message=message, details=details)


# Keys whose values must not be exposed in HTTP responses (can leak token URLs, internal hostnames, etc.)
_SENSITIVE_DETAIL_KEYS = frozenset({
    "token_url", "base_url", "vault_addr", "secret_service_id",
    "credential_ref", "client_secret", "access_token", "refresh_token",
})


def sanitize_exception_details(details: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize exception details before attaching to HTTP response.
    Redacts sensitive keys (token_url, base_url, etc.) to prevent
    information leakage in 4xx/5xx responses. Full details are logged server-side.
    """
    if not details:
        return {}
    sanitized: dict[str, Any] = {}
    sensitive_lower = {k.lower() for k in _SENSITIVE_DETAIL_KEYS}
    for key, value in details.items():
        key_lower = key.lower() if isinstance(key, str) else ""
        if key in _SENSITIVE_DETAIL_KEYS or key_lower in sensitive_lower:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_exception_details(value)
        else:
            sanitized[key] = value
    return sanitized


def _get_request_context(context: dict[str, Any]) -> dict[str, Any]:
    """Extract request context for logging."""
    request = context.get('request')
    if request:
        user_id = None
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = str(request.user.id)
        return {
            'path': request.path,
            'method': request.method,
            'user_id': user_id,
            'correlation_id': get_correlation_id(),
        }
    return {'correlation_id': get_correlation_id()}


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    Custom exception handler that formats errors:
    {
        "error": {
            "code": "NOT_FOUND",
            "message": "Action non trouvée",
            "details": {"action_id": 123}
        }
    }

    Story M.8: Also logs unhandled exceptions with full context and traceback.
    For 500 errors, masks internal details from client but logs full details.
    Adds correlation_id to error response headers.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    request_context = _get_request_context(context)

    # Handle custom exceptions (these are expected, log at warning level with full details)
    _CUSTOM_EXCEPTIONS = (
        (NotFoundError, status.HTTP_404_NOT_FOUND),
        (BadRequestError, status.HTTP_400_BAD_REQUEST),
        (InvalidStateError, status.HTTP_400_BAD_REQUEST),
        (UnauthorizedError, status.HTTP_401_UNAUTHORIZED),
        (ForbiddenError, status.HTTP_403_FORBIDDEN),
        (ServiceUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
        (ConflictError, status.HTTP_409_CONFLICT),
    )
    _CustomExc = Union[
        NotFoundError, BadRequestError, InvalidStateError,
        UnauthorizedError, ForbiddenError, ServiceUnavailableError, ConflictError,
    ]
    for exc_cls, http_status in _CUSTOM_EXCEPTIONS:
        if isinstance(exc, exc_cls):
            cust = cast(_CustomExc, exc)
            logger.warning(
                "handled_exception",
                exception_type=type(cust).__name__,
                code=cust.code,
                message=cust.message,
                details=cust.details,
                **request_context
            )
            sanitized_details = sanitize_exception_details(cust.details)
            resp = Response(
                {
                    "error": {
                        "code": cust.code,
                        "message": cust.message,
                        "details": sanitized_details
                    }
                },
                status=http_status
            )
            resp['X-Correlation-ID'] = request_context.get('correlation_id', '')
            return resp

    # Handle DRF exceptions
    if response is not None:
        # Convert DRF error format to standard error format
        if 'detail' in response.data:
            logger.warning(
                "handled_exception",
                exception_type=type(exc).__name__,
                status_code=response.status_code,
                detail=str(response.data['detail']),
                **request_context
            )
            # Story 13.5: 401 auth failures must use UNAUTHORIZED, not VALIDATION_ERROR
            # Story 17.11: 429 throttled uses THROTTLED error code
            if response.status_code == status.HTTP_401_UNAUTHORIZED:
                error_code = "UNAUTHORIZED"
            elif response.status_code == 429:
                error_code = "THROTTLED"
            else:
                error_code = "VALIDATION_ERROR"
            resp = Response(
                {
                    "error": {
                        "code": error_code,
                        "message": str(response.data['detail']),
                        "details": {}
                    }
                },
                status=response.status_code
            )
            resp['X-Correlation-ID'] = request_context.get('correlation_id', '')
            # Story 17.11: Propagate Retry-After header from DRF throttle response
            if 'Retry-After' in response:
                resp['Retry-After'] = response['Retry-After']
            return resp

        # Handle field validation errors
        if isinstance(response.data, dict) and any(isinstance(v, list) for v in response.data.values()):
            logger.warning(
                "handled_exception",
                exception_type=type(exc).__name__,
                status_code=response.status_code,
                validation_errors=response.data,
                **request_context
            )
            resp = Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "details": response.data
                    }
                },
                status=response.status_code
            )
            resp['X-Correlation-ID'] = request_context.get('correlation_id', '')
            return resp

        # Add correlation_id to any other DRF response
        response['X-Correlation-ID'] = request_context.get('correlation_id', '')
        return response

    # Unhandled exception - log full details but mask from client
    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        exc_info=True,
        **request_context
    )

    # Return generic error message to client (don't expose internal details)
    resp = Response(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {}
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    resp['X-Correlation-ID'] = request_context.get('correlation_id', '')
    return resp
