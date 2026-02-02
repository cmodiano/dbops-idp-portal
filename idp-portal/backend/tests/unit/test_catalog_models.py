"""Tests for catalog Pydantic models (Story 2.1, AC #2).

Tests validation rules:
- name: 1-255 chars, strip whitespace
- description: max 4000 chars
- parameters_schema: valid JSON Schema if present
- impact_rules: valid structure {env: {level: "low"|"medium"|"high"|"critical"}}
"""

import pytest
from datetime import datetime

from app.models.catalog import (
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionCreate,
    ActionResponse,
    ActionDetail,
    ConnectorType,
    ExecutionStepType,
    ExecutionStep,
    ChangeTypeConfigEntry,
    ExecutionStepsUpdate,
    TagCreate,
    TagResponse,
    ActionTagsUpdateRequest,
    normalize_tag_name,
    RemediationRule,
    RemediationSuggestion,
    RemediationRulesUpdateRequest,
    RiskLevel,
)


class TestActionCreateValidation:
    """Tests for ActionCreate model validation."""

    def test_valid_action_minimal(self):
        """Test creating action with minimal required fields."""
        action = ActionCreate(
            name="Create PDB",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert action.name == "Create PDB"
        assert action.engine == ActionEngine.ORACLE
        assert action.platform == ActionPlatform.AAP
        assert action.description is None
        assert action.parameters_schema is None
        assert action.impact_rules is None

    def test_valid_action_full(self):
        """Test creating action with all fields."""
        action = ActionCreate(
            name="Patch Database",
            description="Apply database patches",
            engine=ActionEngine.SQL_SERVER,
            platform=ActionPlatform.GITHUB_ACTIONS,
            parameters_schema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {"version": {"type": "string"}},
            },
            impact_rules={
                "DEV": {"level": "low"},
                "PROD": {"level": "high"},
            },
        )
        assert action.name == "Patch Database"
        assert action.description == "Apply database patches"

    def test_name_strip_whitespace(self):
        """Test that name is stripped of whitespace."""
        action = ActionCreate(
            name="  Create PDB  ",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert action.name == "Create PDB"

    def test_name_empty_raises_error(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_whitespace_only_raises_error(self):
        """Test that whitespace-only name raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="   ",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_too_long_raises_error(self):
        """Test that name > 255 chars raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="x" * 256,
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_max_length_valid(self):
        """Test that name at 255 chars is valid."""
        action = ActionCreate(
            name="x" * 255,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert len(action.name) == 255

    def test_description_too_long_raises_error(self):
        """Test that description > 4000 chars raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="Test Action",
                description="x" * 4001,
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_description_max_length_valid(self):
        """Test that description at 4000 chars is valid."""
        action = ActionCreate(
            name="Test Action",
            description="x" * 4000,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert len(action.description) == 4000


class TestParametersSchemaValidation:
    """Tests for parameters_schema validation."""

    def test_valid_json_schema(self):
        """Test valid JSON Schema is accepted."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["name"],
            },
        )
        assert action.parameters_schema is not None

    def test_valid_minimal_schema(self):
        """Test minimal valid schema with just type."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema={"type": "object"},
        )
        assert action.parameters_schema == {"type": "object"}

    def test_none_parameters_schema_valid(self):
        """Test None parameters_schema is valid."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema=None,
        )
        assert action.parameters_schema is None

    def test_invalid_parameters_schema_no_valid_keys(self):
        """Test invalid schema with no recognized JSON Schema keys."""
        with pytest.raises(ValueError, match="valid JSON Schema"):
            ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                parameters_schema={"foo": "bar", "baz": 123},
            )

    def test_empty_dict_parameters_schema_invalid(self):
        """Test empty dict is invalid (no recognized keys)."""
        with pytest.raises(ValueError, match="valid JSON Schema"):
            ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                parameters_schema={},
            )


class TestImpactRulesValidation:
    """Tests for impact_rules validation."""

    def test_valid_impact_rules_single_env(self):
        """Test valid impact rules with single environment."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            impact_rules={"DEV": {"level": "low"}},
        )
        assert action.impact_rules == {"DEV": {"level": "low"}}

    def test_valid_impact_rules_multiple_envs(self):
        """Test valid impact rules with multiple environments."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            impact_rules={
                "DEV": {"level": "low"},
                "STAGING": {"level": "medium"},
                "PROD": {"level": "critical"},
            },
        )
        assert "DEV" in action.impact_rules
        assert "PROD" in action.impact_rules

    def test_valid_all_impact_levels(self):
        """Test all valid impact levels are accepted."""
        for level in ["low", "medium", "high", "critical"]:
            action = ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"ENV": {"level": level}},
            )
            assert action.impact_rules["ENV"]["level"] == level

    def test_none_impact_rules_valid(self):
        """Test None impact_rules is valid."""
        action = ActionCreate(
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            impact_rules=None,
        )
        assert action.impact_rules is None

    def test_invalid_impact_level(self):
        """Test invalid impact level raises error."""
        with pytest.raises(ValueError, match="level must be one of"):
            ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": {"level": "invalid"}},
            )

    def test_missing_level_key(self):
        """Test missing 'level' key raises error."""
        with pytest.raises(ValueError, match="must have a 'level' key"):
            ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": {"severity": "high"}},
            )

    def test_env_value_not_dict(self):
        """Test non-dict environment value raises error."""
        with pytest.raises(ValueError, match="must be an object"):
            ActionCreate(
                name="Test",
                    engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": "low"},
            )


class TestActionEnums:
    """Tests for action enums. Story 2.23: ActionCategory removed."""

    def test_action_engine_values(self):
        """Test ActionEngine enum values."""
        assert ActionEngine.ORACLE.value == "Oracle"
        assert ActionEngine.SQL_SERVER.value == "SQL Server"
        assert ActionEngine.DB2.value == "DB2"

    def test_action_platform_values(self):
        """Test ActionPlatform enum values."""
        assert ActionPlatform.AAP.value == "AAP"
        assert ActionPlatform.GITHUB_ACTIONS.value == "GitHub Actions"
        assert ActionPlatform.AZURE_DEVOPS.value == "Azure DevOps"
        assert ActionPlatform.TERRAFORM.value == "Terraform"

    def test_action_status_values(self):
        """Test ActionStatus enum values."""
        assert ActionStatus.DRAFT.value == "draft"
        assert ActionStatus.PUBLISHED.value == "published"
        assert ActionStatus.DISABLED.value == "disabled"


class TestActionResponse:
    """Tests for ActionResponse model."""

    def test_action_response_creation(self):
        """Test ActionResponse model creation."""
        response = ActionResponse(
            id=1,
            name="Test Action",
            description="A test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DRAFT,
            created_by=42,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
        )
        assert response.id == 1
        assert response.name == "Test Action"
        assert response.status == ActionStatus.DRAFT


class TestActionDetail:
    """Tests for ActionDetail model. Story 2.14: rbac_policies removed."""

    def test_action_detail_inherits_from_response(self):
        """Test ActionDetail inherits all ActionResponse fields."""
        detail = ActionDetail(
            id=1,
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DRAFT,
            created_at=datetime(2026, 1, 28),
        )
        # Check inherited fields exist
        assert hasattr(detail, "id")
        assert hasattr(detail, "name")
        assert hasattr(detail, "parameters_schema")
        assert hasattr(detail, "impact_rules")
        # Story 2.14: rbac_policies removed
        assert not hasattr(detail, "rbac_policies")

    def test_action_detail_includes_execution_steps(self):
        """AC #1: ActionDetail includes execution_steps field (Story 2.2; Story 2.7 connector_type)."""
        step = ExecutionStep(
            order=1,
            name="Verification",
            type=ExecutionStepType.PREREQUISITE,
            connector_type=ConnectorType.NONE,
        )
        detail = ActionDetail(
            id=1,
            name="Test",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DRAFT,
            created_at=datetime(2026, 1, 28),
            execution_steps=[step],
            change_type_config={"PROD": ChangeTypeConfigEntry(required=True, change_model_code="1516B")},
        )
        assert detail.execution_steps is not None
        assert len(detail.execution_steps) == 1
        assert detail.change_type_config is not None
        assert detail.change_type_config["PROD"].required is True
        assert detail.change_type_config["PROD"].change_model_code == "1516B"


# === Story 2.2: Execution Steps and Change Type Models Tests ===


class TestExecutionStepTypeEnum:
    """Tests for ExecutionStepType enum (AC #1)."""

    def test_execution_step_type_values(self):
        """Test ExecutionStepType enum values."""
        assert ExecutionStepType.PREREQUISITE.value == "prerequisite"
        assert ExecutionStepType.EXECUTION.value == "execution"
        assert ExecutionStepType.VERIFICATION.value == "verification"


class TestChangeTypeConfigEntry:
    """Tests for ChangeTypeConfigEntry (Story 2.24). required + change_model_code per env."""

    def test_required_false_no_code(self):
        """required=False, change_model_code optional."""
        e = ChangeTypeConfigEntry(required=False)
        assert e.required is False
        assert e.change_model_code is None

    def test_required_true_with_code(self):
        """required=True with alphanumeric change_model_code."""
        e = ChangeTypeConfigEntry(required=True, change_model_code="1516B")
        assert e.required is True
        assert e.change_model_code == "1516B"

    def test_required_true_without_code_raises(self):
        """required=True without change_model_code raises."""
        with pytest.raises(ValueError, match="change_model_code is required"):
            ChangeTypeConfigEntry(required=True)

    def test_change_model_code_alphanumeric_only(self):
        """change_model_code must be alphanumeric."""
        with pytest.raises(ValueError, match="alphanumeric"):
            ChangeTypeConfigEntry(required=True, change_model_code="1516-B")


class TestConnectorTypeEnum:
    """Tests for ConnectorType enum (Story 2.7, AC1)."""

    def test_connector_type_values(self):
        """Test ConnectorType enum values."""
        assert ConnectorType.AAP.value == "aap"
        assert ConnectorType.SERVICENOW.value == "servicenow"
        assert ConnectorType.AZUREDEVOPS.value == "azuredevops"
        assert ConnectorType.JIRA.value == "jira"
        assert ConnectorType.GITHUB_ACTIONS.value == "github_actions"
        assert ConnectorType.TERRAFORM.value == "terraform"
        assert ConnectorType.NONE.value == "none"


class TestExecutionStepValidation:
    """Tests for ExecutionStep model validation (AC #1, #2)."""

    def test_valid_execution_step_minimal(self):
        """Test creating step with minimal required fields (Story 2.7: connector_type default)."""
        step = ExecutionStep(
            order=1,
            name="Verification pre-requis",
            type=ExecutionStepType.PREREQUISITE,
        )
        assert step.order == 1
        assert step.name == "Verification pre-requis"
        assert step.type == ExecutionStepType.PREREQUISITE
        assert step.connector_type == ConnectorType.NONE
        assert step.connector_config is None
        assert step.conditional_environments is None

    def test_valid_execution_step_with_servicenow(self):
        """AC #2: Test step with connector_type servicenow and conditional environments (Story 2.7)."""
        step = ExecutionStep(
            order=2,
            name="Ouverture changement ServiceNow",
            type=ExecutionStepType.EXECUTION,
            connector_type=ConnectorType.SERVICENOW,
            connector_config={},
            conditional_environments=["STAGING", "PROD"],
        )
        assert step.connector_type == ConnectorType.SERVICENOW
        assert step.connector_config == {}
        assert step.conditional_environments == ["STAGING", "PROD"]

    def test_step_name_strip_whitespace(self):
        """Test that step name is stripped of whitespace."""
        step = ExecutionStep(
            order=1,
            name="  Verification  ",
            type=ExecutionStepType.PREREQUISITE,
        )
        assert step.name == "Verification"

    def test_step_name_empty_raises_error(self):
        """Test that empty step name raises validation error."""
        with pytest.raises(ValueError):
            ExecutionStep(
                order=1,
                name="",
                type=ExecutionStepType.PREREQUISITE,
            )

    def test_step_name_whitespace_only_raises_error(self):
        """Test that whitespace-only step name raises validation error."""
        with pytest.raises(ValueError):
            ExecutionStep(
                order=1,
                name="   ",
                type=ExecutionStepType.PREREQUISITE,
            )

    def test_step_name_too_long_raises_error(self):
        """Test that step name > 255 chars raises validation error."""
        with pytest.raises(ValueError):
            ExecutionStep(
                order=1,
                name="x" * 256,
                type=ExecutionStepType.PREREQUISITE,
            )

    def test_step_order_must_be_positive(self):
        """Test that order must be >= 1."""
        with pytest.raises(ValueError):
            ExecutionStep(
                order=0,
                name="Test",
                type=ExecutionStepType.PREREQUISITE,
            )

    def test_servicenow_connector_requires_environments(self):
        """AC #2 / Story 2.7: connector_type=servicenow requires conditional_environments."""
        with pytest.raises(ValueError, match="conditional_environments is required"):
            ExecutionStep(
                order=1,
                name="Ouverture changement",
                type=ExecutionStepType.EXECUTION,
                connector_type=ConnectorType.SERVICENOW,
                conditional_environments=None,
            )

    def test_servicenow_connector_empty_environments_raises_error(self):
        """AC #2 / Story 2.7: empty conditional_environments raises error when connector_type=servicenow."""
        with pytest.raises(ValueError, match="conditional_environments is required"):
            ExecutionStep(
                order=1,
                name="Ouverture changement",
                type=ExecutionStepType.EXECUTION,
                connector_type=ConnectorType.SERVICENOW,
                conditional_environments=[],
            )


class TestExecutionStepsUpdateValidation:
    """Tests for ExecutionStepsUpdate model validation (AC #5)."""

    def test_valid_execution_steps_update(self):
        """Test valid ExecutionStepsUpdate with new change_type_config format (Story 2.24)."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
                ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.EXECUTION, connector_type=ConnectorType.NONE),
                ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.VERIFICATION, connector_type=ConnectorType.NONE),
            ],
            change_type_config={
                "DEV": ChangeTypeConfigEntry(required=False),
                "STAGING": ChangeTypeConfigEntry(required=False),
                "PROD": ChangeTypeConfigEntry(required=True, change_model_code="1516B"),
            },
        )
        assert len(update.steps) == 3
        assert update.change_type_config["PROD"].required is True
        assert update.change_type_config["PROD"].change_model_code == "1516B"

    def test_empty_steps_raises_error(self):
        """Test that empty steps list raises validation error."""
        with pytest.raises(ValueError, match="at least one step is required"):
            ExecutionStepsUpdate(steps=[])

    def test_non_sequential_order_raises_error(self):
        """Test that non-sequential order raises validation error."""
        with pytest.raises(ValueError, match="step order must be sequential"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
                    ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.VERIFICATION, connector_type=ConnectorType.NONE),
                ]
            )

    def test_duplicate_order_raises_error(self):
        """Test that duplicate order values raise validation error."""
        with pytest.raises(ValueError, match="order values must be unique"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
                    ExecutionStep(order=1, name="Step 2", type=ExecutionStepType.EXECUTION, connector_type=ConnectorType.NONE),
                ]
            )

    def test_order_not_starting_from_one_raises_error(self):
        """Test that order not starting from 1 raises validation error."""
        with pytest.raises(ValueError, match="step order must be sequential starting from 1"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
                    ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.EXECUTION, connector_type=ConnectorType.NONE),
                ]
            )

    def test_change_type_config_optional(self):
        """AC #3: Test that change_type_config is optional."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
            ],
            change_type_config=None,
        )
        assert update.change_type_config is None

    def test_single_step_valid(self):
        """Test that single step is valid."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Only Step", type=ExecutionStepType.EXECUTION, connector_type=ConnectorType.NONE),
            ],
        )
        assert len(update.steps) == 1

    def test_legacy_change_type_config_string_rejected(self):
        """Story 2.24 AC4: Legacy format (env -> string) rejected with clear message."""
        with pytest.raises(ValueError, match="legacy format"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=1, name="Step", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
                ],
                change_type_config={"PROD": "pre_approved"},
            )


# === Story 2.3: RBAC Policies Models Tests ===


# Story 2.3 RBAC by action model tests removed in Story 2.14 — RBAC now managed via profiles.
# Removed: TestUserProfileEnum, TestEnvironmentPermissionValidation, TestRbacPoliciesValidation, TestRbacPoliciesUpdateValidation


# === Story 2.4: Status Transition and Lifecycle Models Tests ===


class TestStatusTransitionEnum:
    """Tests for StatusTransition enum (Story 2.4, AC #1, #4, #5)."""

    def test_status_transition_values(self):
        """Test StatusTransition enum values."""
        from app.models.catalog import StatusTransition

        assert StatusTransition.PUBLISH.value == "publish"
        assert StatusTransition.DISABLE.value == "disable"
        assert StatusTransition.ENABLE.value == "enable"


class TestStatusUpdateRequestValidation:
    """Tests for StatusUpdateRequest model validation (Story 2.4, AC #5)."""

    def test_valid_status_update_publish(self):
        """Test valid StatusUpdateRequest with publish transition."""
        from app.models.catalog import StatusUpdateRequest, StatusTransition

        request = StatusUpdateRequest(transition=StatusTransition.PUBLISH)
        assert request.transition == StatusTransition.PUBLISH

    def test_valid_status_update_disable(self):
        """Test valid StatusUpdateRequest with disable transition."""
        from app.models.catalog import StatusUpdateRequest, StatusTransition

        request = StatusUpdateRequest(transition=StatusTransition.DISABLE)
        assert request.transition == StatusTransition.DISABLE

    def test_valid_status_update_enable(self):
        """Test valid StatusUpdateRequest with enable transition."""
        from app.models.catalog import StatusUpdateRequest, StatusTransition

        request = StatusUpdateRequest(transition=StatusTransition.ENABLE)
        assert request.transition == StatusTransition.ENABLE


class TestStatusTransitionValidation:
    """Tests for validate_transition function (Story 2.4, AC #1, #4)."""

    def test_valid_transition_draft_to_published(self):
        """Test valid transition: draft -> published (publish)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition

        # Should not raise
        validate_transition(ActionStatus.DRAFT, StatusTransition.PUBLISH)

    def test_valid_transition_published_to_disabled(self):
        """Test valid transition: published -> disabled (disable)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition

        # Should not raise
        validate_transition(ActionStatus.PUBLISHED, StatusTransition.DISABLE)

    def test_valid_transition_disabled_to_published(self):
        """Test valid transition: disabled -> published (enable)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition

        # Should not raise
        validate_transition(ActionStatus.DISABLED, StatusTransition.ENABLE)

    def test_invalid_transition_draft_to_disabled(self):
        """Test invalid transition: draft -> disabled (FORBIDDEN)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition, InvalidTransitionError

        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(ActionStatus.DRAFT, StatusTransition.DISABLE)
        assert "draft" in str(exc_info.value).lower()
        assert "disable" in str(exc_info.value).lower()

    def test_invalid_transition_published_to_draft(self):
        """Test invalid transition: published -> draft (FORBIDDEN, no unpublish)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition, InvalidTransitionError

        # publish on already published is invalid
        with pytest.raises(InvalidTransitionError):
            validate_transition(ActionStatus.PUBLISHED, StatusTransition.PUBLISH)

    def test_invalid_transition_disabled_to_draft(self):
        """Test invalid transition: disabled with publish is valid (enable), but disable again is invalid."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition, InvalidTransitionError

        # disable on disabled is invalid
        with pytest.raises(InvalidTransitionError):
            validate_transition(ActionStatus.DISABLED, StatusTransition.DISABLE)

    def test_invalid_transition_draft_with_enable(self):
        """Test invalid transition: draft with enable (FORBIDDEN)."""
        from app.models.catalog import ActionStatus, StatusTransition, validate_transition, InvalidTransitionError

        with pytest.raises(InvalidTransitionError):
            validate_transition(ActionStatus.DRAFT, StatusTransition.ENABLE)


class TestActionListItemModel:
    """Tests for ActionListItem model (Story 2.4, AC #2)."""

    def test_action_list_item_creation(self):
        """Test ActionListItem model creation with all fields. Story 2.23: category removed."""
        from app.models.catalog import ActionListItem, ActionStatus, ActionEngine

        item = ActionListItem(
            id=1,
            name="Creer PDB Oracle",
            status=ActionStatus.PUBLISHED,
            engine=ActionEngine.ORACLE,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            execution_count=42,
        )
        assert item.id == 1
        assert item.name == "Creer PDB Oracle"
        assert item.status == ActionStatus.PUBLISHED
        assert item.execution_count == 42

    def test_action_list_item_default_execution_count(self):
        """Test ActionListItem with default execution_count of 0."""
        from app.models.catalog import ActionListItem, ActionStatus, ActionEngine

        item = ActionListItem(
            id=1,
            name="Test",
            status=ActionStatus.DRAFT,
            engine=ActionEngine.SQL_SERVER,
            created_at=datetime(2026, 1, 28),
        )
        assert item.execution_count == 0

    def test_action_list_item_default_tags(self):
        """Test ActionListItem with default tags (Story 2.6)."""
        from app.models.catalog import ActionListItem, ActionStatus, ActionEngine

        item = ActionListItem(
            id=1,
            name="Test",
            status=ActionStatus.DRAFT,
            engine=ActionEngine.SQL_SERVER,
            created_at=datetime(2026, 1, 28),
        )
        assert item.tags == []


class TestTagModels:
    """Tests for Tag models (Story 2.6, FR11c)."""

    def test_normalize_tag_name(self):
        """Test normalize_tag_name: lowercase, strip, no spaces."""
        assert normalize_tag_name("RAC") == "rac"
        assert normalize_tag_name("  Data Guard  ") == "dataguard"
        assert normalize_tag_name("provisioning") == "provisioning"
        assert normalize_tag_name("") == ""
        assert normalize_tag_name("   ") == ""

    def test_tag_create_normalizes_name(self):
        """Test TagCreate normalizes name to lowercase, no spaces."""
        tag = TagCreate(name="  RAC  ")
        assert tag.name == "rac"
        tag2 = TagCreate(name="Data Guard")
        assert tag2.name == "dataguard"

    def test_tag_create_empty_raises(self):
        """Test TagCreate with empty or whitespace-only name raises (Pydantic or validator)."""
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            TagCreate(name="")
        with pytest.raises(ValueError, match="cannot be empty"):
            TagCreate(name="   ")

    def test_tag_response(self):
        """Test TagResponse model."""
        tag = TagResponse(
            id=1,
            name="rac",
            created_at=datetime(2026, 1, 28, 12, 0, 0),
        )
        assert tag.id == 1
        assert tag.name == "rac"
        assert tag.created_at.year == 2026


class TestActionTagsUpdateRequest:
    """Tests for ActionTagsUpdateRequest (Story 2.6, AC #5)."""

    def test_tag_ids_only(self):
        """Provide tag_ids only."""
        r = ActionTagsUpdateRequest(tag_ids=[1, 2, 3])
        assert r.tag_ids == [1, 2, 3]
        assert r.tag_names is None

    def test_tag_names_only(self):
        """Provide tag_names only; normalizes to lowercase, no spaces."""
        r = ActionTagsUpdateRequest(tag_names=["RAC", "Data Guard"])
        assert r.tag_names == ["rac", "dataguard"]
        assert r.tag_ids is None

    def test_tag_ids_empty_allowed(self):
        """tag_ids=[] allowed (clear all tags)."""
        r = ActionTagsUpdateRequest(tag_ids=[])
        assert r.tag_ids == []

    def test_tag_names_empty_allowed(self):
        """tag_names=[] allowed (clear all tags)."""
        r = ActionTagsUpdateRequest(tag_names=[])
        assert r.tag_names == []

    def test_both_none_raises(self):
        """Both tag_ids and tag_names None raises."""
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            ActionTagsUpdateRequest()

    def test_both_provided_raises(self):
        """Providing both tag_ids and tag_names raises (mutual exclusivity)."""
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)) as exc_info:
            ActionTagsUpdateRequest(tag_ids=[1, 2], tag_names=["rac", "dataguard"])
        assert "not both" in str(exc_info.value).lower()


# === Story 2.24: ChangeTypeConfigEntry (replaces action-level change_model_code) ===
# ChangeTypeConfigEntry validation covered in TestChangeTypeConfigEntry above.
# ActionCreate no longer has change_model_code; change_type_config is in ExecutionStepsUpdate only.


# === Story 9.1: Remediation Rules Models Tests ===


class TestRiskLevelEnum:
    """Tests for RiskLevel enum (Story 9.1, AC4)."""

    def test_risk_level_values(self):
        """Test RiskLevel enum values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"


class TestRemediationRuleValidation:
    """Tests for RemediationRule model validation (Story 9.1, AC4)."""

    def test_valid_remediation_rule_minimal(self):
        """Test creating remediation rule with minimal required fields."""
        rule = RemediationRule(
            error_pattern="ORA-\\d+",
            target_action_id=42,
            environments=["dev", "prod"],
        )
        assert rule.error_pattern == "ORA-\\d+"
        assert rule.target_action_id == 42
        assert rule.environments == ["dev", "prod"]
        assert rule.auto_trigger is False
        assert rule.risk_level == RiskLevel.MEDIUM

    def test_valid_remediation_rule_full(self):
        """Test creating remediation rule with all fields."""
        rule = RemediationRule(
            error_pattern="timeout|connection refused",
            target_action_id=123,
            environments=["staging", "prod"],
            auto_trigger=True,
            risk_level=RiskLevel.HIGH,
        )
        assert rule.error_pattern == "timeout|connection refused"
        assert rule.target_action_id == 123
        assert rule.auto_trigger is True
        assert rule.risk_level == RiskLevel.HIGH

    def test_error_pattern_empty_raises_error(self):
        """Test that empty error_pattern raises validation error."""
        with pytest.raises(ValueError):
            RemediationRule(
                error_pattern="",
                target_action_id=42,
                environments=["dev"],
            )

    def test_error_pattern_too_long_raises_error(self):
        """Test that error_pattern > 1000 chars raises validation error."""
        with pytest.raises(ValueError):
            RemediationRule(
                error_pattern="x" * 1001,
                target_action_id=42,
                environments=["dev"],
            )

    def test_error_pattern_invalid_regex_raises_error(self):
        """Test that invalid regex pattern raises validation error."""
        with pytest.raises(ValueError, match="not a valid regex"):
            RemediationRule(
                error_pattern="[invalid(regex",
                target_action_id=42,
                environments=["dev"],
            )

    def test_target_action_id_zero_raises_error(self):
        """Test that target_action_id <= 0 raises validation error."""
        with pytest.raises(ValueError):
            RemediationRule(
                error_pattern="ORA-\\d+",
                target_action_id=0,
                environments=["dev"],
            )

    def test_target_action_id_negative_raises_error(self):
        """Test that negative target_action_id raises validation error."""
        with pytest.raises(ValueError):
            RemediationRule(
                error_pattern="ORA-\\d+",
                target_action_id=-1,
                environments=["dev"],
            )

    def test_environments_empty_raises_error(self):
        """Test that empty environments list raises validation error."""
        with pytest.raises(ValueError):
            RemediationRule(
                error_pattern="ORA-\\d+",
                target_action_id=42,
                environments=[],
            )


class TestRemediationSuggestionModel:
    """Tests for RemediationSuggestion model (Story 9.1, AC5)."""

    def test_remediation_suggestion_creation(self):
        """Test RemediationSuggestion model creation."""
        rule = RemediationRule(
            error_pattern="ORA-\\d+",
            target_action_id=42,
            environments=["dev"],
        )
        suggestion = RemediationSuggestion(
            action_id=42,
            action_name="Restart Database Listener",
            action_description="Restarts the Oracle database listener service",
            matching_rule=rule,
        )
        assert suggestion.action_id == 42
        assert suggestion.action_name == "Restart Database Listener"
        assert suggestion.action_description == "Restarts the Oracle database listener service"
        assert suggestion.matching_rule == rule

    def test_remediation_suggestion_optional_description(self):
        """Test RemediationSuggestion with null description."""
        rule = RemediationRule(
            error_pattern="timeout",
            target_action_id=10,
            environments=["staging"],
        )
        suggestion = RemediationSuggestion(
            action_id=10,
            action_name="Retry Action",
            matching_rule=rule,
        )
        assert suggestion.action_description is None


class TestRemediationRulesUpdateRequest:
    """Tests for RemediationRulesUpdateRequest model (Story 9.1, Task 6)."""

    def test_valid_update_with_rules(self):
        """Test valid update with remediation rules."""
        request = RemediationRulesUpdateRequest(
            remediation_rules=[
                RemediationRule(
                    error_pattern="ORA-\\d+",
                    target_action_id=42,
                    environments=["dev", "prod"],
                ),
                RemediationRule(
                    error_pattern="timeout",
                    target_action_id=10,
                    environments=["staging"],
                    risk_level=RiskLevel.LOW,
                ),
            ]
        )
        assert len(request.remediation_rules) == 2

    def test_valid_update_null_clears_rules(self):
        """Test that null remediation_rules clears all rules."""
        request = RemediationRulesUpdateRequest(remediation_rules=None)
        assert request.remediation_rules is None

    def test_valid_update_empty_list_clears_rules(self):
        """Test that empty list is allowed (clear all rules)."""
        request = RemediationRulesUpdateRequest(remediation_rules=[])
        assert request.remediation_rules == []
