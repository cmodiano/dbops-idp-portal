"""Tests for approval API endpoints (Story 7.4).

Tests:
- POST /api/v1/executions/{id}/approve
- POST /api/v1/executions/{id}/reject
- GET /api/v1/executions/pending-approvals
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.api.deps import get_current_user
from app.models.auth import UserProfile
from app.models.execution import ExecutionStatus, ExecutionEnvironment, ExecutionResponse


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


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
def mock_auth_dba():
    """Mock authentication with DBA user for approval tests."""
    user = UserProfile(
        id=10,
        username="dba-user",
        display_name="DBA User",
        profile="DBA",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_auth_dbops():
    """Mock authentication with DBOPS user for approval tests."""
    user = UserProfile(
        id=11,
        username="dbops-user",
        display_name="DBOPS User",
        profile="DBOPS",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_auth_client():
    """Mock authentication with CLIENT user (cannot approve)."""
    user = UserProfile(
        id=1,
        username="client-user",
        display_name="Client User",
        profile="CLIENT",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def pending_execution():
    """Execution in PENDING_APPROVAL status."""
    return ExecutionResponse(
        id=42,
        action_id=5,
        action_name="Create PDB",
        user_id=1,  # Different from DBA user (10)
        environment=ExecutionEnvironment.PROD,
        parameters={"pdb_name": "TEST"},
        status=ExecutionStatus.PENDING_APPROVAL,
        servicenow_change_id=None,
        started_at=None,
        completed_at=None,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
    )


class TestApproveExecution:
    """Tests for POST /api/v1/executions/{id}/approve (Story 7.4, AC3, AC5)."""

    @pytest.mark.asyncio
    async def test_approve_success(self, client, mock_auth_dba, pending_execution):
        """DBA can approve pending execution."""
        with (
            patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get,
            patch("app.api.v1.executions.execution_repository.approve", new_callable=AsyncMock) as mock_approve,
            patch("app.api.v1.executions.get_vault_service") as mock_vault,
            patch("app.api.v1.executions.get_servicenow_service", new_callable=AsyncMock),
            patch("app.api.v1.executions.get_execution_ws_manager"),
            patch("app.api.v1.executions.get_dashboard_ws_manager"),
            patch("app.api.v1.executions.ExecutionService") as mock_exec_service,
        ):
            mock_get.return_value = pending_execution
            mock_approve.return_value = True
            mock_exec_service_instance = MagicMock()
            mock_exec_service_instance.prepare_execution = AsyncMock()
            mock_exec_service_instance.start_execution = AsyncMock()
            mock_exec_service.return_value = mock_exec_service_instance

            response = await client.post("/api/v1/executions/42/approve", json={"comment": "Approved"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()["data"]
            assert data["execution_id"] == 42
            assert data["status"] == "SUBMITTED"
            assert data["approved_by"] == 10

    @pytest.mark.asyncio
    async def test_approve_forbidden_for_client_user(self, client, mock_auth_client):
        """Client user cannot approve executions."""
        response = await client.post("/api/v1/executions/42/approve")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_approve_self_approval_forbidden(self, client, mock_auth_dba, pending_execution):
        """DBA cannot approve their own execution."""
        # Set execution user_id to match DBA user
        pending_execution.user_id = mock_auth_dba.id

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pending_execution

            response = await client.post("/api/v1/executions/42/approve")

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert response.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"

    @pytest.mark.asyncio
    async def test_approve_not_found(self, client, mock_auth_dba):
        """Approve returns 404 when execution not found."""
        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.post("/api/v1/executions/999/approve")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_approve_wrong_status(self, client, mock_auth_dba, pending_execution):
        """Approve returns 400 when execution is not PENDING_APPROVAL."""
        pending_execution.status = ExecutionStatus.SUBMITTED

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pending_execution

            response = await client.post("/api/v1/executions/42/approve")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.json()["error"]["code"] == "INVALID_STATUS"


class TestRejectExecution:
    """Tests for POST /api/v1/executions/{id}/reject (Story 7.4, AC4, AC5)."""

    @pytest.mark.asyncio
    async def test_reject_success(self, client, mock_auth_dba, pending_execution):
        """DBA can reject pending execution."""
        with (
            patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get,
            patch("app.api.v1.executions.execution_repository.reject", new_callable=AsyncMock) as mock_reject,
        ):
            mock_get.return_value = pending_execution
            mock_reject.return_value = True

            response = await client.post("/api/v1/executions/42/reject", json={"comment": "Policy violation"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()["data"]
            assert data["execution_id"] == 42
            assert data["status"] == "REJECTED"
            assert data["rejected_by"] == 10
            assert data["rejection_reason"] == "Policy violation"

    @pytest.mark.asyncio
    async def test_reject_forbidden_for_client_user(self, client, mock_auth_client):
        """Client user cannot reject executions."""
        response = await client.post("/api/v1/executions/42/reject")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_reject_not_found(self, client, mock_auth_dba):
        """Reject returns 404 when execution not found."""
        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.post("/api/v1/executions/999/reject")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_reject_wrong_status(self, client, mock_auth_dba, pending_execution):
        """Reject returns 400 when execution is not PENDING_APPROVAL."""
        pending_execution.status = ExecutionStatus.RUNNING

        with patch("app.api.v1.executions.execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = pending_execution

            response = await client.post("/api/v1/executions/42/reject")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert response.json()["error"]["code"] == "INVALID_STATUS"


class TestListPendingApprovals:
    """Tests for GET /api/v1/executions/pending-approvals (Story 7.4, AC2, AC6)."""

    @pytest.mark.asyncio
    async def test_list_pending_approvals_success(self, client, mock_auth_dba, pending_execution):
        """DBA can list pending approvals."""
        with (
            patch("app.api.v1.executions.execution_repository.count_pending_approvals", new_callable=AsyncMock) as mock_count,
            patch("app.api.v1.executions.execution_repository.list_pending_approvals", new_callable=AsyncMock) as mock_list,
        ):
            mock_count.return_value = 1
            mock_list.return_value = [pending_execution]

            response = await client.get("/api/v1/executions/pending-approvals")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["data"]) == 1
            assert data["data"][0]["id"] == 42
            assert data["data"][0]["status"] == "PENDING_APPROVAL"
            assert data["pagination"]["total_count"] == 1

    @pytest.mark.asyncio
    async def test_list_pending_approvals_count_only(self, client, mock_auth_dba):
        """DBA can get count only for pending approvals."""
        with patch("app.api.v1.executions.execution_repository.count_pending_approvals", new_callable=AsyncMock) as mock_count:
            mock_count.return_value = 5

            response = await client.get("/api/v1/executions/pending-approvals?count_only=true")

            assert response.status_code == status.HTTP_200_OK
            assert response.json() == {"count": 5}

    @pytest.mark.asyncio
    async def test_list_pending_approvals_forbidden_for_client(self, client, mock_auth_client):
        """Client user cannot list pending approvals."""
        response = await client.get("/api/v1/executions/pending-approvals")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_dbops_can_list_pending_approvals(self, client, mock_auth_dbops, pending_execution):
        """DBOPS user can also list pending approvals."""
        with (
            patch("app.api.v1.executions.execution_repository.count_pending_approvals", new_callable=AsyncMock) as mock_count,
            patch("app.api.v1.executions.execution_repository.list_pending_approvals", new_callable=AsyncMock) as mock_list,
        ):
            mock_count.return_value = 1
            mock_list.return_value = [pending_execution]

            response = await client.get("/api/v1/executions/pending-approvals")

            assert response.status_code == status.HTTP_200_OK
