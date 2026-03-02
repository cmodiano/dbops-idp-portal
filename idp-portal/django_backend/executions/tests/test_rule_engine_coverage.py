"""
Coverage tests for executions/rule_engine.py — targeting missing lines to reach ≥90%.
Story 55-3.

Missing lines targeted:
  94, 100, 109, 117, 122, 142-151, 155, 159, 191-195, 223-256,
  270-295, 320-326, 339-345, 360->333, 362-363, 395, 401, 407,
  413, 422, 431, 441, 452->454, 454->456
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.interpreters.base import NormalizedArtifact
from executions.policy_evaluator import PolicyDecision, PolicyEvaluationError
from executions.rule_engine import MAX_ATTR_PATHS_PER_CRITERION, MAX_CRITERIA_COUNT, RuleEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
        }
    ],
}


def _make_step(step_type="terraform_cloud"):
    step = MagicMock()
    step.id = 1
    step.execution_id = 100
    step.step_type = step_type
    return step


def _make_action_inline(policies=None):
    """Action using inline business_rule_policies (no FK)."""
    action = MagicMock()
    action.id = 10
    action.business_rule_policy_id = None
    action.business_rule_policies = policies
    return action


def _make_action_fk(policy_id=99, policy_obj=None):
    """Action using FK predefined policy."""
    action = MagicMock()
    action.id = 10
    action.business_rule_policy_id = policy_id
    action.business_rule_policy = policy_obj
    return action


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


# ---------------------------------------------------------------------------
# evaluate — early-exit paths (no policy, no rules, invalid step_type, no match)
# ---------------------------------------------------------------------------

class TestEvaluateEarlyExits:
    """Cover evaluate() early-return paths."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_policies_defined_returns_no_approval(self, _m):
        """Line 89: policies is None → no approval."""
        engine = RuleEngine()
        step = _make_step()
        action = _make_action_inline(None)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_on_step_output_rules_returns_no_approval(self, _m):
        """Line 94: policies has no 'on_step_output' rules."""
        engine = RuleEngine()
        step = _make_step()
        action = _make_action_inline({"on_step_output": []})

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No on_step_output rules defined" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_invalid_step_type_none_returns_no_approval(self, _m):
        """Line 100: step_type is None → no approval."""
        engine = RuleEngine()
        step = _make_step()
        step.step_type = None
        action = _make_action_inline(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "Invalid step_type" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_invalid_step_type_int_returns_no_approval(self, _m):
        """Line 100: step_type is int (not str) → no approval."""
        engine = RuleEngine()
        step = _make_step()
        step.step_type = 42
        action = _make_action_inline(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "Invalid step_type" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_matching_rule_returns_no_approval(self, _m):
        """Line 109: no policy rule matches step_type."""
        engine = RuleEngine()
        step = _make_step("aap")  # No rule for 'aap' in POLICY_TERRAFORM
        action = _make_action_inline(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No policy rule matches step_type" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_policy_missing_type_returns_no_approval(self, _m):
        """Line 117: policy has no 'type' field."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    # 'type' intentionally absent
                    "require_review_if_modified": [],
                }
            }]
        }
        action = _make_action_inline(policy)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "missing required 'type'" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_unsupported_policy_type_returns_no_approval(self, _m):
        """Line 122: unsupported policy type → no approval."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {"type": "unknown_policy_type", "require_review_if_modified": []},
            }]
        }
        action = _make_action_inline(policy)

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "Unsupported policy type" in decision.decision_reason


# ---------------------------------------------------------------------------
# evaluate — interpreter exceptions (lines 142-151)
# ---------------------------------------------------------------------------

class TestEvaluateInterpreterException:
    """Cover the try/except around interpreter.interpret() — lines 142-151."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_interpreter_exception_is_reraised(self, _m):
        """Lines 142-151: interpreter raises → logged and re-raised."""
        mock_interpreter = MagicMock()
        mock_interpreter.interpret.side_effect = ValueError("bad output")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)
        step = _make_step("terraform_cloud")
        action = _make_action_inline(POLICY_TERRAFORM)

        with pytest.raises(ValueError, match="bad output"):
            engine.evaluate(action, step, TERRAFORM_JSON_PLAN)


# ---------------------------------------------------------------------------
# evaluate — artifact type validation (lines 155, 159)
# ---------------------------------------------------------------------------

class TestEvaluateArtifactTypeValidation:
    """Cover artifact type validation after interpreter call."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_interpreter_returns_non_artifact_raises(self, _m):
        """Line 155: interpreter returns something other than NormalizedArtifact."""
        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = "not_an_artifact"

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)
        step = _make_step("terraform_cloud")
        action = _make_action_inline(POLICY_TERRAFORM)

        with pytest.raises(PolicyEvaluationError, match="returned invalid type"):
            engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_artifact_changes_not_list_raises(self, _m):
        """Line 159: artifact.changes is not a list."""
        mock_interpreter = MagicMock()
        # Build a NormalizedArtifact but override 'changes' with non-list
        # NormalizedArtifact is frozen dataclass, so use object with wrong type
        bad_artifact = MagicMock(spec=NormalizedArtifact)
        bad_artifact.changes = "not_a_list"
        mock_interpreter.interpret.return_value = bad_artifact

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)
        step = _make_step("terraform_cloud")
        action = _make_action_inline(POLICY_TERRAFORM)

        with pytest.raises(PolicyEvaluationError, match="must be a list"):
            engine.evaluate(action, step, TERRAFORM_JSON_PLAN)


# ---------------------------------------------------------------------------
# evaluate — no match without auto_approve (lines 191-195)
# ---------------------------------------------------------------------------

class TestEvaluateNoMatchNoAutoApprove:
    """Lines 191-195: no criteria match and auto_approve_if_none_match is False."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_no_match_no_auto_approve(self, _m1, _m2):
        """Lines 191-195: no criteria matched and auto_approve=False → warning logged."""
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
                    "auto_approve_if_none_match": False,
                },
            }],
        }
        action = _make_action_inline(policy)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "does not auto-approve" in decision.decision_reason


# ---------------------------------------------------------------------------
# _load_policies — FK predefined policy paths (lines 223-256)
# ---------------------------------------------------------------------------

class TestLoadPoliciesFKPaths:
    """Cover _load_policies FK predefined policy code paths."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_fk_policy_obj_directly_on_action_dict(self, _m):
        """Lines 245-252, 255-256: FK found via action.business_rule_policy attribute (dict)."""
        engine = RuleEngine()
        policy_obj = MagicMock()
        policy_obj.is_active = True
        policy_obj.name = "test policy"
        policy_obj.policy_json = POLICY_TERRAFORM  # already a dict

        action = _make_action_fk(policy_id=99, policy_obj=policy_obj)

        # No rules for step_type will match, but policies are loaded successfully
        step = _make_step("other_type")

        decision = engine.evaluate(action, step, {})

        # Policy loaded from FK; no rule matches step_type "other_type"
        assert decision.require_approval is False

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_fk_policy_inactive_returns_none(self, _m):
        """Lines 236-243: FK policy is inactive → _load_policies returns None."""
        engine = RuleEngine()
        policy_obj = MagicMock()
        policy_obj.is_active = False
        policy_obj.name = "inactive policy"

        action = _make_action_fk(policy_id=99, policy_obj=policy_obj)
        step = _make_step("terraform_cloud")

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_fk_policy_json_falsy_returns_none(self, _m):
        """Line 253-254: FK policy loaded but policy_json is falsy → return None."""
        engine = RuleEngine()
        policy_obj = MagicMock()
        policy_obj.is_active = True
        policy_obj.name = "empty policy"
        policy_obj.policy_json = None  # falsy

        action = _make_action_fk(policy_id=99, policy_obj=policy_obj)
        step = _make_step("terraform_cloud")

        decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason

    @pytest.mark.django_db
    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_fk_policy_not_found_in_db_returns_none(self, _m):
        """Lines 225-234: FK policy_obj=None, DB lookup raises DoesNotExist → None."""
        from catalog.models import BusinessRulePolicy

        engine = RuleEngine()
        # policy_obj=None forces a DB lookup
        action = _make_action_fk(policy_id=99999, policy_obj=None)
        step = _make_step("terraform_cloud")

        # BusinessRulePolicy with id=99999 does not exist in test DB
        with patch.object(
            BusinessRulePolicy.objects,
            "get",
            side_effect=BusinessRulePolicy.DoesNotExist,
        ):
            decision = engine.evaluate(action, step, {})

        assert decision.require_approval is False
        assert "No business rule policies defined" in decision.decision_reason


# ---------------------------------------------------------------------------
# _load_policies — inline string JSON parsing (lines 270-295)
# ---------------------------------------------------------------------------

class TestLoadPoliciesStringParsing:
    """Cover _load_policies with inline string-encoded JSON (lines 270-295)."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_inline_string_json_parsed_successfully(self, _m):
        """Lines 270-284: inline policies given as JSON string → parsed to dict."""
        import json

        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action_inline(json.dumps(POLICY_TERRAFORM))

        # No interpreter for terraform_cloud in this test (no policy match needed —
        # just verifying the JSON gets parsed and the engine proceeds)
        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        # Decision type: approval triggered by matching criteria
        assert isinstance(decision, PolicyDecision)

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_inline_string_json_invalid_raises(self, _m):
        """Lines 285-293: inline policies given as invalid JSON string → PolicyEvaluationError."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action_inline("{this is not valid json")

        with pytest.raises(PolicyEvaluationError, match="Failed to parse"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_inline_string_too_large_raises(self, _m):
        """Lines 272-281: inline string > 1MB → PolicyEvaluationError."""
        from executions.rule_engine import MAX_POLICY_JSON_SIZE

        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        huge_string = "x" * (MAX_POLICY_JSON_SIZE + 1)
        action = _make_action_inline(huge_string)

        with pytest.raises(PolicyEvaluationError, match="exceeds maximum size"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_fk_policy_json_as_string_parsed(self, _m):
        """Lines 270-295: FK policy_json is a JSON string → parsed to dict."""
        import json

        engine = RuleEngine()
        policy_obj = MagicMock()
        policy_obj.is_active = True
        policy_obj.name = "string policy"
        policy_obj.policy_json = json.dumps(POLICY_TERRAFORM)  # string, not dict

        action = _make_action_fk(policy_id=99, policy_obj=policy_obj)
        step = _make_step("terraform_cloud")

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert isinstance(decision, PolicyDecision)


# ---------------------------------------------------------------------------
# _validate_criteria — security limit paths (lines 395, 401, 407, 413, 422, 431, 441)
# ---------------------------------------------------------------------------

class TestValidateCriteria:
    """Cover _validate_criteria edge cases."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_criteria_not_a_list_raises(self, _m):
        """Lines 395: criteria is not a list."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": "not_a_list",  # should be list
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="must be a list"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_too_many_criteria_raises(self, _m):
        """Line 401: criteria count exceeds MAX_CRITERIA_COUNT."""
        criteria = [
            {"resource_type": f"type_{i}"} for i in range(MAX_CRITERIA_COUNT + 1)
        ]
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": criteria,
                },
            }]
        }
        action = _make_action_inline(policy)
        step = _make_step("terraform_cloud")

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="Too many review criteria"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_criterion_not_dict_raises(self, _m):
        """Line 407: individual criterion is not a dict."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": ["not_a_dict"],
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="must be a dict"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_criterion_missing_resource_type_and_attr_paths_raises(self, _m):
        """Line 413: criterion has neither resource_type nor attribute_paths."""
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [{"description": "only description, no keys"}],
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="must have 'resource_type' and/or 'attribute_paths'"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_attribute_paths_not_list_raises(self, _m):
        """Line 422: attribute_paths is not a list."""
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_sql_database", "attribute_paths": "not_a_list"},
                    ],
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="'attribute_paths' must be a list"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_too_many_attribute_paths_raises(self, _m):
        """Line 431: attribute_paths count exceeds MAX_ATTR_PATHS_PER_CRITERION."""
        step = _make_step("terraform_cloud")
        attr_paths = [f"path_{i}" for i in range(MAX_ATTR_PATHS_PER_CRITERION + 1)]
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_sql_database", "attribute_paths": attr_paths},
                    ],
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="too many attribute_paths"):
            engine.evaluate(action, step, {})

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_attribute_path_not_string_raises(self, _m):
        """Line 441: individual attribute_path is not a string."""
        step = _make_step("terraform_cloud")
        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {"resource_type": "azurerm_sql_database", "attribute_paths": [42, "valid"]},
                    ],
                },
            }]
        }
        action = _make_action_inline(policy)

        mock_interpreter = MagicMock()
        mock_interpreter.interpret.return_value = NormalizedArtifact(changes=[])

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)

        with pytest.raises(PolicyEvaluationError, match="must be a string"):
            engine.evaluate(action, step, {})


# ---------------------------------------------------------------------------
# _match_criteria — edge cases in change iteration (lines 320-326, 339-345, 362-363)
# ---------------------------------------------------------------------------

class TestMatchCriteriaEdgeCases:
    """Cover _match_criteria warning paths for malformed data."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_criterion_attr_paths_not_list_logged_and_skipped(self, _m):
        """Lines 320-326: criterion_attr_paths is not a list — logs warning, treated as empty."""
        mock_interpreter = MagicMock()
        # Build artifact with a matching resource type
        artifact = NormalizedArtifact(changes=[
            {"resource_type": "azurerm_sql_database", "resource_address": "db.main", "changed_attributes": ["sku_name"]},
        ])
        mock_interpreter.interpret.return_value = artifact

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_interpreter

        engine = RuleEngine(registry=mock_registry)
        _step = _make_step("terraform_cloud")

        policy = {
            "on_step_output": [{
                "when": {"step_type": "terraform_cloud"},
                "policy": {
                    "type": "review_if_modified",
                    "require_review_if_modified": [
                        {
                            "resource_type": "azurerm_sql_database",
                            # attribute_paths provided to pass validation but will be
                            # replaced with a malformed version via direct engine call
                        },
                    ],
                    "auto_approve_if_none_match": True,
                },
            }]
        }
        _action = _make_action_inline(policy)

        # Use _match_criteria directly to force the non-list attribute_paths path
        artifact_direct = NormalizedArtifact(changes=[
            {
                "resource_type": "azurerm_sql_database",
                "resource_address": "db.main",
                "changed_attributes": ["sku_name"],
            }
        ])
        policy_direct = {
            "require_review_if_modified": [
                {
                    "resource_type": "azurerm_sql_database",
                    "attribute_paths": "not_a_list",  # intentionally malformed — bypasses validation
                },
            ]
        }
        # Call _match_criteria directly (bypasses _validate_criteria)
        any_matched, matched = engine._match_criteria(artifact_direct, policy_direct)

        # With non-list attr_paths treated as empty set, only resource_type check applies
        # resource_type matches, no attr_paths → appended to matched
        assert any_matched is True

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_changed_attributes_not_list_logged_and_treated_as_empty(self, _m):
        """Lines 339-345: changed_attributes is not a list — logged, treated as empty set."""
        engine = RuleEngine()

        artifact = NormalizedArtifact(changes=[
            {
                "resource_type": "azurerm_sql_database",
                "resource_address": "db.main",
                "changed_attributes": "not_a_list",  # malformed
            }
        ])
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
            ]
        }
        any_matched, matched = engine._match_criteria(artifact, policy)

        # changed_attributes treated as empty — intersection with attr_paths is empty → no match
        assert any_matched is False

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_match_resource_type_only_no_attr_paths(self, _m):
        """Lines 362-363: criterion has resource_type but no attribute_paths → match on type."""
        engine = RuleEngine()

        artifact = NormalizedArtifact(changes=[
            {
                "resource_type": "azurerm_sql_database",
                "resource_address": "db.main",
                "changed_attributes": ["sku_name"],
            }
        ])
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database"},  # no attribute_paths
            ]
        }
        any_matched, matched = engine._match_criteria(artifact, policy)

        assert any_matched is True
        assert len(matched) == 1

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_match_when_resource_type_differs(self, _m):
        """type_matches=False → continue, no match."""
        engine = RuleEngine()

        artifact = NormalizedArtifact(changes=[
            {
                "resource_type": "azurerm_postgresql_server",
                "resource_address": "pg.main",
                "changed_attributes": ["sku_name"],
            }
        ])
        policy = {
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database"},
            ]
        }
        any_matched, matched = engine._match_criteria(artifact, policy)

        assert any_matched is False

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    def test_no_match_when_resource_type_none_and_no_attr_match(self, _m):
        """criterion_resource_type None + attr_paths set but no intersection → no match."""
        engine = RuleEngine()

        artifact = NormalizedArtifact(changes=[
            {
                "resource_type": "any_type",
                "resource_address": "res.main",
                "changed_attributes": ["other_attr"],
            }
        ])
        policy = {
            "require_review_if_modified": [
                {"attribute_paths": ["sku_name"]},  # no resource_type, attr doesn't match
            ]
        }
        any_matched, matched = engine._match_criteria(artifact, policy)

        assert any_matched is False


# ---------------------------------------------------------------------------
# _describe_criterion — static method coverage (lines 452->454, 454->456)
# ---------------------------------------------------------------------------

class TestDescribeCriterion:
    """Cover _describe_criterion branches."""

    def test_both_resource_type_and_attr_paths(self):
        criterion = {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]}
        result = RuleEngine._describe_criterion(criterion)
        assert "resource_type=azurerm_sql_database" in result
        assert "attributes=['sku_name']" in result

    def test_only_resource_type(self):
        criterion = {"resource_type": "azurerm_sql_database"}
        result = RuleEngine._describe_criterion(criterion)
        assert "resource_type=azurerm_sql_database" in result

    def test_only_attr_paths(self):
        criterion = {"attribute_paths": ["sku_name", "max_size_gb"]}
        result = RuleEngine._describe_criterion(criterion)
        assert "attributes=" in result

    def test_empty_criterion(self):
        result = RuleEngine._describe_criterion({})
        assert result == "unknown criterion"


# ---------------------------------------------------------------------------
# Full integration: happy path — match and auto-approve
# ---------------------------------------------------------------------------

class TestEvaluateHappyPath:
    """Full evaluate() integration using real interpreters."""

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_matching_criteria_requires_approval(self, _m1, _m2):
        engine = RuleEngine()
        step = _make_step("terraform_cloud")
        action = _make_action_inline(POLICY_TERRAFORM)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1

    @patch("executions.rule_engine.get_correlation_id", return_value="test")
    @patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test")
    def test_auto_approve_when_no_match(self, _m1, _m2):
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
            }]
        }
        action = _make_action_inline(policy)

        decision = engine.evaluate(action, step, TERRAFORM_JSON_PLAN)

        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason
