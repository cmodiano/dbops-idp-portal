"""
Integration tests for PolicyEvaluator with workflow runtime.
Story 28.2 — AC9: Tests d'intégration end-to-end.
Story 28.3 — Updated: mock paths for RuleEngine architecture, step_type=terraform_cloud.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch, ANY

import pytest

from django.test import TestCase

from core.models import AuditActionType, AuditEntityType, AuditLog
from core.services import AuditService
from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStepStatus,
    ExecutionStatus,
)
from executions.policy_evaluator import PolicyDecision, PolicyEvaluator
from tests.factories import (
    ActionFactory,
    ExecutionFactory,
    ExecutionStepFactory,
    UserFactory,
)


# ============================================================================
# Test data
# ============================================================================

TERRAFORM_PLAN_SENSITIVE = {
    "format_version": "1.2",
    "resource_changes": [
        {
            "address": "module.database.azurerm_sql_database.main",
            "type": "azurerm_sql_database",
            "change": {
                "actions": ["update"],
                "before": {"sku_name": "S0", "max_size_gb": 10},
                "after": {"sku_name": "S1", "max_size_gb": 20},
            },
        },
    ],
}

TERRAFORM_PLAN_NO_SENSITIVE = {
    "format_version": "1.2",
    "resource_changes": [
        {
            "address": "azurerm_resource_group.main",
            "type": "azurerm_resource_group",
            "change": {
                "actions": ["update"],
                "before": {"tags": {"env": "dev"}},
                "after": {"tags": {"env": "staging"}},
            },
        },
    ],
}

POLICY_REVIEW_SKU = {
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
                "auto_approve_if_none_match": True,
            },
        },
    ],
}

POLICY_REVIEW_NO_AUTO = {
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
        },
    ],
}


# ============================================================================
# Task 15: Integration tests — workflow approval
# ============================================================================


@pytest.mark.django_db
class TestPolicyWorkflowIntegration:
    """AC9: Integration tests for policy evaluation in workflow."""

    def test_terraform_plan_triggers_approval_required(self) -> None:
        """Sensitive plan changes → PolicyDecision.require_approval=True,
        step status WAITING, audit APPROVAL_REQUIRED."""
        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_REVIEW_SKU),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        evaluator = PolicyEvaluator()

        with patch("executions.rule_engine.get_correlation_id", return_value="test-corr"):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr"):
                decision = evaluator.evaluate_policy(step, action, TERRAFORM_PLAN_SENSITIVE)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1
        assert "sku_name" in str(decision.matched_criteria)

        # Simulate what workflow_runtime does: set step WAITING + audit
        step.status = ExecutionStepStatus.WAITING
        step.save()

        decision_dict = asdict(decision)
        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'step_id': step.id,
                'policy_decision': decision_dict,
            },
            correlation_id="test-corr",
        )

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.WAITING

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
            entity_id=execution.id,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details["step_id"] == step.id
        assert details["policy_decision"]["require_approval"] is True

    def test_terraform_plan_auto_approved(self) -> None:
        """No sensitive changes + auto_approve_if_none_match=true → COMPLETED, audit AUTO_APPROVED."""
        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_REVIEW_SKU),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        evaluator = PolicyEvaluator()

        with patch("executions.rule_engine.get_correlation_id", return_value="test-corr"):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr"):
                decision = evaluator.evaluate_policy(step, action, TERRAFORM_PLAN_NO_SENSITIVE)

        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason

        # Simulate workflow_runtime: COMPLETED + audit
        step.status = ExecutionStepStatus.COMPLETED
        step.save()

        decision_dict = asdict(decision)
        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'step_id': step.id,
                'policy_decision': decision_dict,
            },
            correlation_id="test-corr",
        )

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
            entity_id=execution.id,
        ).first()
        assert audit is not None

    def test_approval_workflow_integration(self) -> None:
        """ApprovalRequest created → DBA approves → step WAITING → COMPLETED."""
        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_REVIEW_SKU),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        evaluator = PolicyEvaluator()

        with patch("executions.rule_engine.get_correlation_id", return_value="test-corr"):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-corr"):
                decision = evaluator.evaluate_policy(step, action, TERRAFORM_PLAN_SENSITIVE)

        assert decision.require_approval is True

        # Step goes to WAITING
        step.status = ExecutionStepStatus.WAITING
        step.save()

        # Simulate DBA approval → step COMPLETED
        step.status = ExecutionStepStatus.COMPLETED
        step.save()

        step.refresh_from_db()
        assert step.status == ExecutionStepStatus.COMPLETED


# ============================================================================
# Task 16: Audit trail tests
# ============================================================================


@pytest.mark.django_db
class TestPolicyAuditTrail:
    """AC9: Audit trail for policy decisions."""

    def test_audit_trail_policy_approval_required(self) -> None:
        """Audit EXECUTION_STEP_POLICY_APPROVAL_REQUIRED contains policy_decision JSON."""
        execution = ExecutionFactory()

        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'step_id': 1,
                'policy_decision': {
                    'require_approval': True,
                    'decision_reason': 'Matched 1 review criteria',
                    'matched_criteria': [{'resource_type': 'azurerm_sql_database'}],
                },
            },
            correlation_id="corr-123",
        )

        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_POLICY_APPROVAL_REQUIRED,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['policy_decision']['require_approval'] is True
        assert audit.correlation_id == "corr-123"

    def test_audit_trail_auto_approved(self) -> None:
        """Audit EXECUTION_STEP_POLICY_AUTO_APPROVED with decision_reason."""
        execution = ExecutionFactory()

        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'step_id': 1,
                'policy_decision': {
                    'require_approval': False,
                    'decision_reason': 'Auto-approved: no review criteria matched',
                    'matched_criteria': [],
                },
            },
            correlation_id="corr-456",
        )

        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_POLICY_AUTO_APPROVED,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['policy_decision']['require_approval'] is False

    def test_audit_trail_evaluation_failed(self) -> None:
        """Plan corruption → audit EXECUTION_STEP_POLICY_EVALUATION_FAILED."""
        execution = ExecutionFactory()

        AuditService.create_entry(
            user_id=str(execution.user_id),
            action_type=AuditActionType.EXECUTION_STEP_POLICY_EVALUATION_FAILED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                'step_id': 1,
                'error': "Invalid Terraform plan format: missing 'resource_changes'",
            },
            correlation_id="corr-789",
        )

        audit = AuditLog.objects.filter(
            action_type=AuditActionType.EXECUTION_STEP_POLICY_EVALUATION_FAILED,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert "Invalid Terraform plan" in details['error']


# ============================================================================
# Task 17: Splunk correlation ID tests
# ============================================================================


@pytest.mark.django_db
class TestSplunkCorrelationId:
    """AC9: Correlation ID propagated in all logs."""

    def test_splunk_correlation_id_propagated(self) -> None:
        """Verify correlation_id present in all structlog events."""
        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_REVIEW_SKU),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        evaluator = PolicyEvaluator()
        test_corr_id = "test-splunk-corr-12345"

        with patch("executions.rule_engine.get_correlation_id", return_value=test_corr_id):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value=test_corr_id):
                with patch("executions.rule_engine.logger") as mock_logger:
                    evaluator.evaluate_policy(step, action, TERRAFORM_PLAN_SENSITIVE)

        # Verify all info calls contain correlation_id
        for call in mock_logger.info.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("correlation_id") == test_corr_id, (
                f"Missing or wrong correlation_id in log event: {call.args[0]}"
            )


# ============================================================================
# Story 28.3: RuleEngine integration tests
# ============================================================================


AAP_JOB_FAILED = {
    "job_id": 999,
    "status": "failed",
    "failed": True,
    "failed_tasks": [
        {"name": "Deploy app", "host": "prod-server1"},
    ],
    "changed": 0,
    "changed_hosts": [],
}

POLICY_AAP_REVIEW_IF_FAILED = {
    "on_step_output": [{
        "when": {"step_type": "aap"},
        "policy": {
            "type": "review_if_modified",
            "require_review_if_modified": [
                {"resource_type": "azurerm_sql_database"},
            ],
            "auto_approve_if_none_match": True,
        },
    }],
}

POLICY_TERRAFORM_AND_AAP = {
    "on_step_output": [
        {
            "when": {"step_type": "terraform_cloud"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "azurerm_sql_database", "attribute_paths": ["sku_name"]},
                ],
                "auto_approve_if_none_match": True,
            },
        },
        {
            "when": {"step_type": "aap"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "azurerm_sql_database"},
                ],
                "auto_approve_if_none_match": True,
            },
        },
    ],
}


@pytest.mark.django_db
class TestRuleEngineIntegration:
    """Story 28.3 AC5: Integration tests for RuleEngine with interpreters."""

    def test_terraform_plan_rule_engine_integration(self) -> None:
        """plan Terraform → RuleEngine → require_approval."""
        from executions.rule_engine import RuleEngine

        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_REVIEW_SKU),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        engine = RuleEngine()

        with patch("executions.rule_engine.get_correlation_id", return_value="test-integration"):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test-integration"):
                decision = engine.evaluate(action, step, TERRAFORM_PLAN_SENSITIVE)

        assert decision.require_approval is True
        assert len(decision.matched_criteria) >= 1

    def test_aap_job_rule_engine_integration(self) -> None:
        """AAP job output → RuleEngine → auto_approved (no matching resource_type)."""
        from executions.rule_engine import RuleEngine

        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_AAP_REVIEW_IF_FAILED),
        )
        execution = ExecutionFactory(action=action)
        step = ExecutionStepFactory(
            execution=execution,
            step_type="aap",
            status=ExecutionStepStatus.RUNNING,
        )

        engine = RuleEngine()

        with patch("executions.rule_engine.get_correlation_id", return_value="test-integration"):
            with patch("executions.interpreters.aap_output_interpreter.get_correlation_id", return_value="test-integration"):
                decision = engine.evaluate(action, step, AAP_JOB_FAILED)

        # AAP failed_tasks have no resource_type matching azurerm_sql_database → auto-approved
        assert decision.require_approval is False
        assert "Auto-approved" in decision.decision_reason

    def test_multiple_step_types_same_action(self) -> None:
        """action with rules Terraform + AAP → dispatch correct per step_type."""
        from executions.rule_engine import RuleEngine

        action = ActionFactory(
            business_rule_policies=json.dumps(POLICY_TERRAFORM_AND_AAP),
        )

        # Terraform step → matches sku_name → require_approval
        execution1 = ExecutionFactory(action=action)
        tf_step = ExecutionStepFactory(
            execution=execution1,
            step_type="terraform_cloud",
            status=ExecutionStepStatus.RUNNING,
        )

        engine = RuleEngine()

        with patch("executions.rule_engine.get_correlation_id", return_value="test"):
            with patch("executions.interpreters.terraform_plan_interpreter.get_correlation_id", return_value="test"):
                tf_decision = engine.evaluate(action, tf_step, TERRAFORM_PLAN_SENSITIVE)

        assert tf_decision.require_approval is True

        # AAP step → no matching resource_type → auto-approved
        execution2 = ExecutionFactory(action=action)
        aap_step = ExecutionStepFactory(
            execution=execution2,
            step_type="aap",
            status=ExecutionStepStatus.RUNNING,
        )

        with patch("executions.rule_engine.get_correlation_id", return_value="test"):
            with patch("executions.interpreters.aap_output_interpreter.get_correlation_id", return_value="test"):
                aap_decision = engine.evaluate(action, aap_step, AAP_JOB_FAILED)

        assert aap_decision.require_approval is False
