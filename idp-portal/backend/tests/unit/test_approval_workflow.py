"""Tests for approval workflow (Story 7.4).

Tests:
- Task 10.1: Repository functions for approval workflow
- Task 10.2: API endpoints for approval/rejection
- Task 10.3: Integration tests for complete workflow
"""

import pytest
import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.execution import ExecutionStatus, ExecutionEnvironment
from app.repositories import execution_repository


class TestCreateExecutionPendingApproval:
    """Tests for execution_repository.create_execution_pending_approval (Story 7.4, AC1)."""

    @pytest.mark.asyncio
    async def test_creates_with_pending_approval_status(self):
        """create_execution_pending_approval creates record with PENDING_APPROVAL status."""
        mock_cursor = MagicMock()
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 1, 10, 0, 0)]

        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])
        mock_cursor.execute = AsyncMock()

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.create_execution_pending_approval(
                user_id=1,
                action_id=5,
                environment="prod",
                parameters={"pdb_name": "TEST"},
            )

        assert result.execution_id == 42
        assert result.status == ExecutionStatus.PENDING_APPROVAL
        assert result.created_at == datetime(2026, 2, 1, 10, 0, 0)

    @pytest.mark.asyncio
    async def test_stores_parameters_as_json(self):
        """create_execution_pending_approval stores parameters as JSON string."""
        mock_cursor = MagicMock()
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]

        mock_out_created_at = MagicMock()
        mock_out_created_at.getvalue.return_value = [datetime(2026, 2, 1)]

        mock_cursor.var = MagicMock(side_effect=[mock_out_id, mock_out_created_at])

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.create_execution_pending_approval(
                user_id=1,
                action_id=1,
                environment="prod",
                parameters={"key": "value"},
            )

        # Check that execute was called with PENDING_APPROVAL status
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["status"] == "PENDING_APPROVAL"
        assert params["parameters"] == '{"key": "value"}'


class TestApprove:
    """Tests for execution_repository.approve (Story 7.4, AC3)."""

    @pytest.mark.asyncio
    async def test_approve_updates_status_to_submitted(self):
        """approve updates status from PENDING_APPROVAL to SUBMITTED."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.approve(
                execution_id=42,
                approver_id=10,
                comment="Approved for production",
            )

        assert result is True
        mock_conn.commit.assert_called_once()

        # Verify query parameters
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["execution_id"] == 42
        assert params["new_status"] == "SUBMITTED"
        assert params["current_status"] == "PENDING_APPROVAL"
        assert params["approver_id"] == 10
        # Story 9.7: Verify correct bind variable name (not Oracle reserved word)
        assert params["approval_comment"] == "Approved for production"
        assert "comment" not in params, "Should use 'approval_comment', not 'comment' (Oracle reserved word)"

    @pytest.mark.asyncio
    async def test_approve_returns_false_when_not_found(self):
        """approve returns False when execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.approve(999, 10)

        assert result is False

    @pytest.mark.asyncio
    async def test_approve_fails_when_not_pending_approval(self):
        """approve returns False when execution is not in PENDING_APPROVAL status."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # No rows updated because WHERE STATUS = PENDING_APPROVAL didn't match
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.approve(42, 10)

        assert result is False


class TestReject:
    """Tests for execution_repository.reject (Story 7.4, AC4)."""

    @pytest.mark.asyncio
    async def test_reject_updates_status_to_rejected(self):
        """reject updates status from PENDING_APPROVAL to REJECTED."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.reject(
                execution_id=42,
                rejector_id=10,
                comment="Rejected due to policy violation",
            )

        assert result is True
        mock_conn.commit.assert_called_once()

        # Verify query parameters
        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]
        assert params["execution_id"] == 42
        assert params["new_status"] == "REJECTED"
        assert params["current_status"] == "PENDING_APPROVAL"
        assert params["rejector_id"] == 10
        # Story 9.7: Verify correct bind variable name (not Oracle reserved word)
        assert params["approval_comment"] == "Rejected due to policy violation"
        assert "comment" not in params, "Should use 'approval_comment', not 'comment' (Oracle reserved word)"

    @pytest.mark.asyncio
    async def test_reject_returns_false_when_not_found(self):
        """reject returns False when execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.reject(999, 10)

        assert result is False


class TestListPendingApprovals:
    """Tests for execution_repository.list_pending_approvals (Story 7.4, AC2)."""

    @pytest.mark.asyncio
    async def test_returns_pending_approval_executions(self):
        """list_pending_approvals returns executions with PENDING_APPROVAL status and user display name."""
        rows = [
            (
                1, 5, 2, "prod", '{"key": "value"}',
                "PENDING_APPROVAL", None, None, None,
                datetime(2026, 2, 1, 10, 0, 0), "Create PDB", "John Doe"
            ),
            (
                2, 6, 3, "prod", '{}',
                "PENDING_APPROVAL", None, None, None,
                datetime(2026, 2, 1, 11, 0, 0), "Delete PDB", "Jane Smith"
            ),
        ]

        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=rows)
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.list_pending_approvals(limit=50, offset=0)

        assert len(result) == 2
        assert result[0].id == 1
        assert result[0].status == ExecutionStatus.PENDING_APPROVAL
        assert result[0].action_name == "Create PDB"
        assert result[0].user_display_name == "John Doe"
        assert result[1].id == 2
        assert result[1].user_display_name == "Jane Smith"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none(self):
        """list_pending_approvals returns empty list when no pending approvals."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.list_pending_approvals()

        assert result == []


class TestCountPendingApprovals:
    """Tests for execution_repository.count_pending_approvals (Story 7.4, AC6)."""

    @pytest.mark.asyncio
    async def test_returns_count_of_pending_approvals(self):
        """count_pending_approvals returns count of PENDING_APPROVAL executions."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(5,))
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.count_pending_approvals()

        assert result == 5

    @pytest.mark.asyncio
    async def test_returns_zero_when_none(self):
        """count_pending_approvals returns 0 when no pending approvals."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=(0,))
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.count_pending_approvals()

        assert result == 0


class TestGetByIdWithApproval:
    """Tests for execution_repository.get_by_id_with_approval (Story 7.4)."""

    @pytest.mark.asyncio
    async def test_returns_execution_with_approval_details(self):
        """get_by_id_with_approval returns execution with approval fields."""
        row = (
            1, 5, 2, "prod", '{"key": "value"}',
            "SUBMITTED", None, None, None,
            datetime(2026, 2, 1, 10, 0, 0), "Create PDB",
            10, datetime(2026, 2, 1, 11, 0, 0), "Approved",
            "John Doe", "Jane Admin"
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=row)
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_by_id_with_approval(1)

        assert result is not None
        assert result["id"] == 1
        assert result["status"] == "SUBMITTED"
        assert result["approved_by"] == 10
        assert result["approval_comment"] == "Approved"
        assert result["requester_name"] == "John Doe"
        assert result["approver_name"] == "Jane Admin"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """get_by_id_with_approval returns None when execution doesn't exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = MagicMock()  # Story 9.7: cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            result = await execution_repository.get_by_id_with_approval(999)

        assert result is None


class TestOracleBindVariableRegression:
    """Regression tests for Oracle bind variable naming (Story 9.7).

    These tests verify that bind variables avoid Oracle reserved words to prevent
    ORA-01745 errors. The bug was introduced in Story 7.4 (commit a450130) using
    :comment, and fixed in Story 9.1 (commit 6163b8e) using :approval_comment.

    Story 9.7 adds these regression tests to prevent reintroduction of the bug,
    along with comprehensive documentation and codebase scanning for similar issues.
    """

    @pytest.mark.asyncio
    async def test_approve_uses_approval_comment_bind_variable(self):
        """Regression test: approve() must use :approval_comment, not :comment (Oracle reserved word)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = MagicMock()  # cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.approve(
                execution_id=1,
                approver_id=2,
                comment="Test approval comment",
            )

        # Get the SQL query and params from execute call
        execute_call = mock_cursor.execute.call_args
        query = execute_call[0][0]
        params = execute_call[0][1]

        # Verify SQL uses correct bind variable name
        assert ":approval_comment" in query, (
            "Query must use :approval_comment bind variable. "
            "Using :comment causes ORA-01745 (COMMENT is Oracle reserved word)."
        )

        # Story 9.7 code-review MEDIUM-3: Use regex to detect standalone :comment (robust edge case handling)
        # This prevents false positives with ":comment_something" and catches ":comment " or ":comment\n"
        standalone_comment_pattern = r':comment\b'
        assert not re.search(standalone_comment_pattern, query.replace(":approval_comment", "")), (
            "Query must NOT use :comment bind variable (Oracle reserved word). "
            "Detected standalone :comment (not part of :approval_comment)."
        )

        # Story 9.7 code-review: Verify query structure to prevent refactoring bugs
        assert "UPDATE EXECUTIONS" in query, "Query must update EXECUTIONS table"
        assert "APPROVAL_COMMENT = :approval_comment" in query, "Query must set APPROVAL_COMMENT column"
        assert "WHERE ID = :execution_id" in query, "Query must filter by execution ID"

        # Verify params dict uses correct key
        assert "approval_comment" in params, (
            "params dict must have 'approval_comment' key, not 'comment'."
        )
        assert "comment" not in params, (
            "params dict must NOT have 'comment' key (Oracle reserved word conflict)."
        )
        assert params["approval_comment"] == "Test approval comment"

    @pytest.mark.asyncio
    async def test_reject_uses_approval_comment_bind_variable(self):
        """Regression test: reject() must use :approval_comment, not :comment (Oracle reserved word)."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = MagicMock()  # cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.reject(
                execution_id=1,
                rejector_id=2,
                comment="Test rejection comment",
            )

        # Get the SQL query and params from execute call
        execute_call = mock_cursor.execute.call_args
        query = execute_call[0][0]
        params = execute_call[0][1]

        # Verify SQL uses correct bind variable name
        assert ":approval_comment" in query, (
            "Query must use :approval_comment bind variable. "
            "Using :comment causes ORA-01745 (COMMENT is Oracle reserved word)."
        )

        # Story 9.7 code-review MEDIUM-3: Use regex to detect standalone :comment (robust edge case handling)
        standalone_comment_pattern = r':comment\b'
        assert not re.search(standalone_comment_pattern, query.replace(":approval_comment", "")), (
            "Query must NOT use :comment bind variable (Oracle reserved word). "
            "Detected standalone :comment (not part of :approval_comment)."
        )

        # Story 9.7 code-review: Verify query structure to prevent refactoring bugs
        assert "UPDATE EXECUTIONS" in query, "Query must update EXECUTIONS table"
        assert "APPROVAL_COMMENT = :approval_comment" in query, "Query must set APPROVAL_COMMENT column"
        assert "WHERE ID = :execution_id" in query, "Query must filter by execution ID"

        # Verify params dict uses correct key
        assert "approval_comment" in params, (
            "params dict must have 'approval_comment' key, not 'comment'."
        )
        assert "comment" not in params, (
            "params dict must NOT have 'comment' key (Oracle reserved word conflict)."
        )
        assert params["approval_comment"] == "Test rejection comment"

    @pytest.mark.asyncio
    async def test_approve_with_none_comment_uses_correct_bind_variable(self):
        """Regression test: approve() with None comment still uses approval_comment key."""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_cursor.close = MagicMock()  # cursor.close() is sync, not async
        mock_cursor.execute = AsyncMock()

        mock_conn = MagicMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.execution_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock()

            await execution_repository.approve(
                execution_id=1,
                approver_id=2,
                comment=None,  # Optional comment
            )

        execute_call = mock_cursor.execute.call_args
        params = execute_call[0][1]

        # Even with None, should use 'approval_comment' key
        assert "approval_comment" in params
        assert "comment" not in params
        assert params["approval_comment"] is None
