"""Tests for integrations API endpoints (Story 2.27, AC2-AC4).

Tests:
- GET /api/v1/admin/integrations — list integrations (200, 403)
- GET /api/v1/admin/integrations/{id} — get integration (200, 404, 403)
- POST /api/v1/admin/integrations — create integration (201, 400, 422, 403)
- PUT /api/v1/admin/integrations/{id} — update integration (200, 400, 404, 422, 403)
- DELETE /api/v1/admin/integrations/{id} — delete integration (204, 404, 403)
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.core.security import create_access_token
from app.models.integration import IntegrationResponse, IntegrationType
from app.repositories.integration_repository import DuplicateNameError


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
def sample_integration_response():
    """Sample IntegrationResponse for mocked repository."""
    return IntegrationResponse(
        id=1,
        type=IntegrationType.AAP,
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
        created_at=datetime(2026, 1, 29, 10, 0, 0),
        updated_at=datetime(2026, 1, 29, 10, 0, 0),
    )


@pytest.fixture
def sample_integration_response_2():
    """Second sample IntegrationResponse for list tests."""
    return IntegrationResponse(
        id=2,
        type=IntegrationType.SERVICENOW,
        name="ServiceNow Prod",
        base_url="https://prod.servicenow.com",
        credential_ref="secret/idp/snow-prod",
        icon="servicenow",
        created_at=datetime(2026, 1, 29, 11, 0, 0),
        updated_at=datetime(2026, 1, 29, 11, 0, 0),
    )


class TestListIntegrations:
    """Tests for GET /api/v1/admin/integrations (AC2)."""

    @pytest.mark.asyncio
    async def test_list_integrations_success(
        self, client, dbops_token, sample_integration_response, sample_integration_response_2
    ):
        """Test listing integrations returns list."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.get_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = [sample_integration_response, sample_integration_response_2]

            response = await client.get(
                "/api/v1/admin/integrations",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "AAP Production"
        assert data["data"][1]["name"] == "ServiceNow Prod"
        # Verify credential_ref is exposed (reference only, no secret value)
        assert data["data"][0]["credential_ref"] == "secret/idp/aap-prod"

    @pytest.mark.asyncio
    async def test_list_integrations_empty(self, client, dbops_token):
        """Test listing integrations when none exist."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.get_all", new_callable=AsyncMock) as mock_list:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_list.return_value = []

            response = await client.get(
                "/api/v1/admin/integrations",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_integrations_forbidden_non_dbops(self, client, dba_token):
        """Test listing integrations with non-DBOPS profile returns 403 (AC4)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.get(
                "/api/v1/admin/integrations",
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_list_integrations_unauthorized_no_token(self, client):
        """Test listing integrations without token returns 401."""
        response = await client.get("/api/v1/admin/integrations")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetIntegration:
    """Tests for GET /api/v1/admin/integrations/{id} (AC2)."""

    @pytest.mark.asyncio
    async def test_get_integration_success(self, client, dbops_token, sample_integration_response):
        """Test getting integration by ID returns detail."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_integration_response

            response = await client.get(
                "/api/v1/admin/integrations/1",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "AAP Production"
        assert data["data"]["type"] == "aap"

    @pytest.mark.asyncio
    async def test_get_integration_id_zero_returns_422(self, client, dbops_token):
        """Test GET /integrations/0 rejected by path validation (ge=1)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            response = await client.get(
                "/api/v1/admin/integrations/0",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_integration_not_found(self, client, dbops_token):
        """Test getting non-existent integration returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None

            response = await client.get(
                "/api/v1/admin/integrations/999",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "introuvable" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_get_integration_forbidden_non_dbops(self, client, dba_token):
        """Test getting integration with non-DBOPS profile returns 403 (AC4)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.get(
                "/api/v1/admin/integrations/1",
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCreateIntegration:
    """Tests for POST /api/v1/admin/integrations (AC3)."""

    @pytest.mark.asyncio
    async def test_create_integration_success(self, client, dbops_token, sample_integration_response):
        """Test creating integration returns 201."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = sample_integration_response

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP Production",
                    "base_url": "https://aap.example.com",
                    "credential_ref": "secret/idp/aap-prod",
                    "icon": "aap",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "data" in data
        assert data["data"]["id"] == 1
        assert data["data"]["name"] == "AAP Production"
        assert data["data"]["type"] == "aap"

    @pytest.mark.asyncio
    async def test_create_integration_minimal(self, client, dbops_token, sample_integration_response):
        """Test creating integration with minimal fields (no credential_ref, no icon)."""
        minimal_response = IntegrationResponse(
            id=1,
            type=IntegrationType.TERRAFORM,
            name="Terraform Cloud",
            base_url="https://terraform.io",
            credential_ref=None,
            icon=None,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = minimal_response

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "terraform",
                    "name": "Terraform Cloud",
                    "base_url": "https://terraform.io",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["data"]["credential_ref"] is None
        assert data["data"]["icon"] is None

    @pytest.mark.asyncio
    async def test_create_integration_duplicate_name_returns_400(self, client, dbops_token):
        """Test creating integration with duplicate name returns 400."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.side_effect = DuplicateNameError("AAP Production")

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP Production",
                    "base_url": "https://aap.example.com",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "DUPLICATE_NAME"

    @pytest.mark.asyncio
    async def test_create_integration_validation_error_missing_type(self, client, dbops_token):
        """Test creating integration with missing type returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "name": "Test",
                    "base_url": "https://test.com",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_integration_validation_error_invalid_type(self, client, dbops_token):
        """Test creating integration with invalid type returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "unknown_type",
                    "name": "Test",
                    "base_url": "https://test.com",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_integration_validation_error_empty_name(self, client, dbops_token):
        """Test creating integration with empty name returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "",
                    "base_url": "https://test.com",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_integration_validation_error_invalid_url(self, client, dbops_token):
        """Test creating integration with invalid URL returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "not-a-valid-url",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_integration_forbidden_non_dbops(self, client, dba_token):
        """Test creating integration with non-DBOPS profile returns 403 (AC4)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                },
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateIntegration:
    """Tests for PUT /api/v1/admin/integrations/{id} (AC3)."""

    @pytest.mark.asyncio
    async def test_update_integration_success(self, client, dbops_token, sample_integration_response):
        """Test updating integration returns 200."""
        updated = IntegrationResponse(
            id=1,
            type=IntegrationType.AAP,
            name="AAP Production v2",
            base_url="https://aap-v2.example.com",
            credential_ref="secret/idp/aap-prod-v2",
            icon="aap",
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 12, 0, 0),
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = updated

            response = await client.put(
                "/api/v1/admin/integrations/1",
                json={
                    "name": "AAP Production v2",
                    "base_url": "https://aap-v2.example.com",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["name"] == "AAP Production v2"

    @pytest.mark.asyncio
    async def test_update_integration_not_found(self, client, dbops_token):
        """Test updating non-existent integration returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = None

            response = await client.put(
                "/api/v1/admin/integrations/999",
                json={"name": "Updated"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_integration_duplicate_name_returns_400(self, client, dbops_token):
        """Test updating integration with duplicate name returns 400."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.side_effect = DuplicateNameError("Existing Name")

            response = await client.put(
                "/api/v1/admin/integrations/1",
                json={"name": "Existing Name"},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "DUPLICATE_NAME"

    @pytest.mark.asyncio
    async def test_update_integration_forbidden_non_dbops(self, client, dba_token):
        """Test updating integration with non-DBOPS profile returns 403 (AC4)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.put(
                "/api/v1/admin/integrations/1",
                json={"name": "Updated"},
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeleteIntegration:
    """Tests for DELETE /api/v1/admin/integrations/{id} (AC3)."""

    @pytest.mark.asyncio
    async def test_delete_integration_success(self, client, dbops_token):
        """Test deleting integration returns 204."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.delete", new_callable=AsyncMock) as mock_delete:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_delete.return_value = True

            response = await client.delete(
                "/api/v1/admin/integrations/1",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_integration_not_found(self, client, dbops_token):
        """Test deleting non-existent integration returns 404."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.delete", new_callable=AsyncMock) as mock_delete:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_delete.return_value = False

            response = await client.delete(
                "/api/v1/admin/integrations/999",
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_integration_forbidden_non_dbops(self, client, dba_token):
        """Test deleting integration with non-DBOPS profile returns 403 (AC4)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            response = await client.delete(
                "/api/v1/admin/integrations/1",
                headers={"Authorization": f"Bearer {dba_token}"},
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
