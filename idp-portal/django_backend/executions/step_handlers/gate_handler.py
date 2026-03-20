"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.gate_handler.
"""
from executions.app.handlers.gate_handler import GateHandler  # noqa: F401

__all__ = ["GateHandler"]
