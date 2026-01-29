"""Tests for profiles API (Story 2.9, AC #2, #3, #4, #5)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.core.security import create_access_token
from app.models.profile import ProfileCreate, ProfileResponse, ProfileListItem
from app.core.exceptions import InvalidStateError


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def dbops_token():
    return create_access_token({"sub": "1", "username": "dbops-user", "profile": "dbops"})


@pytest.fixture
def dba_token():
    return create_access_token({"sub": "2", "username": "dba-user", "profile": "dba_app"})


@pytest.fixture
def sample_profile_response():
    return ProfileResponse(
        id=1,
        name="Assurance",
        description="Profil Assurance",
        ad_group="GRP-IDP-ASSURANCE",
        is_admin=False,
        is_auditor=True,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=datetime(2026, 1, 28, 10, 0, 0),
    )


@pytest.fixture
def sample_profile_list_item():
    return ProfileListItem(
        id=1,
        name="Assurance",
        ad_group="GRP-IDP-ASSURANCE",
        permission_count=0,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
    )


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


class TestListProfiles:
    @pytest.mark.asyncio
    async def test_list_success(self, client, dbops_token, sample_profile_list_item):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_all", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = [sample_profile_list_item]
            response = await client.get(
                "/api/v1/admin/profiles",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Assurance"
        assert data["data"][0]["ad_group"] == "GRP-IDP-ASSURANCE"
        assert data["data"][0]["permission_count"] == 0

    @pytest.mark.asyncio
    async def test_list_empty(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_all", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = []
            response = await client.get(
                "/api/v1/admin/profiles",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == []

    @pytest.mark.asyncio
    async def test_list_forbidden_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.get(
                "/api/v1/admin/profiles",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetProfile:
    @pytest.mark.asyncio
    async def test_get_success(self, client, dbops_token, sample_profile_response):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            response = await client.get(
                "/api/v1/admin/profiles/1",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["id"] == 1
        assert response.json()["data"]["name"] == "Assurance"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None
            response = await client.get(
                "/api/v1/admin/profiles/999",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()

    @pytest.mark.asyncio
    async def test_get_forbidden_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.get(
                "/api/v1/admin/profiles/1",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCreateProfile:
    @pytest.mark.asyncio
    async def test_create_success(self, client, dbops_token, sample_profile_response):
        payload = {
            "name": "Assurance",
            "description": "Profil Assurance",
            "ad_group": "GRP-IDP-ASSURANCE",
            "is_admin": False,
            "is_auditor": True,
        }
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.return_value = sample_profile_response
            response = await client.post(
                "/api/v1/admin/profiles",
                json=payload,
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["data"]["name"] == "Assurance"

    @pytest.mark.asyncio
    async def test_create_validation_empty_name(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            response = await client.post(
                "/api/v1/admin/profiles",
                json={"name": "  ", "ad_group": "GRP-X"},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_validation_missing_ad_group(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            response = await client.post(
                "/api/v1/admin/profiles",
                json={"name": "X", "ad_group": ""},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_400(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.create", new_callable=AsyncMock) as mock_create:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_create.side_effect = InvalidStateError(
                code="DUPLICATE_NAME",
                message="Un profil avec ce nom existe déjà.",
                details={"name": "Assurance"},
            )
            response = await client.post(
                "/api/v1/admin/profiles",
                json={"name": "Assurance", "ad_group": "GRP-IDP-ASSURANCE"},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["code"] == "DUPLICATE_NAME"

    @pytest.mark.asyncio
    async def test_create_forbidden_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.post(
                "/api/v1/admin/profiles",
                json={"name": "X", "ad_group": "GRP-X"},
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_update_success(self, client, dbops_token, sample_profile_response):
        updated = ProfileResponse(
            id=sample_profile_response.id,
            name=sample_profile_response.name,
            description=sample_profile_response.description,
            ad_group="GRP-IDP-ASSURANCE-V2",
            is_admin=sample_profile_response.is_admin,
            is_auditor=sample_profile_response.is_auditor,
            created_at=sample_profile_response.created_at,
            updated_at=sample_profile_response.updated_at,
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = updated
            response = await client.put(
                "/api/v1/admin/profiles/1",
                json={"ad_group": "GRP-IDP-ASSURANCE-V2"},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["ad_group"] == "GRP-IDP-ASSURANCE-V2"

    @pytest.mark.asyncio
    async def test_update_not_found(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.return_value = None
            response = await client.put(
                "/api/v1/admin/profiles/999",
                json={"name": "X"},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_duplicate_name_returns_400(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.update", new_callable=AsyncMock) as mock_update:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_update.side_effect = InvalidStateError(
                code="DUPLICATE_NAME",
                message="Un profil avec ce nom existe déjà.",
                details={"name": "Other"},
            )
            response = await client.put(
                "/api/v1/admin/profiles/1",
                json={"name": "Other"},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_update_forbidden_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.put(
                "/api/v1/admin/profiles/1",
                json={"name": "X"},
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDeleteProfile:
    @pytest.mark.asyncio
    async def test_delete_success(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.delete", new_callable=AsyncMock) as mock_del:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_del.return_value = True
            response = await client.delete(
                "/api/v1/admin/profiles/1",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.delete", new_callable=AsyncMock) as mock_del:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_del.return_value = False
            response = await client.delete(
                "/api/v1/admin/profiles/999",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_forbidden_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.delete(
                "/api/v1/admin/profiles/1",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN
