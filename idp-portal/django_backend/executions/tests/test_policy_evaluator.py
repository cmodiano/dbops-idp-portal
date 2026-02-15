"""
Unit tests for PolicyEvaluator service.
Story 28.2 — AC8: Tests unitaires PolicyEvaluator.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from executions.policy_evaluator import (
    PolicyDecision,
    PolicyEvaluationError,
    PolicyEvaluator,
    ResourceChange,
)


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
            "when": {"step_type": "platform"},
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


# LOW-2 FIX: Use constants instead of magic numbers
TEST_STEP_ID = 1
TEST_EXECUTION_ID = 100
TEST_ACTION_ID = 10


def _make_step(step_type: str = "platform") -> MagicMock:
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
# Task 11: Tests parsing Terraform plan
# ============================================================================


class TestParseTerraformPlanJSON:
    """AC2: Parsing plan JSON Terraform Cloud format."""

    def test_parse_terraform_plan_json(self) -> None:
        """Valid JSON plan → list ResourceChange correct."""
        evaluator = PolicyEvaluator()
        changes = evaluator._parse_terraform_plan(SAMPLE_TERRAFORM_JSON_PLAN)

        assert len(changes) == 2

        # First resource: azurerm_sql_database update
        db_change = changes[0]
        assert db_change.resource_type == "azurerm_sql_database"
        assert db_change.actions == ["update"]
        assert "sku_name" in db_change.changed_attributes
        assert "max_size_gb" in db_change.changed_attributes
        assert "backup_retention_days" not in db_change.changed_attributes  # unchanged
        assert db_change.resource_address == "module.database.azurerm_sql_database.main"

        # Second resource: azurerm_sql_server create
        server_change = changes[1]
        assert server_change.resource_type == "azurerm_sql_server"
        assert server_change.actions == ["create"]
        assert "name" in server_change.changed_attributes
        assert server_change.resource_address == "azurerm_sql_server.main"

    def test_parse_terraform_plan_text_fallback(self) -> None:
        """Text plan → list ResourceChange (best-effort)."""
        evaluator = PolicyEvaluator()
        changes = evaluator._parse_terraform_plan(SAMPLE_TERRAFORM_TEXT_PLAN)

        # LOW-3 FIX: Assert exact count instead of >=
        assert len(changes) == 2
        # Should find both resources (database + server)
        db_changes = [c for c in changes if "azurerm_sql_database" in c.resource_type]
        assert len(db_changes) == 1
        assert "sku_name" in db_changes[0].changed_attributes

    def test_invalid_plan_format_raises_error(self) -> None:
        """Malformed JSON plan → PolicyEvaluationError."""
        evaluator = PolicyEvaluator()

        with pytest.raises(PolicyEvaluationError, match="missing 'resource_changes'"):
            evaluator._parse_terraform_plan({"invalid": "data"})

    def test_plan_no_changes_returns_empty_list(self) -> None:
        """Plan with empty resource_changes → empty list."""
        evaluator = PolicyEvaluator()
        changes = evaluator._parse_terraform_plan({"resource_changes": []})
        assert changes == []

    def test_plan_no_op_changes_skipped(self) -> None:
        """No-op changes are filtered out."""
        evaluator = PolicyEvaluator()
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
        changes = evaluator._parse_terraform_plan(plan)
        assert changes == []

    def test_invalid_plan_not_list_raises_error(self) -> None:
        """resource_changes not a list → PolicyEvaluationError."""
        evaluator = PolicyEvaluator()

        with pytest.raises(PolicyEvaluationError, match="not a list"):
            evaluator._parse_terraform_plan({"resource_changes": "invalid"})

    def test_invalid_plan_type_raises_error(self) -> None:
        """Non-dict, non-str input → PolicyEvaluationError."""
        evaluator = PolicyEvaluator()

        with pytest.raises(PolicyEvaluationError, match="expected dict or str"):
            evaluator._parse_terraform_plan(12345)  # type: ignore[arg-type]


# ============================================================================
# Task 12: Tests matching criteria
# ============================================================================


class TestMatchCriteria:
    """AC3: Matching require_review_if_modified criteria."""

    def setup_method(self) -> None:
        self.evaluator = PolicyEvaluator()
        self.resource_changes = [
            ResourceChange(
                resource_type="azurerm_sql_database",
                actions=["update"],
                changed_attributes={"sku_name", "max_size_gb"},
                resource_address="module.database.azurerm_sql_database.main",
            ),
            ResourceChange(
                resource_type="azurerm_sql_server",
                actions=["create"],
                changed_attributes={"name", "version"},
                resource_address="azurerm_sql_server.main",
            ),
        ]

    def test_match_resource_type_only(self) -> None:
        """Criterion with resource_type only matches any change of that type."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_server"},
            ],
        }
        matched, criteria = self.evaluator._match_criteria(self.resource_changes, policy)
        assert matched is True
        assert len(criteria) == 1
        assert "azurerm_sql_server.main" in criteria[0]["matched_resources"]

    def test_match_resource_type_and_attributes(self) -> None:
        """Criterion with resource_type + attribute_paths matches when both match."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
            ],
        }
        matched, criteria = self.evaluator._match_criteria(self.resource_changes, policy)
        assert matched is True
        assert len(criteria) == 1
        assert "module.database.azurerm_sql_database.main" in criteria[0]["matched_resources"]

    def test_match_attribute_paths_only(self) -> None:
        """Criterion with attribute_paths only matches any resource type."""
        policy = {
            "require_review_if_modified": [
                {"attribute_paths": ["sku_name"]},
            ],
        }
        matched, criteria = self.evaluator._match_criteria(self.resource_changes, policy)
        assert matched is True
        assert len(criteria) == 1
        # Should match azurerm_sql_database (has sku_name)
        assert "module.database.azurerm_sql_database.main" in criteria[0]["matched_resources"]

    def test_no_match_returns_empty(self) -> None:
        """Criterion that doesn't match any resource → empty matched_criteria."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_postgresql_server"},
            ],
        }
        matched, criteria = self.evaluator._match_criteria(self.resource_changes, policy)
        assert matched is False
        assert criteria == []

    def test_multiple_criteria_match(self) -> None:
        """Multiple criteria that match → matched_criteria contains all."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
                {"resource_type": "azurerm_sql_server"},
            ],
        }
        matched, criteria = self.evaluator._match_criteria(self.resource_changes, policy)
        assert matched is True
        assert len(criteria) == 2

    def test_resource_type_attribute_no_match(self) -> None:
        """Resource type matches but attribute doesn't → no match."""
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["backup_retention_days"]},
            ],
        }
        # backup_retention_days is NOT in changed_attributes (unchanged)
        resource_changes = [
            ResourceChange(
                resource_type="azurerm_sql_database",
                actions=["update"],
                changed_attributes={"sku_name"},
                resource_address="db.main",
            ),
        ]
        matched, criteria = self.evaluator._match_criteria(resource_changes, policy)
        assert matched is False


# ============================================================================
# Task 13: Tests decision auto_approve
# ============================================================================


class TestAutoApproveDecision:
    """AC4: Auto-approve decision logic."""

    def setup_method(self) -> None:
        self.evaluator = PolicyEvaluator()

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_no_match_auto_approve_true(self, _mock_corr: MagicMock) -> None:
        """No match + auto_approve_if_none_match=true → require_approval=False."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "platform"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_postgresql_server"},
                    ],
                    "auto_approve_if_none_match": True,
                },
            }],
        })

        # Plan has no postgresql changes
        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason
        assert decision.matched_criteria == []

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_no_match_auto_approve_false(self, _mock_corr: MagicMock) -> None:
        """No match + auto_approve_if_none_match=false → require_approval=False + warning logged."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "platform"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_postgresql_server"},
                    ],
                    "auto_approve_if_none_match": False,
                },
            }],
        })

        with patch("executions.policy_evaluator.logger") as mock_logger:
            decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "does not auto-approve" in decision.decision_reason
        mock_logger.warning.assert_called()

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_match_triggers_approval(self, _mock_corr: MagicMock) -> None:
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

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_no_policies_defined_returns_no_approval(self, _mock_corr: MagicMock) -> None:
        """Action with no business_rule_policies → require_approval=False."""
        step = _make_step()
        action = _make_action(None)

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_policy_empty_on_step_output(self, _mock_corr: MagicMock) -> None:
        """business_rule_policies with empty on_step_output → require_approval=False."""
        step = _make_step()
        action = _make_action({"on_step_output": []})

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No on_step_output rules" in decision.decision_reason

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_no_matching_step_type(self, _mock_corr: MagicMock) -> None:
        """Policy rule for different step_type → no approval required."""
        step = _make_step(step_type="servicenow")
        action = _make_action(SAMPLE_POLICY_REVIEW_IF_MODIFIED)  # targets "platform"

        decision = self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No policy rule matches" in decision.decision_reason

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_logging_traces_all_steps(self, _mock_corr: MagicMock) -> None:
        """Verify structlog called for started, parsed, matched, decision_made."""
        step = _make_step()
        action = _make_action(SAMPLE_POLICY_REVIEW_IF_MODIFIED)

        with patch("executions.policy_evaluator.logger") as mock_logger:
            self.evaluator.evaluate_policy(step, action, SAMPLE_TERRAFORM_JSON_PLAN)

        # Check key log events were emitted
        log_events = [call.args[0] for call in mock_logger.info.call_args_list]
        assert "policy_evaluation_started" in log_events
        assert "terraform_plan_parsed" in log_events
        assert "policy_decision_made" in log_events

    def test_validate_criteria_missing_fields(self) -> None:
        """Criterion without resource_type or attribute_paths → ValidationError."""
        evaluator = PolicyEvaluator()

        with pytest.raises(PolicyEvaluationError, match="must have"):
            evaluator._validate_criteria([{"invalid": "field"}])

    def test_validate_criteria_not_dict(self) -> None:
        """Non-dict criterion → PolicyEvaluationError."""
        evaluator = PolicyEvaluator()

        with pytest.raises(PolicyEvaluationError, match="must be a dict"):
            evaluator._validate_criteria(["not_a_dict"])

    @patch("executions.policy_evaluator.get_correlation_id", return_value="test-corr-id")
    def test_unsupported_policy_type(self, _mock_corr: MagicMock) -> None:
        """Unsupported policy type → no approval."""
        step = _make_step()
        action = _make_action({
            "on_step_output": [{
                "when": {"step_type": "platform"},
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
