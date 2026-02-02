"""Tests for scheduled executions API endpoint (Story 11.3, Task 9).

Tests POST /api/v1/scheduled-executions:
- Success case with valid parameters (AC1)
- Error validation: past date (AC2)
- Permission denied (AC3)
- Invalid parameters (AC4)
- Action not found (AC5)
- Audit log creation (AC6)
- Enriched response with action name (AC7)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.models.scheduled_execution import (
    ScheduledExecutionStatus,
    ScheduledExecutionCreateResult,
    ScheduledExecutionWithAction,
)


@pytest.fixture
def mock_audit_repository():
    """Mock audit_repository for tests (Story 11.3, AC6)."""
    with patch("app.api.v1.scheduled_executions.audit_repository") as mock_audit:
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
    """Mock authentication for scheduled execution endpoints."""
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


class TestCreateScheduledExecution:
    """Tests for POST /api/v1/scheduled-executions (Story 11.3)."""

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_success(self, client, mock_auth):
        """POST /scheduled-executions creates schedule and returns 201 (AC1)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.create_scheduled_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None  # No schema = no validation
            mock_create.return_value = ScheduledExecutionCreateResult(
                id=42,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )
            mock_get_by_id.return_value = ScheduledExecutionWithAction(
                id=42,
                action_id=1,
                action_name="Patching Oracle",
                action_description="Applies patches",
                user_id=1,
                environment="prod",
                parameters={"db_name": "PRODDB"},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {"db_name": "PRODDB"},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "data" in data
        assert data["data"]["scheduled_execution_id"] == 42
        assert data["data"]["action_id"] == 1
        assert data["data"]["action_name"] == "Patching Oracle"
        assert data["data"]["environment"] == "prod"
        assert data["data"]["status"] == "pending"
        assert "correlation_id" in data["data"]

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_past_date_returns_400(self, client, mock_auth):
        """POST /scheduled-executions returns 400 for past date (AC2)."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True  # Need to check date before action exists

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {},
                    "scheduled_at": past_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_SCHEDULED_DATE"
        assert "futur" in error["message"].lower()

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_no_permission_returns_403(self, client, mock_auth):
        """POST /scheduled-executions returns 403 when user lacks permission (AC3)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = False  # User does NOT have permission

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.json()["error"]
        assert error["code"] == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_invalid_parameters_returns_400(self, client, mock_auth):
        """POST /scheduled-executions returns 400 for invalid parameters (AC4)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            # Schema requires db_version to be a number
            mock_schema.return_value = {
                "type": "object",
                "properties": {
                    "db_version": {"type": "number"}
                },
                "required": ["db_version"],
            }

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {"db_version": "not_a_number"},  # Invalid type
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_PARAMETERS"

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_action_not_found_returns_404(self, client, mock_auth):
        """POST /scheduled-executions returns 404 when action doesn't exist (AC5)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 999,
                    "environment": "dev",
                    "parameters": {},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["error"]
        assert error["code"] == "ACTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_audit_log_created(self, client, mock_auth, mock_audit_repository):
        """POST /scheduled-executions creates audit log entry (AC6)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.create_scheduled_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ScheduledExecutionCreateResult(
                id=42,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )
            mock_get_by_id.return_value = ScheduledExecutionWithAction(
                id=42,
                action_id=1,
                action_name="Test Action",
                action_description=None,
                user_id=1,
                environment="dev",
                parameters={},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock_audit_repository.create_entry.assert_called_once()
        call_kwargs = mock_audit_repository.create_entry.call_args[1]
        assert call_kwargs["action_type"].value == "SCHEDULED_EXECUTION_CREATED"
        assert call_kwargs["entity_type"].value == "scheduled_execution"
        assert call_kwargs["entity_id"] == 42

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_enriched_response(self, client, mock_auth):
        """POST /scheduled-executions returns enriched response with action_name (AC7)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.create_scheduled_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ScheduledExecutionCreateResult(
                id=42,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )
            mock_get_by_id.return_value = ScheduledExecutionWithAction(
                id=42,
                action_id=1,
                action_name="Patching Oracle Database",
                action_description="Apply security patches to Oracle instances",
                user_id=1,
                environment="prod",
                parameters={"db_name": "PRODDB"},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {"db_name": "PRODDB"},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()["data"]
        assert data["action_name"] == "Patching Oracle Database"

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_validates_required_fields(self, client, mock_auth):
        """POST /scheduled-executions validates required fields."""
        response = await client.post(
            "/api/v1/scheduled-executions",
            json={
                # Missing required fields: action_id, environment, scheduled_at
            }
        )

        # LOW-1 FIX: Use HTTP_422_UNPROCESSABLE_CONTENT instead of deprecated constant
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_scheduled_execution_with_empty_parameters(self, client, mock_auth):
        """POST /scheduled-executions accepts empty parameters object."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        created_at = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.create_scheduled_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ScheduledExecutionCreateResult(
                id=1,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )
            mock_get_by_id.return_value = ScheduledExecutionWithAction(
                id=1,
                action_id=1,
                action_name="Test",
                action_description=None,
                user_id=1,
                environment="dev",
                parameters={},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "dev",
                    "parameters": {},
                    "scheduled_at": future_date.isoformat(),
                }
            )

        assert response.status_code == status.HTTP_201_CREATED
