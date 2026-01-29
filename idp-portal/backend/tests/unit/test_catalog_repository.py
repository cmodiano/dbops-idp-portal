"""Tests for catalog repository (Story 2.1, AC #4).

Uses mocks for Oracle pool to test repository logic without database.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.models.catalog import (
    ActionCreate,
    ActionCategory,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ConnectorType,
    ExecutionStep,
    ExecutionStepType,
    ChangeType,
    StatusTransition,
    InvalidTransitionError,
)
from app.repositories import catalog_repository
from app.repositories.catalog_repository import InvalidStateError


@pytest.fixture
def sample_action_create():
    """Sample ActionCreate for testing."""
    return ActionCreate(
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        category=ActionCategory.PROVISIONING,
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
    """Sample database row for action."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Provisioning",  # CATEGORY
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA (CLOB as string)
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
    )


# Valid RBAC JSON (Story 2.3 schema with "environments" key) for row fixtures
_VALID_RBAC_JSON = '{"environments": {"DEV": {"profiles": ["dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}'


@pytest.fixture
def mock_db_row_with_rbac():
    """Sample database row for action with rbac_policies (valid RbacPolicies schema)."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Provisioning",  # CATEGORY
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
        _VALID_RBAC_JSON,  # RBAC_POLICIES
        None,  # EXECUTION_STEPS
        None,  # CHANGE_TYPE_CONFIG
    )


@pytest.fixture
def mock_db_row_with_execution_steps():
    """Sample database row for action with execution_steps and change_type_config."""
    return (
        1,  # ID
        "Create PDB Oracle",  # NAME
        "Creates a Pluggable Database",  # DESCRIPTION
        "Provisioning",  # CATEGORY
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        '{"type": "object"}',  # PARAMETERS_SCHEMA
        '{"DEV": {"level": "low"}}',  # IMPACT_RULES
        "draft",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        datetime(2026, 1, 28, 11, 0, 0),  # UPDATED_AT
        _VALID_RBAC_JSON,  # RBAC_POLICIES
        '[{"order": 1, "name": "Verification", "type": "prerequisite", "is_servicenow_change": false, "conditional_environments": null}]',  # EXECUTION_STEPS
        '{"DEV": "pre_approved", "PROD": "cab"}',  # CHANGE_TYPE_CONFIG
    )


@pytest.fixture
def mock_db_row_published():
    """Sample database row for published action."""
    return (
        2,  # ID
        "Published Action",  # NAME
        "A published action",  # DESCRIPTION
        "Administration",  # CATEGORY
        "Oracle",  # ENGINE
        "AAP",  # PLATFORM
        None,  # PARAMETERS_SCHEMA
        None,  # IMPACT_RULES
        "published",  # STATUS
        42,  # CREATED_BY
        datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
        None,  # UPDATED_AT
        None,  # RBAC_POLICIES
        None,  # EXECUTION_STEPS
        None,  # CHANGE_TYPE_CONFIG
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
        assert result.category == ActionCategory.PROVISIONING
        assert result.engine == ActionEngine.ORACLE
        assert result.platform == ActionPlatform.AAP
        assert result.status == ActionStatus.DRAFT

    def test_row_to_action_detail(self, mock_db_row_with_rbac):
        """Test converting row to ActionDetail with rbac_policies (safe parse, normalized shape)."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_rbac)
        assert result.id == 1
        assert result.rbac_policies is not None
        assert "environments" in result.rbac_policies
        assert "DEV" in result.rbac_policies["environments"]
        assert result.rbac_policies["environments"]["DEV"]["profiles"] == ["dba_applicatif"]

    def test_row_to_action_detail_invalid_rbac_json_returns_none(self):
        """Test that invalid RBAC CLOB yields rbac_policies=None (no 500)."""
        row = (
            1, "A", "B", "Provisioning", "Oracle", "AAP",
            None, None, "draft", 42, datetime(2026, 1, 28), None,
            '{"invalid": "no environments key"}',  # invalid for RbacPolicies
            None, None,
        )
        result = catalog_repository._row_to_action_detail(row)
        assert result.id == 1
        assert result.rbac_policies is None


class TestCreate:
    """Tests for create() function."""

    @pytest.mark.asyncio
    async def test_create_action_success(self, sample_action_create, mock_db_row_with_rbac):
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
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_rbac)

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
    async def test_create_action_with_json_fields(self, sample_action_create, mock_db_row_with_rbac):
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
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_rbac)
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
    async def test_get_by_id_found(self, mock_db_row_with_rbac):
        """Test getting action by ID when found (Story 2.6: tags mocked)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_db_row_with_rbac)
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
        assert result.rbac_policies is not None
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
        """Test parsing change type config from JSON string (Story 2.8: "cab" → pre_approved)."""
        json_str = '{"DEV": "pre_approved", "PROD": "cab"}'
        result = catalog_repository._parse_change_type_config(json_str)
        assert result is not None
        assert result["DEV"] == ChangeType.PRE_APPROVED
        assert result["PROD"] == ChangeType.PRE_APPROVED

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
        """Test converting change type config to JSON string (Story 2.8: only "pre_approved", never "cab")."""
        config = {"DEV": ChangeType.PRE_APPROVED, "PROD": ChangeType.PRE_APPROVED}
        result = catalog_repository._change_type_config_to_json(config)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["DEV"] == "pre_approved"
        assert parsed["PROD"] == "pre_approved"
        assert "cab" not in result

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
            change_config = {"DEV": ChangeType.PRE_APPROVED, "PROD": ChangeType.PRE_APPROVED}

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
        """Test converting row to ActionDetail with execution_steps (legacy format → connector_type)."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_execution_steps)
        assert result.id == 1
        assert result.execution_steps is not None
        assert len(result.execution_steps) == 1
        assert result.execution_steps[0].name == "Verification"
        assert result.execution_steps[0].connector_type == ConnectorType.NONE  # legacy is_servicenow_change: false
        assert result.change_type_config is not None
        assert result.change_type_config["DEV"] == ChangeType.PRE_APPROVED
        assert result.change_type_config["PROD"] == ChangeType.PRE_APPROVED  # "cab" converted on read (Story 2.8)


# === Story 2.3: RBAC Policies Tests ===


class TestRbacPoliciesConversions:
    """Tests for RBAC policies JSON conversion helpers (Story 2.3)."""

    def test_rbac_policies_to_json(self):
        """Test converting RbacPolicies to JSON string."""
        from app.models.catalog import RbacPolicies, EnvironmentPermission, UserProfile

        policies = RbacPolicies(
            environments={
                "DEV": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF, UserProfile.CLIENT_BUSINESS],
                    requires_approval=False,
                ),
                "PROD": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF],
                    requires_approval=True,
                    approver_profiles=[UserProfile.DBA_INFRASTRUCTURE],
                ),
            }
        )
        result = catalog_repository._rbac_policies_to_json(policies)
        assert result is not None
        parsed = json.loads(result)
        assert "environments" in parsed
        assert "DEV" in parsed["environments"]
        assert parsed["environments"]["DEV"]["profiles"] == ["dba_applicatif", "client_business"]
        assert parsed["environments"]["PROD"]["requires_approval"] is True

    def test_rbac_policies_to_json_none(self):
        """Test converting None returns None."""
        result = catalog_repository._rbac_policies_to_json(None)
        assert result is None

    def test_parse_rbac_policies(self):
        """Test parsing RBAC policies from JSON string."""
        json_str = '{"environments": {"DEV": {"profiles": ["dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}'
        result = catalog_repository._parse_rbac_policies(json_str)
        assert result is not None
        assert "DEV" in result.environments
        assert result.environments["DEV"].profiles[0] == catalog_repository.UserProfile.DBA_APPLICATIF

    def test_parse_rbac_policies_none(self):
        """Test parsing None returns None."""
        result = catalog_repository._parse_rbac_policies(None)
        assert result is None

    def test_safe_parse_rbac_policies_invalid_json(self):
        """Test safe parse logs warning and returns None on invalid JSON."""
        result = catalog_repository._safe_parse_rbac_policies("not valid json")
        assert result is None

    def test_safe_parse_rbac_policies_valid(self):
        """Test safe parse returns valid RbacPolicies on valid JSON."""
        json_str = '{"environments": {"DEV": {"profiles": ["dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}'
        result = catalog_repository._safe_parse_rbac_policies(json_str)
        assert result is not None


class TestUpdateRbacPolicies:
    """Tests for update_rbac_policies() function (Story 2.3, AC #4)."""

    @pytest.fixture
    def sample_rbac_policies(self):
        """Sample RbacPolicies for testing."""
        from app.models.catalog import RbacPolicies, EnvironmentPermission, UserProfile

        return RbacPolicies(
            environments={
                "DEV": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF, UserProfile.CLIENT_BUSINESS],
                    requires_approval=False,
                ),
                "PROD": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF],
                    requires_approval=True,
                    approver_profiles=[UserProfile.DBA_INFRASTRUCTURE],
                ),
            }
        )

    @pytest.fixture
    def mock_db_row_with_rbac_policies(self):
        """Sample database row with updated RBAC policies."""
        return (
            1,  # ID
            "Create PDB Oracle",  # NAME
            "Creates a Pluggable Database",  # DESCRIPTION
            "Provisioning",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            '{"type": "object"}',  # PARAMETERS_SCHEMA
            '{"DEV": {"level": "low"}}',  # IMPACT_RULES
            "draft",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            datetime(2026, 1, 28, 11, 0, 0),  # UPDATED_AT
            '{"environments": {"DEV": {"profiles": ["dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}',  # RBAC_POLICIES
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
        )

    @pytest.mark.asyncio
    async def test_update_rbac_policies_success(self, sample_rbac_policies, mock_db_row_with_rbac_policies):
        """Test updating RBAC policies successfully."""
        mock_cursor_check = AsyncMock()
        mock_cursor_check.fetchone = AsyncMock(return_value=("draft",))
        mock_cursor_check.close = AsyncMock()

        mock_cursor_update = AsyncMock()
        mock_cursor_update.close = AsyncMock()
        mock_cursor_update.rowcount = 1

        mock_cursor_get = AsyncMock()
        mock_cursor_get.fetchone = AsyncMock(return_value=mock_db_row_with_rbac_policies)
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

            result = await catalog_repository.update_rbac_policies(1, sample_rbac_policies)

        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_update_rbac_policies_not_found(self, sample_rbac_policies):
        """Test updating RBAC policies when action not found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.update_rbac_policies(999, sample_rbac_policies)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_rbac_policies_not_draft_raises_error(self, sample_rbac_policies):
        """Test updating RBAC policies when action is not draft raises InvalidStateError."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=("published",))
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(InvalidStateError) as exc_info:
                await catalog_repository.update_rbac_policies(1, sample_rbac_policies)

            assert exc_info.value.current_status == "published"

    @pytest.mark.asyncio
    async def test_update_rbac_policies_zero_rows_raises_error(self, sample_rbac_policies):
        """Test update_rbac_policies when UPDATE affects 0 rows (race: published meanwhile)."""
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

            with pytest.raises(InvalidStateError) as exc_info:
                await catalog_repository.update_rbac_policies(1, sample_rbac_policies)

            assert exc_info.value.current_status == "published"


class TestListAllWithRbacFilter:
    """Tests for list_all() with RBAC filtering (Story 2.3, AC #3)."""

    @pytest.fixture
    def mock_db_row_with_rbac_full(self):
        """Database row with RBAC policies allowing client_business in DEV."""
        return (
            1,  # ID
            "Action for client",  # NAME
            "Visible to client",  # DESCRIPTION
            "Provisioning",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            '{"environments": {"DEV": {"profiles": ["client_business", "dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}',  # RBAC_POLICIES
        )

    @pytest.fixture
    def mock_db_row_dba_only(self):
        """Database row with RBAC policies allowing only DBA profiles."""
        return (
            2,  # ID
            "Action DBA only",  # NAME
            "Not visible to client",  # DESCRIPTION
            "Administration",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            '{"environments": {"DEV": {"profiles": ["dba_applicatif"], "requires_approval": false, "approver_profiles": null}}}',  # RBAC_POLICIES
        )

    @pytest.fixture
    def mock_db_row_no_rbac(self):
        """Database row with no RBAC policies (visible to all)."""
        return (
            3,  # ID
            "Action no RBAC",  # NAME
            "Visible to all",  # DESCRIPTION
            "Monitoring",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            None,  # RBAC_POLICIES - None means visible to all
        )

    @pytest.mark.asyncio
    async def test_list_all_no_filter_returns_all(self, mock_db_row_with_rbac_full, mock_db_row_dba_only):
        """Test list_all without user_profile returns all actions (Story 2.6: get_tags_for_actions mocked)."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_with_rbac_full, mock_db_row_dba_only])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: [], 2: []}):
                result = await catalog_repository.list_all(user_profile=None)

        assert len(result) == 2
        assert all(r.tags == [] for r in result)

    @pytest.mark.asyncio
    async def test_list_all_client_business_sees_allowed_only(
        self, mock_db_row_with_rbac_full, mock_db_row_dba_only, mock_db_row_no_rbac
    ):
        """Test list_all with client_business profile filters out DBA-only actions."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            mock_db_row_with_rbac_full,  # Visible: client_business in DEV
            mock_db_row_dba_only,        # Not visible: only dba_applicatif
            mock_db_row_no_rbac,         # Visible: no RBAC = all can see
        ])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: [], 2: [], 3: []}):
                from app.models.catalog import UserProfile
                result = await catalog_repository.list_all(user_profile=UserProfile.CLIENT_BUSINESS)

        assert len(result) == 2
        names = [r.name for r in result]
        assert "Action for client" in names
        assert "Action no RBAC" in names
        assert "Action DBA only" not in names

    @pytest.mark.asyncio
    async def test_list_all_dba_applicatif_sees_all_with_rbac(
        self, mock_db_row_with_rbac_full, mock_db_row_dba_only
    ):
        """Test list_all with dba_applicatif profile sees both actions."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            mock_db_row_with_rbac_full,  # Visible: dba_applicatif in DEV
            mock_db_row_dba_only,        # Visible: dba_applicatif in DEV
        ])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            with patch("app.repositories.catalog_repository.get_tags_for_actions", new_callable=AsyncMock, return_value={1: [], 2: []}):
                from app.models.catalog import UserProfile
                result = await catalog_repository.list_all(user_profile=UserProfile.DBA_APPLICATIF)

        assert len(result) == 2


# === Story 2.4: Status Transition and Lifecycle Tests ===


class TestUpdateStatus:
    """Tests for update_status() function (Story 2.4, AC #1, #4, #5)."""

    @pytest.fixture
    def mock_db_row_draft(self):
        """Sample database row for draft action."""
        return (
            1,  # ID
            "Draft Action",  # NAME
            "A draft action",  # DESCRIPTION
            "Provisioning",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "draft",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            None,  # UPDATED_AT
            None,  # RBAC_POLICIES
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
        )

    @pytest.fixture
    def mock_db_row_published(self):
        """Sample database row for published action."""
        return (
            1,  # ID
            "Published Action",  # NAME
            "A published action",  # DESCRIPTION
            "Provisioning",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "published",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            datetime(2026, 1, 28, 11, 0, 0),  # UPDATED_AT
            None,  # RBAC_POLICIES
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
        )

    @pytest.fixture
    def mock_db_row_disabled(self):
        """Sample database row for disabled action."""
        return (
            1,  # ID
            "Disabled Action",  # NAME
            "A disabled action",  # DESCRIPTION
            "Provisioning",  # CATEGORY
            "Oracle",  # ENGINE
            "AAP",  # PLATFORM
            None,  # PARAMETERS_SCHEMA
            None,  # IMPACT_RULES
            "disabled",  # STATUS
            42,  # CREATED_BY
            datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
            datetime(2026, 1, 28, 12, 0, 0),  # UPDATED_AT
            None,  # RBAC_POLICIES
            None,  # EXECUTION_STEPS
            None,  # CHANGE_TYPE_CONFIG
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
        """Sample database rows for admin dashboard."""
        return [
            (
                1,  # ID
                "Draft Action",  # NAME
                "draft",  # STATUS
                "Provisioning",  # CATEGORY
                "Oracle",  # ENGINE
                datetime(2026, 1, 28, 10, 0, 0),  # CREATED_AT
                0,  # EXECUTION_COUNT
            ),
            (
                2,  # ID
                "Published Action",  # NAME
                "published",  # STATUS
                "Administration",  # CATEGORY
                "SQL Server",  # ENGINE
                datetime(2026, 1, 27, 10, 0, 0),  # CREATED_AT
                42,  # EXECUTION_COUNT
            ),
            (
                3,  # ID
                "Disabled Action",  # NAME
                "disabled",  # STATUS
                "Patching",  # CATEGORY
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
