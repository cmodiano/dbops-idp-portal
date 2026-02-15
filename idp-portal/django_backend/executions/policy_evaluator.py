"""
PolicyEvaluator service for evaluating business_rule_policies on ExecutionStep output.
Story 28.2: Evaluates policies after step output (e.g., Terraform plan) and determines
whether approval is required or auto-approve.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any

import structlog
from django.utils import timezone

from core.exceptions import BadRequestError
from core.middleware import get_correlation_id

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

    Supports policy type 'review_if_modified' for Terraform Cloud plans:
    - Parses plan (JSON or text fallback) to extract resource changes
    - Matches changes against criteria (resource_type, attribute_paths)
    - Returns PolicyDecision (require_approval or auto-approve)
    """

    def evaluate_policy(
        self,
        execution_step: Any,
        action: Any,
        step_output: dict | str,
    ) -> PolicyDecision:
        """
        Evaluate business_rule_policies for a given step output.

        Args:
            execution_step: ExecutionStep instance
            action: Action instance with business_rule_policies
            step_output: Output from the step (Terraform plan JSON or text)

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

        # No policies defined → no approval required
        policies = getattr(action, 'business_rule_policies', None)
        if not policies:
            decision = PolicyDecision(
                require_approval=False,
                decision_reason="No business rule policies defined",
            )
            logger.info(
                "policy_decision_made",
                require_approval=False,
                decision_reason=decision.decision_reason,
                num_matched_criteria=0,
                correlation_id=correlation_id,
            )
            return decision

        # Handle string (CLOB) or dict — OracleJSONField may return either
        if isinstance(policies, str):
            try:
                policies = json.loads(policies)
            except (ValueError, TypeError) as exc:
                logger.error(
                    "policy_parsing_error",
                    execution_id=execution_id,
                    step_id=step_id,
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                decision = PolicyDecision(
                    require_approval=False,
                    decision_reason="No business rule policies defined",
                )
                logger.info(
                    "policy_decision_made",
                    require_approval=False,
                    decision_reason=decision.decision_reason,
                    num_matched_criteria=0,
                    correlation_id=correlation_id,
                )
                return decision

        # Find matching rule for this step type
        rules = policies.get("on_step_output", [])
        if not rules:
            decision = PolicyDecision(
                require_approval=False,
                decision_reason="No on_step_output rules defined",
            )
            logger.info(
                "policy_decision_made",
                require_approval=False,
                decision_reason=decision.decision_reason,
                num_matched_criteria=0,
                correlation_id=correlation_id,
            )
            return decision

        # Determine step type from execution_step
        step_type = getattr(execution_step, 'step_type', None)

        # Find the first matching rule
        matching_rule = next(
            (r for r in rules if r.get("when", {}).get("step_type") == step_type),
            None,
        )

        if not matching_rule:
            decision = PolicyDecision(
                require_approval=False,
                decision_reason=f"No policy rule matches step_type '{step_type}'",
            )
            logger.info(
                "policy_decision_made",
                require_approval=False,
                decision_reason=decision.decision_reason,
                num_matched_criteria=0,
                correlation_id=correlation_id,
            )
            return decision

        policy = matching_rule.get("policy", {})
        policy_type = policy.get("type")

        if policy_type != "review_if_modified":
            decision = PolicyDecision(
                require_approval=False,
                decision_reason=f"Unsupported policy type: {policy_type}",
            )
            logger.info(
                "policy_decision_made",
                require_approval=False,
                decision_reason=decision.decision_reason,
                num_matched_criteria=0,
                correlation_id=correlation_id,
            )
            return decision

        # Validate criteria
        criteria = policy.get("require_review_if_modified", [])
        self._validate_criteria(criteria)

        # Parse the Terraform plan
        resource_changes = self._parse_terraform_plan(step_output)

        # Match criteria against resource changes
        any_matched, matched_criteria = self._match_criteria(resource_changes, policy)

        # Build decision
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
        else:
            if auto_approve:
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

    def _parse_terraform_plan(self, plan_output: dict | str) -> list[ResourceChange]:
        """
        Parse Terraform plan output (JSON dict or text string).

        Args:
            plan_output: Terraform plan (JSON dict or text string)

        Returns:
            List of ResourceChange extracted from the plan

        Raises:
            PolicyEvaluationError: If the plan format is invalid
        """
        correlation_id = get_correlation_id()

        if isinstance(plan_output, dict):
            changes = self._parse_json_plan(plan_output)
        elif isinstance(plan_output, str):
            logger.warning(
                "terraform_plan_text_fallback_used",
                correlation_id=correlation_id,
            )
            changes = self._parse_text_plan(plan_output)
        else:
            raise PolicyEvaluationError(
                message=f"Invalid Terraform plan format: expected dict or str, got {type(plan_output).__name__}",
            )

        logger.info(
            "terraform_plan_parsed",
            num_resource_changes=len(changes),
            correlation_id=correlation_id,
        )

        return changes

    def _parse_json_plan(self, plan: dict) -> list[ResourceChange]:
        """Parse Terraform Cloud JSON plan format."""
        try:
            if "resource_changes" not in plan:
                raise PolicyEvaluationError(
                    message="Invalid Terraform plan format: missing 'resource_changes'",
                )

            raw_changes = plan["resource_changes"]
            if not isinstance(raw_changes, list):
                raise PolicyEvaluationError(
                    message="Invalid Terraform plan format: 'resource_changes' is not a list",
                )

            resource_changes: list[ResourceChange] = []
            for rc in raw_changes:
                if not isinstance(rc, dict):
                    continue

                actions = rc.get("change", {}).get("actions", [])

                # Skip no-op changes
                if actions == ["no-op"]:
                    continue

                resource_type = rc.get("type", "")
                address = rc.get("address", "")

                # Calculate changed attributes
                before = rc.get("change", {}).get("before") or {}
                after = rc.get("change", {}).get("after") or {}

                changed_attrs: set[str] = set()
                for key in set(before.keys()) | set(after.keys()):
                    if before.get(key) != after.get(key):
                        changed_attrs.add(key)

                resource_changes.append(ResourceChange(
                    resource_type=resource_type,
                    actions=actions,
                    changed_attributes=changed_attrs,
                    resource_address=address,
                ))

            return resource_changes

        except PolicyEvaluationError:
            raise
        except (KeyError, TypeError) as exc:
            raise PolicyEvaluationError(
                message=f"Invalid Terraform plan format: {exc}",
            ) from exc

    def _parse_text_plan(self, plan_text: str) -> list[ResourceChange]:
        """
        Parse Terraform plan text format (fallback / best-effort).

        Patterns matched:
        - Resource blocks: '# <type>.<name> will be <action>'
        - Attribute changes: '~ attr = "old" -> "new"' or '+ attr' or '- attr'
        """
        resource_changes: list[ResourceChange] = []

        # Pattern: # resource_type.name will be created/updated/destroyed
        resource_pattern = re.compile(
            r'#\s+([\w.]+)\s+will be\s+(\w+)',
        )

        # Pattern: attribute changes (~ + -)
        attr_pattern = re.compile(
            r'^\s+[~+-]\s+(\w+)\s+',
            re.MULTILINE,
        )

        # Split into resource blocks
        blocks = re.split(r'(?=\s*#\s+\S+\s+will be)', plan_text)

        for block in blocks:
            resource_match = resource_pattern.search(block)
            if not resource_match:
                continue

            full_address = resource_match.group(1)
            action_text = resource_match.group(2).lower()

            # Extract resource_type from address (handle modules: module.X.type.name → type)
            # MED-2 FIX: Improved extraction for Terraform modules
            parts = full_address.rsplit('.', 1)
            if len(parts) > 1:
                # Remove 'module.X.' prefix if present
                resource_type = parts[0]
                if 'module.' in resource_type:
                    # Extract last component before .name (the actual resource type)
                    type_parts = resource_type.split('.')
                    # Find last non-module part (e.g., azurerm_sql_database)
                    for i in range(len(type_parts) - 1, -1, -1):
                        if not type_parts[i].startswith('module'):
                            resource_type = type_parts[i]
                            break
            else:
                resource_type = full_address

            # Map text action to Terraform actions
            action_map = {
                'created': ['create'],
                'updated': ['update'],
                'destroyed': ['delete'],
                'replaced': ['create', 'delete'],
            }
            actions = action_map.get(action_text, [action_text])

            # Extract changed attributes
            changed_attrs: set[str] = set()
            for attr_match in attr_pattern.finditer(block):
                changed_attrs.add(attr_match.group(1))

            resource_changes.append(ResourceChange(
                resource_type=resource_type,
                actions=actions,
                changed_attributes=changed_attrs,
                resource_address=full_address,
            ))

        return resource_changes

    def _match_criteria(
        self,
        resource_changes: list[ResourceChange],
        policy: dict,
    ) -> tuple[bool, list[dict]]:
        """
        Match require_review_if_modified criteria against resource changes.

        Returns:
            tuple[bool, list[dict]]: (any_matched, matched_criteria details)
        """
        correlation_id = get_correlation_id()
        criteria = policy.get("require_review_if_modified", [])
        matched_criteria: list[dict] = []

        for idx, criterion in enumerate(criteria):
            criterion_resource_type = criterion.get("resource_type")
            criterion_attr_paths = criterion.get("attribute_paths", [])

            matched_resources: list[str] = []

            for rc in resource_changes:
                type_matches = (
                    criterion_resource_type is None
                    or rc.resource_type == criterion_resource_type
                )

                if not type_matches:
                    continue

                if criterion_attr_paths:
                    # Must have at least one matching attribute
                    attr_set = set(criterion_attr_paths)
                    if attr_set & rc.changed_attributes:
                        matched_resources.append(rc.resource_address)
                elif criterion_resource_type:
                    # Resource type only — any change counts
                    matched_resources.append(rc.resource_address)
                else:
                    # Neither specified — skip (invalid criterion)
                    continue

            if matched_resources:
                description = self._describe_criterion(criterion)
                # MED-3 FIX: Ensure criterion is JSON-serializable (convert sets to lists)
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
        """Validate require_review_if_modified criteria format."""
        if not isinstance(criteria, list):
            raise PolicyEvaluationError(
                message="Invalid business_rule_policies: require_review_if_modified must be a list",
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
            # CRIT-2 FIX: Validate attribute_paths is a list if present
            if has_attr_paths and not isinstance(criterion["attribute_paths"], list):
                raise PolicyEvaluationError(
                    message=(
                        f"Invalid business_rule_policies: criterion at index {idx} "
                        "'attribute_paths' must be a list"
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
