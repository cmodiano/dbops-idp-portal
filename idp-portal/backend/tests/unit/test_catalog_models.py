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
    ActionCategory,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionCreate,
    ActionResponse,
    ActionDetail,
    ExecutionStepType,
    ExecutionStep,
    ChangeType,
    ExecutionStepsUpdate,
)


class TestActionCreateValidation:
    """Tests for ActionCreate model validation."""

    def test_valid_action_minimal(self):
        """Test creating action with minimal required fields."""
        action = ActionCreate(
            name="Create PDB",
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert action.name == "Create PDB"
        assert action.category == ActionCategory.PROVISIONING
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
            category=ActionCategory.PATCHING,
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
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
        )
        assert action.name == "Create PDB"

    def test_name_empty_raises_error(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="",
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_whitespace_only_raises_error(self):
        """Test that whitespace-only name raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="   ",
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_too_long_raises_error(self):
        """Test that name > 255 chars raises validation error."""
        with pytest.raises(ValueError):
            ActionCreate(
                name="x" * 256,
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_name_max_length_valid(self):
        """Test that name at 255 chars is valid."""
        action = ActionCreate(
            name="x" * 255,
            category=ActionCategory.PROVISIONING,
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
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
            )

    def test_description_max_length_valid(self):
        """Test that description at 4000 chars is valid."""
        action = ActionCreate(
            name="Test Action",
            description="x" * 4000,
            category=ActionCategory.PROVISIONING,
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
            category=ActionCategory.PROVISIONING,
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
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema={"type": "object"},
        )
        assert action.parameters_schema == {"type": "object"}

    def test_none_parameters_schema_valid(self):
        """Test None parameters_schema is valid."""
        action = ActionCreate(
            name="Test",
            category=ActionCategory.PROVISIONING,
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
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                parameters_schema={"foo": "bar", "baz": 123},
            )

    def test_empty_dict_parameters_schema_invalid(self):
        """Test empty dict is invalid (no recognized keys)."""
        with pytest.raises(ValueError, match="valid JSON Schema"):
            ActionCreate(
                name="Test",
                category=ActionCategory.PROVISIONING,
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
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            impact_rules={"DEV": {"level": "low"}},
        )
        assert action.impact_rules == {"DEV": {"level": "low"}}

    def test_valid_impact_rules_multiple_envs(self):
        """Test valid impact rules with multiple environments."""
        action = ActionCreate(
            name="Test",
            category=ActionCategory.PROVISIONING,
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
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"ENV": {"level": level}},
            )
            assert action.impact_rules["ENV"]["level"] == level

    def test_none_impact_rules_valid(self):
        """Test None impact_rules is valid."""
        action = ActionCreate(
            name="Test",
            category=ActionCategory.PROVISIONING,
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
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": {"level": "invalid"}},
            )

    def test_missing_level_key(self):
        """Test missing 'level' key raises error."""
        with pytest.raises(ValueError, match="must have a 'level' key"):
            ActionCreate(
                name="Test",
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": {"severity": "high"}},
            )

    def test_env_value_not_dict(self):
        """Test non-dict environment value raises error."""
        with pytest.raises(ValueError, match="must be an object"):
            ActionCreate(
                name="Test",
                category=ActionCategory.PROVISIONING,
                engine=ActionEngine.ORACLE,
                platform=ActionPlatform.AAP,
                impact_rules={"DEV": "low"},
            )


class TestActionEnums:
    """Tests for action enums."""

    def test_action_category_values(self):
        """Test ActionCategory enum values."""
        assert ActionCategory.PROVISIONING.value == "Provisioning"
        assert ActionCategory.PATCHING.value == "Patching"
        assert ActionCategory.ADMINISTRATION.value == "Administration"
        assert ActionCategory.MONITORING.value == "Monitoring"

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
            category=ActionCategory.PROVISIONING,
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
    """Tests for ActionDetail model."""

    def test_action_detail_includes_rbac(self):
        """Test ActionDetail includes rbac_policies."""
        detail = ActionDetail(
            id=1,
            name="Test Action",
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DRAFT,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            rbac_policies={"DBOPS": {"DEV": True, "PROD": True}},
        )
        assert detail.rbac_policies == {"DBOPS": {"DEV": True, "PROD": True}}

    def test_action_detail_inherits_from_response(self):
        """Test ActionDetail inherits all ActionResponse fields."""
        detail = ActionDetail(
            id=1,
            name="Test",
            category=ActionCategory.PROVISIONING,
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
        assert hasattr(detail, "rbac_policies")

    def test_action_detail_includes_execution_steps(self):
        """AC #1: ActionDetail includes execution_steps field (Story 2.2)."""
        step = ExecutionStep(
            order=1,
            name="Verification",
            type=ExecutionStepType.PREREQUISITE,
            is_servicenow_change=False,
        )
        detail = ActionDetail(
            id=1,
            name="Test",
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DRAFT,
            created_at=datetime(2026, 1, 28),
            execution_steps=[step],
            change_type_config={"PROD": ChangeType.CAB},
        )
        assert detail.execution_steps is not None
        assert len(detail.execution_steps) == 1
        assert detail.change_type_config == {"PROD": ChangeType.CAB}


# === Story 2.2: Execution Steps and Change Type Models Tests ===


class TestExecutionStepTypeEnum:
    """Tests for ExecutionStepType enum (AC #1)."""

    def test_execution_step_type_values(self):
        """Test ExecutionStepType enum values."""
        assert ExecutionStepType.PREREQUISITE.value == "prerequisite"
        assert ExecutionStepType.EXECUTION.value == "execution"
        assert ExecutionStepType.VERIFICATION.value == "verification"


class TestChangeTypeEnum:
    """Tests for ChangeType enum (AC #3)."""

    def test_change_type_values(self):
        """Test ChangeType enum values."""
        assert ChangeType.PRE_APPROVED.value == "pre_approved"
        assert ChangeType.CAB.value == "cab"


class TestExecutionStepValidation:
    """Tests for ExecutionStep model validation (AC #1, #2)."""

    def test_valid_execution_step_minimal(self):
        """Test creating step with minimal required fields."""
        step = ExecutionStep(
            order=1,
            name="Verification pre-requis",
            type=ExecutionStepType.PREREQUISITE,
        )
        assert step.order == 1
        assert step.name == "Verification pre-requis"
        assert step.type == ExecutionStepType.PREREQUISITE
        assert step.is_servicenow_change is False
        assert step.conditional_environments is None

    def test_valid_execution_step_with_servicenow(self):
        """AC #2: Test step with ServiceNow change and conditional environments."""
        step = ExecutionStep(
            order=2,
            name="Ouverture changement ServiceNow",
            type=ExecutionStepType.EXECUTION,
            is_servicenow_change=True,
            conditional_environments=["STAGING", "PROD"],
        )
        assert step.is_servicenow_change is True
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

    def test_servicenow_change_requires_environments(self):
        """AC #2: Test that is_servicenow_change=True requires conditional_environments."""
        with pytest.raises(ValueError, match="conditional_environments is required"):
            ExecutionStep(
                order=1,
                name="Ouverture changement",
                type=ExecutionStepType.EXECUTION,
                is_servicenow_change=True,
                conditional_environments=None,
            )

    def test_servicenow_change_empty_environments_raises_error(self):
        """AC #2: Test that empty conditional_environments raises error when servicenow_change=True."""
        with pytest.raises(ValueError, match="conditional_environments is required"):
            ExecutionStep(
                order=1,
                name="Ouverture changement",
                type=ExecutionStepType.EXECUTION,
                is_servicenow_change=True,
                conditional_environments=[],
            )


class TestExecutionStepsUpdateValidation:
    """Tests for ExecutionStepsUpdate model validation (AC #5)."""

    def test_valid_execution_steps_update(self):
        """Test valid ExecutionStepsUpdate with sequential order."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE),
                ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.EXECUTION),
                ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.VERIFICATION),
            ],
            change_type_config={
                "DEV": ChangeType.PRE_APPROVED,
                "STAGING": ChangeType.PRE_APPROVED,
                "PROD": ChangeType.CAB,
            },
        )
        assert len(update.steps) == 3
        assert update.change_type_config["PROD"] == ChangeType.CAB

    def test_empty_steps_raises_error(self):
        """Test that empty steps list raises validation error."""
        with pytest.raises(ValueError, match="at least one step is required"):
            ExecutionStepsUpdate(steps=[])

    def test_non_sequential_order_raises_error(self):
        """Test that non-sequential order raises validation error."""
        with pytest.raises(ValueError, match="step order must be sequential"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE),
                    ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.VERIFICATION),
                ]
            )

    def test_duplicate_order_raises_error(self):
        """Test that duplicate order values raise validation error."""
        with pytest.raises(ValueError, match="order values must be unique"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE),
                    ExecutionStep(order=1, name="Step 2", type=ExecutionStepType.EXECUTION),
                ]
            )

    def test_order_not_starting_from_one_raises_error(self):
        """Test that order not starting from 1 raises validation error."""
        with pytest.raises(ValueError, match="step order must be sequential starting from 1"):
            ExecutionStepsUpdate(
                steps=[
                    ExecutionStep(order=2, name="Step 2", type=ExecutionStepType.PREREQUISITE),
                    ExecutionStep(order=3, name="Step 3", type=ExecutionStepType.EXECUTION),
                ]
            )

    def test_change_type_config_optional(self):
        """AC #3: Test that change_type_config is optional."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Step 1", type=ExecutionStepType.PREREQUISITE),
            ],
            change_type_config=None,
        )
        assert update.change_type_config is None

    def test_single_step_valid(self):
        """Test that single step is valid."""
        update = ExecutionStepsUpdate(
            steps=[
                ExecutionStep(order=1, name="Only Step", type=ExecutionStepType.EXECUTION),
            ],
        )
        assert len(update.steps) == 1


# === Story 2.3: RBAC Policies Models Tests ===


class TestUserProfileEnum:
    """Tests for UserProfile enum (Story 2.3, AC #1)."""

    def test_user_profile_values(self):
        """Test UserProfile enum values."""
        from app.models.catalog import UserProfile

        assert UserProfile.DBA_APPLICATIF.value == "dba_applicatif"
        assert UserProfile.DBA_INFRASTRUCTURE.value == "dba_infrastructure"
        assert UserProfile.CLIENT_BUSINESS.value == "client_business"
        assert UserProfile.DBOPS.value == "dbops"


class TestEnvironmentPermissionValidation:
    """Tests for EnvironmentPermission model validation (Story 2.3, AC #1, #2)."""

    def test_valid_environment_permission_minimal(self):
        """Test creating permission with minimal required fields."""
        from app.models.catalog import EnvironmentPermission, UserProfile

        perm = EnvironmentPermission(
            profiles=[UserProfile.DBA_APPLICATIF],
            requires_approval=False,
        )
        assert perm.profiles == [UserProfile.DBA_APPLICATIF]
        assert perm.requires_approval is False
        assert perm.approver_profiles is None

    def test_valid_environment_permission_with_approval(self):
        """AC #2: Test permission with approval requirement."""
        from app.models.catalog import EnvironmentPermission, UserProfile

        perm = EnvironmentPermission(
            profiles=[UserProfile.DBA_APPLICATIF, UserProfile.DBA_INFRASTRUCTURE],
            requires_approval=True,
            approver_profiles=[UserProfile.DBA_INFRASTRUCTURE],
        )
        assert perm.requires_approval is True
        assert perm.approver_profiles == [UserProfile.DBA_INFRASTRUCTURE]

    def test_empty_profiles_raises_error(self):
        """AC #1: Test that empty profiles list raises validation error."""
        from app.models.catalog import EnvironmentPermission

        with pytest.raises(ValueError, match="at least one profile"):
            EnvironmentPermission(
                profiles=[],
                requires_approval=False,
            )

    def test_approval_requires_approver_profiles(self):
        """AC #2: Test that requires_approval=True requires approver_profiles."""
        from app.models.catalog import EnvironmentPermission, UserProfile

        with pytest.raises(ValueError, match="approver_profiles.*required"):
            EnvironmentPermission(
                profiles=[UserProfile.DBA_APPLICATIF],
                requires_approval=True,
                approver_profiles=None,
            )

    def test_approval_empty_approver_profiles_raises_error(self):
        """AC #2: Test that empty approver_profiles raises error when requires_approval=True."""
        from app.models.catalog import EnvironmentPermission, UserProfile

        with pytest.raises(ValueError, match="approver_profiles.*required"):
            EnvironmentPermission(
                profiles=[UserProfile.DBA_APPLICATIF],
                requires_approval=True,
                approver_profiles=[],
            )

    def test_no_approval_allows_none_approver_profiles(self):
        """Test that requires_approval=False allows None approver_profiles."""
        from app.models.catalog import EnvironmentPermission, UserProfile

        perm = EnvironmentPermission(
            profiles=[UserProfile.DBA_APPLICATIF],
            requires_approval=False,
            approver_profiles=None,
        )
        assert perm.approver_profiles is None


class TestRbacPoliciesValidation:
    """Tests for RbacPolicies model validation (Story 2.3, AC #1, #2)."""

    def test_valid_rbac_policies_all_envs(self):
        """Test valid RBAC policies with all environments."""
        from app.models.catalog import RbacPolicies, EnvironmentPermission, UserProfile

        policies = RbacPolicies(
            environments={
                "DEV": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF, UserProfile.DBA_INFRASTRUCTURE, UserProfile.CLIENT_BUSINESS],
                    requires_approval=False,
                ),
                "STAGING": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF, UserProfile.DBA_INFRASTRUCTURE],
                    requires_approval=False,
                ),
                "PROD": EnvironmentPermission(
                    profiles=[UserProfile.DBA_APPLICATIF, UserProfile.DBA_INFRASTRUCTURE],
                    requires_approval=True,
                    approver_profiles=[UserProfile.DBA_INFRASTRUCTURE],
                ),
            }
        )
        assert len(policies.environments) == 3
        assert policies.environments["PROD"].requires_approval is True

    def test_valid_rbac_policies_single_env(self):
        """Test valid RBAC policies with single environment."""
        from app.models.catalog import RbacPolicies, EnvironmentPermission, UserProfile

        policies = RbacPolicies(
            environments={
                "DEV": EnvironmentPermission(
                    profiles=[UserProfile.CLIENT_BUSINESS],
                    requires_approval=False,
                ),
            }
        )
        assert len(policies.environments) == 1


class TestRbacPoliciesUpdateValidation:
    """Tests for RbacPoliciesUpdate model validation (Story 2.3, AC #4)."""

    def test_valid_rbac_policies_update(self):
        """Test valid RbacPoliciesUpdate."""
        from app.models.catalog import RbacPoliciesUpdate, RbacPolicies, EnvironmentPermission, UserProfile

        update = RbacPoliciesUpdate(
            policies=RbacPolicies(
                environments={
                    "DEV": EnvironmentPermission(
                        profiles=[UserProfile.DBA_APPLICATIF],
                        requires_approval=False,
                    ),
                }
            )
        )
        assert update.policies is not None
        assert "DEV" in update.policies.environments


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
        """Test ActionListItem model creation with all fields."""
        from app.models.catalog import ActionListItem, ActionStatus, ActionCategory, ActionEngine

        item = ActionListItem(
            id=1,
            name="Creer PDB Oracle",
            status=ActionStatus.PUBLISHED,
            category=ActionCategory.PROVISIONING,
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
        from app.models.catalog import ActionListItem, ActionStatus, ActionCategory, ActionEngine

        item = ActionListItem(
            id=1,
            name="Test",
            status=ActionStatus.DRAFT,
            category=ActionCategory.ADMINISTRATION,
            engine=ActionEngine.SQL_SERVER,
            created_at=datetime(2026, 1, 28),
        )
        assert item.execution_count == 0
