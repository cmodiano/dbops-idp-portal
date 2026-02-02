"""Tests for scheduled executions external scheduler API (Story 11.10).

Tests GET /api/v1/scheduled-executions/pending (AC1, AC2, AC7):
- List pending executions for external scheduler
- Pagination and sorting (most urgent first)
- RBAC: requires DBOPS profile

Tests PATCH /api/v1/scheduled-executions/{id} with status="executed" (AC4, AC5, AC6, AC8):
- Mark one-time execution as executed
- Mark recurring execution as executed with next_execution_date recalculation
- Error handling (validation, not found, invalid state)
- Audit logging
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import quote
from httpx import AsyncClient, ASGITransport
from fastapi import status


def _format_datetime_for_url(dt: datetime) -> str:
    """Format datetime for URL query parameter (URL-safe ISO 8601 with Z suffix)."""
    # Use Z suffix instead of +00:00 to avoid URL encoding issues
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

from app.main import app
from app.models.scheduled_execution import (
    ScheduledExecutionStatus,
    ScheduledExecutionWithAction,
    ScheduledExecutionPendingItem,
    RecurringPatternResponse,
)


@pytest.fixture
def mock_audit_repository():
    """Mock audit_repository for tests."""
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
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mock_auth_dba():
    """Mock authentication for DBA profile (cannot access pending endpoint)."""
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
def mock_auth_dbops():
    """Mock authentication for DBOPS profile (scheduler service account)."""
    from app.api.deps import get_current_user
    from app.models.auth import UserProfile

    user = UserProfile(
        id=2,
        username="scheduler_svc",
        display_name="Scheduler Service Account",
        profile="dbops",
    )

    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


# ============================================================================
# Story 11.10 Task 12: Tests for GET /api/v1/scheduled-executions/pending
# ============================================================================


class TestGetPendingExecutions:
    """Tests for GET /api/v1/scheduled-executions/pending (Story 11.10, AC1, AC2)."""

    @pytest.mark.asyncio
    async def test_get_pending_executions_one_time(self, client, mock_auth_dbops):
        """GET /pending returns one-time executions with scheduled_at <= before (AC1)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)
        scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=30)  # Past, should be included

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=1,
                    action_id=10,
                    action_name="Patching Oracle",
                    user_id=1,
                    user_name="test_user",
                    environment="prod",
                    parameters={"db_name": "PRODDB"},
                    scheduled_at=scheduled_at,
                    recurring_pattern=None,
                    correlation_id="uuid-123",
                    created_at=datetime.now(timezone.utc) - timedelta(days=1),
                )
            ]
            mock_count.return_value = 1

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["scheduled_execution_id"] == 1
        assert data["data"][0]["action_name"] == "Patching Oracle"
        assert data["data"][0]["recurring_pattern"] is None
        assert "pagination" in data
        assert data["pagination"]["total_count"] == 1

    @pytest.mark.asyncio
    async def test_get_pending_executions_recurring_daily(self, client, mock_auth_dbops):
        """GET /pending returns daily recurring executions with next_execution_date <= before (AC1)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)
        next_exec = datetime.now(timezone.utc) - timedelta(minutes=10)  # Should be included

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=2,
                    action_id=11,
                    action_name="Daily Backup",
                    user_id=1,
                    user_name="test_user",
                    environment="prod",
                    parameters={},
                    scheduled_at=None,  # NULL for recurring
                    recurring_pattern=RecurringPatternResponse(
                        pattern_type="daily",
                        pattern_config={"hour": 2, "minute": 30},
                        next_execution_date=next_exec,
                        is_active=True,
                    ),
                    correlation_id="uuid-456",
                    created_at=datetime.now(timezone.utc) - timedelta(days=7),
                )
            ]
            mock_count.return_value = 1

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["scheduled_at"] is None
        assert data["data"][0]["recurring_pattern"] is not None
        assert data["data"][0]["recurring_pattern"]["pattern_type"] == "daily"

    @pytest.mark.asyncio
    async def test_get_pending_executions_recurring_cron(self, client, mock_auth_dbops):
        """GET /pending returns cron recurring executions with next_execution_date <= before (AC1)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)
        next_exec = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=3,
                    action_id=12,
                    action_name="Cron Job",
                    user_id=1,
                    user_name="test_user",
                    environment="dev",
                    parameters={},
                    scheduled_at=None,
                    recurring_pattern=RecurringPatternResponse(
                        pattern_type="cron",
                        pattern_config={"cron_expression": "0 2 * * 1-5"},
                        next_execution_date=next_exec,
                        is_active=True,
                    ),
                    correlation_id="uuid-789",
                    created_at=datetime.now(timezone.utc) - timedelta(days=30),
                )
            ]
            mock_count.return_value = 1

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"][0]["recurring_pattern"]["pattern_type"] == "cron"

    @pytest.mark.asyncio
    async def test_get_pending_executions_empty_list(self, client, mock_auth_dbops):
        """GET /pending returns empty list when no executions match (AC6)."""
        before = datetime.now(timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = []
            mock_count.return_value = 0

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []
        assert data["pagination"]["total_count"] == 0
        assert data["pagination"]["total_pages"] == 1

    @pytest.mark.asyncio
    async def test_get_pending_executions_pagination(self, client, mock_auth_dbops):
        """GET /pending supports pagination with limit and offset (AC2)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=i,
                    action_id=10,
                    action_name=f"Action {i}",
                    user_id=1,
                    user_name="test_user",
                    environment="prod",
                    parameters={},
                    scheduled_at=datetime.now(timezone.utc),
                    recurring_pattern=None,
                    correlation_id=f"uuid-{i}",
                    created_at=datetime.now(timezone.utc),
                )
                for i in range(10)
            ]
            mock_count.return_value = 250  # Total across all pages

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}&limit=10&offset=0"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]) == 10
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total_count"] == 250
        assert data["pagination"]["total_pages"] == 25

        # Verify pagination params passed to repository
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_pending_executions_includes_action_name(self, client, mock_auth_dbops):
        """GET /pending includes action_name from JOIN with ACTIONS_CATALOG (AC1)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=1,
                    action_id=42,
                    action_name="Patch Oracle 19c Security",
                    user_id=1,
                    user_name="marc.dubois",
                    environment="prod",
                    parameters={"db_sid": "ORCL"},
                    scheduled_at=datetime.now(timezone.utc),
                    recurring_pattern=None,
                    correlation_id="uuid-abc",
                    created_at=datetime.now(timezone.utc),
                )
            ]
            mock_count.return_value = 1

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"][0]
        assert data["action_name"] == "Patch Oracle 19c Security"
        assert data["action_id"] == 42

    @pytest.mark.asyncio
    async def test_get_pending_executions_includes_user_name(self, client, mock_auth_dbops):
        """GET /pending includes user_name from JOIN with USERS (AC1)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = [
                ScheduledExecutionPendingItem(
                    scheduled_execution_id=1,
                    action_id=10,
                    action_name="Test Action",
                    user_id=123,
                    user_name="marc.dubois",
                    environment="prod",
                    parameters={},
                    scheduled_at=datetime.now(timezone.utc),
                    recurring_pattern=None,
                    correlation_id="uuid-xyz",
                    created_at=datetime.now(timezone.utc),
                )
            ]
            mock_count.return_value = 1

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"][0]
        assert data["user_name"] == "marc.dubois"
        assert data["user_id"] == 123


# ============================================================================
# Story 11.10 Task 14: Tests for RBAC and Security
# ============================================================================


class TestGetPendingExecutionsRBAC:
    """Tests for GET /pending RBAC (Story 11.10, AC7)."""

    @pytest.mark.asyncio
    async def test_get_pending_requires_dbops_profile(self, client, mock_auth_dba):
        """GET /pending returns 403 for non-DBOPS users (AC7)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)

        response = await client.get(
            f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.json()["error"]
        assert error["code"] == "PERMISSION_DENIED"
        assert "dbops" in error["message"].lower() or "DBOPS" in error["details"].get("required_profile", "")

    @pytest.mark.asyncio
    async def test_get_pending_with_dbops_profile(self, client, mock_auth_dbops):
        """GET /pending returns 200 for DBOPS users (AC7)."""
        before = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.list_pending_executions", new_callable=AsyncMock) as mock_list, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.count_pending_executions", new_callable=AsyncMock) as mock_count:

            mock_list.return_value = []
            mock_count.return_value = 0

            response = await client.get(
                f"/api/v1/scheduled-executions/pending?before={_format_datetime_for_url(before)}"
            )

        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Story 11.10 Task 13: Tests for PATCH status="executed"
# ============================================================================


class TestUpdateScheduledExecutionExecuted:
    """Tests for PATCH /api/v1/scheduled-executions/{id} with status="executed" (Story 11.10, AC4-AC6)."""

    @pytest.mark.asyncio
    async def test_update_to_executed_one_time_success(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed for one-time execution (AC4)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=1,
                action_id=10,
                action_name="One-time Task",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = None  # One-time, no recurring pattern
            mock_update.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/1",
                json={"status": "executed", "execution_id": 456}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["status"] == "executed"
        assert data["execution_id"] == 456
        assert data["next_execution_date"] is None  # One-time, no next execution

        # Verify update was called
        mock_update.assert_called_once_with(
            scheduled_execution_id=1,
            new_status="executed",
            execution_id=456,
        )

        # Verify audit log
        mock_audit_repository.create_entry.assert_called_once()
        call_kwargs = mock_audit_repository.create_entry.call_args[1]
        assert call_kwargs["action_type"].value == "SCHEDULED_EXECUTION_EXECUTED"
        assert call_kwargs["details"]["recurring"] is False

    @pytest.mark.asyncio
    async def test_update_to_executed_recurring_daily(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed for daily recurring recalculates next_execution_date (AC5)."""
        current_next = datetime.now(timezone.utc)
        expected_new_next = current_next + timedelta(days=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_recurring_pattern_next_execution", new_callable=AsyncMock) as mock_update_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update_status:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=2,
                action_id=11,
                action_name="Daily Backup",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=None,  # Recurring
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = RecurringPatternResponse(
                pattern_type="daily",
                pattern_config={"hour": 2, "minute": 30},
                next_execution_date=current_next,
                is_active=True,
            )
            mock_update_pattern.return_value = True
            mock_update_status.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/2",
                json={"status": "executed", "execution_id": 789}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["status"] == "pending"  # Recurring continues with status=pending
        assert data["execution_id"] == 789
        assert data["next_execution_date"] is not None

        # Verify next_execution_date was recalculated (daily = +1 day)
        mock_update_pattern.assert_called_once()
        call_args = mock_update_pattern.call_args[1]
        new_next_date = call_args["new_next_execution_date"]
        assert new_next_date.date() == expected_new_next.date()

        # Verify status was set back to "pending" for recurring
        mock_update_status.assert_called_once_with(
            scheduled_execution_id=2,
            new_status="pending",
            execution_id=789,
        )

        # Verify audit log
        call_kwargs = mock_audit_repository.create_entry.call_args[1]
        assert call_kwargs["details"]["recurring"] is True
        assert "next_execution_date" in call_kwargs["details"]

    @pytest.mark.asyncio
    async def test_update_to_executed_recurring_weekly(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed for weekly recurring recalculates next_execution_date (AC5)."""
        current_next = datetime.now(timezone.utc)
        expected_new_next = current_next + timedelta(weeks=1)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_recurring_pattern_next_execution", new_callable=AsyncMock) as mock_update_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update_status:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=3,
                action_id=12,
                action_name="Weekly Maintenance",
                action_description=None,
                user_id=1,
                environment="staging",
                parameters={},
                scheduled_at=None,
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = RecurringPatternResponse(
                pattern_type="weekly",
                pattern_config={"day_of_week": 1, "hour": 14, "minute": 0},
                next_execution_date=current_next,
                is_active=True,
            )
            mock_update_pattern.return_value = True
            mock_update_status.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/3",
                json={"status": "executed", "execution_id": 999}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["status"] == "pending"  # Recurring continues

        # Verify next_execution_date was incremented by 7 days
        mock_update_pattern.assert_called_once()
        call_args = mock_update_pattern.call_args[1]
        new_next_date = call_args["new_next_execution_date"]
        assert new_next_date.date() == expected_new_next.date()

    @pytest.mark.asyncio
    async def test_update_to_executed_recurring_cron(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed for cron recurring recalculates next_execution_date via croniter (AC5)."""
        current_next = datetime(2026, 2, 3, 2, 0, 0, tzinfo=timezone.utc)  # Monday 2am

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_recurring_pattern_next_execution", new_callable=AsyncMock) as mock_update_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update_status:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=4,
                action_id=13,
                action_name="Cron Weekday Task",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=None,
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = RecurringPatternResponse(
                pattern_type="cron",
                pattern_config={"cron_expression": "0 2 * * 1-5"},  # Weekdays at 2am
                next_execution_date=current_next,
                is_active=True,
            )
            mock_update_pattern.return_value = True
            mock_update_status.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/4",
                json={"status": "executed", "execution_id": 1234}
            )

        assert response.status_code == status.HTTP_200_OK

        # Verify croniter was used to calculate next execution (next weekday at 2am)
        mock_update_pattern.assert_called_once()
        call_args = mock_update_pattern.call_args[1]
        new_next_date = call_args["new_next_execution_date"]
        # Should be next weekday after Feb 3, 2026 (which is a Tuesday)
        assert new_next_date > current_next

    @pytest.mark.asyncio
    async def test_update_to_executed_missing_execution_id_returns_error(self, client, mock_auth_dbops):
        """PATCH with status=executed without execution_id returns error (AC6)."""
        response = await client.patch(
            "/api/v1/scheduled-executions/1",
            json={"status": "executed"}  # Missing execution_id
        )

        # Pydantic model_validator raises ValueError which becomes 422 validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        # Verify the error message mentions execution_id
        error_str = str(error["details"]["validation_errors"])
        assert "execution_id" in error_str.lower()

    @pytest.mark.asyncio
    async def test_update_to_executed_not_found_returns_404(self, client, mock_auth_dbops):
        """PATCH with non-existent ID returns 404 (AC6)."""
        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            response = await client.patch(
                "/api/v1/scheduled-executions/999",
                json={"status": "executed", "execution_id": 456}
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["error"]
        assert error["code"] == "SCHEDULED_EXECUTION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_already_executed_returns_400(self, client, mock_auth_dbops):
        """PATCH on already executed scheduled execution returns 400 (AC6)."""
        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = ScheduledExecutionWithAction(
                id=1,
                action_id=10,
                action_name="Already Executed",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=datetime.now(timezone.utc) - timedelta(days=1),
                status=ScheduledExecutionStatus.EXECUTED,  # Already executed
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )

            response = await client.patch(
                "/api/v1/scheduled-executions/1",
                json={"status": "executed", "execution_id": 456}
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "INVALID_STATE"

    @pytest.mark.asyncio
    async def test_update_to_executed_audit_log(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed creates SCHEDULED_EXECUTION_EXECUTED audit log (AC8)."""
        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=42,
                action_id=10,
                action_name="Audit Test",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = None  # One-time
            mock_update.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/42",
                json={"status": "executed", "execution_id": 9999}
            )

        assert response.status_code == status.HTTP_200_OK

        mock_audit_repository.create_entry.assert_called_once()
        call_kwargs = mock_audit_repository.create_entry.call_args[1]
        assert call_kwargs["action_type"].value == "SCHEDULED_EXECUTION_EXECUTED"
        assert call_kwargs["entity_type"].value == "scheduled_execution"
        assert call_kwargs["entity_id"] == 42
        assert call_kwargs["details"]["execution_id"] == 9999
        assert call_kwargs["details"]["action_name"] == "Audit Test"

    @pytest.mark.asyncio
    async def test_update_to_executed_execution_id_populated(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=executed populates EXECUTION_ID in DB (AC4)."""
        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_recurring_pattern", new_callable=AsyncMock) as mock_get_pattern, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_scheduled_execution_status_with_execution_id", new_callable=AsyncMock) as mock_update:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=1,
                action_id=10,
                action_name="Test",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_get_pattern.return_value = None
            mock_update.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/1",
                json={"status": "executed", "execution_id": 5678}
            )

        assert response.status_code == status.HTTP_200_OK

        # Verify execution_id was passed to repository
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args[1]
        assert call_kwargs["execution_id"] == 5678


# ============================================================================
# Story 11.10: Backward Compatibility with Story 11.6 (Cancel)
# ============================================================================


class TestUpdateScheduledExecutionCancelled:
    """Tests for PATCH /api/v1/scheduled-executions/{id} backward compatibility (Story 11.6)."""

    @pytest.mark.asyncio
    async def test_cancel_with_explicit_status_works(self, client, mock_auth_dbops, mock_audit_repository):
        """PATCH with status=cancelled still works (backward compat with Story 11.6)."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.update_status", new_callable=AsyncMock) as mock_update:

            mock_get.return_value = ScheduledExecutionWithAction(
                id=1,
                action_id=10,
                action_name="To Cancel",
                action_description=None,
                user_id=2,  # Same as mock_auth_dbops
                environment="prod",
                parameters={},
                scheduled_at=future_date,
                status=ScheduledExecutionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            mock_update.return_value = True

            response = await client.patch(
                "/api/v1/scheduled-executions/1",
                json={"status": "cancelled"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["status"] == "cancelled"

        # Verify audit log for cancelled
        call_kwargs = mock_audit_repository.create_entry.call_args[1]
        assert call_kwargs["action_type"].value == "SCHEDULED_EXECUTION_CANCELLED"
