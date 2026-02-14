"""
Custom exceptions and exception handler for DRF.
Story M.8 - Task 5: Enhanced error handling with structured logging.
"""

from __future__ import annotations

from typing import Any

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

    # Handle custom exceptions (these are expected, log at warning level)
    if isinstance(exc, NotFoundError):
        logger.warning(
            "handled_exception",
            exception_type="NotFoundError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, BadRequestError):
        logger.warning(
            "handled_exception",
            exception_type="BadRequestError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, InvalidStateError):
        logger.warning(
            "handled_exception",
            exception_type="InvalidStateError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, UnauthorizedError):
        logger.warning(
            "handled_exception",
            exception_type="UnauthorizedError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, ForbiddenError):
        logger.warning(
            "handled_exception",
            exception_type="ForbiddenError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_403_FORBIDDEN
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, ServiceUnavailableError):
        logger.warning(
            "handled_exception",
            exception_type="ServiceUnavailableError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
        return resp

    if isinstance(exc, ConflictError):
        logger.warning(
            "handled_exception",
            exception_type="ConflictError",
            code=exc.code,
            message=exc.message,
            **request_context
        )
        resp = Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_409_CONFLICT
        )
        resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
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
            resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
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
            resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
            return resp

        # Add correlation_id to any other DRF response
        response['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
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
    resp['X-Idp-Request-Id'] = request_context.get('correlation_id', '')
    return resp
