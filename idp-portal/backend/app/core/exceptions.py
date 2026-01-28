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
