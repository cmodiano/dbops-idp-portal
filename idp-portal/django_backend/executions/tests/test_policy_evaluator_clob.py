"""
Additional tests for PolicyEvaluator — Oracle CLOB string handling.
Code review fix MED-4: Test business_rule_policies as CLOB string.
Story 28.3: Updated mock paths for RuleEngine architecture.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from executions.policy_evaluator import PolicyEvaluationError, PolicyEvaluator
from executions.rule_engine import RuleEngine


SAMPLE_TERRAFORM_JSON_PLAN = {
    "format_version": "1.2",
    "resource_changes": [
        {
            "address": "azurerm_sql_database.main",
            "type": "azurerm_sql_database",
            "change": {
                "actions": ["update"],
                "before": {"sku_name": "S0"},
                "after": {"sku_name": "S1"},
            },
        },
    ],
}


def _make_step(step_type: str = "terraform_cloud") -> MagicMock:
    """Create a mock ExecutionStep."""
    step = MagicMock()
    step.id = 1
    step.execution_id = 100
    step.step_type = step_type
    return step


def _make_action(business_rule_policies: dict | str | None = None) -> MagicMock:
    """Create a mock Action."""
    action = MagicMock()
    action.id = 10
    action.business_rule_policies = business_rule_policies
    return action


class TestPolicyEvaluatorCLOB:
    """MED-4 FIX: Test CLOB string handling (Oracle OracleJSONField)."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr-id")
    def test_evaluate_policy_with_clob_string_valid(self, _mock1: MagicMock, _mock2: MagicMock) -> None:
        """business_rule_policies as CLOB string (valid JSON) → parsed correctly."""
        policy_dict = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
                        ],
                        "auto_approve_if_none_match": False,
                    },
                }
            ]
        }
        policy_clob = json.dumps(policy_dict)

        step = _make_step()
        action = _make_action(policy_clob)

        evaluator = PolicyEvaluator()
        decision = evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    def test_evaluate_policy_with_clob_string_invalid_json(self, _mock: MagicMock) -> None:
        """business_rule_policies as CLOB string (invalid JSON) → no approval."""
        policy_clob = "{ invalid json }"

        step = _make_step()
        action = _make_action(policy_clob)

        evaluator = PolicyEvaluator()
        decision = evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason


class TestValidationAttributePathsType:
    """CRIT-2 FIX: Validate attribute_paths is a list."""

    def test_validate_criteria_attribute_paths_not_list(self) -> None:
        """attribute_paths not a list → PolicyEvaluationError."""
        engine = RuleEngine()
        invalid_criteria = [
            {"resource_type": "azurerm_sql_database", "attribute_paths": "sku_name"}
        ]

        with pytest.raises(PolicyEvaluationError, match="must be a list"):
            engine._validate_criteria(invalid_criteria)

    def test_validate_criteria_attribute_paths_valid_list(self) -> None:
        """attribute_paths as list → validation passes."""
        engine = RuleEngine()
        valid_criteria = [
            {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name", "max_size_gb"]}
        ]

        # Should not raise
        engine._validate_criteria(valid_criteria)
