"""Custom exception hierarchy for IDP Portal."""


class IdpError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(404, code, message, details)


class UnauthorizedError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(401, code, message, details)


class ForbiddenError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(403, code, message, details)


class PlatformError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)


class VaultError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)


class ServiceNowError(IdpError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(502, code, message, details)


class BadRequestError(IdpError):
    """Raised when request is invalid (HTTP 400)."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(400, code, message, details)


class InvalidStateError(IdpError):
    """Raised when resource is in invalid state for operation (HTTP 400)."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(400, code, message, details)


class ServiceUnavailableError(IdpError):
    """Raised when external service is temporarily unavailable (HTTP 503)."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(503, code, message, details)
