"""
Unit tests for RuleEngine.
Story 28.3 — AC5: Tests unitaires RuleEngine dispatch et évaluation.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.interpreters.registry import OutputInterpreterRegistry
from executions.policy_evaluator import PolicyDecision, PolicyEvaluationError
from executions.rule_engine import RuleEngine


# ============================================================================
# Fixtures
# ============================================================================

TERRAFORM_JSON_PLAN = {
    "format_version": "1.2",
    "terraform_version": "1.5.0",
    "resource_changes": [
        {
            "address": "module.db.azurerm_sql_database.main",
            "type": "azurerm_sql_database",
            "change": {
                "actions": ["update"],
                "before": {"sku_name": "S0", "max_size_gb": 10},
                "after": {"sku_name": "S1", "max_size_gb": 20},
            },
        },
    ],
}

AAP_JOB_OUTPUT = {
    "job_id": 12345,
    "status": "failed",
    "failed": True,
    "failed_tasks": [
        {"name": "Install package", "host": "server1"},
    ],
    "changed": 2,
    "changed_hosts": ["server2", "server3"],
}

POLICY_TERRAFORM = {
    "on_step_output": [{
        "when": {"step_type": "terraform_cloud"},
        "policy": {
            "type": "review_if_modified",
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
            ],
            "auto_approve_if_none_match": True,
        },
    }],
}

POLICY_AAP = {
    "on_step_output": [{
        "when": {"step_type": "aap"},
        "policy": {
            "type": "review_if_modified",
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
            ],
            "auto_approve_if_none_match": True,
        },
    }],
}


def _make_step(step_type: str = "terraform_cloud") -> MagicMock:
    step = MagicMock()
    step.id = 1
    step.execution_id = 100
    step.step_type = step_type
    return step


def _make_action(policies: dict | None = None) -> MagicMock:
    action = MagicMock()
    action.id = 10
    action.business_rule_policy_id = None  # Force inline policy path (Story 28.4 FK takes priority)
    action.business_rule_policies = policies
    return action


# ============================================================================
# Tests
# ============================================================================


class TestRuleEngineDispatch:
    """AC5: RuleEngine dispatch by step_type."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_rule_engine_dispatch_terraform(self, _m1: MagicMock, _m2: MagicMock) -> None:
        """step_type=terraform_cloud → TerraformPlanInterpreter called."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert isinstance(decision, PolicyDecision)
        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.aap_output_interpreter.get_correlation_id", return_value="test")
    def test_rule_engine_dispatch_aap(self, _m1: MagicMock, _m2: MagicMock) -> None:
        """step_type=aap → AAPOutputInterpreter called."""
        engine = RuleEngine()
        step = _make_step("aap")
        action = _make_action(POLICY_AAP)

        decision = engine.evaluate(action, step, AAP_JOB_OUTPUT)

        assert isinstance(decision, PolicyDecision)
        # AAP output has failed_tasks but no resource_type matching azurerm_sql_database
        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_rule_engine_unknown_step_type(self, _m: MagicMock) -> None:
        """step_type=unknown with policy → PolicyEvaluationError (no interpreter)."""
        engine = RuleEngine()
        step = _make_step("unknown_platform")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "unknown_platform"},
                "policy": {"type": "review_if_modified", "require_review_if_modified": []},
            }],
        }
        action = _make_action(policy)

        with pytest.raises(PolicyEvaluationError, match="No interpreter registered"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_rule_engine_no_policies_defined(self, _m: MagicMock) -> None:
        """action.business_rule_policies=None → no approval needed."""
        engine = RuleEngine()
        step = _make_step()
        action = _make_action(None)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_rule_engine_matching_criteria(self, _m1: MagicMock, _m2: MagicMock) -> None:
        """artifact matches criteria → require_approval=True."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1
        assert any("sku_name" in str(mc) for mc in decision.matched_criteria)

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_rule_engine_auto_approve(self, _m1: MagicMock, _m2: MagicMock) -> None:
        """no match + auto_approve_if_none_match → require_approval=False."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
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
        }
        action = _make_action(policy)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_rule_engine_logging(self, _m1: MagicMock, _m2: MagicMock) -> None:
        """Verify structlog events: policy_evaluation_started, interpreter_called, policy_decision_made."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action(POLICY_TERRAFORM)

        with patch("executions.rule_engine.logger") as mock_logger:
            engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        log_events = [call.args[0] for call in mock_logger.info.call_args_list]
        assert "policy_evaluation_started" in log_events
        assert "interpreter_called" in log_events
        assert "policy_decision_made" in log_events


class TestRuleEngineRegistry:
    """Test interpreter registry integration."""

    def test_registry_singleton(self) -> None:
        """Registry is a singleton."""
        r1 = OutputInterpreterRegistry.get_instance()
        r2 = OutputInterpreterRegistry.get_instance()
        assert r1 is r2

    def test_registry_list_registered(self) -> None:
        """Default interpreters are registered."""
        registry = OutputInterpreterRegistry.get_instance()
        registered = registry.list_registered()
        assert "terraform_cloud" in registered
        assert "aap" in registered

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_rule_engine_no_interpreter_registered(self, _m: MagicMock) -> None:
        """step_type with no interpreter → PolicyEvaluationError."""
        # Use a fresh registry without registrations
        registry = OutputInterpreterRegistry()
        engine = RuleEngine(registry=registry)
        step = _make_step("terraform_cloud")
        action = _make_action(POLICY_TERRAFORM)

        with pytest.raises(PolicyEvaluationError, match="No interpreter registered"):
            engine.evaluate(action, step, TERRAFORM_JSON_PLAN)
