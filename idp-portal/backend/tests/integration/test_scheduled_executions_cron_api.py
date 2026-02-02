"""Integration tests for cron scheduled executions API endpoints (Story 11.8).

Tests:
- POST /api/v1/scheduled-executions with cron pattern (AC4, AC5)
- GET /api/v1/scheduled-executions/validate-cron (AC2)
- GET /api/v1/scheduled-executions/cron-next-executions (AC2)
- Audit logging for cron operations (AC11)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.models.scheduled_execution import (
    ScheduledExecutionStatus,
    ScheduledExecutionCreateResult,
    ScheduledExecutionWithAction,
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


class TestValidateCronEndpoint:
    """Tests for GET /api/v1/scheduled-executions/validate-cron (Story 11.8, AC2)."""

    @pytest.mark.asyncio
    async def test_validate_cron_valid_expression(self, client, mock_auth):
        """GET /validate-cron with valid expression returns {"valid": true}."""
        response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": "0 2 * * 1-5"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert data["error"] == ""

    @pytest.mark.asyncio
    async def test_validate_cron_invalid_expression(self, client, mock_auth):
        """GET /validate-cron with invalid expression returns {"valid": false}."""
        response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": "99 99 * * *"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert "invalide" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_validate_cron_empty_expression(self, client, mock_auth):
        """GET /validate-cron with empty expression returns {"valid": false}."""
        response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": ""},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False

    @pytest.mark.asyncio
    async def test_validate_cron_every_15_minutes(self, client, mock_auth):
        """GET /validate-cron with "*/15 * * * *" returns valid."""
        response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": "*/15 * * * *"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_cron_first_of_month(self, client, mock_auth):
        """GET /validate-cron with "0 0 1 * *" (first of month) returns valid."""
        response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": "0 0 1 * *"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True


class TestCronNextExecutionsEndpoint:
    """Tests for GET /api/v1/scheduled-executions/cron-next-executions (Story 11.8, AC2)."""

    @pytest.mark.asyncio
    async def test_cron_next_executions_returns_5_dates(self, client, mock_auth):
        """GET /cron-next-executions returns array of 5 ISO datetime strings."""
        response = await client.get(
            "/api/v1/scheduled-executions/cron-next-executions",
            params={"expression": "0 2 * * *", "count": 5},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "executions" in data
        assert len(data["executions"]) == 5

        # Verify all are valid ISO datetime strings
        for exec_time in data["executions"]:
            parsed = datetime.fromisoformat(exec_time)
            assert parsed.tzinfo is not None  # Should have timezone

    @pytest.mark.asyncio
    async def test_cron_next_executions_custom_count(self, client, mock_auth):
        """GET /cron-next-executions with count=3 returns 3 dates."""
        response = await client.get(
            "/api/v1/scheduled-executions/cron-next-executions",
            params={"expression": "0 2 * * 1-5", "count": 3},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["executions"]) == 3

    @pytest.mark.asyncio
    async def test_cron_next_executions_invalid_expression(self, client, mock_auth):
        """GET /cron-next-executions with invalid expression returns 400."""
        response = await client.get(
            "/api/v1/scheduled-executions/cron-next-executions",
            params={"expression": "invalid cron", "count": 5},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_cron_next_executions_every_15_minutes(self, client, mock_auth):
        """GET /cron-next-executions with */15 pattern returns correct intervals."""
        response = await client.get(
            "/api/v1/scheduled-executions/cron-next-executions",
            params={"expression": "*/15 * * * *", "count": 4},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["executions"]) == 4

        # Verify intervals are 15 minutes apart
        times = [datetime.fromisoformat(t) for t in data["executions"]]
        for i in range(1, len(times)):
            diff = times[i] - times[i - 1]
            assert diff == timedelta(minutes=15)


class TestCreateCronScheduledExecution:
    """Tests for POST /api/v1/scheduled-executions with cron pattern (Story 11.8, AC4, AC5)."""

    @pytest.mark.asyncio
    async def test_create_cron_recurring_execution_success(self, client, mock_auth):
        """POST /scheduled-executions with cron pattern creates recurring execution."""
        created_at = datetime.now(timezone.utc)
        next_exec = datetime(2026, 2, 3, 2, 0, tzinfo=timezone.utc)

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
                action_description="Test description",
                user_id=1,
                environment="prod",
                parameters={"db_name": "PRODDB"},
                scheduled_at=None,  # NULL for recurring
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
                recurring_pattern=RecurringPatternResponse(
                    pattern_type="cron",
                    pattern_config={"cron_expression": "0 2 * * 1-5"},
                    next_execution_date=next_exec,
                    is_active=True,
                ),
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {"db_name": "PRODDB"},
                    "recurring_pattern": {
                        "pattern_type": "cron",
                        "pattern_config": {
                            "cron_expression": "0 2 * * 1-5"
                        },
                    },
                },
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()["data"]

            assert data["scheduled_execution_id"] == 42
            assert data["scheduled_at"] is None  # NULL for recurring
            assert data["recurring_pattern"] is not None
            assert data["recurring_pattern"]["pattern_type"] == "cron"
            assert data["recurring_pattern"]["pattern_config"]["cron_expression"] == "0 2 * * 1-5"
            assert data["recurring_pattern"]["is_active"] is True

    def test_create_cron_invalid_expression_pydantic_validation(self):
        """Pydantic model rejects invalid cron expression (Story 11.8, AC5)."""
        from pydantic import ValidationError
        from app.models.scheduled_execution import ScheduledExecutionCreate

        # Invalid cron expression should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            ScheduledExecutionCreate(
                action_id=1,
                environment="prod",
                parameters={},
                recurring_pattern={
                    "pattern_type": "cron",
                    "pattern_config": {"cron_expression": "99 99 * * *"},
                },
            )

        # Verify error message mentions cron invalide
        error_str = str(exc_info.value)
        assert "cron" in error_str.lower() or "invalide" in error_str.lower()

    def test_create_cron_missing_expression_pydantic_validation(self):
        """Pydantic model rejects missing cron_expression (Story 11.8, AC5)."""
        from pydantic import ValidationError
        from app.models.scheduled_execution import ScheduledExecutionCreate

        # Missing cron_expression should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            ScheduledExecutionCreate(
                action_id=1,
                environment="prod",
                parameters={},
                recurring_pattern={
                    "pattern_type": "cron",
                    "pattern_config": {},  # Missing cron_expression
                },
            )

        error_str = str(exc_info.value)
        assert "cron_expression" in error_str.lower() or "requis" in error_str.lower()


class TestCronAuditLogging:
    """Tests for audit logging of cron operations (Story 11.8, AC11)."""

    @pytest.mark.asyncio
    async def test_create_cron_creates_audit_log(self, client, mock_auth, mock_audit_repository):
        """Creating cron execution logs SCHEDULED_EXECUTION_RECURRING_CREATED."""
        created_at = datetime.now(timezone.utc)
        next_exec = datetime(2026, 2, 3, 2, 0, tzinfo=timezone.utc)

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
                environment="prod",
                parameters={},
                scheduled_at=None,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
                recurring_pattern=RecurringPatternResponse(
                    pattern_type="cron",
                    pattern_config={"cron_expression": "0 2 * * 1-5"},
                    next_execution_date=next_exec,
                    is_active=True,
                ),
            )

            response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {},
                    "recurring_pattern": {
                        "pattern_type": "cron",
                        "pattern_config": {"cron_expression": "0 2 * * 1-5"},
                    },
                },
            )

            assert response.status_code == status.HTTP_201_CREATED

            # Verify audit log was called with SCHEDULED_EXECUTION_RECURRING_CREATED
            mock_audit_repository.create_entry.assert_called_once()
            call_args = mock_audit_repository.create_entry.call_args
            # Enum value might be upper or lowercase depending on Enum definition
            assert "recurring" in call_args.kwargs["action_type"].value.lower()
            assert "recurring_pattern" in call_args.kwargs["details"]
            assert call_args.kwargs["details"]["recurring_pattern"]["pattern_type"] == "cron"


class TestCronCoexistenceWithDailyWeekly:
    """Tests for cron coexistence with daily/weekly patterns (Story 11.8, AC12)."""

    @pytest.mark.asyncio
    async def test_validate_cron_does_not_affect_daily_pattern(self, client, mock_auth):
        """Cron validation endpoint does not interfere with daily pattern creation."""
        # First validate a cron expression
        validate_response = await client.get(
            "/api/v1/scheduled-executions/validate-cron",
            params={"expression": "0 2 * * 1-5"},
        )
        assert validate_response.status_code == status.HTTP_200_OK

        # Then create a daily pattern (should still work)
        created_at = datetime.now(timezone.utc)
        next_exec = datetime(2026, 2, 3, 2, 30, tzinfo=timezone.utc)

        with patch("app.api.v1.scheduled_executions.scheduled_execution_repository.action_exists", new_callable=AsyncMock) as mock_exists, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_action_parameters_schema", new_callable=AsyncMock) as mock_schema, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.create_scheduled_execution", new_callable=AsyncMock) as mock_create, \
             patch("app.api.v1.scheduled_executions.scheduled_execution_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id, \
             patch("app.api.v1.scheduled_executions.rbac_service.can_execute", new_callable=AsyncMock) as mock_rbac:

            mock_exists.return_value = True
            mock_rbac.return_value = True
            mock_schema.return_value = None
            mock_create.return_value = ScheduledExecutionCreateResult(
                id=43,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
            )
            mock_get_by_id.return_value = ScheduledExecutionWithAction(
                id=43,
                action_id=1,
                action_name="Test Action",
                action_description=None,
                user_id=1,
                environment="prod",
                parameters={},
                scheduled_at=None,
                status=ScheduledExecutionStatus.PENDING,
                created_at=created_at,
                recurring_pattern=RecurringPatternResponse(
                    pattern_type="daily",
                    pattern_config={"hour": 2, "minute": 30},
                    next_execution_date=next_exec,
                    is_active=True,
                ),
            )

            daily_response = await client.post(
                "/api/v1/scheduled-executions",
                json={
                    "action_id": 1,
                    "environment": "prod",
                    "parameters": {},
                    "recurring_pattern": {
                        "pattern_type": "daily",
                        "pattern_config": {"hour": 2, "minute": 30},
                    },
                },
            )

            assert daily_response.status_code == status.HTTP_201_CREATED
            data = daily_response.json()["data"]
            assert data["recurring_pattern"]["pattern_type"] == "daily"
