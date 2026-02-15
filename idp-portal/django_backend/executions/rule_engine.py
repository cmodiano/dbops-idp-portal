"""
RuleEngine — Generic business rule evaluation engine.

Dispatches step output to the appropriate OutputInterpreter based on step_type,
then evaluates business_rule_policies against the normalized artifact.

Story 28.3: Replaces platform-specific logic in PolicyEvaluator with an
extensible interpreter-based architecture.

SECURITY NOTES:
- JSON parsing limited to 1MB to prevent memory exhaustion attacks
- Criteria count limited to 100 to prevent CPU exhaustion
- Type validation on all interpreter outputs and policy fields
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

import structlog

from core.middleware import get_correlation_id
from executions.interpreters.base import NormalizedArtifact
from executions.interpreters.registry import OutputInterpreterRegistry
from executions.policy_evaluator import PolicyDecision, PolicyEvaluationError

logger = structlog.get_logger(__name__)

# Security limits to prevent DoS attacks
MAX_POLICY_JSON_SIZE = 1_000_000  # 1MB limit for business_rule_policies CLOB
MAX_CRITERIA_COUNT = 100  # Maximum number of review criteria per policy
MAX_ATTR_PATHS_PER_CRITERION = 50  # Maximum attribute_paths per criterion


class PolicyType(str, Enum):
    """Supported policy types for business rule evaluation."""
    REVIEW_IF_MODIFIED = "review_if_modified"


class RuleEngine:
    """
    Generic rule engine that dispatches step output to interpreters
    and evaluates policies on the resulting artifact.
    """

    def __init__(self, registry: OutputInterpreterRegistry | None = None) -> None:
        self._registry = registry or OutputInterpreterRegistry.get_instance()

    def evaluate(
        self,
        action: Any,
        execution_step: Any,
        step_output: dict | str,
    ) -> PolicyDecision:
        """
        Evaluate business_rule_policies for a step output.

        1. Load policies from action.business_rule_policies
        2. Find rule matching execution_step.step_type
        3. Dispatch to registered OutputInterpreter
        4. Evaluate policy on normalized artifact
        5. Return PolicyDecision

        Args:
            action: Action instance with business_rule_policies
            execution_step: ExecutionStep instance
            step_output: Raw step output (JSON dict or text)

        Returns:
            PolicyDecision with require_approval, decision_reason, matched_criteria
        """
        correlation_id = get_correlation_id()
        execution_id = getattr(execution_step, 'execution_id', None)
        step_id = getattr(execution_step, 'id', None)
        action_id = getattr(action, 'id', None)

        logger.info(
            "policy_evaluation_started",
            execution_id=execution_id,
            step_id=step_id,
            action_id=action_id,
            correlation_id=correlation_id,
        )

        # 1. Load policies
        policies = self._load_policies(action)
        if policies is None:
            return self._no_approval("No business rule policies defined", correlation_id)

        # 2. Find matching rule
        rules = policies.get("on_step_output", [])
        if not rules:
            return self._no_approval("No on_step_output rules defined", correlation_id)

        step_type = getattr(execution_step, 'step_type', None)

        # Validate step_type is not None/empty
        if not step_type or not isinstance(step_type, str):
            return self._no_approval(
                f"Invalid step_type: {step_type!r} (must be non-empty string)", correlation_id,
            )

        matching_rule = next(
            (r for r in rules if r.get("when", {}).get("step_type") == step_type),
            None,
        )
        if not matching_rule:
            return self._no_approval(
                f"No policy rule matches step_type '{step_type}'", correlation_id,
            )

        policy = matching_rule.get("policy", {})
        policy_type = policy.get("type")

        if not policy_type:
            return self._no_approval(
                "Policy is missing required 'type' field", correlation_id,
            )

        if policy_type != PolicyType.REVIEW_IF_MODIFIED.value:
            return self._no_approval(
                f"Unsupported policy type: {policy_type}", correlation_id,
            )

        # 3. Dispatch to interpreter
        interpreter = self._registry.get(step_type)
        if interpreter is None:
            raise PolicyEvaluationError(
                message=f"No interpreter registered for step_type '{step_type}'",
            )

        logger.info(
            "interpreter_called",
            step_type=step_type,
            interpreter_class=type(interpreter).__name__,
            correlation_id=correlation_id,
        )

        try:
            artifact = interpreter.interpret(step_type, step_output)
        except Exception as exc:
            logger.error(
                "interpreter_failed",
                step_type=step_type,
                interpreter_class=type(interpreter).__name__,
                error=str(exc),
                correlation_id=correlation_id,
            )
            raise

        # Validate interpreter returned correct type
        if not isinstance(artifact, NormalizedArtifact):
            raise PolicyEvaluationError(
                message=f"Interpreter {type(interpreter).__name__} returned invalid type {type(artifact).__name__}, expected NormalizedArtifact",
            )
        if not isinstance(artifact.changes, list):
            raise PolicyEvaluationError(
                message=f"NormalizedArtifact.changes must be a list, got {type(artifact.changes).__name__}",
            )

        # 4. Evaluate policy on artifact
        criteria = policy.get("require_review_if_modified", [])
        self._validate_criteria(criteria)

        any_matched, matched_criteria = self._match_criteria(artifact, policy)

        # 5. Build decision
        auto_approve = policy.get("auto_approve_if_none_match", False)

        if any_matched:
            decision_reason = (
                f"Matched {len(matched_criteria)} review criteria: "
                + ", ".join(
                    mc.get("description", "unknown")
                    for mc in matched_criteria
                )
            )
            decision = PolicyDecision(
                require_approval=True,
                decision_reason=decision_reason,
                matched_criteria=matched_criteria,
            )
        elif auto_approve:
            decision = PolicyDecision(
                require_approval=False,
                decision_reason="Auto-approved: no review criteria matched",
            )
        else:
            decision = PolicyDecision(
                require_approval=False,
                decision_reason="No review criteria matched, policy does not auto-approve",
            )
            logger.warning(
                "policy_no_match_no_auto_approve",
                execution_id=execution_id,
                step_id=step_id,
                correlation_id=correlation_id,
            )

        logger.info(
            "policy_decision_made",
            require_approval=decision.require_approval,
            decision_reason=decision.decision_reason,
            num_matched_criteria=len(decision.matched_criteria),
            correlation_id=correlation_id,
        )

        return decision

    def _load_policies(self, action: Any) -> dict | None:
        """Load and parse business_rule_policies from action.

        Security: JSON parsing limited to MAX_POLICY_JSON_SIZE to prevent memory exhaustion.
        """
        correlation_id = get_correlation_id()
        policies = getattr(action, 'business_rule_policies', None)
        if not policies:
            return None

        if isinstance(policies, str):
            # Security: Check size before parsing to prevent memory exhaustion attacks
            if len(policies) > MAX_POLICY_JSON_SIZE:
                logger.error(
                    "policy_json_too_large",
                    size=len(policies),
                    max_size=MAX_POLICY_JSON_SIZE,
                    correlation_id=correlation_id,
                )
                raise PolicyEvaluationError(
                    message=f"business_rule_policies exceeds maximum size of {MAX_POLICY_JSON_SIZE} bytes (got {len(policies)})",
                )

            try:
                policies = json.loads(policies)
            except (ValueError, TypeError) as exc:
                logger.error(
                    "policy_json_parse_failed",
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                # Re-raise to surface configuration errors instead of silently returning None
                raise PolicyEvaluationError(
                    message=f"Failed to parse business_rule_policies JSON: {exc}",
                ) from exc

        return policies  # type: ignore[return-value]

    def _match_criteria(
        self,
        artifact: NormalizedArtifact,
        policy: dict,
    ) -> tuple[bool, list[dict]]:
        """
        Match require_review_if_modified criteria against artifact changes.

        Works generically on NormalizedArtifact.changes — each change dict
        should have 'resource_type' and/or 'changed_attributes' keys.

        Security: Type validation on all fields to prevent wrong policy decisions.
        """
        correlation_id = get_correlation_id()
        criteria = policy.get("require_review_if_modified", [])
        matched_criteria: list[dict] = []

        for idx, criterion in enumerate(criteria):
            criterion_resource_type = criterion.get("resource_type")
            criterion_attr_paths = criterion.get("attribute_paths", [])

            # Validate criterion_attr_paths is a list of strings
            if not isinstance(criterion_attr_paths, list):
                logger.warning(
                    "criterion_attr_paths_not_list",
                    criterion_index=idx,
                    type=type(criterion_attr_paths).__name__,
                    correlation_id=correlation_id,
                )
                criterion_attr_paths = []

            # Convert to set once before loop for performance
            criterion_attr_paths_set = set(criterion_attr_paths) if criterion_attr_paths else set()

            matched_resources: list[str] = []

            for change in artifact.changes:
                resource_type = change.get("resource_type", "")
                raw_changed_attributes = change.get("changed_attributes", [])

                # Security: Validate changed_attributes is a list to prevent type coercion exploits
                if not isinstance(raw_changed_attributes, list):
                    logger.warning(
                        "changed_attributes_not_list",
                        resource_address=change.get("resource_address"),
                        type=type(raw_changed_attributes).__name__,
                        correlation_id=correlation_id,
                    )
                    changed_attributes = set()
                else:
                    changed_attributes = set(raw_changed_attributes)

                resource_address = change.get("resource_address", "unknown")

                type_matches = (
                    criterion_resource_type is None
                    or resource_type == criterion_resource_type
                )

                if not type_matches:
                    continue

                if criterion_attr_paths_set:
                    if criterion_attr_paths_set & changed_attributes:
                        matched_resources.append(resource_address)
                elif criterion_resource_type:
                    matched_resources.append(resource_address)

            if matched_resources:
                description = self._describe_criterion(criterion)
                serializable_criterion = {
                    k: (list(v) if isinstance(v, (set, frozenset)) else v)
                    for k, v in criterion.items()
                }
                matched_criteria.append({
                    "criteria_index": idx,
                    "criterion": serializable_criterion,
                    "matched_resources": matched_resources,
                    "description": description,
                })

                logger.info(
                    "policy_criteria_matched",
                    criteria_index=idx,
                    resource_type=criterion_resource_type,
                    matched_resources=matched_resources,
                    correlation_id=correlation_id,
                )

        return bool(matched_criteria), matched_criteria

    def _validate_criteria(self, criteria: list) -> None:
        """Validate require_review_if_modified criteria format.

        Security: Enforces MAX_CRITERIA_COUNT and MAX_ATTR_PATHS_PER_CRITERION
        to prevent CPU exhaustion attacks.
        """
        if not isinstance(criteria, list):
            raise PolicyEvaluationError(
                message="Invalid business_rule_policies: require_review_if_modified must be a list",
            )

        # Security: Limit criteria count to prevent CPU exhaustion
        if len(criteria) > MAX_CRITERIA_COUNT:
            raise PolicyEvaluationError(
                message=f"Too many review criteria: {len(criteria)}, maximum allowed is {MAX_CRITERIA_COUNT}",
            )

        for idx, criterion in enumerate(criteria):
            if not isinstance(criterion, dict):
                raise PolicyEvaluationError(
                    message=f"Invalid business_rule_policies: criterion at index {idx} must be a dict",
                )
            has_resource_type = "resource_type" in criterion
            has_attr_paths = "attribute_paths" in criterion
            if not has_resource_type and not has_attr_paths:
                raise PolicyEvaluationError(
                    message=(
                        f"Invalid business_rule_policies: criterion at index {idx} "
                        "must have 'resource_type' and/or 'attribute_paths'"
                    ),
                )
            if has_attr_paths:
                attr_paths = criterion["attribute_paths"]
                if not isinstance(attr_paths, list):
                    raise PolicyEvaluationError(
                        message=(
                            f"Invalid business_rule_policies: criterion at index {idx} "
                            "'attribute_paths' must be a list"
                        ),
                    )

                # Security: Limit attribute_paths count to prevent CPU exhaustion
                if len(attr_paths) > MAX_ATTR_PATHS_PER_CRITERION:
                    raise PolicyEvaluationError(
                        message=(
                            f"Criterion {idx} has too many attribute_paths: {len(attr_paths)}, "
                            f"maximum allowed is {MAX_ATTR_PATHS_PER_CRITERION}"
                        ),
                    )

                # Validate all attribute_paths are strings
                for attr_idx, attr_path in enumerate(attr_paths):
                    if not isinstance(attr_path, str):
                        raise PolicyEvaluationError(
                            message=(
                                f"Criterion {idx} attribute_paths[{attr_idx}] must be a string, "
                                f"got {type(attr_path).__name__}"
                            ),
                        )

    @staticmethod
    def _describe_criterion(criterion: dict) -> str:
        """Build a human-readable description of a criterion."""
        parts: list[str] = []
        if "resource_type" in criterion:
            parts.append(f"resource_type={criterion['resource_type']}")
        if "attribute_paths" in criterion:
            parts.append(f"attributes={criterion['attribute_paths']}")
        return ", ".join(parts) if parts else "unknown criterion"

    def _no_approval(self, reason: str, correlation_id: str) -> PolicyDecision:
        """Return a no-approval PolicyDecision with logging."""
        decision = PolicyDecision(
            require_approval=False,
            decision_reason=reason,
        )
        logger.info(
            "policy_decision_made",
            require_approval=False,
            decision_reason=reason,
            num_matched_criteria=0,
            correlation_id=correlation_id,
        )
        return decision
