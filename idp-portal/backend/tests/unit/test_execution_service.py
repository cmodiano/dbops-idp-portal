"""Tests for execution service (Story 4.3, Task 6.2).

Tests ExecutionService:
- start_execution: orchestration flow
- Vault unavailable handling (AC3)
- Adapter trigger failures
- Correlation ID propagation
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import VaultError, PlatformError
from app.models.execution import (
    ExecutionStatus,
    ExecutionEnvironment,
    ExecutionResponse,
    StepStatus,
    StepType,
    ExecutionStepResponse,
)
from app.services.execution_service import ExecutionService, generate_correlation_id


@pytest.fixture
def mock_vault_service():
    """Mock VaultService for testing."""
    vault = MagicMock()
    vault.get_secret = AsyncMock(return_value={"username": "admin", "password": "secret"})
    return vault


@pytest.fixture
def execution_service(mock_vault_service):
    """ExecutionService instance with mocked dependencies."""
    return ExecutionService(mock_vault_service)


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id (Task 3.3)."""

    def test_generates_uuid_string(self):
        """generate_correlation_id returns a valid UUID string."""
        correlation_id = generate_correlation_id()
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 36  # UUID format: 8-4-4-4-12

    def test_generates_unique_ids(self):
        """generate_correlation_id returns unique IDs."""
        ids = [generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100  # All unique


class TestPrepareExecution:
    """Tests for ExecutionService.prepare_execution (Task 3.4)."""

    @pytest.mark.asyncio
    async def test_prepare_execution_creates_steps_from_action(self, execution_service):
        """prepare_execution creates step records from action's execution_steps."""
        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        action_steps = [
            {"order": 1, "name": "Récupération secrets", "type": "vault"},
            {"order": 2, "name": "Exécution", "type": "platform"},
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_execution_steps = AsyncMock(return_value=action_steps)
            mock_repo.create_execution_steps = AsyncMock(return_value=[101, 102])

            result = await execution_service.prepare_execution(1, "test-correlation-id")

        assert result is True
        mock_repo.create_execution_steps.assert_called_once()
        call_args = mock_repo.create_execution_steps.call_args
        assert call_args[0][0] == 1  # execution_id
        assert len(call_args[0][1]) == 2  # 2 steps

    @pytest.mark.asyncio
    async def test_prepare_execution_creates_default_step_when_none_defined(self, execution_service):
        """prepare_execution creates default platform step when no steps defined."""
        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_execution_steps = AsyncMock(return_value=[])  # No steps
            mock_repo.create_execution_steps = AsyncMock(return_value=[101])

            result = await execution_service.prepare_execution(1, "test-correlation-id")

        assert result is True
        call_args = mock_repo.create_execution_steps.call_args
        steps = call_args[0][1]
        assert len(steps) == 1
        assert steps[0].step_type == StepType.PLATFORM

    @pytest.mark.asyncio
    async def test_prepare_execution_returns_false_when_execution_not_found(self, execution_service):
        """prepare_execution returns False when execution doesn't exist."""
        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.get_by_id = AsyncMock(return_value=None)

            result = await execution_service.prepare_execution(999, "test-correlation-id")

        assert result is False


class TestStartExecution:
    """Tests for ExecutionService.start_execution (Task 4.1)."""

    @pytest.mark.asyncio
    async def test_start_execution_completes_all_steps(self, execution_service):
        """start_execution executes all steps and marks execution completed."""
        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={"pdb_name": "TEST"},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        action_info = {
            "id": 10,
            "name": "Create PDB",
            "platform": "mock",
            "execution_steps": [],
            "integration": {
                "id": 1,
                "name": "Mock",
                "platform_type": "mock",
                "base_url": "http://mock",
                "credential_ref": "secret/mock",
                "auth_flow": "token",
            },
        }

        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
            ExecutionStepResponse(
                id=102, execution_id=1, step_order=2, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)

            await execution_service.start_execution(1, "test-correlation-id")

        # Verify execution marked RUNNING then COMPLETED
        status_calls = mock_repo.update_status.call_args_list
        assert status_calls[0][0] == (1, ExecutionStatus.RUNNING)
        assert status_calls[-1][0] == (1, ExecutionStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_start_execution_fails_on_vault_error(self, execution_service, mock_vault_service):
        """start_execution fails execution when Vault is unavailable (AC3)."""
        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Vault is down")
        )

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        action_info = {
            "id": 10,
            "name": "Create PDB",
            "platform": "mock",
            "execution_steps": [],
            "integration": {
                "id": 1,
                "name": "Mock",
                "platform_type": "mock",
                "base_url": "http://mock",
                "credential_ref": "secret/mock",
                "auth_flow": "token",
            },
        }

        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=0)

            await execution_service.start_execution(1, "test-correlation-id")

        # Verify step marked FAILED
        step_calls = [c for c in mock_repo.update_step_status.call_args_list if c[0][1] == StepStatus.FAILED]
        assert len(step_calls) >= 1

        # Verify execution marked FAILED
        status_calls = mock_repo.update_status.call_args_list
        assert status_calls[-1][0] == (1, ExecutionStatus.FAILED)

    @pytest.mark.asyncio
    async def test_start_execution_fails_on_platform_error(self, execution_service):
        """start_execution fails execution when platform trigger fails."""
        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        action_info = {
            "id": 10,
            "name": "Create PDB",
            "platform": "unsupported_platform",  # Will fail
            "execution_steps": [],
            "integration": None,
        }

        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.get_platform_adapter") as mock_adapter:

            mock_adapter.side_effect = ValueError("Plateforme non supportée")
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=0)

            await execution_service.start_execution(1, "test-correlation-id")

        # Verify execution marked FAILED
        status_calls = mock_repo.update_status.call_args_list
        assert status_calls[-1][0] == (1, ExecutionStatus.FAILED)

    @pytest.mark.asyncio
    async def test_start_execution_skips_remaining_steps_on_failure(self, execution_service, mock_vault_service):
        """start_execution skips remaining steps when a step fails."""
        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Vault is down")
        )

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )

        action_info = {
            "id": 10,
            "name": "Create PDB",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"credential_ref": "secret/test"},
        }

        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
            ExecutionStepResponse(
                id=102, execution_id=1, step_order=2, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=1)

            await execution_service.start_execution(1, "test-correlation-id")

        # Verify skip_remaining_steps was called
        mock_repo.skip_remaining_steps.assert_called_once_with(1)


class TestVaultStepExecution:
    """Tests for Vault step execution (AC2, AC3)."""

    @pytest.mark.asyncio
    async def test_vault_step_retrieves_credentials(self, execution_service, mock_vault_service):
        """Vault step retrieves credentials using credential_ref."""
        action_info = {
            "integration": {
                "credential_ref": "secret/idp/aap-prod",
            },
        }

        credentials = await execution_service._execute_vault_step(
            step_id=1,
            action_info=action_info,
            correlation_id="test-id",
        )

        mock_vault_service.get_secret.assert_called_once_with("secret/idp/aap-prod")
        assert credentials == {"username": "admin", "password": "secret"}

    @pytest.mark.asyncio
    async def test_vault_step_returns_empty_when_no_credential_ref(self, execution_service):
        """Vault step returns empty dict when no credential_ref configured."""
        action_info = {
            "integration": {
                "credential_ref": None,
            },
        }

        credentials = await execution_service._execute_vault_step(
            step_id=1,
            action_info=action_info,
            correlation_id="test-id",
        )

        assert credentials == {}

    @pytest.mark.asyncio
    async def test_vault_step_raises_vault_error_on_failure(self, execution_service, mock_vault_service):
        """Vault step raises VaultError when Vault is unavailable (AC3)."""
        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Connection refused")
        )

        action_info = {
            "integration": {
                "credential_ref": "secret/test",
            },
        }

        with pytest.raises(VaultError) as exc_info:
            await execution_service._execute_vault_step(
                step_id=1,
                action_info=action_info,
                correlation_id="test-id",
            )

        assert exc_info.value.code == "VAULT_UNAVAILABLE"


class TestPlatformStepExecution:
    """Tests for Platform step execution (AC2)."""

    @pytest.mark.asyncio
    async def test_platform_step_triggers_adapter(self, execution_service):
        """Platform step triggers adapter and returns job ID."""
        action_info = {
            "platform": "mock",
            "integration": {
                "platform_type": "mock",
                "base_url": "http://mock",
            },
        }

        with patch("app.services.execution_service.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.trigger = AsyncMock(return_value="mock-job-123")
            mock_factory.return_value = mock_adapter

            job_id = await execution_service._execute_platform_step(
                step_id=1,
                action_info=action_info,
                parameters={"pdb_name": "TEST"},
                credentials={"user": "admin"},
                correlation_id="test-id",
            )

        assert job_id == "mock-job-123"
        mock_adapter.trigger.assert_called_once_with(
            {"pdb_name": "TEST"},
            {"user": "admin"},
            "test-id",
        )

    @pytest.mark.asyncio
    async def test_platform_step_raises_error_for_unsupported_platform(self, execution_service):
        """Platform step raises PlatformError for unsupported platform."""
        action_info = {
            "platform": "unsupported",
            "integration": None,
        }

        with patch("app.services.execution_service.get_platform_adapter") as mock_factory:
            mock_factory.side_effect = ValueError("Plateforme non supportée")

            with pytest.raises(PlatformError) as exc_info:
                await execution_service._execute_platform_step(
                    step_id=1,
                    action_info=action_info,
                    parameters={},
                    credentials={},
                    correlation_id="test-id",
                )

            assert exc_info.value.code == "PLATFORM_NOT_SUPPORTED"
