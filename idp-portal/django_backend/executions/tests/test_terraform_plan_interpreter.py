"""
Unit tests for TerraformPlanInterpreter.
Story 28.3 — AC5: Tests unitaires TerraformPlanInterpreter.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.interpreters.terraform_plan_interpreter import TerraformPlanInterpreter
from executions.policy_evaluator import PolicyEvaluationError


CORR_PATCH = "executions.interpreters.terraform_plan_interpreter.get_correlation_id"


class TestTerraformPlanInterpreter:
    """AC5: TerraformPlanInterpreter tests."""

    @patch(CORR_PATCH, return_value="test")
    def test_terraform_interpreter_parse_json(self, _m: MagicMock) -> None:
        """plan JSON → artifact with resource_changes."""
        interpreter = TerraformPlanInterpreter()
        plan = {
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

        artifact = interpreter.interpret("terraform_cloud", plan)

        assert len(artifact.changes) == 1
        change = artifact.changes[0]
        assert change["resource_type"] == "azurerm_sql_database"
        assert change["actions"] == ["update"]
        assert "sku_name" in change["changed_attributes"]
        assert "max_size_gb" in change["changed_attributes"]
        assert change["resource_address"] == "module.db.azurerm_sql_database.main"
        assert artifact.metadata["format_version"] == "1.2"
        assert artifact.metadata["terraform_version"] == "1.5.0"

    @patch(CORR_PATCH, return_value="test")
    def test_terraform_interpreter_parse_text_fallback(self, _m: MagicMock) -> None:
        """plan text → artifact best-effort."""
        interpreter = TerraformPlanInterpreter()
        text_plan = """
  # azurerm_sql_database.main will be updated in-place
  ~ resource "azurerm_sql_database" "main" {
      ~ sku_name = "S0" -> "S1"
    }
"""
        artifact = interpreter.interpret("terraform_cloud", text_plan)

        assert len(artifact.changes) >= 1
        assert artifact.changes[0]["resource_type"] == "azurerm_sql_database"
        assert "sku_name" in artifact.changes[0]["changed_attributes"]
        assert artifact.metadata == {}

    @patch(CORR_PATCH, return_value="test")
    def test_terraform_interpreter_no_changes(self, _m: MagicMock) -> None:
        """plan no-op → changes=[]."""
        interpreter = TerraformPlanInterpreter()
        plan = {"resource_changes": []}

        artifact = interpreter.interpret("terraform_cloud", plan)

        assert artifact.changes == []

    @patch(CORR_PATCH, return_value="test")
    def test_terraform_interpreter_invalid_plan(self, _m: MagicMock) -> None:
        """plan corrompu → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()

        with pytest.raises(PolicyEvaluationError, match="missing 'resource_changes'"):
            interpreter.interpret("terraform_cloud", {"invalid": "data"})
