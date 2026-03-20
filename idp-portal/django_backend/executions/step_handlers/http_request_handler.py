"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.http_request_handler.
"""
from executions.app.handlers.http_request_handler import (  # noqa: F401
    HttpRequestHandler,
    _is_private_ip_literal,
)

__all__ = ["HttpRequestHandler", "_is_private_ip_literal"]
