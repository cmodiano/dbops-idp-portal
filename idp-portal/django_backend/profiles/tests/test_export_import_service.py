"""
Tests for profiles export/import YAML service functions.
Story 20.5: Covers _build_actions_block, _build_targets_block, _validate_yaml_schema,
_yaml_item_to_action_payload, _yaml_item_to_target_payload, export_profiles_yaml, import_profiles_yaml.
"""

import pytest
import yaml
from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from profiles.services_export_import import (
    _build_actions_block,
    _build_targets_block,
    _yaml_item_to_action_payload,
    _yaml_item_to_target_payload,
    _validate_yaml_schema,
    export_profiles_yaml,
    import_profiles_yaml,
)
from core.exceptions import InvalidStateError


class TestBuildActionsBlock(TestCase):
    """Tests for _build_actions_block()."""

    def test_all_type(self):
        result = _build_actions_block("all", None, None)
        self.assertEqual(result, {"type": "all"})

    def test_pattern_type(self):
        result = _build_actions_block("pattern", None, ["oracle*"])
        self.assertEqual(result, {"type": "pattern", "patterns": ["oracle*"]})

    def test_pattern_type_none_patterns(self):
        result = _build_actions_block("pattern", None, None)
        self.assertEqual(result, {"type": "pattern", "patterns": []})

    def test_list_type(self):
        result = _build_actions_block("list", [1, 2], None)
        self.assertEqual(result, {"type": "list", "list": [1, 2]})

    def test_list_type_none_ids(self):
        result = _build_actions_block("list", None, None)
        self.assertEqual(result, {"type": "list", "list": []})


class TestBuildTargetsBlock(TestCase):
    """Tests for _build_targets_block()."""

    def test_all_type(self):
        result = _build_targets_block("all", None, None)
        self.assertEqual(result, {"type": "all"})

    def test_pattern_type(self):
        result = _build_targets_block("pattern", None, ["srv-*"])
        self.assertEqual(result, {"type": "pattern", "patterns": ["srv-*"]})

    def test_list_type(self):
        result = _build_targets_block("list", ["srv-01"], None)
        self.assertEqual(result, {"type": "list", "list": ["srv-01"]})


class TestYamlItemToActionPayload(TestCase):
    """Tests for _yaml_item_to_action_payload()."""

    def test_all_type(self):
        item = {"actions": {"type": "all"}, "environments": ["production"]}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "all")
        self.assertEqual(result["environments"], ["production"])

    def test_list_type_with_ids(self):
        item = {"actions": {"type": "list", "list": [1, 2]}}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "list")
        self.assertEqual(result["action_ids"], [1, 2])

    def test_list_type_empty_upgrades_to_all(self):
        item = {"actions": {"type": "list", "list": []}}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "all")
        self.assertIsNone(result["action_ids"])

    def test_pattern_type(self):
        item = {"actions": {"type": "pattern", "patterns": ["tag:*"]}}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "pattern")
        self.assertEqual(result["tag_patterns"], ["tag:*"])

    def test_no_actions_block(self):
        item = {}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "all")

    def test_no_environments(self):
        item = {"actions": {"type": "all"}}
        result = _yaml_item_to_action_payload(item)
        self.assertIsNone(result["environments"])


class TestYamlItemToTargetPayload(TestCase):
    """Tests for _yaml_item_to_target_payload()."""

    def test_all_type(self):
        item = {"targets": {"type": "all"}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["targets_type"], "all")

    def test_list_type_with_names(self):
        item = {"targets": {"type": "list", "list": ["srv-01"]}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["targets_type"], "list")
        self.assertEqual(result["target_names"], ["srv-01"])

    def test_list_type_empty_upgrades_to_all(self):
        item = {"targets": {"type": "list", "list": []}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["targets_type"], "all")

    def test_pattern_type(self):
        item = {"targets": {"type": "pattern", "patterns": ["db-*"]}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["targets_type"], "pattern")
        self.assertEqual(result["target_patterns"], ["db-*"])


class TestValidateYamlSchema(TestCase):
    """Tests for _validate_yaml_schema()."""

    def test_valid_schema(self):
        parsed = {
            "profiles": [{
                "name": "Test",
                "ad_group": "GRP-TEST",
                "actions": {"type": "all"},
                "targets": {"type": "all"},
            }]
        }
        _validate_yaml_schema(parsed)  # No exception

    def test_not_dict(self):
        with self.assertRaises(InvalidStateError) as ctx:
            _validate_yaml_schema("not a dict")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SCHEMA")

    def test_missing_profiles_key(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"other": []})

    def test_profiles_not_list(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": "not a list"})

    def test_profile_not_dict(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": ["not a dict"]})

    def test_empty_name(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [{"name": "", "ad_group": "G"}]})

    def test_missing_name(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [{"ad_group": "G"}]})

    def test_empty_ad_group(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [{"name": "N", "ad_group": ""}]})

    def test_duplicate_names(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "A", "ad_group": "G1", "actions": {"type": "all"}, "targets": {"type": "all"}},
                {"name": "a", "ad_group": "G2", "actions": {"type": "all"}, "targets": {"type": "all"}},
            ]})

    def test_missing_actions_block(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "targets": {"type": "all"}},
            ]})

    def test_invalid_actions_type(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "invalid"}, "targets": {"type": "all"}},
            ]})

    def test_actions_list_without_ids(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "list"}, "targets": {"type": "all"}},
            ]})

    def test_actions_pattern_without_patterns(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "pattern"}, "targets": {"type": "all"}},
            ]})

    def test_missing_targets_block(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "all"}},
            ]})

    def test_invalid_targets_type(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "all"}, "targets": {"type": "bad"}},
            ]})

    def test_targets_list_without_names(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "all"}, "targets": {"type": "list"}},
            ]})

    def test_targets_pattern_without_patterns(self):
        with self.assertRaises(InvalidStateError):
            _validate_yaml_schema({"profiles": [
                {"name": "N", "ad_group": "G", "actions": {"type": "all"}, "targets": {"type": "pattern"}},
            ]})


@pytest.mark.django_db
class TestExportProfilesYaml(TestCase):
    """Tests for export_profiles_yaml()."""

    def test_export_empty(self):
        """Export with only conftest-seeded profiles returns those profiles."""
        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        # conftest seeds standard profiles; verify export works without custom profiles
        self.assertIsInstance(parsed["profiles"], list)
        # All exported profiles should be from conftest (no custom ones)
        custom_names = {p["name"] for p in parsed["profiles"]} - {
            "DBOPS", "DBA", "client_business", "dba_infrastructure",
            "AUDITOR", "BUSINESS_USER", "dba_applicatif",
        }
        self.assertEqual(custom_names, set())

    def test_export_with_profile(self):
        baseline_count = Profile.objects.count()
        profile = Profile.objects.create(
            name="Export Test", ad_group="GRP-EXPORT", is_admin=1
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type="LIST",
            action_ids_json="[1,2]", tag_patterns_json="[]", environments_json='["production"]'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type="PATTERN",
            target_names_json="[]", target_patterns_json='["srv-*"]'
        )

        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))

        self.assertEqual(len(parsed["profiles"]), baseline_count + 1)
        p = next(p for p in parsed["profiles"] if p["name"] == "Export Test")
        self.assertTrue(p["is_admin"])
        self.assertEqual(p["actions"]["type"], "list")
        self.assertEqual(p["actions"]["list"], [1, 2])
        self.assertEqual(p["targets"]["type"], "pattern")
        self.assertEqual(p["targets"]["patterns"], ["srv-*"])
        self.assertEqual(p["environments"], ["production"])

    def test_export_profile_no_permissions(self):
        """Profile without permissions exports with type='all' defaults."""
        Profile.objects.create(name="NoPerm", ad_group="GRP-NP")

        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        p = next(p for p in parsed["profiles"] if p["name"] == "NoPerm")
        self.assertEqual(p["actions"]["type"], "all")
        self.assertEqual(p["targets"]["type"], "all")


@pytest.mark.django_db
class TestImportProfilesYaml(TestCase):
    """Tests for import_profiles_yaml()."""

    def _make_yaml(self, profiles_list):
        return yaml.dump({"profiles": profiles_list}).encode("utf-8")

    def test_import_create_new(self):
        content = self._make_yaml([{
            "name": "New",
            "ad_group": "GRP-NEW",
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        created, updated = import_profiles_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertTrue(Profile.objects.filter(name="New").exists())

    def test_import_update_existing(self):
        Profile.objects.create(name="Existing", ad_group="GRP-OLD")
        content = self._make_yaml([{
            "name": "Existing",
            "ad_group": "GRP-UPDATED",
            "is_admin": True,
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        created, updated = import_profiles_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        profile = Profile.objects.get(name="Existing")
        self.assertEqual(profile.ad_group, "GRP-UPDATED")
        self.assertEqual(profile.is_admin, 1)

    def test_import_sets_permissions(self):
        content = self._make_yaml([{
            "name": "WithPerms",
            "ad_group": "GRP-P",
            "actions": {"type": "list", "list": [10, 20]},
            "targets": {"type": "pattern", "patterns": ["db-*"]},
            "environments": ["production", "developpement"],
        }])
        import_profiles_yaml(content)

        profile = Profile.objects.get(name="WithPerms")
        action_perm = ProfileActionPermission.objects.get(profile=profile)
        target_perm = ProfileTargetPermission.objects.get(profile=profile)
        self.assertEqual(action_perm.permission_type, "LIST")
        self.assertEqual(action_perm.get_action_ids(), [10, 20])
        self.assertEqual(target_perm.permission_type, "PATTERN")
        self.assertEqual(target_perm.get_target_patterns(), ["db-*"])

    def test_import_invalid_yaml_syntax(self):
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(b"invalid: yaml: [")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")

    def test_import_empty_yaml(self):
        with self.assertRaises(InvalidStateError):
            import_profiles_yaml(b"")

    def test_import_invalid_schema(self):
        with self.assertRaises(InvalidStateError):
            import_profiles_yaml(b"not_profiles: true")

    def test_import_multiple_profiles_mixed(self):
        Profile.objects.create(name="Exist", ad_group="GRP-E")
        content = self._make_yaml([
            {"name": "Exist", "ad_group": "GRP-E2", "actions": {"type": "all"}, "targets": {"type": "all"}},
            {"name": "Brand New", "ad_group": "GRP-BN", "actions": {"type": "all"}, "targets": {"type": "all"}},
        ])
        created, updated = import_profiles_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)
