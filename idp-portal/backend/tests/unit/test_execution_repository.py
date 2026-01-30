"""Tests for execution repository (Story 4.1, Task 8.1 + Story 4.3, Task 6.1).

Tests execution_repository functions:
- create_execution: insert and return execution ID
- action_exists: check action exists and is published
- get_action_parameters_schema: retrieve schema for validation
- create_execution_steps: insert step records (Story 4.3)
- get_steps_by_execution_id: retrieve steps (Story 4.3)
- update_step_status: update step status (Story 4.3)
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
