"""
Custom exceptions and exception handler for DRF to match FastAPI error format.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


class NotFoundError(Exception):
    """Exception for 404 Not Found errors."""
    def __init__(self, code="NOT_FOUND", message="Resource not found", details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class BadRequestError(Exception):
    """Exception for 400 Bad Request errors."""
    def __init__(self, code="BAD_REQUEST", message="Bad request", details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class InvalidStateError(Exception):
    """Exception for 400 Invalid State errors."""
    def __init__(self, code="INVALID_STATE", message="Invalid state", details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class UnauthorizedError(Exception):
    """Exception for 401 Unauthorized errors."""
    def __init__(self, code="UNAUTHORIZED", message="Unauthorized", details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ForbiddenError(Exception):
    """Exception for 403 Forbidden errors."""
    def __init__(self, code="FORBIDDEN", message="Forbidden", details=None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that formats errors like FastAPI:
    {
        "error": {
            "code": "NOT_FOUND",
            "message": "Action non trouvée",
            "details": {"action_id": 123}
        }
    }
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Handle custom exceptions
    if isinstance(exc, NotFoundError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )
    
    if isinstance(exc, BadRequestError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if isinstance(exc, InvalidStateError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if isinstance(exc, UnauthorizedError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    if isinstance(exc, ForbiddenError):
        return Response(
            {
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details
                }
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Handle DRF exceptions
    if response is not None:
        # Convert DRF error format to FastAPI format
        if 'detail' in response.data:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(response.data['detail']),
                        "details": {}
                    }
                },
                status=response.status_code
            )
        
        # Handle field validation errors
        if isinstance(response.data, dict) and any(isinstance(v, list) for v in response.data.values()):
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation failed",
                        "details": response.data
                    }
                },
                status=response.status_code
            )
    
    return response
