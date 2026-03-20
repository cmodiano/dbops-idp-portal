"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.service_call_handler.
"""
from executions.app.handlers.service_call_handler import ServiceCallHandler  # noqa: F401

__all__ = ["ServiceCallHandler"]
