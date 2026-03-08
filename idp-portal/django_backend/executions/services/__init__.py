"""
executions.services package.

Re-exports ExecutionService and _sanitize_parameters from the shadowed module
(executions/services.py). The package directory shadows the .py file, so we
load it explicitly for backward compatibility.
"""
from __future__ import annotations

import importlib.util
import os

# Load executions/services.py (the module file shadowed by this package)
_executions_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_services_py_path = os.path.join(_executions_dir, "services.py")
_spec = importlib.util.spec_from_file_location(
    "executions._services_module",
    _services_py_path,
)
assert _spec is not None and _spec.loader is not None
_services_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_services_module)

ExecutionService = _services_module.ExecutionService
_sanitize_parameters = _services_module._sanitize_parameters
SchedulingService = _services_module.SchedulingService

__all__ = ["ExecutionService", "_sanitize_parameters", "SchedulingService"]
