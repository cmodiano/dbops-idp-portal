"""Remediation service for auto-remediation evaluation and triggering (Story 9.3).

Handles:
- Evaluation of auto-trigger conditions (AC1, AC4)
- Triggering auto-remediation executions (AC1, AC2)
- Monitoring remediation results and fallback (AC3)
- DBA notification on failure (AC3)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import structlog

from app.models.catalog import RemediationRule, RiskLevel
from app.models.execution import ExecutionStatus
from app.repositories import audit_repository, catalog_repository, execution_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType

if TYPE_CHECKING:
    from app.models.execution import ExecutionResponse

logger = structlog.get_logger()


class RemediationResult(str, Enum):
    """Result of auto-remediation attempt."""
    SUCCESS = "success"
    FALLBACK_MANUAL = "fallback_manual"


# Story 9.3, AC1: Evaluate if auto-trigger is allowed for a rule


async def evaluate_auto_trigger_allowed(
    execution: "ExecutionResponse",
    rule: RemediationRule,
) -> tuple[bool, str]:
    """Evaluate if auto-remediation can be triggered for this rule (Story 9.3, AC1, AC4).

    Criteria (all must be true):
    1. rule.auto_trigger == True
    2. rule.risk_level == RiskLevel.LOW
    3. execution.environment in rule.environments
    4. If environment == "prod": requires DBA approval (always blocked for auto)

    Args:
        execution: The failed execution
        rule: The remediation rule to evaluate

    Returns:
        Tuple of (allowed: bool, reason: str)
    """
    # Rule 1: Must be marked auto_trigger
    if not rule.auto_trigger:
        reason = "auto_trigger_disabled"
        logger.info(
            "auto_trigger_evaluation_blocked",
            reason=reason,
            execution_id=execution.id,
            rule_error_pattern=rule.error_pattern[:50],
        )
        return False, reason

    # Rule 2: Risk level must be LOW (faible)
    if rule.risk_level != RiskLevel.LOW:
        reason = f"risk_level_too_high ({rule.risk_level.value})"
        logger.info(
            "auto_trigger_evaluation_blocked",
            reason=reason,
            execution_id=execution.id,
            risk_level=rule.risk_level.value,
        )
        return False, reason

    # Rule 3: Environment must be in allowed environments
    env_lower = execution.environment.value.lower() if hasattr(execution.environment, "value") else str(execution.environment).lower()
    allowed_envs_lower = [e.lower() for e in rule.environments]
    if env_lower not in allowed_envs_lower:
        reason = f"environment_not_authorized ({env_lower} not in {rule.environments})"
        logger.info(
            "auto_trigger_evaluation_blocked",
            reason=reason,
            execution_id=execution.id,
            environment=env_lower,
            allowed_environments=rule.environments,
        )
        return False, reason

    # Rule 4: Production ALWAYS requires human approval - no auto-trigger
    if env_lower == "prod":
        reason = "prod_requires_approval"
        logger.warning(
            "auto_trigger_evaluation_blocked",
            reason=reason,
            execution_id=execution.id,
            environment=env_lower,
        )
        return False, reason

    logger.info(
        "auto_trigger_evaluation_allowed",
        execution_id=execution.id,
        target_action_id=rule.target_action_id,
        risk_level=rule.risk_level.value,
        environment=env_lower,
    )
    return True, "allowed"


# Story 9.3, AC1, AC2: Trigger auto-remediation


async def trigger_auto_remediation(
    parent_exec: "ExecutionResponse",
    rule: RemediationRule,
    correlation_id: str | None = None,
) -> "ExecutionResponse | None":
    """Trigger auto-remediation by creating a child execution (Story 9.3, AC1, AC2).

    Creates an execution with:
    - user_id = 0 (SYSTEM)
    - parent_execution_id = parent_exec.id
    - Same environment as parent
    - Inherits parameters from parent

    Args:
        parent_exec: The failed parent execution
        rule: The matched remediation rule
        correlation_id: Optional correlation ID for tracing

    Returns:
        The created child execution, or None if failed
    """
    try:
        # Load corrective action
        corrective_action = await catalog_repository.get_by_id(rule.target_action_id)
        if corrective_action is None:
            logger.error(
                "auto_remediation_error",
                reason="corrective_action_not_found",
                action_id=rule.target_action_id,
                parent_execution_id=parent_exec.id,
            )
            return None

        # Check action is published
        if corrective_action.status.value != "published":
            logger.error(
                "auto_remediation_error",
                reason="corrective_action_not_published",
                action_id=rule.target_action_id,
                action_status=corrective_action.status.value,
                parent_execution_id=parent_exec.id,
            )
            return None

        # Create child execution with user_id=0 (SYSTEM)
        # Fix: Handle None environment gracefully
        env_str = (
            parent_exec.environment.value
            if parent_exec.environment and hasattr(parent_exec.environment, "value")
            else str(parent_exec.environment or "dev")
        )
        child_create_response = await execution_repository.create_execution(
            user_id=0,  # SYSTEM user for auto-remediation
            action_id=corrective_action.id,
            environment=env_str,
            parameters=parent_exec.parameters,
            parent_execution_id=parent_exec.id,
        )

        # Fetch full child execution details
        child_exec = await execution_repository.get_by_id(child_create_response.execution_id)

        logger.info(
            "auto_remediation_triggered",
            parent_execution_id=parent_exec.id,
            child_execution_id=child_create_response.execution_id,
            corrective_action_id=corrective_action.id,
            corrective_action_name=corrective_action.name,
            rule_error_pattern=rule.error_pattern[:50],
            risk_level=rule.risk_level.value,
            environment=env_str,
        )

        # Audit trail: AUTO_REMEDIATION_TRIGGERED (AC5)
        await audit_repository.create_entry(
            user_id="SYSTEM",
            action_type=AuditActionType.AUTO_REMEDIATION_TRIGGERED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=child_create_response.execution_id,
            details={
                "parent_execution_id": parent_exec.id,
                "parent_action_id": parent_exec.action_id,
                "corrective_action_id": corrective_action.id,
                "corrective_action_name": corrective_action.name,
                "rule_error_pattern": rule.error_pattern[:100],
                "risk_level": rule.risk_level.value,
                "auto": True,
                "environment": env_str,
                "original_error": parent_exec.parameters.get("error_message") if parent_exec.parameters else None,
            },
            correlation_id=correlation_id,
        )

        return child_exec

    except Exception as e:
        logger.error(
            "auto_remediation_error",
            error=str(e),
            parent_execution_id=parent_exec.id,
            rule_target_action_id=rule.target_action_id,
        )
        return None


# Story 9.3, AC3: Handle auto-remediation result


async def handle_auto_remediation_result(
    child_exec: "ExecutionResponse",
    correlation_id: str | None = None,
) -> RemediationResult:
    """Monitor auto-remediation result and trigger fallback if failed (Story 9.3, AC3).

    Args:
        child_exec: The child (corrective) execution
        correlation_id: Optional correlation ID for tracing

    Returns:
        RemediationResult.SUCCESS or RemediationResult.FALLBACK_MANUAL
    """
    from app.services.notification_service import notify_dba_remediation_failed

    if child_exec.status == ExecutionStatus.COMPLETED:
        # Success
        duration_seconds = None
        if child_exec.completed_at and child_exec.started_at:
            duration_seconds = (child_exec.completed_at - child_exec.started_at).total_seconds()

        logger.info(
            "auto_remediation_success",
            child_execution_id=child_exec.id,
            parent_execution_id=child_exec.parent_execution_id,
            duration_seconds=duration_seconds,
        )

        # Audit trail: AUTO_REMEDIATION_SUCCESS (AC5)
        await audit_repository.create_entry(
            user_id="SYSTEM",
            action_type=AuditActionType.AUTO_REMEDIATION_SUCCESS,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=child_exec.id,
            details={
                "parent_execution_id": child_exec.parent_execution_id,
                "duration_seconds": duration_seconds,
            },
            correlation_id=correlation_id,
        )

        return RemediationResult.SUCCESS

    elif child_exec.status == ExecutionStatus.FAILED:
        # Failure -> Fallback to manual mode
        logger.warning(
            "auto_remediation_failed",
            child_execution_id=child_exec.id,
            parent_execution_id=child_exec.parent_execution_id,
        )

        # Load parent execution
        parent_exec = None
        if child_exec.parent_execution_id:
            parent_exec = await execution_repository.get_by_id(child_exec.parent_execution_id)

        # Notify DBA (AC3)
        if parent_exec:
            await notify_dba_remediation_failed(parent_exec, child_exec)

        # Audit trail: AUTO_REMEDIATION_FAILED (AC5)
        await audit_repository.create_entry(
            user_id="SYSTEM",
            action_type=AuditActionType.AUTO_REMEDIATION_FAILED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=child_exec.id,
            details={
                "parent_execution_id": child_exec.parent_execution_id,
            },
            correlation_id=correlation_id,
        )

        return RemediationResult.FALLBACK_MANUAL

    # Other status (RUNNING, SUBMITTED, etc.) - wait for completion
    return RemediationResult.FALLBACK_MANUAL


# Story 9.3: Evaluate and potentially trigger auto-remediation for a failed execution


async def process_failed_execution_for_auto_remediation(
    execution: "ExecutionResponse",
    error_message: str,
    correlation_id: str | None = None,
) -> "ExecutionResponse | None":
    """Process a failed execution and trigger auto-remediation if applicable (Story 9.3, AC1).

    Algorithm:
    1. Load action's remediation_rules
    2. Find rules matching the error_message pattern
    3. For each matching rule, evaluate auto_trigger_allowed()
    4. If allowed, trigger_auto_remediation() and return child execution
    5. If none allowed, return None (manual mode continues)

    Args:
        execution: The failed execution
        error_message: The error message to match against rules
        correlation_id: Optional correlation ID for tracing

    Returns:
        The triggered child execution if auto-remediation was triggered, None otherwise
    """
    import re

    # Load action with remediation rules
    action = await catalog_repository.get_by_id(execution.action_id)
    if action is None or not action.remediation_rules:
        logger.debug(
            "auto_remediation_skip_no_rules",
            execution_id=execution.id,
            action_id=execution.action_id,
        )
        return None

    # Find matching rules
    env_str = execution.environment.value if hasattr(execution.environment, "value") else str(execution.environment)
    matching_rules: list[RemediationRule] = []

    for rule in action.remediation_rules:
        # Check error pattern matches
        try:
            if re.search(rule.error_pattern, error_message, re.IGNORECASE):
                # Check environment matches
                env_lower = env_str.lower()
                if env_lower in [e.lower() for e in rule.environments]:
                    matching_rules.append(rule)
        except re.error as e:
            logger.warning(
                "auto_remediation_invalid_regex",
                execution_id=execution.id,
                error_pattern=rule.error_pattern,
                error=str(e),
            )
            continue

    if not matching_rules:
        logger.debug(
            "auto_remediation_no_matching_rules",
            execution_id=execution.id,
            error_message=error_message[:100],
        )
        return None

    # Evaluate and trigger first allowed rule (one auto-remediation at a time)
    for rule in matching_rules:
        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        if allowed:
            child_exec = await trigger_auto_remediation(execution, rule, correlation_id)
            if child_exec:
                return child_exec
        else:
            logger.info(
                "auto_remediation_rule_not_allowed",
                execution_id=execution.id,
                target_action_id=rule.target_action_id,
                reason=reason,
            )

    logger.info(
        "auto_remediation_no_rules_allowed",
        execution_id=execution.id,
        matching_rules_count=len(matching_rules),
    )
    return None
