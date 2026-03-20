"""
Shim de rétrocompatibilité — Story 85.4.
Le module actif est executions.app.handlers.condition_evaluator.
"""
from executions.app.handlers.condition_evaluator import StepConditionEvaluator  # noqa: F401

__all__ = ["StepConditionEvaluator"]
