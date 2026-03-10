"""
Story 28.1: business_rule_policies validation tests (AC7).
Story 39.3: validate_gate_conditions and validate_notification_config tests (AC#1).

Tests for validate_business_rule_policies:
- Valid schema passes
- Missing 'when' key rejected
- Missing 'policy.type' rejected
- Invalid policy data rejected
- null/empty allowed
- Empty on_step_output array allowed

Tests for validate_gate_conditions:
- Not a list raises ValidationError
- Condition not a dict raises error
- Missing 'type' raises error
- 'type' not string raises error
- 'type' invalid raises error
- Negative timeout_hours raises error
- String timeout raises error
- Invalid on_timeout raises error
- Valid complete condition passes
- Empty list passes

Tests for validate_notification_config:
- None passes
- Non-dict raises error
- channels not list raises error
- channel not dict raises error
- Invalid channel type raises error
- enabled not bool raises error
- conditions not list raises error
- Invalid condition raises error
- Teams http webhook raises error
- Teams vault webhook passes
- Teams https webhook passes
- page_individual_enabled not bool raises error
- Valid full config passes
"""
import pytest
from rest_framework.exceptions import ValidationError

from catalog.validators import (
    validate_business_rule_policies,
    validate_gate_conditions,
    validate_notification_config,
)


# --- Valid schema fixture ---
VALID_TERRAFORM_POLICY = {
    "on_step_output": [
        {
            "when": {
                "step_type": "terraform_cloud",
                "output_key": "plan_output"
            },
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {
                        "resource_type": "azurerm_sql_database",
                        "attribute_paths": ["sku_name", "max_size_gb"]
                    },
                    {
                        "resource_type": "azurerm_sql_server"
                    },
                    {
                        "attribute_paths": ["backup_retention_days"]
                    }
                ],
                "auto_approve_if_none_match": True
            }
        }
    ]
}


class TestBusinessRulePoliciesValidSchema:
    """test_business_rule_policies_valid_schema: valid JSON passes validation."""

    def test_valid_terraform_policy(self):
        """Full valid Terraform policy passes validation."""
        validate_business_rule_policies(VALID_TERRAFORM_POLICY)

    def test_valid_minimal_policy(self):
        """Minimal valid policy (resource_type only) passes."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "aap"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "some_resource"}
                        ]
                    }
                }
            ]
        }
        validate_business_rule_policies(value)

    def test_valid_attribute_paths_only(self):
        """Policy with attribute_paths only (no resource_type) passes."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "aap", "output_key": "job_summary"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"attribute_paths": ["failed_tasks"]}
                        ]
                    }
                }
            ]
        }
        validate_business_rule_policies(value)

    def test_valid_multiple_rules(self):
        """Multiple on_step_output rules pass."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                },
                {
                    "when": {"step_type": "aap"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"attribute_paths": ["failed_tasks"]}
                        ]
                    }
                }
            ]
        }
        validate_business_rule_policies(value)


class TestBusinessRulePoliciesInvalidMissingWhen:
    """test_business_rule_policies_invalid_missing_when: error if 'when' missing."""

    def test_missing_when_key(self):
        """Missing 'when' key raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="when"):
            validate_business_rule_policies(value)

    def test_when_not_dict(self):
        """'when' as string raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": "terraform_cloud",
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="when"):
            validate_business_rule_policies(value)

    def test_when_missing_step_type(self):
        """'when' without 'step_type' raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"output_key": "plan_output"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="step_type"):
            validate_business_rule_policies(value)

    def test_step_type_empty_string(self):
        """Empty step_type raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "  "},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="non-empty string"):
            validate_business_rule_policies(value)


class TestBusinessRulePoliciesInvalidMissingPolicyType:
    """test_business_rule_policies_invalid_missing_policy_type: error if policy.type missing."""

    def test_missing_policy_key(self):
        """Missing 'policy' key raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"}
                }
            ]
        }
        with pytest.raises(ValidationError, match="policy"):
            validate_business_rule_policies(value)

    def test_policy_missing_type(self):
        """Policy without 'type' raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="type"):
            validate_business_rule_policies(value)

    def test_policy_invalid_type(self):
        """Unknown policy type raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "unknown_type",
                        "require_review_if_modified": []
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="review_if_modified"):
            validate_business_rule_policies(value)


class TestBusinessRulePoliciesInvalidPolicyData:
    """test_business_rule_policies_invalid_policy_data: error if require_review_if_modified invalid."""

    def test_missing_require_review_if_modified(self):
        """review_if_modified without require_review_if_modified raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "auto_approve_if_none_match": True
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="require_review_if_modified"):
            validate_business_rule_policies(value)

    def test_require_review_not_list(self):
        """require_review_if_modified as dict raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": {"resource_type": "foo"}
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="must be an array"):
            validate_business_rule_policies(value)

    def test_criteria_missing_both_fields(self):
        """Criteria without resource_type nor attribute_paths raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"some_other_field": "value"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="resource_type.*attribute_paths"):
            validate_business_rule_policies(value)

    def test_attribute_paths_not_list(self):
        """attribute_paths as string raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"attribute_paths": "sku_name"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="attribute_paths must be an array"):
            validate_business_rule_policies(value)

    def test_attribute_paths_item_not_string(self):
        """attribute_paths item as int raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"attribute_paths": [123]}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="attribute_paths.*must be a string"):
            validate_business_rule_policies(value)

    def test_auto_approve_not_boolean(self):
        """auto_approve_if_none_match as string raises error."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ],
                        "auto_approve_if_none_match": "true"
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="auto_approve_if_none_match must be a boolean"):
            validate_business_rule_policies(value)


class TestBusinessRulePoliciesNullAllowed:
    """test_business_rule_policies_null_allowed: null or {} passes validation."""

    def test_none_passes(self):
        """None passes validation."""
        validate_business_rule_policies(None)

    def test_empty_dict_passes(self):
        """Empty dict {} passes validation."""
        validate_business_rule_policies({})


class TestBusinessRulePoliciesEmptyArrayAllowed:
    """test_business_rule_policies_empty_array_allowed: on_step_output=[] passes validation."""

    def test_empty_on_step_output_array(self):
        """on_step_output=[] passes validation."""
        validate_business_rule_policies({"on_step_output": []})


class TestBusinessRulePoliciesEdgeCases:
    """Additional edge case tests for robustness."""

    def test_not_dict_raises_error(self):
        """Non-dict value raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a JSON object"):
            validate_business_rule_policies("invalid")

    def test_missing_on_step_output_key(self):
        """Dict without on_step_output raises ValidationError."""
        with pytest.raises(ValidationError, match="on_step_output"):
            validate_business_rule_policies({"other_key": []})

    def test_on_step_output_not_list(self):
        """on_step_output as dict raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an array"):
            validate_business_rule_policies({"on_step_output": {}})

    def test_on_step_output_item_not_dict(self):
        """on_step_output item as string raises ValidationError."""
        with pytest.raises(ValidationError, match="must be an object"):
            validate_business_rule_policies({"on_step_output": ["invalid"]})

    def test_output_key_not_string(self):
        """output_key as int raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud", "output_key": 123},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="output_key must be a string"):
            validate_business_rule_policies(value)

    def test_resource_type_not_string(self):
        """resource_type as int raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": [
                            {"resource_type": 123}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(ValidationError, match="resource_type must be a string"):
            validate_business_rule_policies(value)

    def test_policy_not_dict(self):
        """policy as string raises ValidationError."""
        value = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": "review_if_modified"
                }
            ]
        }
        with pytest.raises(ValidationError, match="policy must be an object"):
            validate_business_rule_policies(value)


# ============================================================================
# Story 39.3: validate_gate_conditions tests (AC#1)
# ============================================================================

class TestValidateGateConditions:
    """Story 39.3: validate_gate_conditions — toutes les branches (AC#1)."""

    def test_not_a_list_raises(self):
        """1.1: entrée non-liste → ValidationError."""
        with pytest.raises(ValidationError, match="must be a list"):
            validate_gate_conditions("invalid")

    def test_condition_not_dict_raises(self):
        """1.2: condition non-dict → erreur accumulée."""
        with pytest.raises(ValidationError):
            validate_gate_conditions(["not_a_dict"])

    def test_missing_type_raises(self):
        """1.3: 'type' manquant → erreur."""
        with pytest.raises(ValidationError, match="required"):
            validate_gate_conditions([{}])

    def test_type_not_string_raises(self):
        """1.4: 'type' non-string → erreur."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_gate_conditions([{"type": 123}])

    def test_invalid_type_raises(self):
        """1.5: 'type' invalide → erreur."""
        with pytest.raises(ValidationError, match="must be one of"):
            validate_gate_conditions([{"type": "invalid_type"}])

    def test_negative_timeout_raises(self):
        """1.6: 'timeout_hours' négatif → erreur."""
        with pytest.raises(ValidationError, match="positive number"):
            validate_gate_conditions([{"type": "maintenance_window", "timeout_hours": -1}])

    def test_string_timeout_raises(self):
        """1.6b: 'timeout_hours' string → erreur."""
        with pytest.raises(ValidationError, match="positive number"):
            validate_gate_conditions([{"type": "maintenance_window", "timeout_hours": "2h"}])

    def test_invalid_on_timeout_raises(self):
        """1.7: 'on_timeout' invalide → erreur."""
        with pytest.raises(ValidationError, match="on_timeout"):
            validate_gate_conditions([{"type": "maintenance_window", "on_timeout": "IGNORE"}])

    def test_valid_complete_condition_passes(self):
        """1.8: cas valide complet → pas d'erreur."""
        validate_gate_conditions([{
            "type": "maintenance_window",
            "timeout_hours": 2.0,
            "on_timeout": "FAIL"
        }])

    def test_empty_list_passes(self):
        """1.9: liste vide → pas d'erreur."""
        validate_gate_conditions([])

    def test_valid_all_types(self):
        """Tous les types valides passent."""
        for gate_type in ('maintenance_window', 'time_window', 'approval_granted', 'target_state'):
            validate_gate_conditions([{"type": gate_type}])

    def test_on_timeout_skip_passes(self):
        """on_timeout='SKIP' est valide."""
        validate_gate_conditions([{"type": "time_window", "on_timeout": "SKIP"}])

    def test_zero_timeout_raises(self):
        """timeout_hours=0 → pas positif → erreur."""
        with pytest.raises(ValidationError, match="positive number"):
            validate_gate_conditions([{"type": "maintenance_window", "timeout_hours": 0}])

    def test_multiple_conditions_one_invalid(self):
        """Plusieurs conditions dont une invalide → erreur."""
        with pytest.raises(ValidationError):
            validate_gate_conditions([
                {"type": "maintenance_window"},
                {"type": "bad_type"},
            ])


# ============================================================================
# Story 39.3: validate_notification_config tests (AC#1)
# ============================================================================

class TestValidateNotificationConfig:
    """Story 39.3: validate_notification_config — toutes les branches (AC#1)."""

    def test_none_passes(self):
        """1.10: None → pas d'erreur."""
        validate_notification_config(None)

    def test_non_dict_raises(self):
        """1.11: non-dict → ValidationError."""
        with pytest.raises(ValidationError, match="objet JSON"):
            validate_notification_config("invalid")

    def test_channels_not_list_raises(self):
        """1.12: channels non-liste → ValidationError."""
        with pytest.raises(ValidationError, match="liste"):
            validate_notification_config({"channels": "email"})

    def test_channel_not_dict_raises(self):
        """1.13: channel non-dict → ValidationError."""
        with pytest.raises(ValidationError):
            validate_notification_config({"channels": ["email"]})

    def test_invalid_channel_type_raises(self):
        """1.14: type invalide → ValidationError."""
        with pytest.raises(ValidationError, match="invalide"):
            validate_notification_config({"channels": [{"type": "sms"}]})

    def test_enabled_not_bool_raises(self):
        """1.15: enabled non-bool → ValidationError."""
        with pytest.raises(ValidationError, match="booléen"):
            validate_notification_config({"channels": [{"type": "email", "enabled": "yes"}]})

    def test_conditions_not_list_raises(self):
        """1.16: conditions non-liste → ValidationError."""
        with pytest.raises(ValidationError, match="liste"):
            validate_notification_config({"channels": [{"type": "email", "conditions": "on_failure"}]})

    def test_invalid_condition_raises(self):
        """1.17: condition invalide → ValidationError."""
        with pytest.raises(ValidationError, match="invalide"):
            validate_notification_config({"channels": [{"type": "email", "conditions": ["on_warning"]}]})

    def test_teams_http_webhook_raises(self):
        """1.18: webhook http (non-https, non vault:) → ValidationError."""
        with pytest.raises(ValidationError, match="https://"):
            validate_notification_config({"channels": [{
                "type": "teams",
                "webhook_url_ref": "http://example.com/hook"
            }]})

    def test_teams_vault_webhook_passes(self):
        """1.19: webhook vault: → pas d'erreur."""
        validate_notification_config({"channels": [{
            "type": "teams",
            "webhook_url_ref": "vault:secret/teams/hook"
        }]})

    def test_teams_https_webhook_passes(self):
        """1.20: webhook https → pas d'erreur."""
        validate_notification_config({"channels": [{
            "type": "teams",
            "webhook_url_ref": "https://outlook.office.com/webhook/test"
        }]})

    def test_page_individual_not_bool_raises(self):
        """1.21: page_individual_enabled non-bool → ValidationError."""
        with pytest.raises(ValidationError, match="booléen"):
            validate_notification_config({"channels": [], "page_individual_enabled": "yes"})

    def test_valid_full_config_passes(self):
        """1.22: config valide complète → pas d'erreur."""
        validate_notification_config({
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_failure", "on_success"]},
                {"type": "teams", "enabled": False, "webhook_url_ref": "vault:secret/teams"},
                {"type": "page_oncall", "conditions": ["always"]},
            ],
            "page_individual_enabled": False
        })

    def test_on_approval_required_condition_passes(self):
        """Story 57.8: on_approval_required est une condition valide."""
        validate_notification_config({
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"]},
            ],
            "page_individual_enabled": False
        })

    def test_no_channels_key_passes(self):
        """Dict sans 'channels' → channels=[]) → pas d'erreur."""
        validate_notification_config({})

    def test_empty_channels_passes(self):
        """channels=[] → pas d'erreur."""
        validate_notification_config({"channels": []})

    def test_teams_empty_webhook_passes(self):
        """webhook_url_ref vide → pas de validation URL → pas d'erreur."""
        validate_notification_config({"channels": [{"type": "teams", "webhook_url_ref": ""}]})

    def test_page_oncall_channel_type_passes(self):
        """AC6 (Epic 56) : type page_oncall → validation passe sans erreur."""
        validate_notification_config({"channels": [{"type": "page_oncall", "conditions": ["on_failure"]}]})
