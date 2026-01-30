"""Tests for execution models (Story 4.1, Task 8.1).

Tests Pydantic model validation for:
- ExecutionCreate: input validation
- ExecutionEnvironment: enum values
- ExecutionStatus: enum values
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.execution import (
    ExecutionCreate,
    ExecutionEnvironment,
    ExecutionStatus,
    ExecutionResponse,
    ExecutionCreateResponse,
)


class TestExecutionEnvironment:
    """Tests for ExecutionEnvironment enum."""

    def test_valid_environments(self):
        """ExecutionEnvironment accepts dev, staging, prod."""
        assert ExecutionEnvironment.DEV.value == "dev"
        assert ExecutionEnvironment.STAGING.value == "staging"
        assert ExecutionEnvironment.PROD.value == "prod"

    def test_environment_from_string(self):
        """ExecutionEnvironment can be created from string."""
        assert ExecutionEnvironment("dev") == ExecutionEnvironment.DEV
        assert ExecutionEnvironment("staging") == ExecutionEnvironment.STAGING
        assert ExecutionEnvironment("prod") == ExecutionEnvironment.PROD

    def test_invalid_environment_raises(self):
        """ExecutionEnvironment rejects invalid values."""
        with pytest.raises(ValueError):
            ExecutionEnvironment("invalid")


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_all_statuses_exist(self):
        """ExecutionStatus has all expected values."""
        expected = {"SUBMITTED", "PENDING_APPROVAL", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected


class TestExecutionCreate:
    """Tests for ExecutionCreate model (Task 1.1)."""

    def test_valid_execution_create(self):
        """ExecutionCreate accepts valid input."""
        data = {
            "action_id": 1,
            "environment": "dev",
            "parameters": {"pdb_name": "TEST"},
        }
        model = ExecutionCreate(**data)
        assert model.action_id == 1
        assert model.environment == ExecutionEnvironment.DEV
        assert model.parameters == {"pdb_name": "TEST"}

    def test_execution_create_requires_action_id(self):
        """ExecutionCreate requires action_id."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionCreate(environment="dev", parameters={})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("action_id",) for e in errors)

    def test_execution_create_requires_environment(self):
        """ExecutionCreate requires environment."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionCreate(action_id=1, parameters={})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("environment",) for e in errors)

    def test_execution_create_action_id_must_be_positive(self):
        """ExecutionCreate rejects action_id <= 0."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionCreate(action_id=0, environment="dev", parameters={})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("action_id",) for e in errors)

        with pytest.raises(ValidationError) as exc_info:
            ExecutionCreate(action_id=-1, environment="dev", parameters={})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("action_id",) for e in errors)

    def test_execution_create_invalid_environment(self):
        """ExecutionCreate rejects invalid environment."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionCreate(action_id=1, environment="production", parameters={})
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("environment",) for e in errors)

    def test_execution_create_parameters_optional(self):
        """ExecutionCreate allows None parameters."""
        model = ExecutionCreate(action_id=1, environment="dev", parameters=None)
        assert model.parameters is None

    def test_execution_create_parameters_defaults_to_none(self):
        """ExecutionCreate defaults parameters to None when not provided."""
        model = ExecutionCreate(action_id=1, environment="dev")
        assert model.parameters is None

    def test_execution_create_accepts_nested_parameters(self):
        """ExecutionCreate accepts nested dict parameters."""
        params = {
            "pdb_name": "TEST",
            "options": {
                "size_gb": 10,
                "tablespaces": ["USERS", "DATA"],
            },
        }
        model = ExecutionCreate(action_id=1, environment="dev", parameters=params)
        assert model.parameters == params


class TestExecutionResponse:
    """Tests for ExecutionResponse model."""

    def test_execution_response_all_fields(self):
        """ExecutionResponse accepts all fields."""
        response = ExecutionResponse(
            id=1,
            action_id=5,
            action_name="Create PDB",
            user_id=10,
            environment=ExecutionEnvironment.PROD,
            parameters={"key": "value"},
            status=ExecutionStatus.RUNNING,
            servicenow_change_id="CHG0012345",
            started_at=datetime(2026, 1, 29, 10, 0, 0),
            completed_at=None,
            created_at=datetime(2026, 1, 29, 9, 0, 0),
        )
        assert response.id == 1
        assert response.action_name == "Create PDB"
        assert response.status == ExecutionStatus.RUNNING
        assert response.servicenow_change_id == "CHG0012345"

    def test_execution_response_optional_fields(self):
        """ExecutionResponse allows optional fields to be None."""
        response = ExecutionResponse(
            id=1,
            action_id=5,
            user_id=10,
            environment=ExecutionEnvironment.DEV,
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29),
        )
        assert response.action_name is None
        assert response.parameters is None
        assert response.servicenow_change_id is None
        assert response.started_at is None
        assert response.completed_at is None


class TestExecutionCreateResponse:
    """Tests for ExecutionCreateResponse model."""

    def test_create_response_has_required_fields(self):
        """ExecutionCreateResponse has execution_id, status, created_at."""
        response = ExecutionCreateResponse(
            execution_id=42,
            status=ExecutionStatus.SUBMITTED,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        assert response.execution_id == 42
        assert response.status == ExecutionStatus.SUBMITTED
        assert response.created_at == datetime(2026, 1, 29, 10, 0, 0)
