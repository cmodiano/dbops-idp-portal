"""
Unit tests for PolicyEvaluator service.
Story 28.2 — AC8: Tests unitaires PolicyEvaluator.
Story 28.3 — Refactored: PolicyEvaluator delegates to RuleEngine + OutputInterpreters.
Tests updated to target the new architecture while preserving all original assertions.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from executions.interpreters.base import NormalizedArtifact
from executions.interpreters.terraform_plan_interpreter import TerraformPlanInterpreter
from executions.policy_evaluator import (
    PolicyDecision,
    PolicyEvaluationError,
    PolicyEvaluator,
    ResourceChange,
)
from executions.rule_engine import RuleEngine


# ============================================================================
# Test data fixtures
# ============================================================================

SAMPLE_TERRAFORM_JSON_PLAN = {
    "format_version": "1.2",
    "terraform_version": "1.5.0",
    "resource_changes": [
        {
            "address": "module.database.azurerm_sql_database.main",
            "type": "azurerm_sql_database",
            "name": "main",
            "change": {
                "actions": ["update"],
                "before": {
                    "id": "/subscriptions/xxx/databases/mydb",
                    "name": "mydb",
                    "sku_name": "S0",
                    "max_size_gb": 10,
                    "backup_retention_days": 7,
                },
                "after": {
                    "id": "/subscriptions/xxx/databases/mydb",
                    "name": "mydb",
                    "sku_name": "S1",
                    "max_size_gb": 20,
                    "backup_retention_days": 7,
                },
            },
        },
        {
            "address": "azurerm_sql_server.main",
            "type": "azurerm_sql_server",
            "name": "main",
            "change": {
                "actions": ["create"],
                "before": None,
                "after": {
                    "name": "myserver",
                    "version": "12.0",
                },
            },
        },
    ],
}

SAMPLE_TERRAFORM_TEXT_PLAN = """
Terraform will perform the following actions:

  # azurerm_sql_database.main will be updated in-place
  ~ resource "azurerm_sql_database" "main" {
        id   = "/subscriptions/xxx/databases/mydb"
        name = "mydb"
      ~ sku_name = "S0" -> "S1"
      ~ max_size_gb = 10 -> 20
    }

  # azurerm_sql_server.main will be created
  + resource "azurerm_sql_server" "main" {
      + name    = "myserver"
      + version = "12.0"
    }

Plan: 1 to add, 1 to change, 0 to destroy.
"""

SAMPLE_POLICY_REVIEW_IF_MODIFIED = {
    "on_step_output": [
        {
            "when": {"step_type": "terraform_cloud"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {
                        "resource_type": "azurerm_sql_database",
                        "attribute_paths": ["sku_name"],
                    },
                ],
                "auto_approve_if_none_match": False,
            },
        }
    ]
}


TEST_STEP_ID = 1
TEST_EXECUTION_ID = 100
TEST_ACTION_ID = 10


def _make_step(step_type: str = "terraform_cloud") -> MagicMock:
    """Create a mock ExecutionStep."""
    step = MagicMock()
    step.id = TEST_STEP_ID
    step.execution_id = TEST_EXECUTION_ID
    step.step_type = step_type
    step.step_name = "Execute plan"
    return step


def _make_action(business_rule_policies: dict | None = None) -> MagicMock:
    """Create a mock Action."""
    action = MagicMock()
    action.id = TEST_ACTION_ID
    action.business_rule_policies = business_rule_policies
    return action


# ============================================================================
# Task 11: Tests parsing Terraform plan (now via TerraformPlanInterpreter)
# ============================================================================


class TestParseTerraformPlanJSON:
    """AC2: Parsing plan JSON Terraform Cloud format."""

    def test_parse_terraform_plan_json(self) -> None:
        """Valid JSON plan → NormalizedArtifact with correct changes."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            artifact = interpreter.interpret("terraform_cloud", SAMPLE_TERRAFORM_JSON_PLAN)

        assert len(artifact.changes) == 2

        db_change = artifact.changes[0]
        assert db_change["resource_type"] == "azurerm_sql_database"
        assert db_change["actions"] == ["update"]
        assert "sku_name" in db_change["changed_attributes"]
        assert "max_size_gb" in db_change["changed_attributes"]
        assert "backup_retention_days" not in db_change["changed_attributes"]
        assert db_change["resource_address"] == "module.database.azurerm_sql_database.main"

        server_change = artifact.changes[1]
        assert server_change["resource_type"] == "azurerm_sql_server"
        assert server_change["actions"] == ["create"]
        assert "name" in server_change["changed_attributes"]
        assert server_change["resource_address"] == "azurerm_sql_server.main"

    def test_parse_terraform_plan_text_fallback(self) -> None:
        """Text plan → NormalizedArtifact (best-effort)."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            artifact = interpreter.interpret("terraform_cloud", SAMPLE_TERRAFORM_TEXT_PLAN)

        assert len(artifact.changes) == 2
        db_changes = [c for c in artifact.changes if "azurerm_sql_database" in c["resource_type"]]
        assert len(db_changes) == 1
        assert "sku_name" in db_changes[0]["changed_attributes"]

    def test_invalid_plan_format_raises_error(self) -> None:
        """Malformed JSON plan → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            with pytest.raises(PolicyEvaluationError, match="missing 'resource_changes'"):
                interpreter.interpret("terraform_cloud", {"invalid": "data"})

    def test_plan_no_changes_returns_empty_list(self) -> None:
        """Plan with empty resource_changes → empty changes."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            artifact = interpreter.interpret("terraform_cloud", {"resource_changes": []})

        assert artifact.changes == []

    def test_plan_no_op_changes_skipped(self) -> None:
        """No-op changes are filtered out."""
        interpreter = TerraformPlanInterpreter()
        plan = {
            "resource_changes": [
                {
                    "address": "azurerm_resource_group.main",
                    "type": "azurerm_resource_group",
                    "change": {
                        "actions": ["no-op"],
                        "before": {"name": "rg"},
                        "after": {"name": "rg"},
                    },
                },
            ],
        }

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            artifact = interpreter.interpret("terraform_cloud", plan)

        assert artifact.changes == []

    def test_invalid_plan_not_list_raises_error(self) -> None:
        """resource_changes not a list → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            with pytest.raises(PolicyEvaluationError, match="not a list"):
                interpreter.interpret("terraform_cloud", {"resource_changes": "invalid"})

    def test_invalid_plan_type_raises_error(self) -> None:
        """Non-dict, non-str input → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()

        with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
            with pytest.raises(PolicyEvaluationError, match="expected dict or str"):
                interpreter.interpret("terraform_cloud", 12345)  # type: ignore[arg-type]


# ============================================================================
# Task 12: Tests matching criteria (now via RuleEngine)
# ============================================================================


class TestMatchCriteria:
    """AC3: Matching require_review_if_modified criteria."""

    def setup_method(self) -> None:
        self.engine = RuleEngine()
        self.artifact = NormalizedArtifact(
            changes=[
                {
                    "resource_type": "azurerm_sql_database",
                    "actions": ["update"],
                    "changed_attributes": ["sku_name", "max_size_gb"],
                    "resource_address": "module.database.azurerm_sql_database.main",
                },
                {
                    "resource_type": "azurerm_sql_server",
                    "actions": ["create"],
                    "changed_attributes": ["name", "version"],
                    "resource_address": "azurerm_sql_server.main",
                },
            ],
        )

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_match_resource_type_only(self, _mock: MagicMock) -> None:
        """Criterion with resource_type only matches any change of that type."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_server"},
            ],
        }
        matched, criteria = self.engine._match_criteria(self.artifact, policy)
        assert matched is True
        assert len(criteria) == 1
        assert "azurerm_sql_server.main" in criteria[0]["matched_resources"]

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_match_resource_type_and_attributes(self, _mock: MagicMock) -> None:
        """Criterion with resource_type + attribute_paths matches when both match."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
            ],
        }
        matched, criteria = self.engine._match_criteria(self.artifact, policy)
        assert matched is True
        assert len(criteria) == 1
        assert "module.database.azurerm_sql_database.main" in criteria[0]["matched_resources"]

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_match_attribute_paths_only(self, _mock: MagicMock) -> None:
        """Criterion with attribute_paths only matches any resource type."""
        policy = {
            "require_review_if_modified": [
                {"attribute_paths": ["sku_name"]},
            ],
        }
        matched, criteria = self.engine._match_criteria(self.artifact, policy)
        assert matched is True
        assert len(criteria) == 1
        assert "module.database.azurerm_sql_database.main" in criteria[0]["matched_resources"]

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_match_returns_empty(self, _mock: MagicMock) -> None:
        """Criterion that doesn't match any resource → empty matched_criteria."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_postgresql_server"},
            ],
        }
        matched, criteria = self.engine._match_criteria(self.artifact, policy)
        assert matched is False
        assert criteria == []

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_multiple_criteria_match(self, _mock: MagicMock) -> None:
        """Multiple criteria that match → matched_criteria contains all."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
                {"resource_type": "azurerm_sql_server"},
            ],
        }
        matched, criteria = self.engine._match_criteria(self.artifact, policy)
        assert matched is True
        assert len(criteria) == 2

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_resource_type_attribute_no_match(self, _mock: MagicMock) -> None:
        """Resource type matches but attribute doesn't → no match."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["backup_retention_days"]},
            ],
        }
        artifact = NormalizedArtifact(
            changes=[
                {
                    "resource_type": "azurerm_sql_database",
                    "actions": ["update"],
                    "changed_attributes": ["sku_name"],
                    "resource_address": "db.main",
                },
            ],
        )
        matched, criteria = self.engine._match_criteria(artifact, policy)
        assert matched is False


# ============================================================================
# Task 13: Tests decision auto_approve
# ============================================================================


class TestAutoApproveDecision:
    """AC4: Auto-approve decision logic."""

    def setup_method(self) -> None:
        self.evaluator = PolicyEvaluator()

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr-id")
    def test_no_match_auto_approve_true(self, _mock1: MagicMock, _mock2: MagicMock) -> None:
        """No match + auto_approve_if_none_match=true → require_approval=False."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_postgresql_server"},
                    ],
                    "auto_approve_if_none_match": True,
                },
            }],
        })

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason
        assert decision.matched_criteria == []

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr-id")
    def test_no_match_auto_approve_false(self, _mock1: MagicMock, _mock2: MagicMock) -> None:
        """No match + auto_approve_if_none_match=false → require_approval=False + warning logged."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_postgresql_server"},
                    ],
                    "auto_approve_if_none_match": False,
                },
            }],
        })

        with patch("executions.rule_engine.logger") as mock_logger:
            decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "does not auto-approve" in decision.decision_reason
        mock_logger.warning.assert_called()

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr-id")
    def test_match_triggers_approval(self, _mock1: MagicMock, _mock2: MagicMock) -> None:
        """Criterion matches → require_approval=True, matched_criteria non-empty."""
        step = _make_step()
        action = _make_action(SAMPLE_POLICY_REVIEW_IF_MODIFIED)

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1
        assert "Matched" in decision.decision_reason


# ============================================================================
# Task 14: Tests edge cases
# ============================================================================


class TestEdgeCases:
    """AC8: Edge cases and error handling."""

    def setup_method(self) -> None:
        self.evaluator = PolicyEvaluator()

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    def test_no_policies_defined_returns_no_approval(self, _mock: MagicMock) -> None:
        """Action with no business_rule_policies → require_approval=False."""
        step = _make_step()
        action = _make_action(None)

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    def test_policy_empty_on_step_output(self, _mock: MagicMock) -> None:
        """business_rule_policies with empty on_step_output → require_approval=False."""
        step = _make_step()
        action = _make_action({"on_step_output": []})

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No on_step_output rules" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    def test_no_matching_step_type(self, _mock: MagicMock) -> None:
        """Policy rule for different step_type → no approval required."""
        step = _make_step(step_type="servicenow")
        action = _make_action(SAMPLE_POLICY_REVIEW_IF_MODIFIED)

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No policy rule matches" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr-id")
    def test_logging_traces_all_steps(self, _mock1: MagicMock, _mock2: MagicMock) -> None:
        """Verify structlog called for started, interpreter_called, decision_made."""
        step = _make_step()
        action = _make_action(SAMPLE_POLICY_REVIEW_IF_MODIFIED)

        with patch("executions.rule_engine.logger") as mock_logger:
            self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        log_events = [call.args[0] for call in mock_logger.info.call_args_list]
        assert "policy_evaluation_started" in log_events
        assert "interpreter_called" in log_events
        assert "policy_decision_made" in log_events

    def test_validate_criteria_missing_fields(self) -> None:
        """Criterion without resource_type or attribute_paths → ValidationError."""
        engine = RuleEngine()

        with pytest.raises(PolicyEvaluationError, match="must have"):
            engine._validate_criteria([{"invalid": "field"}])

    def test_validate_criteria_not_dict(self) -> None:
        """Non-dict criterion → PolicyEvaluationError."""
        engine = RuleEngine()

        with pytest.raises(PolicyEvaluationError, match="must be a dict"):
            engine._validate_criteria(["not_a_dict"])

    @patch("executions.rule_engine.get_correlation_id", return_value="test-corr-id")
    def test_unsupported_policy_type(self, _mock: MagicMock) -> None:
        """Unsupported policy type → no approval."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "unknown_policy_type",
                },
            }],
        })

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)
        assert decision.require_approval is False
        assert "Unsupported policy type" in decision.decision_reason


# ============================================================================
# PolicyDecision and ResourceChange dataclass tests
# ============================================================================


class TestDataclasses:
    """Verify dataclass structure and serialization."""

    def test_policy_decision_asdict(self) -> None:
        decision = PolicyDecision(
            require_approval=True,
            decision_reason="Test reason",
            matched_criteria=[{"test": "data"}],
        )
        d = asdict(decision)
        assert d["require_approval"] is True
        assert d["decision_reason"] == "Test reason"
        assert d["matched_criteria"] == [{"test": "data"}]

    def test_resource_change_frozen(self) -> None:
        rc = ResourceChange(
            resource_type="test",
            actions=["create"],
            changed_attributes={"attr1"},
            resource_address="test.main",
        )
        with pytest.raises(AttributeError):
            rc.resource_type = "modified"  # type: ignore[misc]

    def test_policy_decision_defaults(self) -> None:
        decision = PolicyDecision(
            require_approval=False,
            decision_reason="No policies",
        )
        assert decision.matched_criteria == []
