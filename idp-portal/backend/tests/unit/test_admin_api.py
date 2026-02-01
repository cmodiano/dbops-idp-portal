"""Tests for admin API endpoints (Story 2.1, AC #5).

Tests:
- POST /api/v1/admin/actions - create action (201, 422, 403)
- GET /api/v1/admin/actions - list actions
- GET /api/v1/admin/actions/{id} - get action (200, 404)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.core.security import create_access_token
from app.models.catalog import (
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionResponse,
    ActionDetail,
    ActionListItem,
    ConnectorType,
    ExecutionStep,
    ExecutionStepType,
    ChangeTypeConfigEntry,
    StatusTransition,
    ActionListResponse,
    TagResponse,
)
from app.repositories.catalog_repository import InvalidStateError as RepoInvalidStateError


@pytest.fixture
def client():
    """Async test client for FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def dbops_token():
    """JWT token for DBOPS user."""
    return create_access_token({"sub": "1", "username": "dbops-user", "profile": "dbops"})


@pytest.fixture
def dba_token():
    """JWT token for DBA user (non-DBOPS)."""
    return create_access_token({"sub": "2", "username": "dba-user", "profile": "dba_app"})


@pytest.fixture
def sample_action_response():
    """Sample ActionResponse for mocked repository. Story 2.24: change_model_code removed."""
    return ActionResponse(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        default_impact_level=None,
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
    )


@pytest.fixture
def sample_action_detail():
    """Sample ActionDetail for mocked repository. Story 2.14: rbac_policies removed."""
    return ActionDetail(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        default_impact_level=None,
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
    )


@pytest.fixture
def sample_action_detail_with_steps():
    """Sample ActionDetail with execution_steps and change_type_config. Story 2.14: rbac_policies removed."""
    return ActionDetail(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        default_impact_level=None,
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=datetime(2026, 1, 28, 11, 0, 0),
        execution_steps=[
            ExecutionStep(order=1, name="Verification", type=ExecutionStepType.PREREQUISITE, connector_type=ConnectorType.NONE),
        ],
        change_type_config={
            "DEV": ChangeTypeConfigEntry(required=False),
            "PROD": ChangeTypeConfigEntry(required=True, change_model_code="1516B"),
        },
    )


class TestCreateAction:
    """Tests for POST /api/v1/admin/actions."""

    async def test_create_action_success(self, client, dbops_token, sample_action_response):
        """Test creating action returns 201."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = sample_action_response

            response = await client.post(
                "/api/v1/admin/actions",
                json={
                    "name": "Create PDB Oracle",
                    "description": "Creates a Pluggable Database",
                    "engine": "Oracle",
                    "platform": "AAP",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "Create PDB Oracle"
        assert data["data"]["status"] == "draft"

    async def test_create_action_with_json_fields(self, client, dbops_token, sample_action_response):
        """Test creating action with parameters_schema and impact_rules."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = sample_action_response

            response = await client.post(
                "/api/v1/admin/actions",
                json={
                    "name": "Create PDB Oracle",
                    "engine": "Oracle",
                    "platform": "AAP",
                    "parameters_schema": {"type": "object", "properties": {}},
                    "impact_rules": {"DEV": {"level": "low"}},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_action_validation_error_empty_name(self, client, dbops_token):
        """Test creating action with empty name returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/actions",
                json={
                    "name": "",
                    "engine": "Oracle",
                    "platform": "AAP",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_action_validation_error_missing_field(self, client, dbops_token):
        """Test creating action with missing required field returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/actions",
                json={
                    "name": "Test",
                    # missing engine, platform
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_action_forbidden_non_dbops(self, client, dba_token):
        """Test creating action with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.post(
                "/api/v1/admin/actions",
                json={
                    "name": "Test",
                    "engine": "Oracle",
                    "platform": "AAP",
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestListActions:
    """Tests for GET /api/v1/admin/actions (Story 2.4, AC #2)."""

    @pytest.fixture
    def sample_action_list_items(self):
        """Sample ActionListItem list for admin dashboard."""
        return [
            ActionListItem(
                id=1,
                name="Draft Action",
                status=ActionStatus.DRAFT,
                    engine=ActionEngine.ORACLE,
                created_at=datetime(2026, 1, 28, 10, 0, 0),
                execution_count=0,
            ),
            ActionListItem(
                id=2,
                name="Published Action",
                status=ActionStatus.PUBLISHED,
                engine=ActionEngine.SQL_SERVER,
                created_at=datetime(2026, 1, 27, 10, 0, 0),
                execution_count=42,
            ),
        ]

    async def test_list_actions_success(self, client, dbops_token, sample_action_list_items):
        """Test listing actions returns list with execution counts and pagination."""
        from app.models.catalog import PaginationInfo

        pagination = PaginationInfo(page=1, page_size=25, total_count=2, total_pages=1)
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all_admin", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = (sample_action_list_items, pagination)

            response = await client.get(
                "/api/v1/admin/actions",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) == 2
        assert data["data"][1]["execution_count"] == 42
        assert data["pagination"]["total_count"] == 2

    async def test_list_actions_with_status_filter(self, client, dbops_token, sample_action_list_items):
        """Test listing actions with status filter."""
        from app.models.catalog import PaginationInfo

        pagination = PaginationInfo(page=1, page_size=25, total_count=1, total_pages=1)
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all_admin", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = ([sample_action_list_items[0]], pagination)  # Only draft

            response = await client.get(
                "/api/v1/admin/actions?status=draft",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(status=ActionStatus.DRAFT, engine=None, item_type=None, page=1, page_size=25)

    async def test_list_actions_empty(self, client, dbops_token):
        """Test listing actions when none exist."""
        from app.models.catalog import PaginationInfo

        pagination = PaginationInfo(page=1, page_size=25, total_count=0, total_pages=0)
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all_admin", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = ([], pagination)

            response = await client.get(
                "/api/v1/admin/actions",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []

    async def test_list_actions_forbidden_non_dbops(self, client, dba_token):
        """Test listing actions with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.get(
                "/api/v1/admin/actions",
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_list_actions_invalid_page_rejected(self, client, dbops_token):
        """Test page=0 or negative returns 422 (avoids negative offset in repository)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            for invalid_page in (0, -1):
                response = await client.get(
                    f"/api/v1/admin/actions?page={invalid_page}",
                    headers={"Authorization": f"Bearer {dbops_token}"},
                )
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_list_actions_invalid_page_size_rejected(self, client, dbops_token):
        """Test page_size=0 or negative returns 422 (avoids ZeroDivisionError in repository)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            for invalid_size in (0, -1):
                response = await client.get(
                    f"/api/v1/admin/actions?page_size={invalid_size}",
                    headers={"Authorization": f"Bearer {dbops_token}"},
                )
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetAction:
    """Tests for GET /api/v1/admin/actions/{id}."""

    async def test_get_action_success(self, client, dbops_token, sample_action_detail):
        """Test getting action by ID returns detail."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_action_detail

            response = await client.get(
                "/api/v1/admin/actions/1",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        # Story 2.14: rbac_policies removed — RBAC now managed via profiles
        assert "rbac_policies" not in data["data"]

    async def test_get_action_not_found(self, client, dbops_token):
        """Test getting non-existent action returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None

            response = await client.get(
                "/api/v1/admin/actions/999",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "introuvable" in data["error"]["message"]

    async def test_get_action_forbidden_non_dbops(self, client, dba_token):
        """Test getting action with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.get(
                "/api/v1/admin/actions/1",
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# === Story 2.2: PUT /admin/actions/{id}/steps Tests ===


class TestUpdateActionSteps:
    """Tests for PUT /api/v1/admin/actions/{id}/steps (Story 2.2, AC #5)."""

    async def test_update_steps_success(self, client, dbops_token, sample_action_detail_with_steps):
        """Test updating execution steps returns 200."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_execution_steps", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = sample_action_detail_with_steps

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [
                        {"order": 1, "name": "Verification", "type": "prerequisite", "connector_type": "none"}
                    ],
                    "change_type_config": {"DEV": {"required": False}, "PROD": {"required": True, "change_model_code": "1516B"}},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["execution_steps"] is not None
        assert data["data"]["change_type_config"] is not None

    async def test_update_steps_with_servicenow_and_environments_success(
        self, client, dbops_token, sample_action_detail_with_steps
    ):
        """Story 2.7, AC2/AC4: PUT steps with connector_type servicenow and conditional_environments returns 200."""
        step_sn = ExecutionStep(
            order=1,
            name="Ouverture changement",
            type=ExecutionStepType.EXECUTION,
            connector_type=ConnectorType.SERVICENOW,
            connector_config={},
            conditional_environments=["PROD"],
        )
        detail_with_sn = sample_action_detail_with_steps.model_copy(update={"execution_steps": [step_sn]})
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_execution_steps", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = detail_with_sn

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [
                        {
                            "order": 1,
                            "name": "Ouverture changement",
                            "type": "execution",
                            "connector_type": "servicenow",
                            "connector_config": {},
                            "conditional_environments": ["PROD"],
                        }
                    ],
                    "change_type_config": {"PROD": {"required": False}},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["execution_steps"][0]["connector_type"] == "servicenow"
        assert data["data"]["execution_steps"][0]["conditional_environments"] == ["PROD"]

    async def test_update_steps_servicenow_without_conditional_environments_returns_422(
        self, client, dbops_token
    ):
        """Story 2.7, AC2: PUT steps with connector_type servicenow and no conditional_environments returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [
                        {
                            "order": 1,
                            "name": "Ouverture changement",
                            "type": "execution",
                            "connector_type": "servicenow",
                            "connector_config": None,
                            "conditional_environments": None,
                        }
                    ],
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_update_steps_change_type_config_legacy_format_rejected_422(self, client, dbops_token):
        """Story 2.24 AC4: PUT steps with legacy change_type_config (env -> string) returns 422 with explicit message."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [{"order": 1, "name": "Step", "type": "prerequisite", "connector_type": "none"}],
                    "change_type_config": {"DEV": "pre_approved", "PROD": "pre_approved"},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        detail_str = str(body.get("detail", []))
        assert "legacy" in detail_str.lower() or "new format" in detail_str.lower() or "required" in detail_str.lower()

    async def test_update_steps_change_type_config_required_without_code_returns_422(self, client, dbops_token):
        """Story 2.24 AC2/AC4: PUT steps with required=true but missing change_model_code returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [{"order": 1, "name": "Step", "type": "prerequisite", "connector_type": "none"}],
                    "change_type_config": {"PROD": {"required": True}},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        detail_str = str(body.get("detail", []))
        assert "change_model_code" in detail_str or "required" in detail_str.lower()

    async def test_update_steps_not_found(self, client, dbops_token):
        """Test updating steps for non-existent action returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_execution_steps", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = None

            response = await client.put(
                "/api/v1/admin/actions/999/steps",
                json={
                    "steps": [
                        {"order": 1, "name": "Step", "type": "prerequisite", "connector_type": "none"}
                    ],
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    async def test_update_steps_not_draft_returns_400(self, client, dbops_token):
        """Test updating steps for non-draft action returns 400."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_execution_steps", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.side_effect = RepoInvalidStateError(
                "Les etapes ne peuvent etre modifiees que pour une action en brouillon",
                current_status="published",
            )

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [
                        {"order": 1, "name": "Step", "type": "prerequisite", "connector_type": "none"}
                    ],
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_STATE"
        assert data["error"]["details"]["status"] == "published"

    async def test_update_steps_validation_error(self, client, dbops_token):
        """Test updating steps with invalid data returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [],  # Empty steps should fail
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_update_steps_forbidden_non_dbops(self, client, dba_token):
        """Test updating steps with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/steps",
                json={
                    "steps": [
                        {"order": 1, "name": "Step", "type": "prerequisite", "connector_type": "none"}
                    ],
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# Story 2.3 RBAC tests removed in Story 2.14 — RBAC now managed via profiles.

# Story 2.24: change_model_code removed from ActionCreate/ActionResponse/ActionDetail.
# change_type_config is in ExecutionStepsUpdate (PUT /actions/{id}/steps) only.


# === Story 2.4: PATCH /admin/actions/{id}/status Tests ===


class TestUpdateActionStatus:
    """Tests for PATCH /api/v1/admin/actions/{id}/status (Story 2.4, AC #1, #4, #5)."""

    @pytest.fixture
    def sample_action_detail_published(self):
        """Sample ActionDetail with published status."""
        return ActionDetail(
            id=1,
            name="Published Action",
            description="A published action",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.PUBLISHED,
            created_by=1,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            updated_at=datetime(2026, 1, 28, 11, 0, 0),
        )

    @pytest.fixture
    def sample_action_detail_disabled(self):
        """Sample ActionDetail with disabled status."""
        return ActionDetail(
            id=1,
            name="Disabled Action",
            description="A disabled action",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            status=ActionStatus.DISABLED,
            created_by=1,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            updated_at=datetime(2026, 1, 28, 12, 0, 0),
        )

    async def test_patch_status_publish_success(self, client, dbops_token, sample_action_detail_published):
        """Test publishing action returns 200."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_status", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = sample_action_detail_published

            response = await client.patch(
                "/api/v1/admin/actions/1/status",
                json={"transition": "publish"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["status"] == "published"
        # Verify user_id and transition were passed (API uses keyword args)
        mock_update.assert_called_once_with(1, transition=StatusTransition.PUBLISH, user_id="1")

    async def test_patch_status_disable_success(self, client, dbops_token, sample_action_detail_disabled):
        """Test disabling action returns 200."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_status", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = sample_action_detail_disabled

            response = await client.patch(
                "/api/v1/admin/actions/1/status",
                json={"transition": "disable"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["status"] == "disabled"

    async def test_patch_status_enable_success(self, client, dbops_token, sample_action_detail_published):
        """Test enabling action returns 200."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_status", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = sample_action_detail_published

            response = await client.patch(
                "/api/v1/admin/actions/1/status",
                json={"transition": "enable"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["status"] == "published"

    async def test_patch_status_not_found(self, client, dbops_token):
        """Test updating status for non-existent action returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_status", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = None

            response = await client.patch(
                "/api/v1/admin/actions/999/status",
                json={"transition": "publish"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    async def test_patch_status_invalid_transition_returns_400(self, client, dbops_token):
        """Test invalid transition returns 400."""
        from app.models.catalog import InvalidTransitionError

        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_status", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.side_effect = InvalidTransitionError(
                current_status="draft",
                transition="disable",
            )

            response = await client.patch(
                "/api/v1/admin/actions/1/status",
                json={"transition": "disable"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_STATE"
        assert "draft" in data["error"]["details"]["current_status"]
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[1]["user_id"] == "1"
        assert call_args[1]["transition"] == StatusTransition.DISABLE

    async def test_patch_status_forbidden_non_dbops(self, client, dba_token):
        """Test updating status with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.patch(
                "/api/v1/admin/actions/1/status",
                json={"transition": "publish"},
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetTags:
    """Tests for GET /api/v1/tags (Story 2.6, AC #5)."""

    @pytest.mark.asyncio
    async def test_get_tags_returns_list(self, client):
        """GET /tags returns { data: list[TagResponse] }."""
        tags = [
            TagResponse(id=1, name="rac", created_at=datetime(2026, 1, 28, 10, 0, 0)),
            TagResponse(id=2, name="dataguard", created_at=datetime(2026, 1, 28, 10, 1, 0)),
        ]
        with patch("app.api.v1.tags.catalog_repository.get_all_tags", new_callable=AsyncMock) as m:
            m.return_value = tags
            response = await client.get("/api/v1/tags")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "rac"
        assert data["data"][1]["name"] == "dataguard"

    @pytest.mark.asyncio
    async def test_get_tags_empty(self, client):
        """GET /tags returns empty list when no tags."""
        with patch("app.api.v1.tags.catalog_repository.get_all_tags", new_callable=AsyncMock) as m:
            m.return_value = []
            response = await client.get("/api/v1/tags")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == []


class TestUpdateActionTags:
    """Tests for PUT /api/v1/admin/actions/{id}/tags (Story 2.6, AC #5)."""

    @pytest.fixture
    def sample_action_with_tags(self):
        """ActionDetail with tags."""
        return ActionDetail(
            id=1,
            name="Create PDB",
            description="",
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema=None,
            impact_rules=None,
            status=ActionStatus.DRAFT,
            created_by=1,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            updated_at=None,
            execution_steps=None,
            change_type_config=None,
            tags=["rac", "dataguard"],
        )

    @pytest.mark.asyncio
    async def test_put_tags_tag_names_creates_and_sets(self, client, dbops_token, sample_action_with_tags):
        """PUT with tag_names creates missing tags and sets them."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.repositories.catalog_repository.create_tag_if_not_exists", new_callable=AsyncMock) as mock_create, \
             patch("app.repositories.catalog_repository.set_action_tags", new_callable=AsyncMock) as mock_set:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_action_with_tags
            mock_create.side_effect = [10, 20]  # ids for "rac", "dataguard"

            response = await client.put(
                "/api/v1/admin/actions/1/tags",
                json={"tag_names": ["rac", "dataguard"]},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert mock_create.call_count == 2
        mock_set.assert_called_once_with(1, [10, 20])
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1

    @pytest.mark.asyncio
    async def test_put_tags_tag_ids(self, client, dbops_token, sample_action_with_tags):
        """PUT with tag_ids sets tags directly."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.repositories.catalog_repository.set_action_tags", new_callable=AsyncMock) as mock_set:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_action_with_tags

            response = await client.put(
                "/api/v1/admin/actions/1/tags",
                json={"tag_ids": [10, 20]},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_set.assert_called_once_with(1, [10, 20])

    @pytest.mark.asyncio
    async def test_put_tags_404(self, client, dbops_token):
        """PUT tags for non-existent action returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None

            response = await client.put(
                "/api/v1/admin/actions/999/tags",
                json={"tag_ids": [1, 2]},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_put_tags_422_no_ids_or_names(self, client, dbops_token):
        """PUT tags without tag_ids or tag_names returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/tags",
                json={},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_put_tags_422_both_ids_and_names(self, client, dbops_token):
        """PUT tags with both tag_ids and tag_names returns 422 (mutual exclusivity)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/tags",
                json={"tag_ids": [1, 2], "tag_names": ["rac", "dataguard"]},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        body = response.json()
        assert "detail" in body
        assert any("not both" in str(d).lower() for d in body["detail"])

    @pytest.mark.asyncio
    async def test_put_tags_forbidden_non_dbops(self, client, dba_token):
        """PUT tags with non-DBOPS returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/tags",
                json={"tag_ids": [1, 2]},
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
