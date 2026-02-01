"""Tests for catalog repository (Story 2.1, AC #4).

Uses mocks for Oracle pool to test repository logic without database.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.models.catalog import (
    ActionCreate,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ConnectorType,
    ExecutionStep,
    ExecutionStepType,
    ChangeTypeConfigEntry,
    StatusTransition,
    InvalidTransitionError,
)
from app.repositories import catalog_repository
from app.repositories.catalog_repository import InvalidStateError


@pytest.fixture
def sample_action_create():
    """Sample ActionCreate for testing. Story 2.23: category removed."""
    return ActionCreate(
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={
            "type": "object",
            "properties": {"db_name": {"type": "string"}},
        },
        impact_rules={
            "DEV": {"level": "low"},
            "PROD": {"level": "high"},
        },
    )


@pytest.fixture
def mock_db_row():
    """Sample database row for action. Story 5.7: ITEM_TYPE column added (V027)."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA (CLOB as string)
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
        None,  # DOCUMENTATION_MD (Story 3.4)
        "action",  # ITEM_TYPE (Story 5.7)
    )


# Story 2.14: RBAC_POLICIES column removed — RBAC now managed via profiles.


@pytest.fixture
def mock_db_row_with_detail():
    """Sample database row for action detail. Story 5.7: ITEM_TYPE column added (V027)."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
        None,  # EXECUTION_STEPS
        None,  # CHANGE_TYPE_CONFIG
        None,  # DOCUMENTATION_MD (Story 3.4)
        "action",  # ITEM_TYPE (Story 5.7)
    )


@pytest.fixture
def mock_db_row_with_execution_steps():
    """Sample database row for action with execution_steps and change_type_config. Story 5.7: ITEM_TYPE column added."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        "low",  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        datetime(2026, 1, 28, 11, 0, 0),  # UPDATED_AT
        '[{"order": 1, "name": "Verification", "type": "prerequisite", "connector_type": "none", "connector_config": null, "conditional_environments": null}]',  # EXECUTION_STEPS
        '{"DEV": {"required": false}, "PROD": {"required": true, "change_model_code": "1516B"}}',  # CHANGE_TYPE_CONFIG (Story 2.24)
        '# Documentation\n\nThis action creates a PDB.',  # DOCUMENTATION_MD (Story 3.4)
        "action",  # ITEM_TYPE (Story 5.7)
    )


@pytest.fixture
def mock_db_row_published():
    """Sample database row for published action. Story 5.7: ITEM_TYPE column added (V027)."""
    return (
        2,  # ID
        "Published Action",  # NAME
        "A published action",  # DESCRIPTION
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        None,  # PARAMETERS_SCHEMA
        None,  # IMPACT_RULES
        None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
        "published",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
        None,  # EXECUTION_STEPS
        None,  # CHANGE_TYPE_CONFIG
        None,  # DOCUMENTATION_MD (Story 3.4)
        "action",  # ITEM_TYPE (Story 5.7)
    )


class TestJsonConversions:
    """Tests for JSON conversion helpers."""

    def test_json_to_str_with_dict(self):
        """Test converting dict to JSON string."""
        result = catalog_repository._json_to_str({"key": "value"})
        assert result == '{"key": "value"}'

    def test_json_to_str_with_none(self):
        """Test converting None returns None."""
        result = catalog_repository._json_to_str(None)
        assert result is None

    def test_str_to_json_with_string(self):
        """Test converting JSON string to dict."""
        result = catalog_repository._str_to_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_str_to_json_with_none(self):
        """Test converting None returns None."""
        result = catalog_repository._str_to_json(None)
        assert result is None


class TestRowConversions:
    """Tests for database row to model conversions."""

    def test_row_to_action_response(self, mock_db_row):
        """Test converting row to ActionResponse."""
        result = catalog_repository._row_to_action_response(mock_db_row)
        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        assert result.engine == ActionEngine.ORACLE
        assert result.platform == ActionPlatform.AAP
        assert result.status == ActionStatus.DRAFT

    def test_row_to_action_detail(self, mock_db_row_with_detail):
        """Test converting row to ActionDetail. Story 2.14: rbac_policies removed."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_detail)
        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        # Story 2.14: rbac_policies removed
        assert not hasattr(result, "rbac_policies")


class TestCreate:
    """Tests for create() function."""

    @pytest.mark.asyncio
    async def test_create_action_success(self, sample_action_create, mock_db_row_with_detail):
        """Test creating action successfully."""
        mock_cursor = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        mock_conn.commit = AsyncMock()

        # Mock the var() method for RETURNING clause
        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        # For the get_by_id call after create
        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_detail)

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                result = await catalog_repository.create(sample_action_create, user_id=42)

        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        assert result.status == ActionStatus.DRAFT
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_create_action_with_json_fields(self, sample_action_create, mock_db_row_with_detail):
        """Test that JSON fields are properly serialized."""
        captured_params = {}

        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_detail)
        mock_cursor_get.close = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count, captured_params
            call_count += 1
            if call_count == 1:
                captured_params = params.copy()
                return mock_cursor
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                await catalog_repository.create(sample_action_create, user_id=42)

        # Verify JSON serialization
        assert captured_params["parameters_schema"] is not None
        assert isinstance(captured_params["parameters_schema"], str)
        assert "type" in captured_params["parameters_schema"]

        assert captured_params["impact_rules"] is not None
        assert isinstance(captured_params["impact_rules"], str)


class TestGetById:
    """Tests for get_by_id() function."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_db_row_with_detail):
        """Test getting action by ID when found (Story 2.6: tags mocked)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_db_row_with_detail)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                result = await catalog_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        # Story 2.14: rbac_policies removed
        assert not hasattr(result, "rbac_policies")
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """Test getting action by ID when not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.get_by_id(999)

        assert result is None


class TestListAll:
    """Tests for list_all() function."""

    @pytest.mark.asyncio
    async def test_list_all_no_filter(self, mock_db_row):
        """Test listing all actions without filter (Story 2.6: tags via get_tags_for_actions)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row, mock_db_row])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: []}):
                result = await catalog_repository.list_all()

        assert len(result) == 2
        assert all(r.name == "Create PDB Oracle" for r in result)
        assert all(r.tags == [] for r in result)

    @pytest.mark.asyncio
    async def test_list_all_with_status_filter(self, mock_db_row):
        """Test listing actions with status filter."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        captured_params = {}

        async def capture_execute(query, params):
            nonlocal captured_params
            captured_params = params
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: []}):
                result = await catalog_repository.list_all(status=ActionStatus.DRAFT)

        assert len(result) == 1
        assert captured_params["status"] == "draft"
        assert result[0].tags == []

    @pytest.mark.asyncio
    async def test_list_all_empty(self):
        """Test listing actions when none exist (Story 2.6: get_tags_for_actions returns {})."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_with_tags_filter(self, mock_db_row):
        """Test listing actions filtered by tags (Story 2.6, AC4)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        captured_params = {}

        async def capture_execute(query, params):
            captured_params.update(params)
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: ["rac"]}):
                result = await catalog_repository.list_all(
                    status=ActionStatus.PUBLISHED,
                    tags_filter=["rac", "dataguard"],
                )

        assert len(result) == 1
        assert result[0].tags == ["rac"]
        assert captured_params.get("tag0") == "rac"
        assert captured_params.get("tag1") == "dataguard"
        assert captured_params.get("status") == "published"


# === Story 2.2: Execution Steps Tests ===


class TestExecutionStepsConversions:
    """Tests for execution steps JSON conversion helpers."""

    def test_parse_execution_steps(self):
        """Test parsing execution steps from JSON string (Story 2.7: new format connector_type)."""
        json_str = '[{"order": 1, "name": "Step 1", "type": "prerequisite", "connector_type": "none", "connector_config": null, "conditional_environments": null}]'
        result = catalog_repository._parse_execution_steps(json_str)
        assert result is not None
        assert len(result) == 1
        assert result[0].order == 1
        assert result[0].name == "Step 1"
        assert result[0].type == ExecutionStepType.PREREQUISITE
        assert result[0].connector_type == ConnectorType.NONE

    def test_parse_execution_steps_legacy_is_servicenow_change(self):
        """AC3: Parse legacy format is_servicenow_change → connector_type (Story 2.7)."""
        json_str = '[{"order": 1, "name": "Step 1", "type": "prerequisite", "is_servicenow_change": false, "conditional_environments": null}]'
        result = catalog_repository._parse_execution_steps(json_str)
        assert result[0].connector_type == ConnectorType.NONE
        json_str_sn = '[{"order": 1, "name": "Change", "type": "execution", "is_servicenow_change": true, "conditional_environments": ["PROD"]}]'
        result_sn = catalog_repository._parse_execution_steps(json_str_sn)
        assert result_sn[0].connector_type == ConnectorType.SERVICENOW
        assert result_sn[0].conditional_environments == ["PROD"]

    def test_parse_execution_steps_with_servicenow(self):
        """Test parsing steps with connector_type servicenow (new format)."""
        json_str = '[{"order": 1, "name": "Change", "type": "execution", "connector_type": "servicenow", "connector_config": {}, "conditional_environments": ["PROD"]}]'
        result = catalog_repository._parse_execution_steps(json_str)
        assert result[0].connector_type == ConnectorType.SERVICENOW
        assert result[0].conditional_environments == ["PROD"]

    def test_parse_execution_steps_none(self):
        """Test parsing None returns None."""
        result = catalog_repository._parse_execution_steps(None)
        assert result is None

    def test_parse_change_type_config(self):
        """Test parsing change type config new format (Story 2.24)."""
        json_str = '{"DEV": {"required": false}, "PROD": {"required": true, "change_model_code": "1516B"}}'
        result = catalog_repository._parse_change_type_config(json_str)
        assert result is not None
        assert result["DEV"].required is False
        assert result["DEV"].change_model_code is None
        assert result["PROD"].required is True
        assert result["PROD"].change_model_code == "1516B"

    def test_parse_change_type_config_legacy_raises(self):
        """Story 2.24 AC4: Legacy format (env -> string) raises LegacyChangeTypeConfigError."""
        from app.repositories.catalog_repository import LegacyChangeTypeConfigError
        json_str = '{"DEV": "pre_approved", "PROD": "pre_approved"}'
        with pytest.raises(LegacyChangeTypeConfigError, match="legacy format"):
            catalog_repository._parse_change_type_config(json_str)

    def test_parse_change_type_config_none(self):
        """Test parsing None returns None."""
        result = catalog_repository._parse_change_type_config(None)
        assert result is None

    def test_execution_steps_to_json(self):
        """Test converting execution steps to JSON string (Story 2.7: connector_type only, no is_servicenow_change)."""
        steps = [
            ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
            ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.EXECUTION, connector_type=ConnectorType.SERVICENOW, connector_config={}, conditional_environments=["PROD"]),
        ]
        result = catalog_repository._execution_steps_to_json(steps)
        assert result is not None
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Step 1"
        assert parsed[0]["connector_type"] == "none"
        assert "is_servicenow_change" not in parsed[0]
        assert parsed[1]["type"] == "execution"
        assert parsed[1]["connector_type"] == "servicenow"
        assert parsed[1]["conditional_environments"] == ["PROD"]

    def test_execution_steps_to_json_none(self):
        """Test converting None returns None."""
        result = catalog_repository._execution_steps_to_json(None)
        assert result is None

    def test_change_type_config_to_json(self):
        """Test converting change type config to JSON string (Story 2.24)."""
        config = {
            "DEV": ChangeTypeConfigEntry(required=False),
            "PROD": ChangeTypeConfigEntry(required=True, change_model_code="1516B"),
        }
        result = catalog_repository._change_type_config_to_json(config)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["DEV"] == {"required": False, "change_model_code": None}
        assert parsed["PROD"] == {"required": True, "change_model_code": "1516B"}

    def test_change_type_config_to_json_none(self):
        """Test converting None returns None."""
        result = catalog_repository._change_type_config_to_json(None)
        assert result is None


class TestUpdateExecutionSteps:
    """Tests for update_execution_steps() function (AC #5)."""

    @pytest.mark.asyncio
    async def test_update_execution_steps_success(self, mock_db_row_with_execution_steps):
        """Test updating execution steps successfully."""
        # First call: check status (returns draft)
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("draft",))
        mock_cursor_check.close = AsyncMock()

        # Second call: update
        mock_cursor_update = AsyncMock()
        mock_cursor_update.close = AsyncMock()
        mock_cursor_update.rowcount = 1

        # Third call: get_by_id (separate conn in real code)
        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_execution_steps)
        mock_cursor_get.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor_check
            elif call_count == 2:
                return mock_cursor_update
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            steps = [
                ExecutionStep(order=1, name="Verification", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
            ]
            change_config = {
                "DEV": ChangeTypeConfigEntry(required=False),
                "PROD": ChangeTypeConfigEntry(required=True, change_model_code="1516B"),
            }

            result = await catalog_repository.update_execution_steps(1, steps, change_config)

        assert result is not None
        assert result.id == 1
        assert result.execution_steps is not None

    @pytest.mark.asyncio
    async def test_update_execution_steps_not_found(self):
        """Test updating execution steps when action not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE)]
            result = await catalog_repository.update_execution_steps(999, steps, None)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_execution_steps_not_draft_raises_error(self):
        """Test updating execution steps when action is not draft raises InvalidStateError."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=("published",))
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE)]

            with pytest.raises(InvalidStateError) as exc_info:
                await catalog_repository.update_execution_steps(1, steps, None)

            assert exc_info.value.current_status == "published"
            assert "brouillon" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_execution_steps_zero_rows_raises_error(self):
        """Test update_execution_steps when UPDATE affects 0 rows (race: published meanwhile)."""
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("draft",))
        mock_cursor_check.close = AsyncMock()

        mock_cursor_update = AsyncMock()
        mock_cursor_update.close = AsyncMock()
        mock_cursor_update.rowcount = 0

        mock_cursor_status = AsyncMock()
        mock_cursor_status.fetchone = AsyncMock(return_value=("published",))
        mock_cursor_status.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor_check
            if call_count == 2:
                return mock_cursor_update
            return mock_cursor_status

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE)]

            with pytest.raises(InvalidStateError) as exc_info:
                await catalog_repository.update_execution_steps(1, steps, None)

            assert exc_info.value.current_status == "published"
            assert "plus en brouillon" in str(exc_info.value) or "modifiée" in str(exc_info.value)


class TestRowToActionDetailWithExecutionSteps:
    """Tests for _row_to_action_detail with execution_steps."""

    def test_row_to_action_detail_with_execution_steps(self, mock_db_row_with_execution_steps):
        """Test converting row to ActionDetail with execution_steps and new change_type_config (Story 2.24)."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_execution_steps)
        assert result.id == 1
        assert result.execution_steps is not None
        assert len(result.execution_steps) == 1
        assert result.execution_steps[0].name == "Verification"
        assert result.execution_steps[0].connector_type == ConnectorType.NONE
        assert result.change_type_config is not None
        assert result.change_type_config["DEV"].required is False
        assert result.change_type_config["PROD"].required is True
        assert result.change_type_config["PROD"].change_model_code == "1516B"


# Story 2.3 RBAC by action tests removed in Story 2.14 — RBAC now managed via profiles.
# Removed: TestRbacPoliciesConversions, TestUpdateRbacPolicies, TestListAllWithRbacFilter


# === Story 2.4: Status Transition and Lifecycle Tests ===


class TestUpdateStatus:
    """Tests for update_status() function (Story 2.4, AC #1, #4, #5)."""

    @pytest.fixture
    def mock_db_row_draft(self):
        """Sample database row for draft action. Story 3.4: DOCUMENTATION_MD column added (V022)."""
        return (
            1,  # ID
            "Draft Action",  # NAME
            "A draft action",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
            "draft",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
            None,  # DOCUMENTATION_MD (Story 3.4)
        )

    @pytest.fixture
    def mock_db_row_published(self):
        """Sample database row for published action. Story 3.4: DOCUMENTATION_MD column added (V022)."""
        return (
            1,  # ID
            "Published Action",  # NAME
            "A published action",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            datetime(2026, 1, 28, 11, 0, 0),  # UPDATED_AT
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
            None,  # DOCUMENTATION_MD (Story 3.4)
        )

    @pytest.fixture
    def mock_db_row_disabled(self):
        """Sample database row for disabled action. Story 3.4: DOCUMENTATION_MD column added (V022)."""
        return (
            1,  # ID
            "Disabled Action",  # NAME
            "A disabled action",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            None,  # DEFAULT_IMPACT_LEVEL (Story 2.18 AC5)
            "disabled",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            datetime(2026, 1, 28, 12, 0, 0),  # UPDATED_AT
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
            None,  # DOCUMENTATION_MD (Story 3.4)
        )

    @pytest.mark.asyncio
    async def test_update_status_publish_success(self, mock_db_row_published):
        """Test publishing a draft action successfully."""
        from app.models.catalog import StatusTransition

        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("draft",))
        mock_cursor_check.close = AsyncMock()

        mock_cursor_update = AsyncMock()
        mock_cursor_update.rowcount = 1
        mock_cursor_update.close = AsyncMock()

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_published)
        mock_cursor_get.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor_check
            elif call_count == 2:
                return mock_cursor_update
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                with patch("app.repositories.audit_repository.create_entry", new_callable=AsyncMock, return_value=1):
                    result = await catalog_repository.update_status(1, StatusTransition.PUBLISH, user_id="user123")

        assert result is not None
        assert result.id == 1
        assert result.status == ActionStatus.PUBLISHED
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_update_status_disable_success(self, mock_db_row_disabled):
        """Test disabling a published action successfully."""
        from app.models.catalog import StatusTransition

        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("published",))
        mock_cursor_check.close = AsyncMock()

        mock_cursor_update = AsyncMock()
        mock_cursor_update.rowcount = 1
        mock_cursor_update.close = AsyncMock()

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_disabled)
        mock_cursor_get.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor_check
            elif call_count == 2:
                return mock_cursor_update
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                with patch("app.repositories.audit_repository.create_entry", new_callable=AsyncMock, return_value=1):
                    result = await catalog_repository.update_status(1, StatusTransition.DISABLE, user_id="user123")

        assert result is not None
        assert result.status == ActionStatus.DISABLED
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_update_status_enable_success(self, mock_db_row_published):
        """Test enabling a disabled action successfully."""
        from app.models.catalog import StatusTransition

        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("disabled",))
        mock_cursor_check.close = AsyncMock()

        mock_cursor_update = AsyncMock()
        mock_cursor_update.rowcount = 1
        mock_cursor_update.close = AsyncMock()

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_published)
        mock_cursor_get.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor_check
            elif call_count == 2:
                return mock_cursor_update
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                with patch("app.repositories.audit_repository.create_entry", new_callable=AsyncMock, return_value=1):
                    result = await catalog_repository.update_status(1, StatusTransition.ENABLE, user_id="user123")

        assert result is not None
        assert result.status == ActionStatus.PUBLISHED
        assert result.tags == []

    @pytest.mark.asyncio
    async def test_update_status_not_found(self):
        """Test updating status when action not found."""
        from app.models.catalog import StatusTransition

        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.update_status(999, StatusTransition.PUBLISH, user_id="user123")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_invalid_transition_draft_disable(self):
        """Test invalid transition draft -> disable raises InvalidTransitionError."""
        from app.models.catalog import StatusTransition, InvalidTransitionError

        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=("draft",))
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(InvalidTransitionError) as exc_info:
                await catalog_repository.update_status(1, StatusTransition.DISABLE, user_id="user123")

            assert "draft" in exc_info.value.current_status


class TestListAllAdmin:
    """Tests for list_all_admin() function (Story 2.4, AC #2)."""

    @pytest.fixture
    def mock_db_rows_admin(self):
        """Sample database rows for admin dashboard. Query returns ID, NAME, STATUS, ENGINE, CREATED_AT, EXECUTION_COUNT (Story 2.23: no CATEGORY)."""
        return [
            (
                1,  # ID
                "Draft Action",  # NAME
                "draft",  # STATUS
                "Oracle",  # ENGINE
                datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
                0,  # EXECUTION_COUNT
            ),
            (
                2,  # ID
                "Published Action",  # NAME
                "published",  # STATUS
                "SQL Server",  # ENGINE
                datetime(2026, 1, 27, 10, 0, 0),  # CREATED_AT
                42,  # EXECUTION_COUNT
            ),
            (
                3,  # ID
                "Disabled Action",  # NAME
                "disabled",  # STATUS
                "Oracle",  # ENGINE
                datetime(2026, 1, 26, 10, 0, 0),  # CREATED_AT
                15,  # EXECUTION_COUNT
            ),
        ]

    @pytest.mark.asyncio
    async def test_list_all_admin_returns_all_statuses(self, mock_db_rows_admin):
        """Test list_all_admin returns actions of all statuses."""
        mock_cursor_count = AsyncMock()
        mock_cursor_count.fetchone = AsyncMock(return_value=(3,))
        mock_cursor_count.close = AsyncMock()

        mock_cursor_data = AsyncMock()
        mock_cursor_data.fetchall = AsyncMock(return_value=mock_db_rows_admin)
        mock_cursor_data.close = AsyncMock()

        mock_cursor_tags = AsyncMock()
        mock_cursor_tags.fetchall = AsyncMock(return_value=[])  # no tags (Story 2.6)
        mock_cursor_tags.close = AsyncMock()

        mock_conn = AsyncMock()
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            # Dedicated count query only (main query has COUNT in EXECUTION_LOG subquery)
            if query.strip().startswith("SELECT COUNT(*)"):
                return mock_cursor_count
            # Tags query joins ACTION_TAGS and TAGS tables (Story 2.6)
            if "FROM ACTION_TAGS" in query or "FROM TAGS" in query or "JOIN TAGS" in query:
                return mock_cursor_tags
            return mock_cursor_data

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            actions, pagination = await catalog_repository.list_all_admin()

        assert len(actions) == 3
        statuses = [r.status for r in actions]
        assert ActionStatus.DRAFT in statuses
        assert ActionStatus.PUBLISHED in statuses
        assert ActionStatus.DISABLED in statuses
        assert pagination.total_count == 3
        assert all(r.tags == [] for r in actions)

    @pytest.mark.asyncio
    async def test_list_all_admin_includes_execution_count(self, mock_db_rows_admin):
        """Test list_all_admin includes execution_count."""
        mock_cursor_count = AsyncMock()
        mock_cursor_count.fetchone = AsyncMock(return_value=(3,))
        mock_cursor_count.close = AsyncMock()

        mock_cursor_data = AsyncMock()
        mock_cursor_data.fetchall = AsyncMock(return_value=mock_db_rows_admin)
        mock_cursor_data.close = AsyncMock()

        mock_cursor_tags = AsyncMock()
        mock_cursor_tags.fetchall = AsyncMock(return_value=[])
        mock_cursor_tags.close = AsyncMock()

        mock_conn = AsyncMock()
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if query.strip().startswith("SELECT COUNT(*)"):
                return mock_cursor_count
            if "ACTION_TAGS" in query or "TAGS" in query:
                return mock_cursor_tags
            return mock_cursor_data

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            actions, pagination = await catalog_repository.list_all_admin()

        # Find the published action (id=2)
        published = next(r for r in actions if r.id == 2)
        assert published.execution_count == 42
        assert published.tags == []

    @pytest.mark.asyncio
    async def test_list_all_admin_with_status_filter(self, mock_db_rows_admin):
        """Test list_all_admin with status filter."""
        # Only return published actions
        mock_db_rows_filtered = [r for r in mock_db_rows_admin if r[2] == "published"]

        mock_cursor_count = AsyncMock()
        mock_cursor_count.fetchone = AsyncMock(return_value=(1,))
        mock_cursor_count.close = AsyncMock()

        mock_cursor_data = AsyncMock()
        mock_cursor_data.fetchall = AsyncMock(return_value=mock_db_rows_filtered)
        mock_cursor_data.close = AsyncMock()

        mock_cursor_tags = AsyncMock()
        mock_cursor_tags.fetchall = AsyncMock(return_value=[])
        mock_cursor_tags.close = AsyncMock()

        mock_conn = AsyncMock()
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if query.strip().startswith("SELECT COUNT(*)"):
                return mock_cursor_count
            if "ACTION_TAGS" in query or "TAGS" in query:
                return mock_cursor_tags
            return mock_cursor_data

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            actions, pagination = await catalog_repository.list_all_admin(status=ActionStatus.PUBLISHED)

        assert len(actions) == 1
        assert actions[0].status == ActionStatus.PUBLISHED
        assert actions[0].tags == []
        assert pagination.total_count == 1


class TestTagsRepository:
    """Tests for tags repository functions (Story 2.6, FR11c)."""

    @pytest.mark.asyncio
    async def test_get_all_tags_empty(self):
        """Test get_all_tags when no tags exist."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.get_all_tags()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_tags_returns_tag_responses(self):
        """Test get_all_tags returns list of TagResponse."""
        from datetime import datetime
        from app.models.catalog import TagResponse

        mock_row = (1, "rac", datetime(2026, 1, 28, 12, 0, 0))
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_row])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.get_all_tags()

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "rac"

    @pytest.mark.asyncio
    async def test_get_tags_for_action_returns_names(self):
        """Test get_tags_for_action returns tag names for action."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[("rac",), ("dataguard",)])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.get_tags_for_action(1)

        assert result == ["rac", "dataguard"]

    @pytest.mark.asyncio
    async def test_create_tag_if_not_exists_inserts_new(self):
        """Test create_tag_if_not_exists inserts and returns id when tag does not exist."""
        mock_cursor_select = AsyncMock()
        mock_cursor_select.fetchone = AsyncMock(return_value=None)
        mock_cursor_select.close = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [5]
        mock_conn = AsyncMock()
        mock_conn.var = MagicMock(return_value=mock_out_id)
        mock_conn.commit = AsyncMock()
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if "SELECT" in query:
                return mock_cursor_select
            return AsyncMock(close=AsyncMock())

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.create_tag_if_not_exists("RAC")

        assert result == 5
        assert call_count >= 2  # SELECT then INSERT

    @pytest.mark.asyncio
    async def test_create_tag_if_not_exists_returns_existing(self):
        """Test create_tag_if_not_exists returns existing id when tag exists."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(3,))
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.create_tag_if_not_exists("rac")

        assert result == 3

    @pytest.mark.asyncio
    async def test_set_action_tags_deletes_and_inserts(self):
        """Test set_action_tags deletes existing and inserts new links."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=AsyncMock(close=AsyncMock()))
        mock_conn.commit = AsyncMock()
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            return AsyncMock(close=AsyncMock())

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            await catalog_repository.set_action_tags(1, [10, 20])

        assert call_count == 3  # DELETE + 2 INSERTs
        mock_conn.commit.assert_called_once()


class TestListCatalog:
    """Tests for list_catalog() function (Story 3.1, AC1, AC3, AC10, AC11)."""

    @pytest.fixture
    def mock_db_row_catalog(self):
        """Sample database row for catalog list with execution_count. Story 3.4: DOCUMENTATION_MD column added (V022)."""
        return (
            1,  # ID
            "Create PDB Oracle",  # NAME
            "Creates a Pluggable Database",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            '{"type": "object"}',  # PARAMETERS_SCHEMA
            '{"DEV": {"level": "low"}}',  # IMPACT_RULES
            "low",  # DEFAULT_IMPACT_LEVEL
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            '# Documentation\n\nThis action creates a PDB.',  # DOCUMENTATION_MD (Story 3.4)
            5,  # EXECUTION_COUNT
        )

    @pytest.mark.asyncio
    async def test_list_catalog_returns_actions_with_execution_count(self, mock_db_row_catalog):
        """AC3: list_catalog includes execution_count for each action."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_catalog])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: ["rac"]}):
                result = await catalog_repository.list_catalog(status=ActionStatus.PUBLISHED)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Create PDB Oracle"
        assert result[0]["execution_count"] == 5
        assert result[0]["tags"] == ["rac"]

    @pytest.mark.asyncio
    async def test_list_catalog_with_tags_filter(self, mock_db_row_catalog):
        """AC6: list_catalog filters by tags (category maps to tag)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_catalog])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        captured_params = {}

        async def capture_execute(query, params):
            captured_params.update(params)
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: []}):
                result = await catalog_repository.list_catalog(
                    status=ActionStatus.PUBLISHED,
                    tags_filter=["provisioning"],
                )

        assert len(result) == 1
        assert captured_params.get("tag0") == "provisioning"

    @pytest.mark.asyncio
    async def test_list_catalog_with_action_ids_filter(self, mock_db_row_catalog):
        """AC11: list_catalog filters by action_ids (RBAC filtering)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_catalog])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        captured_params = {}

        async def capture_execute(query, params):
            captured_params.update(params)
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: []}):
                result = await catalog_repository.list_catalog(
                    status=ActionStatus.PUBLISHED,
                    action_ids_filter=[1, 2, 3],
                )

        assert len(result) == 1
        assert captured_params.get("aid0") == 1
        assert captured_params.get("aid1") == 2
        assert captured_params.get("aid2") == 3

    @pytest.mark.asyncio
    async def test_list_catalog_empty(self):
        """Test list_catalog returns empty list when no actions match."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_catalog()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_catalog_with_q_engine_environment_impact(self, mock_db_row_catalog):
        """Story 3.3 AC9: list_catalog accepts q, engine, environment, impact (case-insensitive search)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_catalog])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        captured_params = {}
        captured_query = []

        async def capture_execute(query, params):
            captured_params.update(params)
            captured_query.append(query)
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: ["rac"]}):
                result = await catalog_repository.list_catalog(
                    status=ActionStatus.PUBLISHED,
                    q="oracle",
                    engine="Oracle",
                    environment="PROD",
                    impact="high",
                )

        assert len(result) == 1
        # Story 3.3: Case-insensitive search uses UPPER()
        assert captured_params.get("q_name") == "%ORACLE%"
        assert captured_params.get("q_desc") == "%ORACLE%"
        assert captured_params.get("q_tag") == "%ORACLE%"
        assert captured_params.get("engine") == "Oracle"
        assert captured_params.get("environment") == "PROD"
        assert captured_params.get("impact") == "high"
        query_str = captured_query[0]
        assert "UPPER(AC.NAME) LIKE :q_name" in query_str
        assert "ENGINE = :engine" in query_str
        assert "DEFAULT_IMPACT_LEVEL = :impact" in query_str


class TestListTagsWithCounts:
    """Tests for list_tags_with_counts() (Story 3.3, AC3, AC10)."""

    @pytest.mark.asyncio
    async def test_list_tags_with_counts_returns_name_and_count(self):
        """list_tags_with_counts returns list of { name, action_count } for published actions."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[("rac", 5), ("dataguard", 2)])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_tags_with_counts()

        assert len(result) == 2
        assert result[0]["name"] == "rac"
        assert result[0]["action_count"] == 5
        assert result[1]["name"] == "dataguard"
        assert result[1]["action_count"] == 2

    @pytest.mark.asyncio
    async def test_list_tags_with_counts_with_action_ids_filter(self):
        """list_tags_with_counts with action_ids_filter restricts to those actions."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[("rac", 2)])
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        captured_params = {}

        async def capture_execute(query, params):
            captured_params.update(params)
            return mock_cursor

        mock_conn.execute = capture_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_tags_with_counts(action_ids_filter=[1, 2, 3])

        assert len(result) == 1
        assert result[0]["name"] == "rac"
        assert result[0]["action_count"] == 2
        assert captured_params.get("aid0") == 1
        assert captured_params.get("aid1") == 2
        assert captured_params.get("aid2") == 3


class TestDocumentationMd:
    """Tests for documentation_md field (Story 3.4, FR12)."""

    @pytest.fixture
    def mock_db_row_with_documentation(self):
        """Sample database row with documentation_md content."""
        return (
            1,  # ID
            "Create PDB Oracle",  # NAME
            "Creates a Pluggable Database",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            '{"type": "object"}',  # PARAMETERS_SCHEMA
            '{"DEV": {"level": "low"}}',  # IMPACT_RULES
            "low",  # DEFAULT_IMPACT_LEVEL
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
            "# Create PDB\n\n## Overview\n\nThis action creates a **Pluggable Database**.\n\n```sql\nCREATE PLUGGABLE DATABASE pdb_name;\n```",  # DOCUMENTATION_MD
        )

    @pytest.fixture
    def mock_db_row_without_documentation(self):
        """Sample database row without documentation_md content."""
        return (
            2,  # ID
            "Delete PDB",  # NAME
            "Deletes a Pluggable Database",  # DESCRIPTION
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            None,  # DEFAULT_IMPACT_LEVEL
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
            None,  # DOCUMENTATION_MD
        )

    def test_row_to_action_detail_with_documentation_md(self, mock_db_row_with_documentation):
        """Test _row_to_action_detail includes documentation_md when present (AC4)."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_documentation)
        assert result.documentation_md is not None
        assert "# Create PDB" in result.documentation_md
        assert "```sql" in result.documentation_md

    def test_row_to_action_detail_without_documentation_md(self, mock_db_row_without_documentation):
        """Test _row_to_action_detail returns None for documentation_md when absent (AC3)."""
        result = catalog_repository._row_to_action_detail(mock_db_row_without_documentation)
        assert result.documentation_md is None

    def test_row_to_action_response_with_documentation_md(self, mock_db_row_with_documentation):
        """Test _row_to_action_response includes documentation_md (AC4)."""
        row_for_response = mock_db_row_with_documentation[:12] + (mock_db_row_with_documentation[14],)
        result = catalog_repository._row_to_action_response(row_for_response)
        assert result.documentation_md is not None
        assert "# Create PDB" in result.documentation_md

    @pytest.mark.asyncio
    async def test_get_by_id_returns_documentation_md(self, mock_db_row_with_documentation):
        """Test get_by_id returns documentation_md field (AC4)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_db_row_with_documentation)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                result = await catalog_repository.get_by_id(1)

        assert result is not None
        assert result.documentation_md is not None
        assert "# Create PDB" in result.documentation_md

    @pytest.mark.asyncio
    async def test_get_by_id_returns_null_documentation_md(self, mock_db_row_without_documentation):
        """Test get_by_id returns None for documentation_md when not set (AC3)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_db_row_without_documentation)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                result = await catalog_repository.get_by_id(2)

        assert result is not None
        assert result.documentation_md is None

    @pytest.mark.asyncio
    async def test_create_action_with_documentation_md(self, mock_db_row_with_documentation):
        """Test create action with documentation_md persists to database."""
        from app.models.catalog import ActionCreate, ActionEngine, ActionPlatform

        action_create = ActionCreate(
            name="Create PDB Oracle",
            description="Creates a Pluggable Database",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            documentation_md="# Create PDB\n\nThis action creates a PDB.",
        )

        captured_params = {}
        mock_cursor = AsyncMock()
        mock_cursor.close = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.commit = AsyncMock()

        mock_out_id = MagicMock()
        mock_out_id.getvalue.return_value = [1]
        mock_conn.var = MagicMock(return_value=mock_out_id)

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_documentation)
        mock_cursor_get.close = AsyncMock()

        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count, captured_params
            call_count += 1
            if call_count == 1:
                captured_params = {k: v for k, v in params.items() if k != "out_id"}
                return mock_cursor
            return mock_cursor_get

        mock_conn.execute = mock_execute

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_action", new_callable=AsyncMock, return_value=[]):
                result = await catalog_repository.create(action_create, user_id=42)

        assert "documentation_md" in captured_params
        assert captured_params["documentation_md"] == "# Create PDB\n\nThis action creates a PDB."
        assert result.documentation_md is not None
