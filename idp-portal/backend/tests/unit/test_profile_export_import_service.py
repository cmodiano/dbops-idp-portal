"""Tests for profile YAML export/import service (Story 2.13, Task 2, 6.1)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from app.services import profile_export_import_service


@pytest.fixture
def profile_list_item():
    from app.models.profile import ProfileListItem
    return ProfileListItem(
        id=1,
        name="Assurance",
        ad_group="GRP-IDP-ASSURANCE",
        permission_count=0,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
    )


@pytest.fixture
def profile_response():
    from app.models.profile import ProfileResponse
    return ProfileResponse(
        id=1,
        name="Assurance",
        description="Equipe assurance",
        ad_group="GRP-IDP-ASSURANCE",
        is_admin=False,
        is_auditor=False,
        created_at=datetime(2026, 1, 28, 10, 0, 0),
        updated_at=datetime(2026, 1, 28, 10, 0, 0),
    )


@pytest.fixture
def actions_perm_pattern():
    from app.models.profile import ProfileActionPermissionsResponse
    return ProfileActionPermissionsResponse(
        actions_type="pattern",
        action_ids=[],
        tag_patterns=["tag:oracle", "tag:provisioning"],
        environments=["DEV", "STAGING"],
    )


@pytest.fixture
def targets_perm_pattern():
    from app.models.profile import ProfileTargetPermissionsResponse
    return ProfileTargetPermissionsResponse(
        targets_type="pattern",
        target_names=[],
        target_patterns=["assurance-*"],
    )


class TestExportProfilesYaml:
    """Export: 0 profil, 1 profil, N profils (6.1)."""

    @pytest.mark.asyncio
    async def test_export_zero_profiles(self):
        with (
            patch("app.services.profile_export_import_service.profile_repository.get_all", new_callable=AsyncMock) as mock_get_all,
            patch("app.services.profile_export_import_service.profile_repository.get_by_id", new_callable=AsyncMock),
            patch("app.services.profile_export_import_service.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock),
            patch("app.services.profile_export_import_service.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock),
        ):
            mock_get_all.return_value = []
            content = await profile_export_import_service.export_profiles_yaml()
        data = yaml.safe_load(content.decode("utf-8"))
        assert data == {"profiles": []}
        assert isinstance(content, bytes)

    @pytest.mark.asyncio
    async def test_export_one_profile_with_patterns(
        self, profile_list_item, profile_response, actions_perm_pattern, targets_perm_pattern
    ):
        with (
            patch("app.services.profile_export_import_service.profile_repository.get_all", new_callable=AsyncMock) as mock_get_all,
            patch("app.services.profile_export_import_service.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id,
            patch("app.services.profile_export_import_service.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_actions,
            patch("app.services.profile_export_import_service.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock) as mock_targets,
        ):
            mock_get_all.return_value = [profile_list_item]
            mock_get_by_id.return_value = profile_response
            mock_actions.return_value = actions_perm_pattern
            mock_targets.return_value = targets_perm_pattern

            content = await profile_export_import_service.export_profiles_yaml()
        data = yaml.safe_load(content.decode("utf-8"))
        assert len(data["profiles"]) == 1
        p = data["profiles"][0]
        assert p["name"] == "Assurance"
        assert p["description"] == "Equipe assurance"
        assert p["ad_group"] == "GRP-IDP-ASSURANCE"
        assert p["is_admin"] is False
        assert p["is_auditor"] is False
        assert p["actions"] == {"type": "pattern", "patterns": ["tag:oracle", "tag:provisioning"]}
        assert p["targets"] == {"type": "pattern", "patterns": ["assurance-*"]}
        assert p["environments"] == ["DEV", "STAGING"]

    @pytest.mark.asyncio
    async def test_export_one_profile_all_permissions(self, profile_list_item, profile_response):
        with (
            patch("app.services.profile_export_import_service.profile_repository.get_all", new_callable=AsyncMock) as mock_get_all,
            patch("app.services.profile_export_import_service.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id,
            patch("app.services.profile_export_import_service.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_actions,
            patch("app.services.profile_export_import_service.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock) as mock_targets,
        ):
            mock_get_all.return_value = [profile_list_item]
            mock_get_by_id.return_value = profile_response
            mock_actions.return_value = None
            mock_targets.return_value = None

            content = await profile_export_import_service.export_profiles_yaml()
        data = yaml.safe_load(content.decode("utf-8"))
        assert len(data["profiles"]) == 1
        p = data["profiles"][0]
        assert p["actions"] == {"type": "all"}
        assert p["targets"] == {"type": "all"}
        assert p["environments"] == []

    @pytest.mark.asyncio
    async def test_export_n_profiles_with_list_type(self):
        from app.models.profile import (
            ProfileListItem,
            ProfileResponse,
            ProfileActionPermissionsResponse,
            ProfileTargetPermissionsResponse,
        )
        items = [
            ProfileListItem(id=1, name="P1", ad_group="G1", permission_count=0, created_at=datetime(2026, 1, 28)),
            ProfileListItem(id=2, name="P2", ad_group="G2", permission_count=0, created_at=datetime(2026, 1, 28)),
        ]
        full1 = ProfileResponse(id=1, name="P1", description="D1", ad_group="G1", is_admin=False, is_auditor=False, created_at=datetime(2026, 1, 28), updated_at=datetime(2026, 1, 28))
        full2 = ProfileResponse(id=2, name="P2", description=None, ad_group="G2", is_admin=True, is_auditor=False, created_at=datetime(2026, 1, 28), updated_at=datetime(2026, 1, 28))
        actions_list = ProfileActionPermissionsResponse(actions_type="list", action_ids=[5, 12], tag_patterns=[], environments=["PROD"])
        targets_list = ProfileTargetPermissionsResponse(targets_type="list", target_names=["srv-01"], target_patterns=[])

        with (
            patch("app.services.profile_export_import_service.profile_repository.get_all", new_callable=AsyncMock) as mock_get_all,
            patch("app.services.profile_export_import_service.profile_repository.get_by_id", new_callable=AsyncMock) as mock_get_by_id,
            patch("app.services.profile_export_import_service.profile_action_permission_repository.get_actions_permissions", new_callable=AsyncMock) as mock_actions,
            patch("app.services.profile_export_import_service.profile_target_permission_repository.get_target_permissions", new_callable=AsyncMock) as mock_targets,
        ):
            mock_get_all.return_value = items
            mock_get_by_id.side_effect = [full1, full2]
            mock_actions.side_effect = [actions_list, actions_list]
            mock_targets.side_effect = [targets_list, targets_list]

            content = await profile_export_import_service.export_profiles_yaml()
        data = yaml.safe_load(content.decode("utf-8"))
        assert len(data["profiles"]) == 2
        assert data["profiles"][0]["name"] == "P1"
        assert data["profiles"][0]["actions"] == {"type": "list", "list": [5, 12]}
        assert data["profiles"][0]["targets"] == {"type": "list", "list": ["srv-01"]}
        assert data["profiles"][1]["name"] == "P2"
        assert data["profiles"][1]["is_admin"] is True


class TestImportProfilesYaml:
    """Import: valid upsert, invalid syntax, invalid schema (6.1)."""

    @pytest.mark.asyncio
    async def test_import_invalid_syntax(self):
        """Real YAML parsing test - invalid syntax should fail without mocks."""
        from app.core.exceptions import InvalidStateError
        with pytest.raises(InvalidStateError) as exc_info:
            await profile_export_import_service.import_profiles_yaml(b"not: valid: yaml: [")
        assert exc_info.value.code == "INVALID_YAML_SYNTAX"
        assert "error" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_import_invalid_syntax_unclosed_bracket(self):
        """Real YAML parsing test - unclosed bracket."""
        from app.core.exceptions import InvalidStateError
        with pytest.raises(InvalidStateError) as exc_info:
            await profile_export_import_service.import_profiles_yaml(b"profiles: [")
        assert exc_info.value.code == "INVALID_YAML_SYNTAX"

    @pytest.mark.asyncio
    async def test_import_empty_file(self):
        from app.core.exceptions import InvalidStateError
        with pytest.raises(InvalidStateError) as exc_info:
            await profile_export_import_service.import_profiles_yaml(b"")
        assert exc_info.value.code in ("INVALID_YAML_SYNTAX", "INVALID_YAML_SCHEMA")

    @pytest.mark.asyncio
    async def test_import_duplicate_names_in_yaml(self):
        """Duplicate profile names within the same YAML should fail validation."""
        from app.core.exceptions import InvalidStateError
        yaml_content = """
profiles:
  - name: DuplicateName
    ad_group: GRP-1
    actions:
      type: all
    targets:
      type: all
  - name: DuplicateName
    ad_group: GRP-2
    actions:
      type: all
    targets:
      type: all
"""
        with pytest.raises(InvalidStateError) as exc_info:
            await profile_export_import_service.import_profiles_yaml(yaml_content.encode("utf-8"))
        assert exc_info.value.code == "INVALID_YAML_SCHEMA"
        assert "doublon" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_import_invalid_schema_no_profiles_key(self):
        from app.core.exceptions import InvalidStateError
        with pytest.raises(InvalidStateError) as exc_info:
            await profile_export_import_service.import_profiles_yaml(b"other: value\n")
        assert exc_info.value.code == "INVALID_YAML_SCHEMA"

    @pytest.mark.asyncio
    async def test_import_valid_creates_one_profile(self):
        from app.models.profile import ProfileResponse
        from datetime import datetime
        yaml_content = """
profiles:
  - name: NewProfile
    ad_group: GRP-NEW
    actions:
      type: pattern
      patterns: ["tag:x"]
    targets:
      type: pattern
      patterns: ["t-*"]
"""
        with (
            patch("app.services.profile_export_import_service.profile_repository.get_by_name", new_callable=AsyncMock) as mock_get_by_name,
            patch("app.services.profile_export_import_service.profile_repository.create", new_callable=AsyncMock) as mock_create,
            patch("app.services.profile_export_import_service.profile_action_permission_repository.set_actions_permissions", new_callable=AsyncMock),
            patch("app.services.profile_export_import_service.profile_target_permission_repository.set_target_permissions", new_callable=AsyncMock),
        ):
            mock_get_by_name.return_value = None
            mock_create.return_value = ProfileResponse(
                id=42, name="NewProfile", description=None, ad_group="GRP-NEW",
                is_admin=False, is_auditor=False,
                created_at=datetime(2026, 1, 28), updated_at=datetime(2026, 1, 28),
            )
            created, updated = await profile_export_import_service.import_profiles_yaml(yaml_content.encode("utf-8"))
        assert created == 1
        assert updated == 0
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_valid_updates_existing_by_name(self):
        from app.models.profile import ProfileResponse
        from datetime import datetime
        yaml_content = """
profiles:
  - name: Existing
    description: Updated desc
    ad_group: GRP-EXISTING
    is_admin: true
    actions:
      type: list
      list: [1, 2]
    targets:
      type: list
      list: ["srv-a"]
    environments: [PROD]
"""
        existing = ProfileResponse(
            id=10, name="Existing", description="Old", ad_group="GRP-EXISTING",
            is_admin=False, is_auditor=False,
            created_at=datetime(2026, 1, 28), updated_at=datetime(2026, 1, 28),
        )
        with (
            patch("app.services.profile_export_import_service.profile_repository.get_by_name", new_callable=AsyncMock) as mock_get_by_name,
            patch("app.services.profile_export_import_service.profile_repository.update", new_callable=AsyncMock) as mock_update,
            patch("app.services.profile_export_import_service.profile_action_permission_repository.set_actions_permissions", new_callable=AsyncMock),
            patch("app.services.profile_export_import_service.profile_target_permission_repository.set_target_permissions", new_callable=AsyncMock),
        ):
            mock_get_by_name.return_value = existing
            created, updated = await profile_export_import_service.import_profiles_yaml(yaml_content.encode("utf-8"))
        assert created == 0
        assert updated == 1
        mock_update.assert_called_once()
