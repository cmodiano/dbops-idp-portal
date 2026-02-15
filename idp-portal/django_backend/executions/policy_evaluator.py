"""
PolicyEvaluator service for evaluating business_rule_policies on ExecutionStep output.

Story 28.2: Original implementation with Terraform-specific parsing.
Story 28.3: Refactored to delegate to RuleEngine + OutputInterpreters.
PolicyEvaluator is now a lightweight wrapper around RuleEngine.evaluate().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from core.exceptions import BadRequestError

logger = structlog.get_logger(__name__)


class PolicyEvaluationError(BadRequestError):
    """Exception raised when policy evaluation fails (invalid plan, corrupt data)."""

    def __init__(self, message: str = "Policy evaluation failed", details: dict | None = None) -> None:
        super().__init__(code="POLICY_EVALUATION_ERROR", message=message, details=details)


@dataclass(frozen=True)
class ResourceChange:
    """Represents a single resource change extracted from a Terraform plan."""
    resource_type: str
    actions: list[str]
    changed_attributes: set[str]
    resource_address: str


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a policy evaluation."""
    require_approval: bool
    decision_reason: str
    matched_criteria: list[dict] = field(default_factory=list)


class PolicyEvaluator:
    """
    Evaluate business_rule_policies after an ExecutionStep produces output.

    Story 28.3: Delegates to RuleEngine for interpreter-based evaluation.
    Preserves the same public API (evaluate_policy) for backward compatibility.
    """

    def evaluate_policy(
        self,
        execution_step: Any,
        action: Any,
        step_output: dict | str,
    ) -> PolicyDecision:
        """
        Evaluate business_rule_policies for a given step output.

        Delegates to RuleEngine.evaluate() which dispatches to the appropriate
        OutputInterpreter based on step_type.

        Args:
            execution_step: ExecutionStep instance
            action: Action instance with business_rule_policies
            step_output: Output from the step (JSON or text)

        Returns:
            PolicyDecision with require_approval, decision_reason, matched_criteria
        """
        from executions.rule_engine import RuleEngine

        engine = RuleEngine()
        return engine.evaluate(action, execution_step, step_output)
