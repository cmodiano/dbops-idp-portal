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
    ExecutionStep,
    ExecutionStepType,
    ChangeType,
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

            result = await catalog_repository.create(sample_action_create, user_id=42)

        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        assert result.status == ActionStatus.DRAFT

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
        """Test getting action by ID when found."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_db_row_with_rbac)
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.get_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "Create PDB Oracle"
        assert result.rbac_policies is not None

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
        """Test listing all actions without filter."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row, mock_db_row])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_all()

        assert len(result) == 2
        assert all(r.name == "Create PDB Oracle" for r in result)

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

            result = await catalog_repository.list_all(status=ActionStatus.DRAFT)

        assert len(result) == 1
        assert captured_params["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_all_empty(self):
        """Test listing actions when none exist."""
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


# === Story 2.2: Execution Steps Tests ===


class TestExecutionStepsConversions:
    """Tests for execution steps JSON conversion helpers."""

    def test_parse_execution_steps(self):
        """Test parsing execution steps from JSON string."""
        json_str = '[{"order": 1, "name": "Step 1", "type": "prerequisite", "is_servicenow_change": false, "conditional_environments": null}]'
        result = catalog_repository._parse_execution_steps(json_str)
        assert result is not None
        assert len(result) == 1
        assert result[0].order == 1
        assert result[0].name == "Step 1"
        assert result[0].type == ExecutionStepType.PREREQUISITE

    def test_parse_execution_steps_with_servicenow(self):
        """Test parsing steps with ServiceNow change."""
        json_str = '[{"order": 1, "name": "Change", "type": "execution", "is_servicenow_change": true, "conditional_environments": ["PROD"]}]'
        result = catalog_repository._parse_execution_steps(json_str)
        assert result[0].is_servicenow_change is True
        assert result[0].conditional_environments == ["PROD"]

    def test_parse_execution_steps_none(self):
        """Test parsing None returns None."""
        result = catalog_repository._parse_execution_steps(None)
        assert result is None

    def test_parse_change_type_config(self):
        """Test parsing change type config from JSON string."""
        json_str = '{"DEV": "pre_approved", "PROD": "cab"}'
        result = catalog_repository._parse_change_type_config(json_str)
        assert result is not None
        assert result["DEV"] == ChangeType.PRE_APPROVED
        assert result["PROD"] == ChangeType.CAB

    def test_parse_change_type_config_none(self):
        """Test parsing None returns None."""
        result = catalog_repository._parse_change_type_config(None)
        assert result is None

    def test_execution_steps_to_json(self):
        """Test converting execution steps to JSON string."""
        steps = [
            ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE),
            ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.EXECUTION),
        ]
        result = catalog_repository._execution_steps_to_json(steps)
        assert result is not None
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "Step 1"
        assert parsed[1]["type"] == "execution"

    def test_execution_steps_to_json_none(self):
        """Test converting None returns None."""
        result = catalog_repository._execution_steps_to_json(None)
        assert result is None

    def test_change_type_config_to_json(self):
        """Test converting change type config to JSON string."""
        config = {"DEV": ChangeType.PRE_APPROVED, "PROD": ChangeType.CAB}
        result = catalog_repository._change_type_config_to_json(config)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["DEV"] == "pre_approved"
        assert parsed["PROD"] == "cab"

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
                ExecutionStep(order=1, name="Verification", type=ExecutionStepType.PREREQUISITE),
            ]
            change_config = {"DEV": ChangeType.PRE_APPROVED, "PROD": ChangeType.CAB}

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

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE)]
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

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE)]

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

            steps = [ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE)]

            with pytest.raises(InvalidStateError) as exc_info:
                await catalog_repository.update_execution_steps(1, steps, None)

            assert exc_info.value.current_status == "published"
            assert "plus en brouillon" in str(exc_info.value) or "modifiée" in str(exc_info.value)


class TestRowToActionDetailWithExecutionSteps:
    """Tests for _row_to_action_detail with execution_steps."""

    def test_row_to_action_detail_with_execution_steps(self, mock_db_row_with_execution_steps):
        """Test converting row to ActionDetail with execution_steps."""
        result = catalog_repository._row_to_action_detail(mock_db_row_with_execution_steps)
        assert result.id == 1
        assert result.execution_steps is not None
        assert len(result.execution_steps) == 1
        assert result.execution_steps[0].name == "Verification"
        assert result.change_type_config is not None
        assert result.change_type_config["DEV"] == ChangeType.PRE_APPROVED
        assert result.change_type_config["PROD"] == ChangeType.CAB


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
        """Test list_all without user_profile returns all actions."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[mock_db_row_with_rbac_full, mock_db_row_dba_only])
        mock_cursor.close = AsyncMock()

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("app.repositories.catalog_repository.get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await catalog_repository.list_all(user_profile=None)

        assert len(result) == 2

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

            from app.models.catalog import UserProfile
            result = await catalog_repository.list_all(user_profile=UserProfile.DBA_APPLICATIF)

        assert len(result) == 2
