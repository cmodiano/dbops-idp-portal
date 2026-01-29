"""Tests for profile YAML import models (Story 2.13, AC5, Task 1)."""

import pytest
from pydantic import ValidationError

from app.models.profile_import import (
    ProfileYamlActions,
    ProfileYamlTargets,
    ProfileYamlItem,
    ProfilesYamlImport,
)


class TestProfileYamlActions:
    """1.1 — actions type + patterns or list validation."""

    def test_valid_pattern(self):
        data = {"type": "pattern", "patterns": ["tag:oracle", "tag:provisioning"]}
        obj = ProfileYamlActions.model_validate(data)
        assert obj.type == "pattern"
        assert obj.patterns == ["tag:oracle", "tag:provisioning"]
        assert obj.action_ids is None

    def test_valid_list(self):
        data = {"type": "list", "list": [5, 12, 23]}
        obj = ProfileYamlActions.model_validate(data)
        assert obj.type == "list"
        assert obj.action_ids == [5, 12, 23]
        assert obj.patterns is None

    def test_pattern_requires_patterns(self):
        with pytest.raises(ValidationError) as exc_info:
            ProfileYamlActions.model_validate({"type": "pattern"})
        assert "patterns" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_list_requires_list(self):
        with pytest.raises(ValidationError) as exc_info:
            ProfileYamlActions.model_validate({"type": "list"})
        err = str(exc_info.value).lower()
        assert "list" in err or "action_ids" in err or "required" in err

    def test_type_all_valid(self):
        data = {"type": "all"}
        obj = ProfileYamlActions.model_validate(data)
        assert obj.type == "all"
        assert obj.patterns is None
        assert obj.action_ids is None


class TestProfileYamlTargets:
    """1.1 — targets type + patterns or list validation."""

    def test_valid_pattern(self):
        data = {"type": "pattern", "patterns": ["assurance-*"]}
        obj = ProfileYamlTargets.model_validate(data)
        assert obj.type == "pattern"
        assert obj.patterns == ["assurance-*"]
        assert obj.target_names is None

    def test_valid_list(self):
        data = {"type": "list", "list": ["assurance-srv-01", "assurance-srv-02"]}
        obj = ProfileYamlTargets.model_validate(data)
        assert obj.type == "list"
        assert obj.target_names == ["assurance-srv-01", "assurance-srv-02"]
        assert obj.patterns is None

    def test_pattern_requires_patterns(self):
        with pytest.raises(ValidationError):
            ProfileYamlTargets.model_validate({"type": "pattern"})

    def test_list_requires_list(self):
        with pytest.raises(ValidationError):
            ProfileYamlTargets.model_validate({"type": "list"})

    def test_type_all_valid(self):
        data = {"type": "all"}
        obj = ProfileYamlTargets.model_validate(data)
        assert obj.type == "all"
        assert obj.patterns is None
        assert obj.target_names is None


class TestProfileYamlItem:
    """1.1 — full profile item: name, description, ad_group, is_admin, is_auditor, actions, targets, environments."""

    def test_valid_full(self):
        data = {
            "name": "Assurance",
            "description": "Equipe assurance",
            "ad_group": "GRP-IDP-ASSURANCE",
            "is_admin": False,
            "is_auditor": False,
            "actions": {"type": "pattern", "patterns": ["tag:oracle", "tag:provisioning"]},
            "targets": {"type": "pattern", "patterns": ["assurance-*"]},
            "environments": ["DEV", "STAGING"],
        }
        obj = ProfileYamlItem.model_validate(data)
        assert obj.name == "Assurance"
        assert obj.description == "Equipe assurance"
        assert obj.ad_group == "GRP-IDP-ASSURANCE"
        assert obj.is_admin is False
        assert obj.is_auditor is False
        assert obj.actions.type == "pattern"
        assert obj.targets.type == "pattern"
        assert obj.environments == ["DEV", "STAGING"]

    def test_valid_minimal(self):
        data = {
            "name": "Minimal",
            "ad_group": "GRP-MIN",
            "actions": {"type": "list", "list": [1, 2]},
            "targets": {"type": "list", "list": ["srv-01"]},
        }
        obj = ProfileYamlItem.model_validate(data)
        assert obj.name == "Minimal"
        assert obj.description is None
        assert obj.is_admin is False
        assert obj.is_auditor is False
        assert obj.environments == []

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ProfileYamlItem.model_validate({
                "ad_group": "GRP-X",
                "actions": {"type": "pattern", "patterns": ["x"]},
                "targets": {"type": "pattern", "patterns": ["y"]},
            })

    def test_ad_group_required(self):
        with pytest.raises(ValidationError):
            ProfileYamlItem.model_validate({
                "name": "X",
                "actions": {"type": "pattern", "patterns": ["x"]},
                "targets": {"type": "pattern", "patterns": ["y"]},
            })


class TestProfilesYamlImport:
    """1.2 — root model with profiles: list[ProfileYamlItem]."""

    def test_valid_one_profile(self):
        data = {
            "profiles": [
                {
                    "name": "A",
                    "ad_group": "GRP-A",
                    "actions": {"type": "pattern", "patterns": ["tag:a"]},
                    "targets": {"type": "pattern", "patterns": ["a-*"]},
                }
            ]
        }
        obj = ProfilesYamlImport.model_validate(data)
        assert len(obj.profiles) == 1
        assert obj.profiles[0].name == "A"

    def test_valid_multiple_profiles(self):
        data = {
            "profiles": [
                {"name": "P1", "ad_group": "G1", "actions": {"type": "list", "list": [1]}, "targets": {"type": "list", "list": ["t1"]}},
                {"name": "P2", "ad_group": "G2", "actions": {"type": "pattern", "patterns": ["p"]}, "targets": {"type": "pattern", "patterns": ["t*"]}},
            ]
        }
        obj = ProfilesYamlImport.model_validate(data)
        assert len(obj.profiles) == 2
        assert obj.profiles[0].name == "P1"
        assert obj.profiles[1].name == "P2"

    def test_empty_profiles_allowed(self):
        data = {"profiles": []}
        obj = ProfilesYamlImport.model_validate(data)
        assert obj.profiles == []

    def test_profiles_required(self):
        with pytest.raises(ValidationError):
            ProfilesYamlImport.model_validate({})
