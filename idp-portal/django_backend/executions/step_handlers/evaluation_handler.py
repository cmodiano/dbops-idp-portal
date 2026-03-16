"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.evaluation_handler.
"""
from executions.app.handlers.evaluation_handler import EvaluationHandler  # noqa: F401

__all__ = ["EvaluationHandler"]
