"""Tests for audit repository (Story 2.4, AC #3).

Uses mocks for Oracle pool to test repository logic without database.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType


class TestAuditActionTypeEnum:
    """Tests for AuditActionType enum."""

    def test_action_type_values(self):
        """Test AuditActionType enum values."""
        assert AuditActionType.ACTION_CREATED.value == "ACTION_CREATED"
        assert AuditActionType.ACTION_UPDATED.value == "ACTION_UPDATED"
        assert AuditActionType.ACTION_PUBLISHED.value == "ACTION_PUBLISHED"
        assert AuditActionType.ACTION_DISABLED.value == "ACTION_DISABLED"
        assert AuditActionType.ACTION_ENABLED.value == "ACTION_ENABLED"

    def test_execution_action_type_values(self):
        """Test execution-related AuditActionType enum values (Story 6.1)."""
        assert AuditActionType.EXECUTION_SUBMITTED.value == "EXECUTION_SUBMITTED"
        assert AuditActionType.EXECUTION_STARTED.value == "EXECUTION_STARTED"
        assert AuditActionType.EXECUTION_COMPLETED.value == "EXECUTION_COMPLETED"
        assert AuditActionType.EXECUTION_FAILED.value == "EXECUTION_FAILED"
        assert AuditActionType.SERVICENOW_CHANGE_CREATED.value == "SERVICENOW_CHANGE_CREATED"


class TestAuditEntityTypeEnum:
    """Tests for AuditEntityType enum."""

    def test_entity_type_values(self):
        """Test AuditEntityType enum values."""
        assert AuditEntityType.ACTION.value == "action"
        assert AuditEntityType.USER.value == "user"
        assert AuditEntityType.PERMISSION.value == "permission"

    def test_execution_entity_type(self):
        """Test execution entity type (Story 6.1)."""
        assert AuditEntityType.EXECUTION.value == "execution"


class TestCreateEntry:
    """Tests for create_entry() function."""

    @pytest.mark.asyncio
    async def test_create_entry_success(self):
        """Test creating audit entry successfully."""
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.close = MagicMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [42]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_PUBLISHED,
                entity_type=AuditEntityType.ACTION,
                entity_id=1,
                details={"action_name": "Create PDB", "previous_status": "draft", "new_status": "published"},
            )

        assert result == 42
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_entry_with_ip_address(self):
        """Test creating audit entry with IP address."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = MagicMock()

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [43]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_DISABLED,
                entity_type=AuditEntityType.ACTION,
                entity_id=2,
                ip_address="192.168.1.1",
            )

        assert result == 43
        assert captured_params["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_create_entry_without_details(self):
        """Test creating audit entry without details."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = MagicMock()

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [44]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_CREATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=3,
                details=None,
            )

        assert result == 44
        assert captured_params["details"] is None

    @pytest.mark.asyncio
    async def test_create_entry_serializes_details_to_json(self):
        """Test that details dict is serialized to JSON string."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = MagicMock()

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [45]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.ACTION_UPDATED,
                entity_type=AuditEntityType.ACTION,
                entity_id=4,
                details={"key": "value"},
            )

        assert captured_params["details"] == '{"key": "value"}'
        assert isinstance(captured_params["details"], str)

    @pytest.mark.asyncio
    async def test_create_entry_with_correlation_id(self):
        """Test creating audit entry with correlation_id (Story 6.1, AC6)."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = MagicMock()

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [46]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await audit_repository.create_entry(
                user_id="user123",
                action_type=AuditActionType.EXECUTION_SUBMITTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=100,
                details={"action_id": 5, "environment": "dev"},
                ip_address="10.0.0.1",
                correlation_id="abc-123-def-456",
            )

        assert result == 46
        assert captured_params["correlation_id"] == "abc-123-def-456"
        assert captured_params["entity_type"] == "execution"
        assert captured_params["action_type"] == "EXECUTION_SUBMITTED"

    @pytest.mark.asyncio
    async def test_create_entry_execution_types(self):
        """Test creating audit entries with all execution action types (Story 6.1)."""
        mock_cursor = AsyncMock()
        mock_cursor.close = MagicMock()
        mock_cursor.execute = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [47]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        execution_types = [
            AuditActionType.EXECUTION_SUBMITTED,
            AuditActionType.EXECUTION_STARTED,
            AuditActionType.EXECUTION_COMPLETED,
            AuditActionType.EXECUTION_FAILED,
            AuditActionType.SERVICENOW_CHANGE_CREATED,
        ]

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            for action_type in execution_types:
                result = await audit_repository.create_entry(
                    user_id="user123",
                    action_type=action_type,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=100,
                )
                assert result == 47


class TestListEntries:
    """Tests for list_entries() function (Story 6.1, AC7)."""

    @pytest.mark.asyncio
    async def test_list_entries_no_filters(self):
        """Test listing audit entries without filters."""
        from datetime import datetime

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            (1, datetime(2026, 1, 30, 10, 0, 0), "user1", "EXECUTION_SUBMITTED", "execution", 100,
             '{"action_id": 5}', "10.0.0.1", "corr-123"),
            (2, datetime(2026, 1, 30, 10, 0, 1), "user1", "EXECUTION_STARTED", "execution", 100,
             None, "10.0.0.1", "corr-123"),
        ])

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            entries = await audit_repository.list_entries()

        assert len(entries) == 2
        assert entries[0]["id"] == 1
        assert entries[0]["action_type"] == "EXECUTION_SUBMITTED"
        assert entries[0]["correlation_id"] == "corr-123"
        assert entries[0]["details"] == {"action_id": 5}
        assert entries[1]["details"] is None

    @pytest.mark.asyncio
    async def test_list_entries_by_entity(self):
        """Test listing audit entries filtered by entity."""
        from datetime import datetime

        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            (1, datetime(2026, 1, 30, 10, 0, 0), "user1", "EXECUTION_SUBMITTED", "execution", 100,
             None, "10.0.0.1", "corr-123"),
        ])

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params.copy()
            return mock_cursor

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)
        mock_cursor.execute = capture_execute

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            entries = await audit_repository.list_entries(
                entity_type=AuditEntityType.EXECUTION,
                entity_id=100,
            )

        assert len(entries) == 1
        assert captured_params["entity_type"] == "execution"
        assert captured_params["entity_id"] == 100


class TestGetByEntity:
    """Tests for get_by_entity() function (Story 6.1, AC7)."""

    @pytest.mark.asyncio
    async def test_get_by_entity_delegates_to_list_entries(self):
        """Test that get_by_entity calls list_entries with correct params."""
        with patch("app.repositories.audit_repository.list_entries") as mock_list:
            mock_list.return_value = [{"id": 1}]

            result = await audit_repository.get_by_entity(
                entity_type=AuditEntityType.EXECUTION,
                entity_id=100,
            )

        mock_list.assert_called_once_with(
            entity_type=AuditEntityType.EXECUTION,
            entity_id=100,
        )
        assert result == [{"id": 1}]


class TestAppendOnlyGuarantee:
    """Tests for append-only guarantee (Story 6.1, AC3, AC7)."""

    def test_no_update_method_exposed(self):
        """audit_repository does NOT expose update methods (AC3)."""
        public_functions = [
            name for name in dir(audit_repository)
            if not name.startswith("_") and callable(getattr(audit_repository, name))
        ]
        assert "update" not in " ".join(public_functions).lower()
        assert "update_entry" not in public_functions
        assert "modify" not in " ".join(public_functions).lower()

    def test_no_delete_method_exposed(self):
        """audit_repository does NOT expose delete methods (AC3)."""
        public_functions = [
            name for name in dir(audit_repository)
            if not name.startswith("_") and callable(getattr(audit_repository, name))
        ]
        assert "delete" not in " ".join(public_functions).lower()
        assert "delete_entry" not in public_functions
        assert "remove" not in " ".join(public_functions).lower()

    def test_only_insert_and_select_methods(self):
        """audit_repository only exposes create (INSERT) and list/get (SELECT)."""
        import inspect

        # These are the ONLY allowed public async functions defined in audit_repository
        # Story 6.3 adds list_execution_audit_entries and count_execution_audit_entries
        allowed_functions = {
            "create_entry",
            "list_entries",
            "get_by_entity",
            "list_execution_audit_entries",
            "count_execution_audit_entries",
        }

        # Get only functions DEFINED in audit_repository module (not imported)
        public_async_functions = {
            name for name, obj in inspect.getmembers(audit_repository, inspect.iscoroutinefunction)
            if not name.startswith("_")
            and getattr(obj, "__module__", None) == audit_repository.__name__
        }
        # Check all public async functions are in allowed set
        for func in public_async_functions:
            assert func in allowed_functions, f"Unexpected function: {func}"


# Story 6.3: Tests for list_execution_audit_entries and count_execution_audit_entries


class TestListExecutionAuditEntries:
    """Tests for list_execution_audit_entries() function (Story 6.3, AC6, AC7)."""

    @pytest.mark.asyncio
    async def test_list_execution_entries_no_filters(self):
        """Test listing execution audit entries without filters."""
        from datetime import datetime

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            (1, datetime(2026, 1, 30, 10, 0, 0), "user1", "EXECUTION_COMPLETED", "execution", 100,
             '{"action_id": 5, "environment": "prod"}', "10.0.0.1", "corr-123"),
            (2, datetime(2026, 1, 30, 9, 0, 0), "user2", "EXECUTION_FAILED", "execution", 101,
             '{"action_id": 6, "environment": "dev"}', "10.0.0.2", "corr-456"),
        ])

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            entries = await audit_repository.list_execution_audit_entries()

        assert len(entries) == 2
        assert entries[0]["id"] == 1
        assert entries[0]["action_type"] == "EXECUTION_COMPLETED"
        assert entries[0]["derived_status"] == "success"
        assert entries[0]["details"]["environment"] == "prod"
        assert entries[1]["derived_status"] == "failed"

    @pytest.mark.asyncio
    async def test_list_execution_entries_with_date_filter(self):
        """Test listing with from_date and to_date filters."""
        captured_query = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_query
            captured_query = query

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(
                from_date="2026-01-01T00:00:00",
                to_date="2026-01-31T23:59:59",
            )

        assert "TO_TIMESTAMP(:from_date" in captured_query
        assert "TO_TIMESTAMP(:to_date" in captured_query

    @pytest.mark.asyncio
    async def test_list_execution_entries_with_environment_filter(self):
        """Test listing with environment filter using JSON_VALUE."""
        captured_query = None
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_query, captured_params
            captured_query = query
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(environment="prod")

        assert "JSON_VALUE(DETAILS, '$.environment')" in captured_query
        assert captured_params["environment"] == "prod"

    @pytest.mark.asyncio
    async def test_list_execution_entries_with_status_success(self):
        """Test listing with status=success filter maps to EXECUTION_COMPLETED."""
        captured_query = None
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_query, captured_params
            captured_query = query
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(status="success")

        assert "ACTION_TYPE IN" in captured_query
        assert captured_params["at0"] == "EXECUTION_COMPLETED"

    @pytest.mark.asyncio
    async def test_list_execution_entries_with_status_failed(self):
        """Test listing with status=failed filter maps to EXECUTION_FAILED."""
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(status="failed")

        assert captured_params["at0"] == "EXECUTION_FAILED"

    @pytest.mark.asyncio
    async def test_list_execution_entries_with_status_running(self):
        """Test listing with status=running filter maps to EXECUTION_STARTED/SUBMITTED."""
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(status="running")

        assert captured_params["at0"] == "EXECUTION_STARTED"
        assert captured_params["at1"] == "EXECUTION_SUBMITTED"

    @pytest.mark.asyncio
    async def test_list_execution_entries_pagination(self):
        """Test pagination with limit and offset."""
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await audit_repository.list_execution_audit_entries(limit=10, offset=25)

        assert captured_params["limit_val"] == 10
        assert captured_params["offset_val"] == 25


class TestCountExecutionAuditEntries:
    """Tests for count_execution_audit_entries() function (Story 6.3, Task 1.2)."""

    @pytest.mark.asyncio
    async def test_count_execution_entries_no_filters(self):
        """Test counting execution audit entries without filters."""
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(42,))

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            count = await audit_repository.count_execution_audit_entries()

        assert count == 42

    @pytest.mark.asyncio
    async def test_count_execution_entries_with_filters(self):
        """Test counting with same filters as list function."""
        captured_query = None
        captured_params = None

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(10,))

        async def capture_execute(query, params):
            nonlocal captured_query, captured_params
            captured_query = query
            captured_params = params

        mock_cursor.execute = capture_execute

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            count = await audit_repository.count_execution_audit_entries(
                from_date="2026-01-01T00:00:00",
                environment="prod",
                status="success",
            )

        assert count == 10
        assert "COUNT(DISTINCT ENTITY_ID)" in captured_query
        assert "JSON_VALUE(DETAILS, '$.environment')" in captured_query
        assert "ACTION_TYPE IN" in captured_query
        assert captured_params["environment"] == "prod"
        assert captured_params["at0"] == "EXECUTION_COMPLETED"

    @pytest.mark.asyncio
    async def test_count_execution_entries_empty_result(self):
        """Test counting returns 0 when no row found."""
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_conn = AsyncMock()
        mock_conn.cursor = MagicMock(return_value=mock_cursor)

        with patch("app.repositories.audit_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            count = await audit_repository.count_execution_audit_entries()

        assert count == 0
