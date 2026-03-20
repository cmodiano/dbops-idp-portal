"""
Shim de rétrocompatibilité — Story 85.3.
Le module actif est executions.app.command_processor.
"""
from executions.app.command_processor import WorkflowCommandService  # noqa: F401

__all__ = [
    "WorkflowCommandService",
]
