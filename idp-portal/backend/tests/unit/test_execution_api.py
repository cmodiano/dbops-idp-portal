"""Tests for executions API endpoints (Story 4.1, Task 8.1 + Story 4.3, Task 6.3).

Tests POST /api/v1/executions:
- Success case with valid parameters
- Error validation (invalid parameters, action not found)
- JSON Schema validation (Task 1.4)
- Correlation ID in response (Story 4.3)
- Background task triggering (Story 4.3)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.models.execution import ExecutionStatus, ExecutionEnvironment, ExecutionCreateResponse


@pytest.fixture
def mock_audit_repository():
    """Mock audit_repository for tests (Story 6.1)."""
    with patch("app.api.v1.executions.audit_repository") as mock_audit:
        mock_audit.create_entry = AsyncMock(return_value=1)
        yield mock_audit


@pytest.fixture(autouse=True)
def auto_mock_audit_repository(mock_audit_repository):
    """Auto-apply mock_audit_repository to all tests."""
    return mock_audit_repository


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mock_auth():
    """Mock authentication for execution endpoints (requires get_current_user)."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=1,
        username="test_dba",
        display_name="Test DBA",
        profile="dba",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_auth_regular_user():
    """Mock authentication with a regular user (not DBA/DBOPS) for ownership tests."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=1,
        username="test_user",
        display_name="Test User",
        profile="developer",  # Not dba/dbops, cannot see others' executions
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


class TestCreateExecution:
    """Tests for POST /api/v1/executions (Story 4.1, Task 1.1 + Story 4.3)."""

    @pytest.mark.asyncio
    async def test_create_execution_success(self, client, mock_auth):
        """POST /executions creates execution and returns 201 with correlation_id (AC3, AC4)."""
        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service") as mock_vault_factory, \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)) as mock_servicenow_factory, \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True  # User has permission (Story 4.3, Task 3.2)
            mock_schema.return_value = None  # No schema = no validation
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=1,
                status=ExecutionStatus.SUBMITTED,
                correlation_id="test-correlation-id",
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"pdb_name": "TEST_PDB"},
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "data" in data
        assert data["data"]["execution_id"] == 1
        assert data["data"]["status"] == "SUBMITTED"
        assert "correlation_id" in data["data"]
        mock_create.assert_called_once_with(
            user_id=1,
            action_id=1,
            environment="dev",
            parameters={"pdb_name": "TEST_PDB"},
        )

    @pytest.mark.asyncio
    async def test_create_execution_prepares_steps(self, client, mock_auth):
        """POST /executions calls prepare_execution to create steps (Story 4.3)."""
        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service") as mock_vault_factory, \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)) as mock_servicenow_factory, \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=42,
                status=ExecutionStatus.SUBMITTED,
                correlation_id="test-id",
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.post(
                "/api/v1/executions",
                json={"action_id": 1, "environment": "dev", "parameters": {}},
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock_execution_service.prepare_execution.assert_called_once()
        call_args = mock_execution_service.prepare_execution.call_args
        assert call_args[0][0] == 42  # execution_id

    @pytest.mark.asyncio
    async def test_create_execution_action_not_found(self, client, mock_auth):
        """POST /executions returns 404 when action doesn't exist (Task 1.1)."""
        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 999,
                    "environment": "dev",
                    "parameters": {},
                }
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["error"]
        assert error["code"] == "ACTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_execution_permission_denied(self, client, mock_auth):
        """POST /executions returns 403 when user lacks permission (Task 3.2 - RBAC)."""
        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:
            mock_exists.return_value = True
            mock_rbac.return_value = False  # User does NOT have permission

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {},
                }
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.json()["error"]
        assert error["code"] == "PERMISSION_DENIED"
        assert "permission" in error["message"].lower()

    @pytest.mark.asyncio
    async def test_create_execution_invalid_environment(self, client, mock_auth):
        """POST /executions returns 422 for invalid environment (Task 1.1)."""
        response = await client.post(
            "/api/v1/executions",
            json={
                "action_id": 1,
                "environment": "invalid_env",
                "parameters": {},
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_execution_validates_parameters_against_schema(self, client, mock_auth):
        """POST /executions validates parameters against action's parameters_schema (Task 1.4)."""
        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = {
                "type": "object",
                "properties": {
                    "pdb_name": {"type": "string", "pattern": "^[A-Z_]+$"},
                    "size_gb": {"type": "number", "minimum": 1},
                },
                "required": ["pdb_name"],
            }

            # Invalid: pdb_name doesn't match pattern (lowercase)
            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"pdb_name": "test_pdb"},  # lowercase fails pattern
                }
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_PARAMETERS"
        assert "pdb_name" in error["details"]["field"]

    @pytest.mark.asyncio
    async def test_create_execution_missing_required_parameter(self, client, mock_auth):
        """POST /executions returns 400 when required parameter is missing (Task 1.4)."""
        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = {
                "type": "object",
                "properties": {
                    "pdb_name": {"type": "string"},
                },
                "required": ["pdb_name"],
            }

            # Missing required pdb_name
            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {},
                }
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_PARAMETERS"
        assert "pdb_name" in error["message"]

    @pytest.mark.asyncio
    async def test_create_execution_invalid_parameter_type(self, client, mock_auth):
        """POST /executions returns 400 when parameter has wrong type (Task 1.4)."""
        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = {
                "type": "object",
                "properties": {
                    "size_gb": {"type": "number"},
                },
            }

            # size_gb should be number, not string
            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"size_gb": "ten"},
                }
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_PARAMETERS"

    @pytest.mark.asyncio
    async def test_create_execution_no_schema_accepts_any_parameters(self, client, mock_auth):
        """POST /executions accepts any parameters when action has no schema (Task 1.4)."""
        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service"), \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)), \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None  # No schema
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=1,
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"anything": "goes", "nested": {"value": 123}},
                }
            )

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio
    async def test_create_execution_all_environments_valid(self, client, mock_auth):
        """POST /executions accepts dev, staging, prod environments (Task 1.1)."""
        for env in ["dev", "staging", "prod"]:
            mock_execution_service = MagicMock()
            mock_execution_service.prepare_execution = AsyncMock(return_value=True)
            mock_execution_service.start_execution = AsyncMock()

            with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
                 patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
                 patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
                 patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
                 patch("app.api.v1.executions.get_vault_service"), \
                 patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)), \
                 patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

                mock_exists.return_value = True
                mock_rbac.return_value = True
                mock_schema.return_value = None
                mock_create.return_value = ExecutionCreateResponse(
                    execution_id=1,
                    status=ExecutionStatus.SUBMITTED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                )

                response = await client.post(
                    "/api/v1/executions",
                    json={
                        "action_id": 1,
                        "environment": env,
                        "parameters": {},
                    }
                )

            assert response.status_code == status.HTTP_201_CREATED, f"Failed for environment: {env}"

    @pytest.mark.asyncio
    async def test_create_execution_requires_authentication(self, client):
        """POST /executions returns 401 without authentication."""
        # Remove mock auth - should fail
        app.dependency_overrides.clear()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.auth_dev_bypass = False

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {},
                }
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetExecution:
    """Tests for GET /api/v1/executions/{id} (Story 4.1)."""

    @pytest.mark.asyncio
    async def test_get_execution_success(self, client, mock_auth):
        """GET /executions/{id} returns execution details."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ExecutionResponse(
                id=1,
                action_id=1,
                action_name="Create PDB",
                user_id=1,  # Same as mock_auth user
                environment=ExecutionEnvironment.DEV,
                parameters={"pdb_name": "TEST"},
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.get("/api/v1/executions/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["id"] == 1
        assert data["data"]["action_name"] == "Create PDB"
        assert data["data"]["status"] == "SUBMITTED"

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, client, mock_auth):
        """GET /executions/{id} returns 404 when not found."""
        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.get("/api/v1/executions/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_execution_not_owned_by_user(self, client, mock_auth_regular_user):
        """GET /executions/{id} returns 404 when execution belongs to another user (non-DBA)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ExecutionResponse(
                id=1,
                action_id=1,
                action_name="Create PDB",
                user_id=999,  # Different user than mock_auth_regular_user (id=1)
                environment=ExecutionEnvironment.DEV,
                parameters={},
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.get("/api/v1/executions/1")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListExecutions:
    """Tests for GET /api/v1/executions (Story 4.1)."""

    @pytest.mark.asyncio
    async def test_list_executions_returns_user_executions(self, client, mock_auth):
        """GET /executions returns list of user's executions and pagination (Story 4.8 AC4)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 2
            mock_list.return_value = [
                ExecutionResponse(
                    id=1,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=1,
                    environment=ExecutionEnvironment.DEV,
                    parameters={},
                    status=ExecutionStatus.SUBMITTED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                ),
                ExecutionResponse(
                    id=2,
                    action_id=2,
                    action_name="Drop PDB",
                    user_id=1,
                    environment=ExecutionEnvironment.STAGING,
                    parameters={},
                    status=ExecutionStatus.COMPLETED,
                    created_at=datetime(2026, 1, 29, 11, 0, 0),
                ),
            ]

            response = await client.get("/api/v1/executions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 2
        assert "pagination" in data
        assert data["pagination"]["total_count"] == 2
        assert data["pagination"]["page_size"] == 50
        mock_list.assert_called_once_with(user_id=1, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_list_executions_with_pagination(self, client, mock_auth):
        """GET /executions accepts limit and offset parameters (Story 4.8)."""
        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 0
            mock_list.return_value = []

            response = await client.get("/api/v1/executions?limit=10&offset=20")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["page"] == 3  # offset 20, limit 10 -> page 3
        assert data["pagination"]["total_count"] == 0
        mock_list.assert_called_once_with(user_id=1, limit=10, offset=20)

    @pytest.mark.asyncio
    async def test_list_executions_caps_limit_at_100(self, client, mock_auth):
        """GET /executions caps limit at 100 for performance."""
        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 0
            mock_list.return_value = []

            response = await client.get("/api/v1/executions?limit=500")

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(user_id=1, limit=100, offset=0)


class TestGetExecutionSteps:
    """Tests for GET /api/v1/executions/{id}/steps (Story 4.3, Task 6.3)."""

    @pytest.mark.asyncio
    async def test_get_execution_steps_returns_steps(self, client, mock_auth):
        """GET /executions/{id}/steps returns list of steps."""
        from app.models.execution import ExecutionResponse, ExecutionStepResponse, StepStatus, StepType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=1,
            action_name="Create PDB",
            user_id=1,  # Same as mock_auth
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.RUNNING,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )

        mock_steps = [
            ExecutionStepResponse(
                id=101,
                execution_id=1,
                step_order=1,
                step_name="Vault",
                step_type=StepType.VAULT,
                status=StepStatus.COMPLETED,
                started_at=datetime(2026, 1, 29, 10, 0, 0),
                completed_at=datetime(2026, 1, 29, 10, 0, 5),
            ),
            ExecutionStepResponse(
                id=102,
                execution_id=1,
                step_order=2,
                step_name="Platform",
                step_type=StepType.PLATFORM,
                status=StepStatus.RUNNING,
                started_at=datetime(2026, 1, 29, 10, 0, 5),
                platform_job_id="aap-job-123",
            ),
        ]

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.executions.execution_repository.get_steps_by_execution_id", new_callable=AsyncMock) as mock_steps_get:

            mock_get.return_value = mock_execution
            mock_steps_get.return_value = mock_steps

            response = await client.get("/api/v1/executions/1/steps")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 2
        assert data["data"][0]["step_name"] == "Vault"
        assert data["data"][0]["status"] == "COMPLETED"
        assert data["data"][1]["platform_job_id"] == "aap-job-123"

    @pytest.mark.asyncio
    async def test_get_execution_steps_not_found(self, client, mock_auth):
        """GET /executions/{id}/steps returns 404 when execution not found."""
        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.get("/api/v1/executions/999/steps")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_execution_steps_not_owned_by_user(self, client, mock_auth_regular_user):
        """GET /executions/{id}/steps returns 404 when not owned by user (non-DBA)."""
        from app.models.execution import ExecutionResponse

        mock_execution = ExecutionResponse(
            id=1,
            action_id=1,
            action_name="Create PDB",
            user_id=999,  # Different user
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.RUNNING,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_execution

            response = await client.get("/api/v1/executions/1/steps")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetStepLogs:
    """Tests for GET /api/v1/executions/{id}/steps/{step_id}/logs (Story 4.7, AC6, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_get_step_logs_returns_output_and_error_message(self, client, mock_auth):
        """GET /executions/{id}/steps/{step_id}/logs returns step logs with output/error_message."""
        from app.models.execution import ExecutionResponse, ExecutionStepResponse, StepStatus, StepType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=1,
            action_name="Create PDB",
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.COMPLETED,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )

        mock_step = ExecutionStepResponse(
            id=101,
            execution_id=1,
            step_order=1,
            step_name="Platform",
            step_type=StepType.PLATFORM,
            status=StepStatus.FAILED,
            started_at=datetime(2026, 1, 29, 10, 0, 0),
            completed_at=datetime(2026, 1, 29, 10, 0, 10),
            output={"job_id": "aap-123", "stdout": "..."},
            error_message="Connection timeout",
        )

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.executions.execution_repository.get_step_by_id", new_callable=AsyncMock) as mock_step_get:

            mock_get.return_value = mock_execution
            mock_step_get.return_value = mock_step

            response = await client.get("/api/v1/executions/1/steps/101/logs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["step_id"] == 101
        assert data["data"]["output"] == {"job_id": "aap-123", "stdout": "..."}
        assert data["data"]["error_message"] == "Connection timeout"
        assert "started_at" in data["data"]
        assert "completed_at" in data["data"]

    @pytest.mark.asyncio
    async def test_get_step_logs_execution_not_found(self, client, mock_auth):
        """GET step logs returns 404 when execution not found."""
        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.get("/api/v1/executions/999/steps/101/logs")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_step_logs_not_owned_by_user(self, client, mock_auth_regular_user):
        """GET step logs returns 404 when execution belongs to another user (non-DBA RBAC)."""
        from app.models.execution import ExecutionResponse

        mock_execution = ExecutionResponse(
            id=1,
            action_id=1,
            action_name="Create PDB",
            user_id=999,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.RUNNING,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_execution

            response = await client.get("/api/v1/executions/1/steps/101/logs")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_step_logs_step_not_found(self, client, mock_auth):
        """GET step logs returns 404 when step not found or step not in execution."""
        from app.models.execution import ExecutionResponse, ExecutionStepResponse, StepStatus, StepType

        mock_execution = ExecutionResponse(
            id=1,
            action_id=1,
            action_name="Create PDB",
            user_id=1,
            environment=ExecutionEnvironment.DEV,
            parameters={},
            status=ExecutionStatus.RUNNING,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )

        # Step exists but belongs to another execution (execution_id=2)
        mock_step = ExecutionStepResponse(
            id=101,
            execution_id=2,
            step_order=1,
            step_name="Platform",
            step_type=StepType.PLATFORM,
            status=StepStatus.COMPLETED,
        )

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.executions.execution_repository.get_step_by_id", new_callable=AsyncMock) as mock_step_get:

            mock_get.return_value = mock_execution
            mock_step_get.return_value = mock_step

            response = await client.get("/api/v1/executions/1/steps/101/logs")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["error"]["code"] == "STEP_NOT_FOUND"


class TestExecutionPerformance:
    """Tests for execution performance requirements (NFR2)."""

    @pytest.mark.asyncio
    async def test_create_execution_response_time_under_3_seconds(self, client, mock_auth):
        """POST /executions returns in < 3 seconds (NFR2, Task 6.3)."""
        import time

        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service") as mock_vault_factory, \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)) as mock_servicenow_factory, \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True  # User has permission
            mock_schema.return_value = None
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=1,
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            # Measure response time
            start_time = time.perf_counter()
            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"pdb_name": "TEST_PDB"},
                }
            )
            elapsed_time = time.perf_counter() - start_time

        assert response.status_code == status.HTTP_201_CREATED
        # NFR2: Response must be under 3 seconds (3000ms)
        assert elapsed_time < 3.0, f"Response time {elapsed_time:.3f}s exceeds NFR2 requirement of 3s"


class TestExecutionAudit:
    """Tests for execution audit trail (Story 6.1)."""

    @pytest.mark.asyncio
    async def test_create_execution_creates_audit_entry(self, client, mock_auth, mock_audit_repository):
        """POST /executions creates EXECUTION_SUBMITTED audit entry (AC1)."""
        from app.repositories.audit_repository import AuditActionType, AuditEntityType

        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service") as mock_vault_factory, \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)), \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=42,
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.post(
                "/api/v1/executions",
                json={
                    "action_id": 5,
                    "environment": "prod",
                    "parameters": {"pdb_name": "PROD_PDB"},
                }
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify audit_repository.create_entry was called with correct params
        mock_audit_repository.create_entry.assert_called_once()
        call_args = mock_audit_repository.create_entry.call_args

        # Check action_type and entity_type
        assert call_args.kwargs["action_type"] == AuditActionType.EXECUTION_SUBMITTED
        assert call_args.kwargs["entity_type"] == AuditEntityType.EXECUTION
        assert call_args.kwargs["entity_id"] == 42
        assert call_args.kwargs["user_id"] == "1"  # mock_auth user id

        # Check details contain required fields (AC1)
        details = call_args.kwargs["details"]
        assert details["action_id"] == 5
        assert details["environment"] == "prod"
        assert details["parameters"] == {"pdb_name": "PROD_PDB"}
        assert "rbac_context" in details

        # Check correlation_id is present (AC6)
        assert call_args.kwargs["correlation_id"] is not None

    @pytest.mark.asyncio
    async def test_create_execution_captures_ip_address(self, client, mock_auth, mock_audit_repository):
        """POST /executions captures IP address in audit entry (AC5)."""
        mock_execution_service = MagicMock()
        mock_execution_service.prepare_execution = AsyncMock(return_value=True)
        mock_execution_service.start_execution = AsyncMock()

        with patch("app.api.v1.executions.execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.executions.execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.executions.execution_repository.create_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac, \
             patch("app.api.v1.executions.get_vault_service") as mock_vault_factory, \
             patch("app.api.v1.executions.get_servicenow_service", new=AsyncMock(return_value=None)), \
             patch("app.api.v1.executions.ExecutionService", return_value=mock_execution_service):

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ExecutionCreateResponse(
                execution_id=1,
                status=ExecutionStatus.SUBMITTED,
                created_at=datetime(2026, 1, 29, 10, 0, 0),
            )

            response = await client.post(
                "/api/v1/executions",
                json={"action_id": 1, "environment": "dev", "parameters": {}},
            )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify ip_address is captured (may be testclient or None)
        call_args = mock_audit_repository.create_entry.call_args
        # ip_address should be passed (may be None for test client)
        assert "ip_address" in call_args.kwargs

        # Verify start_execution (background task) receives client_ip for AC5 propagation
        mock_execution_service.start_execution.assert_called_once()
        start_call = mock_execution_service.start_execution.call_args
        assert "client_ip" in start_call.kwargs


class TestListExecutionsScope:
    """Tests for GET /api/v1/executions with scope parameter (Story 8.9)."""

    @pytest.mark.asyncio
    async def test_list_executions_scope_mine_returns_user_executions(self, client, mock_auth):
        """GET /executions?scope=mine returns user's executions only (Story 8.9, AC3)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 1
            mock_list.return_value = [
                ExecutionResponse(
                    id=1,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=1,
                    environment=ExecutionEnvironment.DEV,
                    parameters={},
                    status=ExecutionStatus.COMPLETED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                ),
            ]

            response = await client.get("/api/v1/executions?scope=mine")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 1
        mock_list.assert_called_once_with(user_id=1, limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_list_executions_scope_all_returns_all_for_dba(self, client, mock_auth):
        """GET /executions?scope=all returns all executions for DBA (Story 8.9, AC2, AC7)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_all_executions", new_callable=AsyncMock) as mock_count_all, \
             patch("app.api.v1.executions.execution_repository.list_all_executions", new_callable=AsyncMock) as mock_list_all:
            mock_count_all.return_value = 3
            mock_list_all.return_value = [
                ExecutionResponse(
                    id=1,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=1,
                    user_display_name="Test DBA",
                    environment=ExecutionEnvironment.DEV,
                    parameters={},
                    status=ExecutionStatus.COMPLETED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                ),
                ExecutionResponse(
                    id=2,
                    action_id=2,
                    action_name="Drop PDB",
                    user_id=2,
                    user_display_name="Other User",
                    environment=ExecutionEnvironment.STAGING,
                    parameters={},
                    status=ExecutionStatus.RUNNING,
                    created_at=datetime(2026, 1, 29, 11, 0, 0),
                ),
                ExecutionResponse(
                    id=3,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=3,
                    user_display_name="Third User",
                    environment=ExecutionEnvironment.PROD,
                    parameters={},
                    status=ExecutionStatus.FAILED,
                    created_at=datetime(2026, 1, 29, 12, 0, 0),
                ),
            ]

            response = await client.get("/api/v1/executions?scope=all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 3
        assert data["pagination"]["total_count"] == 3
        mock_list_all.assert_called_once_with(limit=50, offset=0)

    @pytest.mark.asyncio
    async def test_list_executions_scope_all_fallback_for_non_dba(self, client, mock_auth_regular_user):
        """GET /executions?scope=all falls back to user's executions for non-DBA (Story 8.9, AC8)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 1
            mock_list.return_value = [
                ExecutionResponse(
                    id=1,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=1,
                    environment=ExecutionEnvironment.DEV,
                    parameters={},
                    status=ExecutionStatus.COMPLETED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                ),
            ]

            response = await client.get("/api/v1/executions?scope=all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should use user's list, not all executions (RBAC fallback)
        mock_list.assert_called_once_with(user_id=1, limit=50, offset=0)
        assert data["pagination"]["total_count"] == 1

    @pytest.mark.asyncio
    async def test_list_executions_scope_all_count_correct(self, client, mock_auth):
        """GET /executions?scope=all returns correct total_count (Story 8.9, AC7)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_all_executions", new_callable=AsyncMock) as mock_count_all, \
             patch("app.api.v1.executions.execution_repository.list_all_executions", new_callable=AsyncMock) as mock_list_all:
            mock_count_all.return_value = 150
            mock_list_all.return_value = []

            response = await client.get("/api/v1/executions?scope=all&limit=25&offset=50")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["pagination"]["total_count"] == 150
        assert data["pagination"]["page"] == 3  # offset 50, limit 25 -> page 3
        assert data["pagination"]["total_pages"] == 6  # 150 / 25 = 6 pages
        mock_list_all.assert_called_once_with(limit=25, offset=50)

    @pytest.mark.asyncio
    async def test_list_executions_scope_all_includes_user_display_name(self, client, mock_auth):
        """GET /executions?scope=all includes user_display_name in results (Story 8.9, AC9)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_all_executions", new_callable=AsyncMock) as mock_count_all, \
             patch("app.api.v1.executions.execution_repository.list_all_executions", new_callable=AsyncMock) as mock_list_all:
            mock_count_all.return_value = 1
            mock_list_all.return_value = [
                ExecutionResponse(
                    id=1,
                    action_id=1,
                    action_name="Create PDB",
                    user_id=2,
                    user_display_name="John Doe",
                    environment=ExecutionEnvironment.DEV,
                    parameters={},
                    status=ExecutionStatus.COMPLETED,
                    created_at=datetime(2026, 1, 29, 10, 0, 0),
                ),
            ]

            response = await client.get("/api/v1/executions?scope=all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["user_display_name"] == "John Doe"

    @pytest.mark.asyncio
    async def test_list_executions_scope_invalid_returns_422(self, client, mock_auth):
        """GET /executions?scope=invalid returns 422 validation error (Story 8.9)."""
        response = await client.get("/api/v1/executions?scope=invalid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_executions_default_scope_is_mine(self, client, mock_auth):
        """GET /executions without scope parameter defaults to scope=mine (Story 8.9)."""
        from app.models.execution import ExecutionResponse

        with patch("app.api.v1.executions.execution_repository.count_by_user", new_callable=AsyncMock) as mock_count, \
             patch("app.api.v1.executions.execution_repository.list_by_user", new_callable=AsyncMock) as mock_list:
            mock_count.return_value = 0
            mock_list.return_value = []

            response = await client.get("/api/v1/executions")

        assert response.status_code == status.HTTP_200_OK
        # Should call list_by_user, not list_all_executions
        mock_list.assert_called_once_with(user_id=1, limit=50, offset=0)


class TestGetExecutionStats:
    """Tests for GET /api/v1/executions/stats (Story 9.4, AC3)."""

    @pytest.mark.asyncio
    async def test_get_execution_stats_mine_returns_user_stats(self, client, mock_auth):
        """GET /executions/stats?scope=mine returns stats for current user only (Story 9.4, AC3)."""
        mock_stats = {
            "executions_jour": 5,
            "taux_succes_pct": 80.0,
            "executions_en_cours": 2,
            "executions_en_erreur": 1,
        }

        with patch("app.api.v1.executions.execution_repository.get_execution_stats", new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            response = await client.get("/api/v1/executions/stats?scope=mine")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["executions_jour"] == 5
        assert data["taux_succes_pct"] == 80.0
        assert data["executions_en_cours"] == 2
        assert data["executions_en_erreur"] == 1

        # Verify scope=mine was passed
        mock_get_stats.assert_called_once()
        call_kwargs = mock_get_stats.call_args.kwargs
        assert call_kwargs["scope"] == "mine"
        assert call_kwargs["user_id"] == 1

    @pytest.mark.asyncio
    async def test_get_execution_stats_all_dba_returns_all_stats(self, client, mock_auth):
        """GET /executions/stats?scope=all for DBA returns global stats (Story 9.4, AC3)."""
        mock_stats = {
            "executions_jour": 100,
            "taux_succes_pct": 92.5,
            "executions_en_cours": 10,
            "executions_en_erreur": 5,
        }

        with patch("app.api.v1.executions.execution_repository.get_execution_stats", new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            response = await client.get("/api/v1/executions/stats?scope=all")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["executions_jour"] == 100
        assert data["taux_succes_pct"] == 92.5

        # Verify scope=all was passed (DBA can view all)
        mock_get_stats.assert_called_once()
        call_kwargs = mock_get_stats.call_args.kwargs
        assert call_kwargs["scope"] == "all"
        assert call_kwargs["user_profiles"] == ["dba"]

    @pytest.mark.asyncio
    async def test_get_execution_stats_default_scope_is_mine(self, client, mock_auth):
        """GET /executions/stats without scope defaults to mine (Story 9.4, AC3)."""
        mock_stats = {
            "executions_jour": 3,
            "taux_succes_pct": 75.0,
            "executions_en_cours": 1,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.executions.execution_repository.get_execution_stats", new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            response = await client.get("/api/v1/executions/stats")

        assert response.status_code == status.HTTP_200_OK

        # Verify default scope=mine
        mock_get_stats.assert_called_once()
        call_kwargs = mock_get_stats.call_args.kwargs
        assert call_kwargs["scope"] == "mine"

    @pytest.mark.asyncio
    async def test_get_execution_stats_invalid_scope_returns_422(self, client, mock_auth):
        """GET /executions/stats?scope=invalid returns 422 (Story 9.4)."""
        response = await client.get("/api/v1/executions/stats?scope=invalid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_execution_stats_regular_user_scope_all_returns_mine(self, client, mock_auth_regular_user):
        """GET /executions/stats?scope=all for non-DBA user falls back to mine (Story 9.4, AC3)."""
        mock_stats = {
            "executions_jour": 2,
            "taux_succes_pct": 50.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 1,
        }

        with patch("app.api.v1.executions.execution_repository.get_execution_stats", new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            response = await client.get("/api/v1/executions/stats?scope=all")

        assert response.status_code == status.HTTP_200_OK

        # Repository will enforce RBAC (user_profiles will be used to decide effective scope)
        mock_get_stats.assert_called_once()
        call_kwargs = mock_get_stats.call_args.kwargs
        assert call_kwargs["scope"] == "all"  # User requested all
        assert call_kwargs["user_profiles"] == ["developer"]  # But user is not DBA

    @pytest.mark.asyncio
    async def test_get_execution_stats_handles_zero_stats(self, client, mock_auth):
        """GET /executions/stats returns 0 for all stats when no executions (Story 9.4)."""
        mock_stats = {
            "executions_jour": 0,
            "taux_succes_pct": 0.0,
            "executions_en_cours": 0,
            "executions_en_erreur": 0,
        }

        with patch("app.api.v1.executions.execution_repository.get_execution_stats", new_callable=AsyncMock) as mock_get_stats:
            mock_get_stats.return_value = mock_stats

            response = await client.get("/api/v1/executions/stats?scope=mine")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["executions_jour"] == 0
        assert data["taux_succes_pct"] == 0.0
        assert data["executions_en_cours"] == 0
        assert data["executions_en_erreur"] == 0
