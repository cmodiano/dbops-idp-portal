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

    @patch(CORR_PATCH, return_value="test")
    def test_interpret_invalid_type_raises(self, _m: MagicMock) -> None:
        """Neither dict nor str → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()

        with pytest.raises(PolicyEvaluationError, match="Invalid Terraform plan format"):
            interpreter.interpret("terraform_cloud", 12345)

    @patch(CORR_PATCH, return_value="test")
    def test_resource_changes_not_a_list_raises(self, _m: MagicMock) -> None:
        """resource_changes not a list → PolicyEvaluationError."""
        interpreter = TerraformPlanInterpreter()
        plan = {"resource_changes": {"not": "a list"}}

        with pytest.raises(PolicyEvaluationError, match="not a list"):
            interpreter.interpret("terraform_cloud", plan)

    @patch(CORR_PATCH, return_value="test")
    def test_non_dict_item_in_resource_changes_is_skipped(self, _m: MagicMock) -> None:
        """Non-dict items inside resource_changes are silently skipped."""
        interpreter = TerraformPlanInterpreter()
        plan = {
            "resource_changes": [
                "not a dict",
                {
                    "address": "aws_instance.web",
                    "type": "aws_instance",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"instance_type": "t3.micro"},
                    },
                },
            ]
        }

        artifact = interpreter.interpret("terraform_cloud", plan)
        assert len(artifact.changes) == 1
        assert artifact.changes[0]["resource_type"] == "aws_instance"

    @patch(CORR_PATCH, return_value="test")
    def test_no_op_resource_changes_are_skipped(self, _m: MagicMock) -> None:
        """Resources with actions=['no-op'] are excluded from changes."""
        interpreter = TerraformPlanInterpreter()
        plan = {
            "resource_changes": [
                {
                    "address": "aws_vpc.main",
                    "type": "aws_vpc",
                    "change": {
                        "actions": ["no-op"],
                        "before": {"cidr_block": "10.0.0.0/16"},
                        "after": {"cidr_block": "10.0.0.0/16"},
                    },
                },
                {
                    "address": "aws_subnet.public",
                    "type": "aws_subnet",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"cidr_block": "10.0.1.0/24"},
                    },
                },
            ]
        }

        artifact = interpreter.interpret("terraform_cloud", plan)
        assert len(artifact.changes) == 1
        assert artifact.changes[0]["resource_type"] == "aws_subnet"

    @patch(CORR_PATCH, return_value="test")
    def test_unchanged_attributes_not_in_changed_attrs(self, _m: MagicMock) -> None:
        """Attributes with same before/after value are not listed as changed."""
        interpreter = TerraformPlanInterpreter()
        plan = {
            "resource_changes": [
                {
                    "address": "aws_instance.app",
                    "type": "aws_instance",
                    "change": {
                        "actions": ["update"],
                        "before": {"instance_type": "t2.micro", "ami": "ami-12345"},
                        "after": {"instance_type": "t3.micro", "ami": "ami-12345"},
                    },
                },
            ]
        }

        artifact = interpreter.interpret("terraform_cloud", plan)
        change = artifact.changes[0]
        assert "instance_type" in change["changed_attributes"]
        assert "ami" not in change["changed_attributes"]

    @patch(CORR_PATCH, return_value="test")
    def test_parse_json_before_none_after_none(self, _m: MagicMock) -> None:
        """before=None and after=None resolve to {} via 'or {}' — no changed_attributes."""
        interpreter = TerraformPlanInterpreter()
        plan = {
            "resource_changes": [
                {
                    "address": "aws_s3_bucket.data",
                    "type": "aws_s3_bucket",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": None,
                    },
                },
            ]
        }

        artifact = interpreter.interpret("terraform_cloud", plan)
        assert len(artifact.changes) == 1
        assert artifact.changes[0]["changed_attributes"] == []

    @patch(CORR_PATCH, return_value="test")
    def test_parse_text_plan_module_resource_type(self, _m: MagicMock) -> None:
        """Text plan with module-prefixed address extracts the resource type correctly."""
        interpreter = TerraformPlanInterpreter()
        text_plan = """
  # module.network.module.subnets.aws_subnet.private will be created
  + resource "aws_subnet" "private" {
      + cidr_block = "10.0.2.0/24"
    }
"""
        artifact = interpreter.interpret("terraform_cloud", text_plan)
        assert len(artifact.changes) >= 1
        # The extracted resource_type should be 'aws_subnet', not the full module path
        assert artifact.changes[0]["resource_type"] == "aws_subnet"

    @patch(CORR_PATCH, return_value="test")
    def test_parse_text_plan_unknown_action_text(self, _m: MagicMock) -> None:
        """Text plan with an unmapped action word uses the raw action text."""
        interpreter = TerraformPlanInterpreter()
        text_plan = """
  # aws_security_group.web will be tainted
  - resource "aws_security_group" "web" {
      - description = "old"
    }
"""
        artifact = interpreter.interpret("terraform_cloud", text_plan)
        assert len(artifact.changes) >= 1
        assert artifact.changes[0]["actions"] == ["tainted"]

    @patch(CORR_PATCH, return_value="test")
    def test_parse_text_plan_address_without_dot(self, _m: MagicMock) -> None:
        """Text plan where full_address has no dot uses the full address as resource_type (else branch)."""
        interpreter = TerraformPlanInterpreter()
        # The regex matches `# <address> will be <action>`.
        # An address like "null_resource" has no dot, so rsplit('.', 1) gives one part.
        text_plan = """
  # null_resource will be created
  + resource "null_resource" "example" {
    }
"""
        artifact = interpreter.interpret("terraform_cloud", text_plan)
        assert len(artifact.changes) >= 1
        assert artifact.changes[0]["resource_address"] == "null_resource"
        assert artifact.changes[0]["resource_type"] == "null_resource"

    @patch(CORR_PATCH, return_value="test")
    def test_parse_text_plan_all_module_parts(self, _m: MagicMock) -> None:
        """Text plan where all type_parts start with 'module' — loop exhausts without break."""
        interpreter = TerraformPlanInterpreter()
        # Address: "module.a.module.b.module" — after rsplit('.', 1) we get
        # parts[0]="module.a.module.b" and parts[1]="module"
        # parts[0] contains 'module.' so we enter the module-extraction block.
        # type_parts = ["module", "a", "module", "b"] — "a" and "b" don't start with 'module'
        # so break will be hit. To avoid break, all parts must start with 'module':
        # address = "module.module.module" → parts[0]="module.module", parts[1]="module"
        # type_parts = ["module", "module"] — all start with "module" → loop ends without break
        text_plan = """
  # module.module.module will be created
  + resource "module" "module" {
    }
"""
        artifact = interpreter.interpret("terraform_cloud", text_plan)
        # It should not crash; result may be empty or have the module entry
        assert isinstance(artifact.changes, list)
