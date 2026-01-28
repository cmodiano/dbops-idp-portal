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
    ActionCategory,
    ActionEngine,
    ActionPlatform,
    ActionStatus,
    ActionResponse,
    ActionDetail,
    ExecutionStep,
    ExecutionStepType,
    ChangeType,
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
    """Sample ActionResponse for mocked repository."""
    return ActionResponse(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        category=ActionCategory.PROVISIONING,
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
    )


@pytest.fixture
def sample_action_detail():
    """Sample ActionDetail for mocked repository (valid RbacPolicies shape)."""
    return ActionDetail(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        category=ActionCategory.PROVISIONING,
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=None,
        rbac_policies={
            "environments": {
                "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False, "approver_profiles": None},
            }
        },
    )


@pytest.fixture
def sample_action_detail_with_steps():
    """Sample ActionDetail with execution_steps and change_type_config (valid RbacPolicies shape)."""
    return ActionDetail(
        id=1,
        name="Create PDB Oracle",
        description="Creates a Pluggable Database",
        category=ActionCategory.PROVISIONING,
        engine=ActionEngine.ORACLE,
        platform=ActionPlatform.AAP,
        parameters_schema={"type": "object"},
        impact_rules={"DEV": {"level": "low"}},
        status=ActionStatus.DRAFT,
        created_by=1,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=datetime(2026, 1, 28, 11, 0, 0),
        rbac_policies={
            "environments": {
                "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False, "approver_profiles": None},
            }
        },
        execution_steps=[
            ExecutionStep(order=1, name="Verification", type=ExecutionStepType.PREREQUISITE),
        ],
        change_type_config={"DEV": ChangeType.PRE_APPROVED, "PROD": ChangeType.CAB},
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
                    "category": "Provisioning",
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
                    "category": "Provisioning",
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
                    "category": "Provisioning",
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
                    # missing category, engine, platform
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
                    "category": "Provisioning",
                    "engine": "Oracle",
                    "platform": "AAP",
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestListActions:
    """Tests for GET /api/v1/admin/actions."""

    async def test_list_actions_success(self, client, dbops_token, sample_action_response):
        """Test listing actions returns list."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = [sample_action_response, sample_action_response]

            response = await client.get(
                "/api/v1/admin/actions",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2

    async def test_list_actions_with_status_filter(self, client, dbops_token, sample_action_response):
        """Test listing actions with status filter."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = [sample_action_response]

            response = await client.get(
                "/api/v1/admin/actions?status_filter=draft",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(status=ActionStatus.DRAFT)

    async def test_list_actions_empty(self, client, dbops_token):
        """Test listing actions when none exist."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.list_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = []

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
        assert data["data"]["rbac_policies"] is not None
        assert "environments" in data["data"]["rbac_policies"]

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
                        {"order": 1, "name": "Verification", "type": "prerequisite", "is_servicenow_change": False}
                    ],
                    "change_type_config": {"DEV": "pre_approved", "PROD": "cab"},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["execution_steps"] is not None
        assert data["data"]["change_type_config"] is not None

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
                        {"order": 1, "name": "Step", "type": "prerequisite", "is_servicenow_change": False}
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
                        {"order": 1, "name": "Step", "type": "prerequisite", "is_servicenow_change": False}
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
                        {"order": 1, "name": "Step", "type": "prerequisite", "is_servicenow_change": False}
                    ],
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# === Story 2.3: PUT /admin/actions/{id}/rbac Tests ===


class TestUpdateActionRbac:
    """Tests for PUT /api/v1/admin/actions/{id}/rbac (Story 2.3, AC #4)."""

    @pytest.fixture
    def sample_action_detail_with_rbac(self):
        """Sample ActionDetail with RBAC policies."""
        return ActionDetail(
            id=1,
            name="Create PDB Oracle",
            description="Creates a Pluggable Database",
            category=ActionCategory.PROVISIONING,
            engine=ActionEngine.ORACLE,
            platform=ActionPlatform.AAP,
            parameters_schema={"type": "object"},
            impact_rules={"DEV": {"level": "low"}},
            status=ActionStatus.DRAFT,
            created_by=1,
            created_at=datetime(2026, 1, 28, 10, 0, 0),
            updated_at=datetime(2026, 1, 28, 11, 0, 0),
            rbac_policies={
                "environments": {
                    "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False, "approver_profiles": None}
                }
            },
        )

    async def test_update_rbac_success(self, client, dbops_token, sample_action_detail_with_rbac):
        """Test updating RBAC policies returns 200."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_rbac_policies", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = sample_action_detail_with_rbac

            response = await client.put(
                "/api/v1/admin/actions/1/rbac",
                json={
                    "policies": {
                        "environments": {
                            "DEV": {"profiles": ["dba_applicatif", "client_business"], "requires_approval": False},
                            "PROD": {"profiles": ["dba_applicatif"], "requires_approval": True, "approver_profiles": ["dba_infrastructure"]},
                        }
                    }
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1

    async def test_update_rbac_not_found(self, client, dbops_token):
        """Test updating RBAC for non-existent action returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_rbac_policies", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = None

            response = await client.put(
                "/api/v1/admin/actions/999/rbac",
                json={
                    "policies": {
                        "environments": {
                            "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False},
                        }
                    }
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    async def test_update_rbac_not_draft_returns_400(self, client, dbops_token):
        """Test updating RBAC for non-draft action returns 400."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.catalog_repository.update_rbac_policies", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.side_effect = RepoInvalidStateError(
                "Les politiques RBAC ne peuvent etre modifiees que pour une action en brouillon",
                current_status="published",
            )

            response = await client.put(
                "/api/v1/admin/actions/1/rbac",
                json={
                    "policies": {
                        "environments": {
                            "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False},
                        }
                    }
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_STATE"
        assert data["error"]["details"]["status"] == "published"

    async def test_update_rbac_validation_error_empty_profiles(self, client, dbops_token):
        """Test updating RBAC with empty profiles returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/rbac",
                json={
                    "policies": {
                        "environments": {
                            "DEV": {"profiles": [], "requires_approval": False},
                        }
                    }
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_update_rbac_forbidden_non_dbops(self, client, dba_token):
        """Test updating RBAC with non-DBOPS profile returns 403."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.put(
                "/api/v1/admin/actions/1/rbac",
                json={
                    "policies": {
                        "environments": {
                            "DEV": {"profiles": ["dba_applicatif"], "requires_approval": False},
                        }
                    }
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
