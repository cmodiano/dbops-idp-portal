"""Unit tests for RemediationService (Story 9.3, Tasks 15-17).

Tests auto-remediation evaluation, triggering, and monitoring.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.remediation_service import (
    evaluate_auto_trigger_allowed,
    trigger_auto_remediation,
    handle_auto_remediation_result,
    process_failed_execution_for_auto_remediation,
    RemediationResult,
)
from app.models.catalog import RemediationRule, RiskLevel, ActionStatus
from app.models.execution import ExecutionStatus, ExecutionEnvironment


def _make_mock_execution(
    execution_id: int = 1,
    action_id: int = 10,
    user_id: int = 1,
    environment: str = "dev",
    status: ExecutionStatus = ExecutionStatus.FAILED,
    parent_execution_id: int | None = None,
    parameters: dict | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    action_name: str | None = None,
) -> MagicMock:
    """Create a mock ExecutionResponse."""
    mock = MagicMock()
    mock.id = execution_id
    mock.action_id = action_id
    mock.user_id = user_id
    mock.environment = MagicMock()
    mock.environment.value = environment
    mock.status = status
    mock.parent_execution_id = parent_execution_id
    mock.parameters = parameters or {}
    mock.started_at = started_at
    mock.completed_at = completed_at
    mock.action_name = action_name
    return mock


def _make_mock_rule(
    error_pattern: str = "ORA-\\d+",
    target_action_id: int = 20,
    environments: list[str] = None,
    auto_trigger: bool = True,
    risk_level: RiskLevel = RiskLevel.LOW,
) -> RemediationRule:
    """Create a RemediationRule for testing."""
    return RemediationRule(
        error_pattern=error_pattern,
        target_action_id=target_action_id,
        environments=environments or ["dev", "staging"],
        auto_trigger=auto_trigger,
        risk_level=risk_level,
    )


# === Task 15: Tests evaluate_auto_trigger_allowed ===


class TestEvaluateAutoTriggerAllowed:
    """Tests for evaluate_auto_trigger_allowed (Story 9.3, AC1, AC4)."""

    @pytest.mark.asyncio
    async def test_auto_trigger_allowed_with_auto_true_risk_low(self):
        """Return True when auto=True, risk_level=low, environment matches."""
        execution = _make_mock_execution(environment="dev")
        rule = _make_mock_rule(auto_trigger=True, risk_level=RiskLevel.LOW, environments=["dev"])

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is True
        assert reason == "allowed"

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_if_auto_false(self):
        """Return False when auto_trigger=False."""
        execution = _make_mock_execution(environment="dev")
        rule = _make_mock_rule(auto_trigger=False, risk_level=RiskLevel.LOW)

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is False
        assert "auto_trigger_disabled" in reason

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_if_risk_medium(self):
        """Return False when risk_level=medium."""
        execution = _make_mock_execution(environment="dev")
        rule = _make_mock_rule(auto_trigger=True, risk_level=RiskLevel.MEDIUM)

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is False
        assert "risk_level_too_high" in reason

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_if_risk_high(self):
        """Return False when risk_level=high."""
        execution = _make_mock_execution(environment="dev")
        rule = _make_mock_rule(auto_trigger=True, risk_level=RiskLevel.HIGH)

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is False
        assert "risk_level_too_high" in reason

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_if_env_not_authorized(self):
        """Return False when environment not in rule.environments."""
        execution = _make_mock_execution(environment="qa")
        rule = _make_mock_rule(auto_trigger=True, risk_level=RiskLevel.LOW, environments=["dev"])

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is False
        assert "environment_not_authorized" in reason

    @pytest.mark.asyncio
    async def test_auto_trigger_blocked_in_prod(self):
        """Return False for PROD environment (always requires human approval)."""
        execution = _make_mock_execution(environment="prod")
        rule = _make_mock_rule(
            auto_trigger=True,
            risk_level=RiskLevel.LOW,
            environments=["dev", "staging", "prod"]
        )

        allowed, reason = await evaluate_auto_trigger_allowed(execution, rule)

        assert allowed is False
        assert "prod_requires_approval" in reason


# === Task 16: Tests trigger_auto_remediation ===


class TestTriggerAutoRemediation:
    """Tests for trigger_auto_remediation (Story 9.3, AC1, AC2)."""

    @pytest.mark.asyncio
    async def test_trigger_auto_remediation_creates_child_execution(self):
        """trigger_auto_remediation creates child execution with correct fields."""
        parent_exec = _make_mock_execution(
            execution_id=100, action_id=10, environment="dev", parameters={"key": "value"}
        )
        rule = _make_mock_rule(target_action_id=20)

        mock_action = MagicMock()
        mock_action.id = 20
        mock_action.name = "Fix Action"
        mock_action.status = MagicMock()
        mock_action.status.value = "published"

        mock_child_create = MagicMock()
        mock_child_create.execution_id = 200

        mock_child_exec = _make_mock_execution(
            execution_id=200, action_id=20, user_id=0, parent_execution_id=100
        )

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
                with patch("app.services.remediation_service.audit_repository") as mock_audit:
                    mock_catalog.get_by_id = AsyncMock(return_value=mock_action)
                    mock_exec_repo.create_execution = AsyncMock(return_value=mock_child_create)
                    mock_exec_repo.get_by_id = AsyncMock(return_value=mock_child_exec)
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    result = await trigger_auto_remediation(parent_exec, rule, "corr-123")

        assert result is not None
        assert result.id == 200
        mock_exec_repo.create_execution.assert_called_once()
        call_args = mock_exec_repo.create_execution.call_args
        assert call_args[1]["user_id"] == 0  # SYSTEM user
        assert call_args[1]["action_id"] == 20
        assert call_args[1]["parent_execution_id"] == 100

    @pytest.mark.asyncio
    async def test_trigger_auto_remediation_user_id_system(self):
        """Child execution has user_id=0 (SYSTEM)."""
        parent_exec = _make_mock_execution(execution_id=100)
        rule = _make_mock_rule(target_action_id=20)

        mock_action = MagicMock()
        mock_action.id = 20
        mock_action.status = MagicMock()
        mock_action.status.value = "published"

        mock_child_create = MagicMock()
        mock_child_create.execution_id = 200

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
                with patch("app.services.remediation_service.audit_repository") as mock_audit:
                    mock_catalog.get_by_id = AsyncMock(return_value=mock_action)
                    mock_exec_repo.create_execution = AsyncMock(return_value=mock_child_create)
                    mock_exec_repo.get_by_id = AsyncMock(return_value=MagicMock())
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    await trigger_auto_remediation(parent_exec, rule)

        call_args = mock_exec_repo.create_execution.call_args
        assert call_args[1]["user_id"] == 0

    @pytest.mark.asyncio
    async def test_trigger_auto_remediation_inherits_environment(self):
        """Child execution inherits parent's environment."""
        parent_exec = _make_mock_execution(execution_id=100, environment="staging")
        rule = _make_mock_rule(target_action_id=20)

        mock_action = MagicMock()
        mock_action.id = 20
        mock_action.status = MagicMock()
        mock_action.status.value = "published"

        mock_child_create = MagicMock()
        mock_child_create.execution_id = 200

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
                with patch("app.services.remediation_service.audit_repository") as mock_audit:
                    mock_catalog.get_by_id = AsyncMock(return_value=mock_action)
                    mock_exec_repo.create_execution = AsyncMock(return_value=mock_child_create)
                    mock_exec_repo.get_by_id = AsyncMock(return_value=MagicMock())
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    await trigger_auto_remediation(parent_exec, rule)

        call_args = mock_exec_repo.create_execution.call_args
        assert call_args[1]["environment"] == "staging"

    @pytest.mark.asyncio
    async def test_trigger_auto_remediation_returns_none_if_action_not_found(self):
        """Return None if corrective action not found."""
        parent_exec = _make_mock_execution(execution_id=100)
        rule = _make_mock_rule(target_action_id=999)

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            mock_catalog.get_by_id = AsyncMock(return_value=None)

            result = await trigger_auto_remediation(parent_exec, rule)

        assert result is None


# === Task 17: Tests handle_auto_remediation_result ===


class TestHandleAutoRemediationResult:
    """Tests for handle_auto_remediation_result (Story 9.3, AC3)."""

    @pytest.mark.asyncio
    async def test_handle_auto_remediation_result_success(self):
        """Return SUCCESS when child execution COMPLETED."""
        child_exec = _make_mock_execution(
            execution_id=200,
            status=ExecutionStatus.COMPLETED,
            parent_execution_id=100,
            started_at=datetime(2026, 2, 2, 10, 0),
            completed_at=datetime(2026, 2, 2, 10, 5),
        )

        with patch("app.services.remediation_service.audit_repository") as mock_audit:
            mock_audit.create_entry = AsyncMock(return_value=1)

            result = await handle_auto_remediation_result(child_exec)

        assert result == RemediationResult.SUCCESS

    @pytest.mark.asyncio
    async def test_handle_auto_remediation_result_failure_fallback(self):
        """Return FALLBACK_MANUAL and notify DBA when child FAILED."""
        child_exec = _make_mock_execution(
            execution_id=200,
            status=ExecutionStatus.FAILED,
            parent_execution_id=100,
            user_id=0,
        )
        parent_exec = _make_mock_execution(execution_id=100)

        with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
            with patch("app.services.remediation_service.audit_repository") as mock_audit:
                with patch("app.services.notification_service.notify_dba_remediation_failed", new_callable=AsyncMock) as mock_notify:
                    mock_exec_repo.get_by_id = AsyncMock(return_value=parent_exec)
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    result = await handle_auto_remediation_result(child_exec)

        assert result == RemediationResult.FALLBACK_MANUAL
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_auto_remediation_result_logs_audit_success(self):
        """Audit trail AUTO_REMEDIATION_SUCCESS logged on success."""
        child_exec = _make_mock_execution(
            execution_id=200,
            status=ExecutionStatus.COMPLETED,
            parent_execution_id=100,
            started_at=datetime(2026, 2, 2, 10, 0),
            completed_at=datetime(2026, 2, 2, 10, 5),
        )

        with patch("app.services.remediation_service.audit_repository") as mock_audit:
            mock_audit.create_entry = AsyncMock(return_value=1)

            await handle_auto_remediation_result(child_exec, "corr-123")

        mock_audit.create_entry.assert_called_once()
        call_args = mock_audit.create_entry.call_args
        assert call_args[1]["action_type"].value == "AUTO_REMEDIATION_SUCCESS"

    @pytest.mark.asyncio
    async def test_handle_auto_remediation_result_logs_audit_failed(self):
        """Audit trail AUTO_REMEDIATION_FAILED logged on failure."""
        child_exec = _make_mock_execution(
            execution_id=200,
            status=ExecutionStatus.FAILED,
            parent_execution_id=100,
        )

        with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
            with patch("app.services.remediation_service.audit_repository") as mock_audit:
                with patch("app.services.notification_service.notify_dba_remediation_failed", new_callable=AsyncMock):
                    mock_exec_repo.get_by_id = AsyncMock(return_value=MagicMock())
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    await handle_auto_remediation_result(child_exec, "corr-123")

        mock_audit.create_entry.assert_called_once()
        call_args = mock_audit.create_entry.call_args
        assert call_args[1]["action_type"].value == "AUTO_REMEDIATION_FAILED"


# === Task 18: Tests process_failed_execution_for_auto_remediation ===


class TestProcessFailedExecutionForAutoRemediation:
    """Tests for process_failed_execution_for_auto_remediation (Story 9.3, AC1)."""

    @pytest.mark.asyncio
    async def test_triggers_auto_remediation_when_rule_matches(self):
        """Auto-remediation triggered when rule matches and is allowed."""
        execution = _make_mock_execution(execution_id=100, action_id=10, environment="dev")
        error_message = "ORA-12345: connection failed"

        mock_action = MagicMock()
        mock_action.id = 10
        mock_action.remediation_rules = [
            _make_mock_rule(
                error_pattern="ORA-\\d+",
                target_action_id=20,
                environments=["dev"],
                auto_trigger=True,
                risk_level=RiskLevel.LOW,
            )
        ]

        mock_corrective = MagicMock()
        mock_corrective.id = 20
        mock_corrective.status = MagicMock()
        mock_corrective.status.value = "published"

        mock_child_create = MagicMock()
        mock_child_create.execution_id = 200

        mock_child_exec = _make_mock_execution(execution_id=200)

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            with patch("app.services.remediation_service.execution_repository") as mock_exec_repo:
                with patch("app.services.remediation_service.audit_repository") as mock_audit:
                    mock_catalog.get_by_id = AsyncMock(side_effect=lambda id: mock_action if id == 10 else mock_corrective)
                    mock_exec_repo.create_execution = AsyncMock(return_value=mock_child_create)
                    mock_exec_repo.get_by_id = AsyncMock(return_value=mock_child_exec)
                    mock_audit.create_entry = AsyncMock(return_value=1)

                    result = await process_failed_execution_for_auto_remediation(
                        execution, error_message, "corr-123"
                    )

        assert result is not None
        assert result.id == 200

    @pytest.mark.asyncio
    async def test_skips_if_no_rules(self):
        """Return None if action has no remediation rules."""
        execution = _make_mock_execution(execution_id=100, action_id=10)
        error_message = "Some error"

        mock_action = MagicMock()
        mock_action.remediation_rules = None

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            mock_catalog.get_by_id = AsyncMock(return_value=mock_action)

            result = await process_failed_execution_for_auto_remediation(
                execution, error_message
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_if_auto_not_allowed(self):
        """Return None if auto-trigger not allowed (e.g., risk_level=medium)."""
        execution = _make_mock_execution(execution_id=100, action_id=10, environment="dev")
        error_message = "ORA-12345: connection failed"

        mock_action = MagicMock()
        mock_action.remediation_rules = [
            _make_mock_rule(
                error_pattern="ORA-\\d+",
                target_action_id=20,
                environments=["dev"],
                auto_trigger=True,
                risk_level=RiskLevel.MEDIUM,  # Not LOW, so blocked
            )
        ]

        with patch("app.services.remediation_service.catalog_repository") as mock_catalog:
            mock_catalog.get_by_id = AsyncMock(return_value=mock_action)

            result = await process_failed_execution_for_auto_remediation(
                execution, error_message
            )

        assert result is None
