"""Tests for execution repository (Story 4.1, Task 8.1 + Story 4.3, Task 6.1 + Story 8.1).

Tests execution_repository functions:
- create_execution: insert and return execution ID
- action_exists: check action exists and is published
- get_action_parameters_schema: retrieve schema for validation
- create_execution_steps: insert step records (Story 4.3)
- get_steps_by_execution_id: retrieve steps (Story 4.3)
- update_step_status: update step status (Story 4.3)
- get_action_stats: aggregated stats for an action (Story 8.1)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.execution import (
    ExecutionStatus,
    ExecutionEnvironment,
    StepStatus,
    StepType,
    ExecutionStepCreate,
)
from app.repositories import execution_repository


class TestCreateExecution:
    """Tests for execution_repository.create_execution (Task 1.2)."""

    @pytest.mark.asyncio
    async def test_create_execution_inserts_and_returns_response(self):
        """create_execution inserts record and returns ExecutionCreateResponse."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 1, 29, 10, 0, 0)]

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.create_execution(
                user_id=1,
                action_id=5,
                environment="dev",
                parameters={"pdb_name": "TEST"},
            )

        assert result.execution_id == 42
        assert result.status == ExecutionStatus.SUBMITTED
        assert result.created_at == datetime(2026, 1, 29, 10, 0, 0)
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_execution_stores_parameters_as_json(self):
        """create_execution stores parameters as JSON string in CLOB."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 1, 29)]

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.create_execution(
                user_id=1,
                action_id=1,
                environment="prod",
                parameters={"key": "value", "nested": {"inner": 123}},
            )

        # Check that execute was called with JSON parameters
        execute_call = mock_conn.execute.call_args
        params = execute_call[0][1]
        assert params["parameters"] == '{"key": "value", "nested": {"inner": 123}}'
        assert params["environment"] == "prod"
        assert params["status"] == "SUBMITTED"


class TestActionExists:
    """Tests for execution_repository.action_exists (Task 1.4)."""

    @pytest.mark.asyncio
    async def test_action_exists_returns_true_for_published_action(self):
        """action_exists returns True when action exists and is published."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.action_exists(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_action_exists_returns_false_when_not_found(self):
        """action_exists returns False when action doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.action_exists(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_action_exists_returns_false_for_draft_action(self):
        """action_exists returns False for draft (non-published) action."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)  # Query filters STATUS='published'
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.action_exists(1)

        assert result is False
        # Verify query includes STATUS check
        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        assert "STATUS = 'published'" in query


class TestGetActionParametersSchema:
    """Tests for execution_repository.get_action_parameters_schema (Task 1.4)."""

    @pytest.mark.asyncio
    async def test_get_schema_returns_parsed_json(self):
        """get_action_parameters_schema returns parsed JSON schema."""
        schema_json = '{"type": "object", "properties": {"name": {"type": "string"}}}'

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(schema_json,))
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_parameters_schema(1)

        assert result == {"type": "object", "properties": {"name": {"type": "string"}}}

    @pytest.mark.asyncio
    async def test_get_schema_returns_none_when_no_schema(self):
        """get_action_parameters_schema returns None when action has no schema."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(None,))
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_parameters_schema(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_schema_returns_none_when_action_not_found(self):
        """get_action_parameters_schema returns None when action doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_parameters_schema(999)

        assert result is None


class TestGetById:
    """Tests for execution_repository.get_by_id."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_execution_with_action_name(self):
        """get_by_id returns ExecutionResponse with action_name from JOIN."""
        row = (
            1,  # ID
            5,  # ACTION_ID
            1,  # USER_ID
            "dev",  # ENVIRONMENT
            '{"key": "value"}',  # PARAMETERS
            "SUBMITTED",  # STATUS
            None,  # SERVICENOW_CHANGE_ID
            None,  # STARTED_AT
            None,  # COMPLETED_AT
            datetime(2026, 1, 29, 10, 0, 0),  # CREATED_AT
            "Create PDB",  # ACTION_NAME from JOIN
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.action_id == 5
        assert result.action_name == "Create PDB"
        assert result.environment == ExecutionEnvironment.DEV
        assert result.parameters == {"key": "value"}
        assert result.status == ExecutionStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        """get_by_id returns None when execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_by_id(999)

        assert result is None


class TestUpdateStatus:
    """Tests for execution_repository.update_status."""

    @pytest.mark.asyncio
    async def test_update_status_updates_status(self):
        """update_status updates the status and returns True."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.update_status(1, ExecutionStatus.RUNNING)

        assert result is True
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_returns_false_when_not_found(self):
        """update_status returns False when execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.update_status(999, ExecutionStatus.RUNNING)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_sets_started_at_for_running(self):
        """update_status sets STARTED_AT when transitioning to RUNNING."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.update_status(1, ExecutionStatus.RUNNING)

        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        assert "STARTED_AT = SYSTIMESTAMP" in query

    @pytest.mark.asyncio
    async def test_update_status_sets_completed_at_for_completed(self):
        """update_status sets COMPLETED_AT when transitioning to COMPLETED."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.update_status(1, ExecutionStatus.COMPLETED)

        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        assert "COMPLETED_AT = SYSTIMESTAMP" in query


# === Story 4.3 Tests: Execution Steps ===


class TestCreateExecutionSteps:
    """Tests for execution_repository.create_execution_steps (Story 4.3, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_create_execution_steps_inserts_and_returns_ids(self):
        """create_execution_steps inserts step records and returns IDs."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()

        mock_out_id1 = MagicMock()
        mock_out_id1.getvalue.return_value = [101]
        mock_out_id2 = MagicMock()
        mock_out_id2.getvalue.return_value = [102]

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.var = MagicMock(side_effect=[mock_out_id1, mock_out_id2])

        steps = [
            ExecutionStepCreate(step_order=1, step_name="Vault", step_type=StepType.VAULT),
            ExecutionStepCreate(step_order=2, step_name="Platform", step_type=StepType.PLATFORM),
        ]

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.create_execution_steps(1, steps)

        assert result == [101, 102]
        assert mock_conn.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_execution_steps_sets_pending_status(self):
        """create_execution_steps sets initial status to PENDING."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.var = MagicMock(return_value=mock_out_id)

        steps = [ExecutionStepCreate(step_order=1, step_name="Test", step_type=StepType.PLATFORM)]

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.create_execution_steps(1, steps)

        execute_call = mock_conn.execute.call_args
        params = execute_call[0][1]
        assert params["status"] == "PENDING"


class TestGetStepsByExecutionId:
    """Tests for execution_repository.get_steps_by_execution_id (Story 4.3, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_get_steps_returns_ordered_list(self):
        """get_steps_by_execution_id returns steps ordered by step_order."""
        rows = [
            (1, 10, 1, "Vault", "vault", "COMPLETED", datetime(2026, 1, 29, 10, 0), datetime(2026, 1, 29, 10, 1), None, None, None),
            (2, 10, 2, "Platform", "platform", "RUNNING", datetime(2026, 1, 29, 10, 1), None, None, "job-123", None),
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=rows)
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_steps_by_execution_id(10)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].step_order == 1
        assert result[0].step_name == "Vault"
        assert result[0].step_type == StepType.VAULT
        assert result[0].status == StepStatus.COMPLETED
        assert result[1].id == 2
        assert result[1].platform_job_id == "job-123"

    @pytest.mark.asyncio
    async def test_get_steps_returns_empty_list_when_none(self):
        """get_steps_by_execution_id returns empty list when no steps exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_steps_by_execution_id(999)

        assert result == []


class TestUpdateStepStatus:
    """Tests for execution_repository.update_step_status (Story 4.3, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_update_step_status_updates_and_returns_true(self):
        """update_step_status updates status and returns True."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.update_step_status(1, StepStatus.RUNNING)

        assert result is True
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_step_status_returns_false_when_not_found(self):
        """update_step_status returns False when step doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.update_step_status(999, StepStatus.RUNNING)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_step_status_sets_started_at_for_running(self):
        """update_step_status sets STARTED_AT when transitioning to RUNNING."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.update_step_status(1, StepStatus.RUNNING)

        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        assert "STARTED_AT = SYSTIMESTAMP" in query

    @pytest.mark.asyncio
    async def test_update_step_status_sets_completed_at_for_failed(self):
        """update_step_status sets COMPLETED_AT when transitioning to FAILED."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.update_step_status(
                1, StepStatus.FAILED, error_message="Vault down"
            )

        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        params = execute_call[0][1]
        assert "COMPLETED_AT = SYSTIMESTAMP" in query
        assert "ERROR_MESSAGE = :error_message" in query
        assert params["error_message"] == "Vault down"

    @pytest.mark.asyncio
    async def test_update_step_status_with_platform_job_id(self):
        """update_step_status can set platform_job_id."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.update_step_status(
                1, StepStatus.COMPLETED, platform_job_id="aap-job-456"
            )

        execute_call = mock_conn.execute.call_args
        query = execute_call[0][0]
        params = execute_call[0][1]
        assert "PLATFORM_JOB_ID = :platform_job_id" in query
        assert params["platform_job_id"] == "aap-job-456"


class TestSkipRemainingSteps:
    """Tests for execution_repository.skip_remaining_steps (Story 4.3, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_skip_remaining_steps_updates_pending_to_skipped(self):
        """skip_remaining_steps marks all PENDING steps as SKIPPED."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3  # 3 steps skipped
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.skip_remaining_steps(1)

        assert result == 3
        execute_call = mock_conn.execute.call_args
        params = execute_call[0][1]
        assert params["skipped_status"] == "SKIPPED"
        assert params["pending_status"] == "PENDING"


class TestGetActionExecutionSteps:
    """Tests for execution_repository.get_action_execution_steps (Story 4.3, Task 6.1)."""

    @pytest.mark.asyncio
    async def test_get_action_execution_steps_returns_parsed_json(self):
        """get_action_execution_steps returns parsed JSON steps."""
        steps_json = '[{"order": 1, "name": "Vault", "type": "vault"}, {"order": 2, "name": "Platform", "type": "platform"}]'

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(steps_json,))
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_execution_steps(1)

        assert len(result) == 2
        assert result[0]["name"] == "Vault"
        assert result[1]["type"] == "platform"

    @pytest.mark.asyncio
    async def test_get_action_execution_steps_returns_empty_when_null(self):
        """get_action_execution_steps returns empty list when EXECUTION_STEPS is NULL."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(None,))
        mock_cursor.close = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_execution_steps(1)

        assert result == []


# === Story 8.1 Tests: Action Stats ===


class TestGetActionStats:
    """Tests for execution_repository.get_action_stats (Story 8.1, AC4, AC5)."""

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_stats_with_executions(self):
        """get_action_stats returns aggregated stats when executions exist."""
        # Row: total_executions, completed_count, failed_count, avg_duration_ms
        row = (100, 90, 10, 5000.0)

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_stats(1)

        assert result is not None
        assert result["total_executions"] == 100
        assert result["incidents_count"] == 10
        assert result["success_rate"] == 90.0  # 90 / (90 + 10) * 100
        assert result["avg_execution_time_ms"] == 5000

    @pytest.mark.asyncio
    async def test_get_action_stats_returns_none_when_no_executions(self):
        """get_action_stats returns None when no executions exist (AC3)."""
        row = (0, 0, 0, None)

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_stats(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_action_stats_handles_all_failures(self):
        """get_action_stats handles case where all executions failed (0% success)."""
        row = (10, 0, 10, None)  # 10 total, 0 completed, 10 failed, no avg time

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_stats(1)

        assert result is not None
        assert result["success_rate"] == 0.0  # 0 / (0 + 10) * 100
        assert result["avg_execution_time_ms"] is None
        assert result["incidents_count"] == 10

    @pytest.mark.asyncio
    async def test_get_action_stats_handles_all_success(self):
        """get_action_stats handles case where all executions succeeded (100% success)."""
        row = (50, 50, 0, 1234.5)  # 50 total, 50 completed, 0 failed

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_stats(1)

        assert result is not None
        assert result["success_rate"] == 100.0  # 50 / (50 + 0) * 100
        assert result["incidents_count"] == 0
        assert result["avg_execution_time_ms"] == 1234  # Rounded with round()

    @pytest.mark.asyncio
    async def test_get_action_stats_calculates_success_rate_correctly(self):
        """get_action_stats calculates success_rate as completed/(completed+failed)*100."""
        # 80 completed, 20 failed = 80% success rate
        row = (120, 80, 20, 3000.0)  # 120 total (includes other statuses), 80+20=100 finished

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = AsyncMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_action_stats(1)

        assert result["success_rate"] == 80.0  # 80 / (80 + 20) * 100


# === Story 8.2 Tests: Admin Analytics ===


class TestGetAdminAnalytics:
    """Tests for execution_repository.get_admin_analytics (Story 8.2, AC4)."""

    @pytest.mark.asyncio
    async def test_get_admin_analytics_returns_all_aggregations(self):
        """get_admin_analytics returns complete analytics data."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()

        # Sequence of fetchone/fetchall calls for each query
        mock_cursor.fetchone = AsyncMock(return_value=(15,))  # published_query
        mock_cursor.fetchall = AsyncMock(side_effect=[
            [("Oracle", 100), ("SQL Server", 50)],  # by_engine_query
            [("dba_app", 80), ("dbops", 70)],  # by_profile_query
            [("2026-01-01", "Oracle", 10), ("2026-01-08", "Oracle", 20)],  # trend_query
        ])
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_admin_analytics(days=90)

        assert result is not None
        assert result["total_published_actions"] == 15
        assert len(result["executions_by_engine"]) == 2
        assert result["executions_by_engine"][0]["engine"] == "Oracle"
        assert result["executions_by_engine"][0]["count"] == 100
        assert len(result["executions_by_profile"]) == 2
        assert result["executions_by_profile"][0]["profile"] == "dba_app"
        assert len(result["adoption_trend"]) == 2
        assert result["adoption_trend"][0]["week_start"] == "2026-01-01"

    @pytest.mark.asyncio
    async def test_get_admin_analytics_handles_empty_data(self):
        """get_admin_analytics returns empty lists when no data."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))  # No published actions
        mock_cursor.fetchall = AsyncMock(side_effect=[[], [], []])  # Empty results
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_admin_analytics(days=30)

        assert result is not None
        assert result["total_published_actions"] == 0
        assert result["executions_by_engine"] == []
        assert result["executions_by_profile"] == []
        assert result["adoption_trend"] == []

    @pytest.mark.asyncio
    async def test_get_admin_analytics_uses_correct_period(self):
        """get_admin_analytics passes days parameter to queries."""
        mock_cursor = MagicMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        mock_cursor.fetchall = AsyncMock(side_effect=[[], [], []])
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.get_admin_analytics(days=365)

        # Verify days parameter was used in queries (2nd, 3rd, 4th execute calls)
        execute_calls = mock_cursor.execute.call_args_list
        # Query 2 (by_engine) - check days param
        assert execute_calls[1][0][1]["days"] == 365
        # Query 3 (by_profile) - check days param
        assert execute_calls[2][0][1]["days"] == 365
        # Query 4 (trend) - check days param
        assert execute_calls[3][0][1]["days"] == 365


# === Story 9.2 Tests: Parent Execution ID (Remediation) ===


class TestCreateExecutionWithParent:
    """Tests for execution_repository.create_execution with parent_execution_id (Story 9.2, Task 20)."""

    @pytest.mark.asyncio
    async def test_create_execution_with_parent_id(self):
        """create_execution inserts record with parent_execution_id."""
        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 2, 10, 0, 0)]

        mock_cursor = MagicMock()
        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])
        mock_cursor.execute = AsyncMock()
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.create_execution(
                user_id=1,
                action_id=5,
                environment="dev",
                parameters={"pdb_name": "TEST"},
                parent_execution_id=100,  # Parent execution ID for remediation
            )

        assert result.execution_id == 42
        # Verify parent_execution_id was passed to the query
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["parent_execution_id"] == 100

    @pytest.mark.asyncio
    async def test_create_execution_without_parent_id(self):
        """create_execution inserts record with NULL parent_execution_id when not provided."""
        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [43]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 2, 10, 0, 0)]

        mock_cursor = MagicMock()
        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])
        mock_cursor.execute = AsyncMock()
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.create_execution(
                user_id=1,
                action_id=5,
                environment="dev",
                parameters=None,
            )

        assert result.execution_id == 43
        # Verify parent_execution_id is None in params
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["parent_execution_id"] is None


class TestGetExecutionIncludesParentId:
    """Tests for get_by_id including parent_execution_id (Story 9.2, Task 20)."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_parent_execution_id(self):
        """get_by_id returns ExecutionResponse with parent_execution_id from query."""
        # Row with parent_execution_id as last column
        row = (
            1,  # ID
            5,  # ACTION_ID
            1,  # USER_ID
            "dev",  # ENVIRONMENT
            '{"key": "value"}',  # PARAMETERS
            "COMPLETED",  # STATUS
            None,  # SERVICENOW_CHANGE_ID
            datetime(2026, 2, 2, 10, 0, 0),  # STARTED_AT
            datetime(2026, 2, 2, 10, 5, 0),  # COMPLETED_AT
            datetime(2026, 2, 2, 9, 0, 0),  # CREATED_AT
            "Fix PDB",  # ACTION_NAME from JOIN
            None,  # APPROVED_BY
            None,  # APPROVED_AT
            None,  # APPROVAL_COMMENT
            100,  # PARENT_EXECUTION_ID
        )

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.parent_execution_id == 100


class TestGetChildrenExecutions:
    """Tests for execution_repository.get_children_executions (Story 9.2, Task 20)."""

    @pytest.mark.asyncio
    async def test_get_children_executions_returns_ordered_list(self):
        """get_children_executions returns children ordered by created_at DESC."""
        rows = [
            (2, 5, 1, "dev", None, "COMPLETED", None, datetime(2026, 2, 2, 10, 0), datetime(2026, 2, 2, 10, 5), datetime(2026, 2, 2, 10, 0), "Fix PDB", None, None, None, 1),
            (3, 6, 1, "dev", None, "FAILED", None, datetime(2026, 2, 2, 11, 0), datetime(2026, 2, 2, 11, 5), datetime(2026, 2, 2, 11, 0), "Repair Index", None, None, None, 1),
        ]

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=rows)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_children_executions(1)

        assert len(result) == 2
        assert result[0].id == 2
        assert result[0].parent_execution_id == 1
        assert result[1].id == 3
        assert result[1].action_name == "Repair Index"

    @pytest.mark.asyncio
    async def test_get_children_executions_returns_empty_when_none(self):
        """get_children_executions returns empty list when no children exist."""
        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_children_executions(999)

        assert result == []


class TestGetParentExecution:
    """Tests for execution_repository.get_parent_execution (Story 9.2, Task 20)."""

    @pytest.mark.asyncio
    async def test_get_parent_execution_returns_parent(self):
        """get_parent_execution returns parent execution when exists."""
        # Row: parent_execution_id query result - should return (parent_execution_id,)
        parent_id_row = (1,)
        # Parent execution row
        parent_row = (
            1, 4, 1, "dev", None, "FAILED", None,
            datetime(2026, 2, 2, 9, 0), datetime(2026, 2, 2, 9, 5),
            datetime(2026, 2, 2, 9, 0), "Create PDB", None, None, None, None  # no parent
        )

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(side_effect=[parent_id_row, parent_row])
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_parent_execution(2)

        assert result is not None
        assert result.id == 1
        assert result.action_name == "Create PDB"
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_get_parent_execution_returns_none_when_no_parent(self):
        """get_parent_execution returns None when execution has no parent."""
        # Row where parent_execution_id is NULL
        row = (None,)

        mock_cursor = MagicMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = MagicMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_parent_execution(1)

        assert result is None
