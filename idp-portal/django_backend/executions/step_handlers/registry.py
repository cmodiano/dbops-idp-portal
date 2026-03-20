"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.registry.
"""
from executions.app.handlers.registry import (  # noqa: F401
    StepHandlerRegistry,
    step_handler_registry,
)

__all__ = ["StepHandlerRegistry", "step_handler_registry"]
