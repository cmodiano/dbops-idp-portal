"""Tests for integrations API endpoints (Story 2.27, 4.9, 5.4).

Tests:
- GET /api/v1/admin/integrations — list integrations (200, 403)
- GET /api/v1/admin/integrations/{id} — get integration (200, 404, 403)
- POST /api/v1/admin/integrations — create integration (201, 400, 422, 403)
- PUT /api/v1/admin/integrations/{id} — update integration (200, 400, 404, 422, 403)
- DELETE /api/v1/admin/integrations/{id} — delete integration (204, 404, 403)
- POST /api/v1/admin/integrations/upload-icon — upload icon (Story 4.9, 201, 400, 403)
- Story 5.4: config JSON Schema validation — valid accepted, invalid returns 400 INVALID_CONFIG
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, mock_open, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.core.security import create_access_token
from app.models.integration import IntegrationResponse, AuthFlow
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
    """Sample IntegrationResponse with free-form type and auth_flow (Story 4.9, 5.3)."""
    return IntegrationResponse(
        id=1,
        type="aap",  # Story 4.9: free-form string
        name="AAP Production",
        base_url="https://aap.example.com",
        credential_ref="secret/idp/aap-prod",
        icon="aap",
        auth_flow=AuthFlow.TOKEN,
        token_url=None,
        config=None,
        created_at=datetime(2026, 1, 29, 10, 0, 0),
        updated_at=datetime(2026, 1, 29, 10, 0, 0),
    )


@pytest.fixture
def sample_integration_response_2():
    """Second sample IntegrationResponse for list tests (Story 4.9, 5.3)."""
    return IntegrationResponse(
        id=2,
        type="servicenow",  # Story 4.9: free-form string
        name="ServiceNow Prod",
        base_url="https://prod.servicenow.com",
        credential_ref="secret/idp/snow-prod",
        icon="servicenow",
        auth_flow=AuthFlow.BASIC,
        token_url=None,
        config=None,
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
            type="terraform",  # Story 4.9: free-form string
            name="Terraform Cloud",
            base_url="https://terraform.io",
            credential_ref=None,
            icon=None,
            auth_flow=None,  # Story 4.9: auth_flow field
            token_url=None,
            config=None,
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
    async def test_create_integration_validation_error_type_too_long(self, client, dbops_token):
        """Test creating integration with type > 100 chars returns 422 (Story 4.9 AC1)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "x" * 101,  # 101 characters - exceeds max_length=100
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
    async def test_create_integration_with_token_url_and_config(self, client, dbops_token):
        """Story 5.3: POST with token_url and config returns 201 and includes them in response (AC3). Valid per 5.4 schema."""
        response_with_flow = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP With Flow",
            base_url="https://aap.example.com",
            credential_ref="secret/aap",
            icon=None,
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/api/v2/token/",
            config={"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]},
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = response_with_flow

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP With Flow",
                    "base_url": "https://aap.example.com",
                    "credential_ref": "secret/aap",
                    "auth_flow": "basic_then_token",
                    "token_url": "https://aap.example.com/api/v2/token/",
                    "config": {"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["data"]["token_url"] == "https://aap.example.com/api/v2/token/"
        assert data["data"]["config"] == {"auth_flow": [{"step": "obtain_token", "url_ref": "token_url"}]}

    @pytest.mark.asyncio
    async def test_create_integration_valid_config_full_returns_201(self, client, dbops_token):
        """Story 5.4 AC2: POST with valid full config (credentials.ref, keys, use_token_from_step) accepted."""
        valid_config = {
            "auth_flow": [
                {
                    "step": "obtain_token",
                    "url_ref": "token_url",
                    "credentials": {"ref": "credential_ref", "keys": ["username", "password"]},
                    "response_token_path": "access_token",
                },
                {"step": "call_api", "url_ref": "base_url", "credentials": {"use_token_from_step": 0}},
            ]
        }
        response_with_config = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP Full Config",
            base_url="https://aap.example.com",
            credential_ref="secret/aap",
            icon=None,
            auth_flow=AuthFlow.BASIC_THEN_TOKEN,
            token_url="https://aap.example.com/token",
            config=valid_config,
            created_at=datetime(2026, 1, 29, 10, 0, 0),
            updated_at=datetime(2026, 1, 29, 10, 0, 0),
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.repositories.integration_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = response_with_config

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP Full Config",
                    "base_url": "https://aap.example.com",
                    "credential_ref": "secret/aap",
                    "auth_flow": "basic_then_token",
                    "token_url": "https://aap.example.com/token",
                    "config": valid_config,
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["config"] == valid_config

    @pytest.mark.asyncio
    async def test_create_integration_empty_config_accepted(self, client, dbops_token, sample_integration_response):
        """Story 5.4: POST with config {} is accepted (optional, no schema validation)."""
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
                    "name": "AAP Empty Config",
                    "base_url": "https://aap.example.com",
                    "config": {},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio
    async def test_create_integration_invalid_config_credentials_ref_arbitrary_returns_400(self, client, dbops_token):
        """Story 5.4 AC1/AC2: POST with credentials.ref arbitrary (e.g. Vault path) returns 400 INVALID_CONFIG."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {
                        "auth_flow": [
                            {
                                "step": "obtain_token",
                                "url_ref": "token_url",
                                "credentials": {"ref": "vault/secret/mysecret", "keys": ["username", "password"]},
                            }
                        ]
                    },
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_CONFIG"
        assert "field" in data["error"].get("details", {})

    @pytest.mark.asyncio
    async def test_create_integration_invalid_config_empty_auth_flow_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: POST with config.auth_flow empty array returns 400 INVALID_CONFIG (minItems: 1)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": []},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_create_integration_invalid_config_unknown_step_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: POST with config step unknown returns 400 INVALID_CONFIG."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": [{"step": "unknown_step", "url_ref": "token_url"}]},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_CONFIG"
        assert "field" in data["error"].get("details", {})

    @pytest.mark.asyncio
    async def test_create_integration_invalid_config_url_ref_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: POST with config url_ref invalid (e.g. vault path) returns 400 INVALID_CONFIG."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": [{"step": "obtain_token", "url_ref": "vault/secret/path"}]},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_create_integration_invalid_config_missing_auth_flow_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: POST with config missing auth_flow returns 400 INVALID_CONFIG."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"other_key": 1},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_create_integration_token_url_invalid_returns_422(self, client, dbops_token):
        """Story 5.3 AC1: token_url must be http(s); invalid URL returns 422."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "token_url": "ftp://invalid.example.com/token",
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_integration_config_invalid_auth_flow_not_list_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: config.auth_flow not a list returns 400 INVALID_CONFIG (JSON Schema)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": "not_a_list"},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_create_integration_config_missing_step_key_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: config.auth_flow step missing 'step' key returns 400 INVALID_CONFIG (JSON Schema)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": [{"url_ref": "token_url"}]},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_create_integration_config_invalid_step_value_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: config.auth_flow step invalid value returns 400 INVALID_CONFIG (JSON Schema)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.post(
                "/api/v1/admin/integrations",
                json={
                    "type": "aap",
                    "name": "AAP",
                    "base_url": "https://aap.example.com",
                    "config": {"auth_flow": [{"step": "invalid_step_name"}]},
                },
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "INVALID_CONFIG"

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
            type="aap",  # Story 4.9: free-form string
            name="AAP Production v2",
            base_url="https://aap-v2.example.com",
            credential_ref="secret/idp/aap-prod-v2",
            icon="aap",
            auth_flow=AuthFlow.TOKEN,  # Story 4.9: auth_flow field
            token_url=None,
            config=None,
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
    async def test_update_integration_with_config_null_retracts_config(self, client, dbops_token):
        """Story 5.3: PUT with config null retracts config (AC3)."""
        updated = IntegrationResponse(
            id=1,
            type="aap",
            name="AAP Production",
            base_url="https://aap.example.com",
            credential_ref="secret/aap",
            icon="aap",
            auth_flow=AuthFlow.TOKEN,
            token_url=None,
            config=None,
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
                json={"config": None},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["config"] is None

    @pytest.mark.asyncio
    async def test_update_integration_invalid_config_returns_400(self, client, dbops_token):
        """Story 5.4 AC2: PUT with invalid config (unknown step) returns 400 INVALID_CONFIG."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            response = await client.put(
                "/api/v1/admin/integrations/1",
                json={"config": {"auth_flow": [{"step": "invalid_step", "url_ref": "base_url"}]}},
                headers={"Authorization": f"Bearer {dbops_token}"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_CONFIG"

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


class TestUploadIcon:
    """Tests for POST /api/v1/admin/integrations/upload-icon (Story 4.9, AC3, AC6)."""

    @pytest.mark.asyncio
    async def test_upload_icon_success(self, client, dbops_token):
        """Test uploading icon returns 201 with icon_url (Story 4.9, AC3; LOW-10 fix: full isolation)."""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("builtins.open", mock_open()) as mock_file, \
             patch("pathlib.Path.mkdir") as mock_mkdir, \
             patch("pathlib.Path.exists", return_value=True):
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            # Create fake PNG file
            files = {"file": ("test-icon.png", b"fake-png-content", "image/png")}
            response = await client.post(
                "/api/v1/admin/integrations/upload-icon",
                headers={"Authorization": f"Bearer {dbops_token}"},
                files=files,
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "data" in data
        assert "icon_url" in data["data"]
        assert data["data"]["icon_url"].startswith("/static/icons/")
        assert data["data"]["icon_url"].endswith(".png")

    @pytest.mark.asyncio
    async def test_upload_icon_invalid_mime_type(self, client, dbops_token):
        """Test uploading non-image file returns 400 (Story 4.9, AC3)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            # Create fake text file
            files = {"file": ("test.txt", b"not-an-image", "text/plain")}
            response = await client.post(
                "/api/v1/admin/integrations/upload-icon",
                headers={"Authorization": f"Bearer {dbops_token}"},
                files=files,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "INVALID_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_upload_icon_file_too_large(self, client, dbops_token):
        """Test uploading file > 2MB returns 400 (Story 4.9, AC3)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })

            # Create fake large file (3MB)
            large_content = b"x" * (3 * 1024 * 1024)
            files = {"file": ("large-icon.png", large_content, "image/png")}
            response = await client.post(
                "/api/v1/admin/integrations/upload-icon",
                headers={"Authorization": f"Bearer {dbops_token}"},
                files=files,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["error"]["code"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_upload_icon_forbidden_non_dbops(self, client, dba_token):
        """Test uploading icon with non-DBOPS profile returns 403 (Story 4.9, AC3)."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })

            files = {"file": ("test-icon.png", b"fake-png-content", "image/png")}
            response = await client.post(
                "/api/v1/admin/integrations/upload-icon",
                headers={"Authorization": f"Bearer {dba_token}"},
                files=files,
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN
