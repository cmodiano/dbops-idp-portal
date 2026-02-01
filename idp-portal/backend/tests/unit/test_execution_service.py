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

from app.core.exceptions import VaultError, PlatformError, ServiceNowError
from app.models.execution import (
    ExecutionStatus,
    ExecutionEnvironment,
    ExecutionResponse,
    StepStatus,
    StepType,
    ExecutionStepResponse,
)
from app.services.execution_service import ExecutionService, generate_correlation_id


@pytest.fixture(autouse=True)
def mock_audit_repository():
    """Auto-mock audit_repository for all tests (Story 6.1)."""
    with patch("app.services.execution_service.audit_repository") as mock_audit:
        mock_audit.create_entry = AsyncMock(return_value=1)
        yield mock_audit


@pytest.fixture(autouse=True)
def mock_catalog_repository():
    """Auto-mock catalog_repository for all tests (Story 6.2)."""
    with patch("app.services.execution_service.catalog_repository") as mock_catalog:
        # Default: no special tags (regular action)
        mock_catalog.get_tags_for_action = AsyncMock(return_value=[])
        yield mock_catalog


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

        mock_vault_service.get_secret.assert_called_once_with("secret/idp/aap-prod", "test-id")
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
                step_order=1,
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
            integration=action_info["integration"],
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
                    step_order=1,
                    action_info=action_info,
                    parameters={},
                    credentials={},
                    correlation_id="test-id",
                )

            assert exc_info.value.code == "PLATFORM_NOT_SUPPORTED"

    @pytest.mark.asyncio
    async def test_platform_step_aap_merges_connector_config(self, execution_service):
        """Story 4.10: AAP step merges connector_config (resource_type, template id) with parameters."""
        action_info = {
            "platform": "aap",
            "integration": {
                "platform_type": "aap",
                "base_url": "https://aap.example.com",
            },
            "execution_steps": [
                {
                    "order": 1,
                    "name": "Run AAP",
                    "type": "platform",
                    "connector_config": {
                        "resource_type": "workflow_job",
                        "workflow_job_template_id": 99,
                    },
                },
            ],
        }

        with patch("app.services.execution_service.get_platform_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.trigger = AsyncMock(return_value="wf-job-888")
            mock_factory.return_value = mock_adapter

            job_id = await execution_service._execute_platform_step(
                step_id=1,
                step_order=1,
                action_info=action_info,
                parameters={"extra_vars": {"target": "db-01"}},
                credentials={"token": "secret"},
                correlation_id="test-id",
            )

        assert job_id == "wf-job-888"
        call_args = mock_adapter.trigger.call_args[0]
        params = call_args[0]
        assert params["resource_type"] == "workflow_job"
        assert params["workflow_job_template_id"] == 99
        assert params["extra_vars"] == {"target": "db-01"}


class TestServiceNowStepExecution:
    """Tests for ServiceNow step execution (Story 4.5, Task 8.2)."""

    @pytest.fixture
    def mock_servicenow_service(self):
        """Mock ServiceNowService for testing."""
        servicenow = MagicMock()
        servicenow.create_change = AsyncMock(return_value={
            "change_id": "abc123",
            "change_number": "CHG0030123",
            "status": "approved",
        })
        return servicenow

    @pytest.fixture
    def execution_service_with_servicenow(self, mock_vault_service, mock_servicenow_service):
        """ExecutionService instance with mocked ServiceNow service."""
        return ExecutionService(mock_vault_service, mock_servicenow_service)

    @pytest.mark.asyncio
    async def test_servicenow_step_creates_change_approved(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """ServiceNow step creates change and returns approved status."""
        action_info = {
            "name": "Create PDB",
            "change_model_code": "STD-DB-CREATE-PDB",
            "execution_steps": [{"type": "servicenow", "change_model_code": "STD-DB-CREATE-PDB"}],
            "integration": None,
        }

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)

            result = await execution_service_with_servicenow._execute_servicenow_step(
                step_id=1,
                execution_id=100,
                action_info=action_info,
                environment="prod",
                parameters={"pdb_name": "NEWPDB"},
                user_id=1,
                correlation_id="test-corr-id",
            )

        assert result["change_id"] == "abc123"
        assert result["change_number"] == "CHG0030123"
        assert result["status"] == "approved"
        mock_servicenow_service.create_change.assert_called_once()

    @pytest.mark.asyncio
    async def test_servicenow_step_creates_change_pending_approval(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """ServiceNow step creates change and returns pending_approval status."""
        mock_servicenow_service.create_change = AsyncMock(return_value={
            "change_id": "xyz789",
            "change_number": "CHG0030124",
            "status": "pending_approval",
        })

        action_info = {
            "name": "Major Migration",
            "change_model_code": None,
            "execution_steps": [],
            "integration": None,
        }

        result = await execution_service_with_servicenow._execute_servicenow_step(
            step_id=1,
            execution_id=100,
            action_info=action_info,
            environment="prod",
            parameters={},
            user_id=1,
            correlation_id="test-corr-id",
        )

        assert result["status"] == "pending_approval"

    @pytest.mark.asyncio
    async def test_servicenow_step_returns_none_when_not_configured(
        self, mock_vault_service
    ):
        """ServiceNow step returns None when servicenow_service is not configured."""
        execution_service = ExecutionService(mock_vault_service, servicenow_service=None)

        action_info = {
            "name": "Test Action",
            "change_model_code": None,
            "execution_steps": [],
            "integration": None,
        }

        result = await execution_service._execute_servicenow_step(
            step_id=1,
            execution_id=100,
            action_info=action_info,
            environment="prod",
            parameters={},
            user_id=1,
            correlation_id="test-corr-id",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_servicenow_step_raises_error_on_failure(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """ServiceNow step raises ServiceNowError on failure."""
        mock_servicenow_service.create_change = AsyncMock(
            side_effect=ServiceNowError(code="SERVICENOW_TIMEOUT", message="Timeout")
        )

        action_info = {
            "name": "Test Action",
            "change_model_code": None,
            "execution_steps": [],
            "integration": None,
        }

        with pytest.raises(ServiceNowError) as exc_info:
            await execution_service_with_servicenow._execute_servicenow_step(
                step_id=1,
                execution_id=100,
                action_info=action_info,
                environment="prod",
                parameters={},
                user_id=1,
                correlation_id="test-corr-id",
            )

        assert exc_info.value.code == "SERVICENOW_TIMEOUT"

    @pytest.mark.asyncio
    async def test_servicenow_step_uses_change_model_from_step_config(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """ServiceNow step uses change_model_code from step configuration."""
        action_info = {
            "name": "Test Action",
            "change_model_code": "ACTION_LEVEL_CODE",  # Action-level fallback
            "execution_steps": [
                {"type": "servicenow", "change_model_code": "STEP_LEVEL_CODE"}
            ],
            "integration": None,
        }

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)

            await execution_service_with_servicenow._execute_servicenow_step(
                step_id=1,
                execution_id=100,
                action_info=action_info,
                environment="prod",
                parameters={},
                user_id=1,
                correlation_id="test-corr-id",
            )

        call_kwargs = mock_servicenow_service.create_change.call_args.kwargs
        assert call_kwargs["change_model_code"] == "STEP_LEVEL_CODE"

    @pytest.mark.asyncio
    async def test_servicenow_step_falls_back_to_action_change_model(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """ServiceNow step falls back to action-level change_model_code."""
        action_info = {
            "name": "Test Action",
            "change_model_code": "ACTION_LEVEL_CODE",
            "execution_steps": [
                {"type": "servicenow"}  # No step-level change_model_code
            ],
            "integration": None,
        }

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)

            await execution_service_with_servicenow._execute_servicenow_step(
                step_id=1,
                execution_id=100,
                action_info=action_info,
                environment="prod",
                parameters={},
                user_id=1,
                correlation_id="test-corr-id",
            )

        call_kwargs = mock_servicenow_service.create_change.call_args.kwargs
        assert call_kwargs["change_model_code"] == "ACTION_LEVEL_CODE"

    @pytest.mark.asyncio
    async def test_start_execution_servicenow_approved_stores_step_output(
        self, execution_service_with_servicenow, mock_servicenow_service
    ):
        """AC2: When ServiceNow step returns approved, step is marked COMPLETED with output (change_number for timeline)."""
        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=1,
            environment=ExecutionEnvironment.PROD,
            parameters={"pdb_name": "NEWPDB"},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )
        action_info = {
            "id": 10,
            "name": "Create PDB",
            "platform": "mock",
            "execution_steps": [{"order": 1, "name": "Changement ServiceNow", "type": "servicenow"}],
            "integration": None,
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101,
                execution_id=1,
                step_order=1,
                step_name="Changement ServiceNow",
                step_type=StepType.SERVICENOW,
                status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)

            await execution_service_with_servicenow.start_execution(1, "test-corr-id")

        # AC2: step must be marked COMPLETED with output containing change_id, change_number, status
        completed_calls = [
            c for c in mock_repo.update_step_status.call_args_list
            if len(c[0]) >= 2 and c[0][1] == StepStatus.COMPLETED
        ]
        assert len(completed_calls) >= 1
        call_kwargs = completed_calls[0].kwargs
        assert "output" in call_kwargs
        output = call_kwargs["output"]
        assert output is not None
        assert output.get("change_id") == "abc123"
        assert output.get("change_number") == "CHG0030123"
        assert output.get("status") == "approved"


class TestExecutionAuditTrail:
    """Tests for execution audit trail (Story 6.1)."""

    @pytest.mark.asyncio
    async def test_start_execution_creates_started_audit_entry(self, execution_service, mock_audit_repository):
        """start_execution creates EXECUTION_STARTED audit entry (AC1)."""
        from app.repositories.audit_repository import AuditActionType, AuditEntityType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )
        action_info = {
            "id": 10,
            "name": "Test Action",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)

            await execution_service.start_execution(1, "test-corr-id", client_ip="192.168.1.1")

        # Verify EXECUTION_STARTED audit entry (AC1, AC5)
        started_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_STARTED
        ]
        assert len(started_calls) >= 1
        call_kwargs = started_calls[0].kwargs
        assert call_kwargs["entity_type"] == AuditEntityType.EXECUTION
        assert call_kwargs["entity_id"] == 1
        assert call_kwargs["user_id"] == "42"
        assert call_kwargs["correlation_id"] == "test-corr-id"
        assert call_kwargs.get("ip_address") == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_start_execution_creates_completed_audit_entry(self, execution_service, mock_audit_repository):
        """start_execution creates EXECUTION_COMPLETED audit entry on success (AC1)."""
        from app.repositories.audit_repository import AuditActionType, AuditEntityType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )
        action_info = {
            "id": 10,
            "name": "Test Action",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_COMPLETED audit entry
        completed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_COMPLETED
        ]
        assert len(completed_calls) >= 1
        call_kwargs = completed_calls[0].kwargs
        assert call_kwargs["entity_type"] == AuditEntityType.EXECUTION
        assert call_kwargs["entity_id"] == 1
        assert "steps_summary" in call_kwargs["details"]

    @pytest.mark.asyncio
    async def test_fail_execution_creates_failed_audit_entry(self, execution_service, mock_audit_repository):
        """_fail_execution creates EXECUTION_FAILED audit entry (AC1)."""
        from app.repositories.audit_repository import AuditActionType, AuditEntityType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.RUNNING,
            created_at=datetime(2026, 1, 29),
        )
        action_info = {"id": 10, "name": "Test Action"}

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.skip_remaining_steps = AsyncMock()
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)

            await execution_service._fail_execution(1, "Test error", "corr-123")

        # Verify EXECUTION_FAILED audit entry
        failed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_FAILED
        ]
        assert len(failed_calls) >= 1
        call_kwargs = failed_calls[0].kwargs
        assert call_kwargs["entity_type"] == AuditEntityType.EXECUTION
        assert call_kwargs["entity_id"] == 1
        assert call_kwargs["details"]["error_message"] == "Test error"
        assert call_kwargs["correlation_id"] == "corr-123"

    @pytest.mark.asyncio
    async def test_servicenow_step_creates_servicenow_change_created_audit_entry(
        self, execution_service, mock_audit_repository
    ):
        """When ServiceNow step runs, create_entry is called with SERVICENOW_CHANGE_CREATED and user_id as str (Story 6.1, AC2)."""
        from app.repositories.audit_repository import AuditActionType, AuditEntityType

        mock_servicenow = MagicMock()
        mock_servicenow.create_change = AsyncMock(return_value={
            "change_id": "abc123",
            "change_number": "CHG0030123",
            "status": "approved",
        })
        service = ExecutionService(
            MagicMock(get_secret=AsyncMock(return_value={})),
            mock_servicenow,
        )

        action_info = {
            "name": "Create PDB",
            "execution_steps": [{"order": 1, "type": "servicenow"}],
            "integration": None,
        }

        with patch("app.services.execution_service.execution_repository") as mock_repo:
            mock_repo.update_status = AsyncMock(return_value=True)

            await service._execute_servicenow_step(
                step_id=1,
                execution_id=100,
                action_info=action_info,
                environment="prod",
                parameters={},
                user_id=42,
                correlation_id="test-corr-id",
            )

        sn_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.SERVICENOW_CHANGE_CREATED
        ]
        assert len(sn_calls) >= 1
        call_kwargs = sn_calls[0].kwargs
        assert call_kwargs["entity_type"] == AuditEntityType.EXECUTION
        assert call_kwargs["entity_id"] == 100
        assert call_kwargs["user_id"] == "42"
        assert call_kwargs["details"]["servicenow_change_id"] == "abc123"
        assert call_kwargs["details"]["change_number"] == "CHG0030123"
        assert call_kwargs["details"]["approval_status"] == "approved"


class TestPatchingEvidenceAudit:
    """Tests for patching evidence in audit trail (Story 6.2, AC1, AC3, AC4)."""

    @pytest.mark.asyncio
    async def test_execution_completed_patching_enriches_details(
        self, execution_service, mock_audit_repository
    ):
        """AC1: When patching action completes, audit details contain version_source, version_target, patch_result, components_modified."""
        from app.repositories.audit_repository import AuditActionType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={
                "version_source": "19.3.0",
                "version_target": "19.21.0",
                "components": ["oracle-db", "grid-infra"],
            },
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 30),
        )
        action_info = {
            "id": 10,
            "name": "Oracle Patching",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            # Action has "patching" tag
            mock_catalog.get_tags_for_action = AsyncMock(return_value=["patching", "oracle"])

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_COMPLETED audit entry has patching evidence
        completed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_COMPLETED
        ]
        assert len(completed_calls) >= 1
        details = completed_calls[0].kwargs["details"]
        assert details.get("version_source") == "19.3.0"
        assert details.get("version_target") == "19.21.0"
        assert details.get("components_modified") == ["oracle-db", "grid-infra"]
        # patch_result derived from execution status (COMPLETED = success)
        assert details.get("patch_result") == "success"

    @pytest.mark.asyncio
    async def test_execution_failed_patching_enriches_details(
        self, execution_service, mock_audit_repository, mock_vault_service
    ):
        """AC1: When patching action fails, audit details contain patching evidence with patch_result=failed."""
        from app.repositories.audit_repository import AuditActionType

        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Vault is down")
        )

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={
                "version_source": "19.3.0",
                "version_target": "19.21.0",
                "components": ["oracle-db"],
            },
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 30),
        )
        action_info = {
            "id": 10,
            "name": "Oracle Patching",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"credential_ref": "secret/test"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=0)
            mock_catalog.get_tags_for_action = AsyncMock(return_value=["patching"])

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_FAILED audit entry has patching evidence
        failed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_FAILED
        ]
        assert len(failed_calls) >= 1
        details = failed_calls[0].kwargs["details"]
        assert details.get("version_source") == "19.3.0"
        assert details.get("version_target") == "19.21.0"
        assert details.get("patch_result") == "failed"


class TestPrivilegeAccountEvidenceAudit:
    """Tests for compte à privilèges evidence in audit trail (Story 6.2, AC2, AC3, AC4)."""

    @pytest.mark.asyncio
    async def test_execution_completed_privilege_account_enriches_details(
        self, execution_service, mock_audit_repository
    ):
        """AC2: When compte à privilèges action completes, audit details contain justification, approbateur, privilege_scope."""
        from app.repositories.audit_repository import AuditActionType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=20,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={
                "justification": "Maintenance planifiée - ticket INC0012345",
                "approbateur": "john.manager@company.com",
                "privilege_scope": "DBA",
                "username": "svc_patch_account",
            },
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 30),
        )
        action_info = {
            "id": 20,
            "name": "Création compte DBA",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=201, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            # Action has "compte-privileges" tag
            mock_catalog.get_tags_for_action = AsyncMock(return_value=["compte-privileges", "dba"])

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_COMPLETED audit entry has privilege account evidence
        completed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_COMPLETED
        ]
        assert len(completed_calls) >= 1
        details = completed_calls[0].kwargs["details"]
        assert details.get("justification") == "Maintenance planifiée - ticket INC0012345"
        assert details.get("approbateur") == "john.manager@company.com"
        assert details.get("privilege_scope") == "DBA"

    @pytest.mark.asyncio
    async def test_execution_failed_privilege_account_enriches_details(
        self, execution_service, mock_audit_repository, mock_vault_service
    ):
        """AC2: When compte à privilèges action fails, audit details contain privilege account evidence."""
        from app.repositories.audit_repository import AuditActionType

        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Vault is down")
        )

        mock_execution = ExecutionResponse(
            id=1,
            action_id=20,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={
                "justification": "Emergency access",
                "approbateur": "jane.director@company.com",
                "privilege_scope": "SYSDBA",
            },
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 30),
        )
        action_info = {
            "id": 20,
            "name": "Création compte SYSDBA",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"credential_ref": "secret/test"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=201, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=0)
            mock_catalog.get_tags_for_action = AsyncMock(return_value=["compte-privileges"])

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_FAILED audit entry has privilege account evidence
        failed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_FAILED
        ]
        assert len(failed_calls) >= 1
        details = failed_calls[0].kwargs["details"]
        assert details.get("justification") == "Emergency access"
        assert details.get("approbateur") == "jane.director@company.com"
        assert details.get("privilege_scope") == "SYSDBA"


class TestRegularActionAuditRetrocompat:
    """Tests for regular action audit backward compatibility (Story 6.2, AC5, retrocompat)."""

    @pytest.mark.asyncio
    async def test_execution_completed_regular_action_no_extra_fields(
        self, execution_service, mock_audit_repository
    ):
        """AC5/Retrocompat: When regular action completes, audit details remain unchanged (no patching/privilege fields)."""
        from app.repositories.audit_repository import AuditActionType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=30,
            user_id=42,
            environment=ExecutionEnvironment.DEV,
            parameters={"db_name": "TESTDB"},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 30),
        )
        action_info = {
            "id": 30,
            "name": "Create Database",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=301, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            # Action has no patching or compte-privileges tags
            mock_catalog.get_tags_for_action = AsyncMock(return_value=["database", "create"])

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_COMPLETED audit entry does NOT have patching/privilege fields
        completed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_COMPLETED
        ]
        assert len(completed_calls) >= 1
        details = completed_calls[0].kwargs["details"]
        # Should only have standard fields
        assert "status" in details
        assert "steps_summary" in details
        # Should NOT have patching fields
        assert "version_source" not in details
        assert "version_target" not in details
        assert "patch_result" not in details
        assert "components_modified" not in details
        # Should NOT have privilege account fields
        assert "justification" not in details
        assert "approbateur" not in details
        assert "privilege_scope" not in details


class TestCatalogRepositoryFailureResilience:
    """Tests for catalog_repository failure resilience (Code Review fix)."""

    @pytest.mark.asyncio
    async def test_execution_completed_catalog_failure_falls_back_to_regular_audit(
        self, execution_service, mock_audit_repository
    ):
        """When catalog_repository.get_tags_for_action fails, execution completes with regular audit (no crash)."""
        from app.repositories.audit_repository import AuditActionType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.DEV,
            parameters={"version_source": "19.3.0"},  # Would trigger patching if tags worked
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 31),
        )
        action_info = {
            "id": 10,
            "name": "Test Action",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"platform_type": "mock", "base_url": "http://mock"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Platform",
                step_type=StepType.PLATFORM, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            # Simulate catalog_repository failure (database error)
            mock_catalog.get_tags_for_action = AsyncMock(side_effect=Exception("Database connection lost"))

            # Should NOT crash - execution should complete gracefully
            await execution_service.start_execution(1, "test-corr-id")

        # Verify execution marked COMPLETED (not crashed)
        status_calls = mock_repo.update_status.call_args_list
        assert status_calls[-1][0] == (1, ExecutionStatus.COMPLETED)

        # Verify EXECUTION_COMPLETED audit entry exists with regular structure (no enrichment)
        completed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_COMPLETED
        ]
        assert len(completed_calls) >= 1
        details = completed_calls[0].kwargs["details"]
        # Should have standard fields
        assert details.get("status") == "COMPLETED"
        assert "steps_summary" in details
        # Should NOT have patching fields (fallback to regular audit)
        assert "version_source" not in details
        assert "patch_result" not in details

    @pytest.mark.asyncio
    async def test_fail_execution_catalog_failure_falls_back_to_regular_audit(
        self, execution_service, mock_audit_repository, mock_vault_service
    ):
        """When catalog_repository fails during _fail_execution, audit still works with regular structure."""
        from app.repositories.audit_repository import AuditActionType

        mock_vault_service.get_secret = AsyncMock(
            side_effect=VaultError(code="VAULT_UNAVAILABLE", message="Vault is down")
        )

        mock_execution = ExecutionResponse(
            id=1,
            action_id=10,
            user_id=42,
            environment=ExecutionEnvironment.PROD,
            parameters={"version_source": "19.3.0"},
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 31),
        )
        action_info = {
            "id": 10,
            "name": "Test Action",
            "platform": "mock",
            "execution_steps": [],
            "integration": {"credential_ref": "secret/test"},
        }
        mock_steps = [
            ExecutionStepResponse(
                id=101, execution_id=1, step_order=1, step_name="Vault",
                step_type=StepType.VAULT, status=StepStatus.PENDING,
            ),
        ]

        with patch("app.services.execution_service.execution_repository") as mock_repo, \
             patch("app.services.execution_service.catalog_repository") as mock_catalog:
            mock_repo.update_status = AsyncMock(return_value=True)
            mock_repo.get_by_id = AsyncMock(return_value=mock_execution)
            mock_repo.get_action_with_integration = AsyncMock(return_value=action_info)
            mock_repo.get_steps_by_execution_id = AsyncMock(return_value=mock_steps)
            mock_repo.update_step_status = AsyncMock(return_value=True)
            mock_repo.skip_remaining_steps = AsyncMock(return_value=0)
            # Simulate catalog_repository failure
            mock_catalog.get_tags_for_action = AsyncMock(side_effect=Exception("Query timeout"))

            await execution_service.start_execution(1, "test-corr-id")

        # Verify EXECUTION_FAILED audit entry exists (not crashed)
        failed_calls = [
            c for c in mock_audit_repository.create_entry.call_args_list
            if c.kwargs.get("action_type") == AuditActionType.EXECUTION_FAILED
        ]
        assert len(failed_calls) >= 1
        details = failed_calls[0].kwargs["details"]
        assert details.get("status") == "FAILED"
        # Should NOT have patching fields (fallback to regular audit)
        assert "version_source" not in details
        assert "patch_result" not in details
