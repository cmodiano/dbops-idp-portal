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


# --- Story 2.10: PUT/GET profile actions (AC2–AC5) ---


class TestGetProfileActions:
    @pytest.mark.asyncio
    async def test_get_actions_success(self, client, dbops_token, sample_profile_response):
        from app.models.profile import ProfileActionPermissionsResponse

        perms = ProfileActionPermissionsResponse(
            actions_type="list",
            action_ids=[1, 2],
            tag_patterns=[],
            environments=["DEV", "STAGING"],
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_perms:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_perms.return_value = perms
            response = await client.get(
                "/api/v1/admin/profiles/1/actions",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["actions_type"] == "list"
        assert data["action_ids"] == [1, 2]
        assert data["environments"] == ["DEV", "STAGING"]

    @pytest.mark.asyncio
    async def test_get_actions_success_pattern(self, client, dbops_token, sample_profile_response):
        from app.models.profile import ProfileActionPermissionsResponse

        perms = ProfileActionPermissionsResponse(
            actions_type="pattern",
            action_ids=[],
            tag_patterns=["oracle", "provisioning"],
            environments=["PROD"],
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_perms:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_perms.return_value = perms
            response = await client.get(
                "/api/v1/admin/profiles/1/actions",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["actions_type"] == "pattern"
        assert data["tag_patterns"] == ["oracle", "provisioning"]
        assert data["action_ids"] == []
        assert data["environments"] == ["PROD"]

    @pytest.mark.asyncio
    async def test_get_actions_default_all_when_no_row(self, client, dbops_token, sample_profile_response):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_perms:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_perms.return_value = None
            response = await client.get(
                "/api/v1/admin/profiles/1/actions",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["actions_type"] == "all"
        assert response.json()["data"]["action_ids"] == []

    @pytest.mark.asyncio
    async def test_get_actions_404_profile(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None
            response = await client.get(
                "/api/v1/admin/profiles/999/actions",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_actions_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.get(
                "/api/v1/admin/profiles/1/actions",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSetProfileActions:
    @pytest.mark.asyncio
    async def test_put_actions_200(self, client, dbops_token, sample_profile_response):
        from app.models.profile import ProfileActionPermissionsResponse

        payload = {
            "actions_type": "list",
            "action_ids": [1, 2],
            "tag_patterns": [],
            "environments": ["DEV", "STAGING"],
        }
        result_perms = ProfileActionPermissionsResponse(
            actions_type="list",
            action_ids=[1, 2],
            tag_patterns=[],
            environments=["DEV", "STAGING"],
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_action_permission_repository.set_actions_permissions", new_callable=AsyncMock) as mock_set:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_set.return_value = result_perms
            response = await client.put(
                "/api/v1/admin/profiles/1/actions",
                json=payload,
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["actions_type"] == "list"
        assert response.json()["data"]["action_ids"] == [1, 2]

    @pytest.mark.asyncio
    async def test_put_actions_validation_list_requires_action_ids(self, client, dbops_token, sample_profile_response):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            response = await client.put(
                "/api/v1/admin/profiles/1/actions",
                json={"actions_type": "list", "action_ids": [], "tag_patterns": [], "environments": []},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_put_actions_404_profile(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None
            response = await client.put(
                "/api/v1/admin/profiles/999/actions",
                json={"actions_type": "all", "action_ids": [], "tag_patterns": [], "environments": []},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_put_actions_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.put(
                "/api/v1/admin/profiles/1/actions",
                json={"actions_type": "all", "action_ids": [], "tag_patterns": [], "environments": []},
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Story 2.11: PUT/GET profile targets (AC1–AC5) ---


class TestGetProfileTargets:
    @pytest.mark.asyncio
    async def test_get_targets_success(self, client, dbops_token, sample_profile_response):
        from app.models.profile import ProfileTargetPermissionsResponse

        perms = ProfileTargetPermissionsResponse(
            targets_type="list",
            target_names=["assurance-db01", "assurance-db02"],
            target_patterns=[],
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock) as mock_perms:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_perms.return_value = perms
            response = await client.get(
                "/api/v1/admin/profiles/1/targets",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["targets_type"] == "list"
        assert data["target_names"] == ["assurance-db01", "assurance-db02"]
        assert data["target_patterns"] == []

    @pytest.mark.asyncio
    async def test_get_targets_default_all_when_no_row(self, client, dbops_token, sample_profile_response):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock) as mock_perms:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_perms.return_value = None
            response = await client.get(
                "/api/v1/admin/profiles/1/targets",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["targets_type"] == "all"
        assert response.json()["data"]["target_names"] == []

    @pytest.mark.asyncio
    async def test_get_targets_404_profile(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None
            response = await client.get(
                "/api/v1/admin/profiles/999/targets",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_targets_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.get(
                "/api/v1/admin/profiles/1/targets",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSetProfileTargets:
    @pytest.mark.asyncio
    async def test_put_targets_200(self, client, dbops_token, sample_profile_response):
        from app.models.profile import ProfileTargetPermissionsResponse

        payload = {
            "targets_type": "list",
            "target_names": ["assurance-db01", "assurance-db02"],
            "target_patterns": [],
        }
        result_perms = ProfileTargetPermissionsResponse(
            targets_type="list",
            target_names=["assurance-db01", "assurance-db02"],
            target_patterns=[],
        )
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.profiles.profile_target_permission_repository.set_target_permissions", new_callable=AsyncMock) as mock_set:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            mock_set.return_value = result_perms
            response = await client.put(
                "/api/v1/admin/profiles/1/targets",
                json=payload,
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["targets_type"] == "list"
        assert response.json()["data"]["target_names"] == ["assurance-db01", "assurance-db02"]

    @pytest.mark.asyncio
    async def test_put_targets_validation_list_requires_target_names(self, client, dbops_token, sample_profile_response):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = sample_profile_response
            response = await client.put(
                "/api/v1/admin/profiles/1/targets",
                json={"targets_type": "list", "target_names": [], "target_patterns": []},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_put_targets_404_profile(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_get.return_value = None
            response = await client.put(
                "/api/v1/admin/profiles/999/targets",
                json={"targets_type": "all", "target_names": [], "target_patterns": []},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_put_targets_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.put(
                "/api/v1/admin/profiles/1/targets",
                json={"targets_type": "all", "target_names": [], "target_patterns": []},
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# --- Story 2.13: Export/Import YAML (6.2) ---


class TestExportImportProfiles:
    """GET /admin/profiles/export, POST /admin/profiles/import."""

    @pytest.mark.asyncio
    async def test_import_rejects_non_yaml_extension(self, client, dbops_token):
        """File extension validation: .txt files should be rejected."""
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            response = await client.post(
                "/api/v1/admin/profiles/import",
                files={"file": ("profiles.txt", b"profiles: []", "text/plain")},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "INVALID_FILE" in response.json().get("error", {}).get("code", "")

    @pytest.mark.asyncio
    async def test_export_returns_200_and_yaml(self, client, dbops_token, sample_profile_list_item):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_export_import_service.export_profiles_yaml", new_callable=AsyncMock) as mock_export:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_export.return_value = b"profiles:\n  - name: A\n    ad_group: G1\n"
            response = await client.get(
                "/api/v1/admin/profiles/export",
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_200_OK
        assert "application/x-yaml" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "profiles.yaml" in response.headers.get("content-disposition", "")
        assert b"profiles:" in response.content

    @pytest.mark.asyncio
    async def test_export_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.get(
                "/api/v1/admin/profiles/export",
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_import_valid_returns_200_and_summary(self, client, dbops_token):
        yaml_content = """
profiles:
  - name: P1
    ad_group: G1
    actions:
      type: pattern
      patterns: ["x"]
    targets:
      type: pattern
      patterns: ["t-*"]
"""
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_export_import_service.import_profiles_yaml", new_callable=AsyncMock) as mock_import:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_import.return_value = (1, 0)
            response = await client.post(
                "/api/v1/admin/profiles/import",
                files={"file": ("profiles.yaml", yaml_content.encode("utf-8"), "application/x-yaml")},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        data = response.json()
        assert "data" in data
        assert "created" in data["data"]
        assert "updated" in data["data"]
        assert data["data"]["created"] == 1
        assert data["data"]["updated"] == 0

    @pytest.mark.asyncio
    async def test_import_invalid_yaml_returns_400(self, client, dbops_token):
        with patch("app.api.deps.user_repository") as mock_repo, \
             patch("app.api.v1.profiles.profile_export_import_service.import_profiles_yaml", new_callable=AsyncMock) as mock_import:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 1, "username": "dbops-user", "display_name": "DBOPS", "profile": "dbops"
            })
            mock_import.side_effect = InvalidStateError(
                code="INVALID_YAML_SCHEMA",
                message="Schéma YAML invalide.",
                details={"errors": []},
            )
            response = await client.post(
                "/api/v1/admin/profiles/import",
                files={"file": ("profiles.yaml", b"invalid: [", "application/x-yaml")},
                headers=_auth_headers(dbops_token),
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error" in data or "code" in data or "message" in data

    @pytest.mark.asyncio
    async def test_import_403_non_dbops(self, client, dba_token):
        with patch("app.api.deps.user_repository") as mock_repo:
            mock_repo.get_by_username = AsyncMock(return_value={
                "id": 2, "username": "dba-user", "display_name": "DBA", "profile": "dba_app"
            })
            response = await client.post(
                "/api/v1/admin/profiles/import",
                files={"file": ("profiles.yaml", b"profiles: []", "application/x-yaml")},
                headers=_auth_headers(dba_token),
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN
