"""
Tests for profiles export/import YAML service functions.
Story 20.5 / Story 64.7: Covers all functions in profiles/services_export_import.py.
"""

import pytest
import yaml
from django.test import TestCase

from catalog.models import Action
from core.exceptions import InvalidStateError
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from profiles.services_export_import import (
    _build_actions_block,
    _build_targets_block,
    _resolve_action_ids_to_names,
    _resolve_action_names_to_ids,
    _validate_yaml_schema,
    _yaml_item_to_action_payload,
    _yaml_item_to_target_payload,
    export_profile_yaml,
    export_profiles_yaml,
    import_profiles_yaml,
)


# ──────────────────────────────────────────────────────────────────
# _build_actions_block
# ──────────────────────────────────────────────────────────────────

class TestBuildActionsBlock(TestCase):
    """Tests for _build_actions_block() — now uses action_names, not IDs."""

    def test_all_type(self):
        result = _build_actions_block("all", None, None)
        self.assertEqual(result, {"type": "all"})

    def test_pattern_type(self):
        result = _build_actions_block("pattern", None, ["oracle*"])
        self.assertEqual(result, {"type": "pattern", "patterns": ["oracle*"]})

    def test_pattern_type_none_patterns(self):
        result = _build_actions_block("pattern", None, None)
        self.assertEqual(result, {"type": "pattern", "patterns": []})

    def test_list_type_with_names(self):
        result = _build_actions_block("list", ["deploy-oracle", "patch-oracle"], None)
        self.assertEqual(result, {"type": "list", "action_names": ["deploy-oracle", "patch-oracle"]})

    def test_list_type_none_names(self):
        result = _build_actions_block("list", None, None)
        self.assertEqual(result, {"type": "list", "action_names": []})


# ──────────────────────────────────────────────────────────────────
# _build_targets_block
# ──────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────
# _yaml_item_to_action_payload
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestYamlItemToActionPayload(TestCase):
    """Tests for _yaml_item_to_action_payload()."""

    def test_all_type(self):
        item = {"actions": {"type": "all"}, "environments": ["production"]}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "all")
        self.assertEqual(result["environments"], ["production"])

    def test_list_type_with_ids_backward_compat(self):
        """Old flat format: actions.list with integer IDs still works."""
        item = {"actions": {"type": "list", "list": [1, 2]}}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "list")
        self.assertEqual(result["action_ids"], [1, 2])

    def test_list_type_with_action_names(self):
        """New format: actions.action_names resolved to IDs via DB."""
        action = Action.objects.create(name="oracle-patching-quarterly")
        item = {"actions": {"type": "list", "action_names": ["oracle-patching-quarterly"]}}
        result = _yaml_item_to_action_payload(item)
        self.assertEqual(result["actions_type"], "list")
        self.assertEqual(result["action_ids"], [action.id])

    def test_list_type_unknown_action_name_raises(self):
        item = {"actions": {"type": "list", "action_names": ["unknown-action"]}}
        with self.assertRaises(InvalidStateError) as ctx:
            _yaml_item_to_action_payload(item)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")
        self.assertIn("unknown-action", ctx.exception.details["missing_actions"])

    def test_list_type_empty_upgrades_to_all(self):
        item = {"actions": {"type": "list"}}
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


# ──────────────────────────────────────────────────────────────────
# _yaml_item_to_target_payload
# ──────────────────────────────────────────────────────────────────

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

    def test_exclusion_patterns_extracted(self):
        item = {"targets": {"type": "pattern", "patterns": ["PROD-*"], "exclusion_patterns": ["PROD-CRITICAL-*"]}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["exclusion_patterns"], ["PROD-CRITICAL-*"])

    def test_filter_by_attribute_extracted(self):
        item = {"targets": {"type": "all", "filter_by_attribute": {"engine_type": ["oracle"]}}}
        result = _yaml_item_to_target_payload(item)
        self.assertEqual(result["filter_by_attribute"], {"engine_type": ["oracle"]})

    def test_exclusion_patterns_absent_returns_none(self):
        item = {"targets": {"type": "all"}}
        result = _yaml_item_to_target_payload(item)
        self.assertIsNone(result["exclusion_patterns"])

    def test_filter_by_attribute_absent_returns_none(self):
        item = {"targets": {"type": "all"}}
        result = _yaml_item_to_target_payload(item)
        self.assertIsNone(result["filter_by_attribute"])


# ──────────────────────────────────────────────────────────────────
# _validate_yaml_schema
# ──────────────────────────────────────────────────────────────────

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

    def test_valid_schema_with_action_names(self):
        """action_names key accepted for type=list."""
        parsed = {
            "profiles": [{
                "name": "Test",
                "ad_group": "GRP-TEST",
                "actions": {"type": "list", "action_names": ["deploy-oracle"]},
                "targets": {"type": "all"},
            }]
        }
        _validate_yaml_schema(parsed)  # No exception

    def test_valid_schema_with_legacy_list(self):
        """Legacy list key with IDs still accepted."""
        parsed = {
            "profiles": [{
                "name": "Test",
                "ad_group": "GRP-TEST",
                "actions": {"type": "list", "list": [1, 2]},
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

    def test_actions_list_without_ids_or_names(self):
        """Neither list nor action_names → error."""
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


# ──────────────────────────────────────────────────────────────────
# export_profile_yaml (single, new envelope)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExportProfileYaml(TestCase):
    """Tests for export_profile_yaml() — single profile with IaC envelope."""

    def test_not_found_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_profile_yaml("nonexistent-profile")
        self.assertEqual(ctx.exception.code, "PROFILE_NOT_FOUND")

    def test_envelope_structure(self):
        Profile.objects.create(name="dbops-team", ad_group="GRP-DBOPS", is_approver=1)
        result = export_profile_yaml("dbops-team")
        parsed = yaml.safe_load(result.decode("utf-8"))

        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "Profile")
        self.assertEqual(parsed["metadata"]["name"], "dbops-team")
        self.assertEqual(parsed["metadata"]["ad_group"], "GRP-DBOPS")
        self.assertIn("spec", parsed)
        self.assertTrue(parsed["spec"]["is_approver"])

    def test_description_in_metadata_when_present(self):
        Profile.objects.create(name="desc-profile", ad_group="GRP-D", description="My desc")
        result = export_profile_yaml("desc-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertEqual(parsed["metadata"]["description"], "My desc")

    def test_no_description_omitted(self):
        Profile.objects.create(name="nodesc-profile", ad_group="GRP-ND")
        result = export_profile_yaml("nodesc-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertNotIn("description", parsed["metadata"])

    def test_action_names_in_export_for_list_type(self):
        """AC#3: export uses action_names (not raw IDs) for type=list."""
        profile = Profile.objects.create(name="action-list-profile", ad_group="GRP-AL")
        action1 = Action.objects.create(name="oracle-patching-quarterly")
        action2 = Action.objects.create(name="oracle-provisioning")
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="LIST",
            action_ids_json=f"[{action1.id}, {action2.id}]",
            tag_patterns_json="[]",
            environments_json="[]",
        )

        result = export_profile_yaml("action-list-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))

        actions_block = parsed["spec"]["actions"]
        self.assertEqual(actions_block["type"], "list")
        self.assertIn("action_names", actions_block)
        self.assertNotIn("list", actions_block)
        self.assertEqual(sorted(actions_block["action_names"]), ["oracle-patching-quarterly", "oracle-provisioning"])

    def test_action_names_sorted(self):
        """action_names are alphabetically sorted."""
        profile = Profile.objects.create(name="sorted-actions", ad_group="GRP-SA")
        a1 = Action.objects.create(name="z-action")
        a2 = Action.objects.create(name="a-action")
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="LIST",
            action_ids_json=f"[{a1.id}, {a2.id}]",
            tag_patterns_json="[]",
            environments_json="[]",
        )
        result = export_profile_yaml("sorted-actions")
        parsed = yaml.safe_load(result.decode("utf-8"))
        names = parsed["spec"]["actions"]["action_names"]
        self.assertEqual(names, sorted(names))

    def test_targets_exclusion_patterns_exported(self):
        """AC#2: exclusion_patterns in spec.targets when non-empty."""
        profile = Profile.objects.create(name="excl-profile", ad_group="GRP-EX")
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="PATTERN",
            target_names_json="[]",
            target_patterns_json='["PROD-*"]',
            exclusion_patterns_json='["PROD-CRITICAL-*"]',
        )
        result = export_profile_yaml("excl-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertEqual(parsed["spec"]["targets"]["exclusion_patterns"], ["PROD-CRITICAL-*"])

    def test_targets_filter_by_attribute_exported(self):
        """AC#2: filter_by_attribute in spec.targets when non-None."""
        profile = Profile.objects.create(name="fba-profile", ad_group="GRP-FBA")
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="ALL",
            target_names_json="[]",
            target_patterns_json="[]",
            filter_by_attribute_json='{"engine_type": ["oracle"]}',
        )
        result = export_profile_yaml("fba-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertEqual(parsed["spec"]["targets"]["filter_by_attribute"], {"engine_type": ["oracle"]})

    def test_no_permissions_defaults_to_all(self):
        """Profile without permissions: actions/targets both default to type=all."""
        Profile.objects.create(name="noperm-profile", ad_group="GRP-NP")
        result = export_profile_yaml("noperm-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertEqual(parsed["spec"]["actions"]["type"], "all")
        self.assertEqual(parsed["spec"]["targets"]["type"], "all")

    def test_environments_in_spec(self):
        profile = Profile.objects.create(name="env-profile", ad_group="GRP-ENV")
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="ALL",
            action_ids_json="[]",
            tag_patterns_json="[]",
            environments_json='["production", "staging"]',
        )
        result = export_profile_yaml("env-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertEqual(parsed["spec"]["environments"], ["production", "staging"])

    def test_empty_environments_omitted(self):
        profile = Profile.objects.create(name="noenv-profile", ad_group="GRP-NEV")
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="ALL",
            action_ids_json="[]",
            tag_patterns_json="[]",
            environments_json="[]",
        )
        result = export_profile_yaml("noenv-profile")
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertNotIn("environments", parsed["spec"])


# ──────────────────────────────────────────────────────────────────
# export_profiles_yaml (bulk)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExportProfilesYaml(TestCase):
    """Tests for export_profiles_yaml() — bulk flat format with new fields."""

    def test_export_empty(self):
        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        self.assertIsInstance(parsed["profiles"], list)

    def test_export_with_profile_uses_action_names(self):
        """AC#9: bulk export uses action_names instead of raw IDs."""
        profile = Profile.objects.create(name="BulkTest", ad_group="GRP-BULK", is_approver=1)
        action = Action.objects.create(name="bulk-action")
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="LIST",
            action_ids_json=f"[{action.id}]",
            tag_patterns_json="[]",
            environments_json='["production"]',
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="PATTERN",
            target_names_json="[]",
            target_patterns_json='["srv-*"]',
        )

        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))

        p = next(pr for pr in parsed["profiles"] if pr["name"] == "BulkTest")
        self.assertTrue(p["is_approver"])
        self.assertEqual(p["actions"]["type"], "list")
        self.assertEqual(p["actions"]["action_names"], ["bulk-action"])
        self.assertNotIn("list", p["actions"])
        self.assertEqual(p["targets"]["type"], "pattern")
        self.assertEqual(p["targets"]["patterns"], ["srv-*"])
        self.assertEqual(p["environments"], ["production"])

    def test_export_bulk_includes_exclusion_patterns(self):
        """AC#9: exclusion_patterns exported in targets block."""
        profile = Profile.objects.create(name="BulkExcl", ad_group="GRP-BEXCL")
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="PATTERN",
            target_names_json="[]",
            target_patterns_json='["PROD-*"]',
            exclusion_patterns_json='["PROD-CRITICAL-*"]',
        )
        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        p = next(pr for pr in parsed["profiles"] if pr["name"] == "BulkExcl")
        self.assertEqual(p["targets"]["exclusion_patterns"], ["PROD-CRITICAL-*"])

    def test_export_bulk_includes_filter_by_attribute(self):
        """AC#9: filter_by_attribute exported in targets block."""
        profile = Profile.objects.create(name="BulkFBA", ad_group="GRP-BFBA")
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="ALL",
            target_names_json="[]",
            target_patterns_json="[]",
            filter_by_attribute_json='{"zone": ["prod"]}',
        )
        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        p = next(pr for pr in parsed["profiles"] if pr["name"] == "BulkFBA")
        self.assertEqual(p["targets"]["filter_by_attribute"], {"zone": ["prod"]})

    def test_export_profile_no_permissions(self):
        """Profile without permissions exports with type='all' defaults."""
        Profile.objects.create(name="NoPerm", ad_group="GRP-NP")
        result = export_profiles_yaml()
        parsed = yaml.safe_load(result.decode("utf-8"))
        p = next(pr for pr in parsed["profiles"] if pr["name"] == "NoPerm")
        self.assertEqual(p["actions"]["type"], "all")
        self.assertEqual(p["targets"]["type"], "all")


# ──────────────────────────────────────────────────────────────────
# import_profiles_yaml — flat format (backward compat)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestImportProfilesYaml(TestCase):
    """Tests for import_profiles_yaml() — flat format (backward compat)."""

    def _make_yaml(self, profiles_list):
        return yaml.dump({"profiles": profiles_list}).encode("utf-8")

    def test_import_create_new(self):
        content = self._make_yaml([{
            "name": "New",
            "ad_group": "GRP-NEW",
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        created, updated, unchanged = import_profiles_yaml(content)
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
        created, updated, unchanged = import_profiles_yaml(content)
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
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(b"")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")

    def test_import_invalid_schema(self):
        with self.assertRaises(InvalidStateError):
            import_profiles_yaml(b"not_profiles: true")

    def test_import_multiple_profiles_mixed(self):
        Profile.objects.create(name="Exist", ad_group="GRP-E")
        content = self._make_yaml([
            {"name": "Exist", "ad_group": "GRP-E2", "actions": {"type": "all"}, "targets": {"type": "all"}},
            {"name": "Brand New", "ad_group": "GRP-BN", "actions": {"type": "all"}, "targets": {"type": "all"}},
        ])
        created, updated, unchanged = import_profiles_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)

    def test_import_flat_is_approver(self):
        """AC#7: is_approver imported in flat format."""
        content = self._make_yaml([{
            "name": "ApproverFlat",
            "ad_group": "GRP-APP",
            "is_approver": True,
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="ApproverFlat")
        self.assertEqual(profile.is_approver, 1)

    def test_import_flat_exclusion_patterns(self):
        """AC#6: exclusion_patterns imported in flat format."""
        content = self._make_yaml([{
            "name": "ExclFlat",
            "ad_group": "GRP-EF",
            "actions": {"type": "all"},
            "targets": {"type": "pattern", "patterns": ["PROD-*"], "exclusion_patterns": ["PROD-CRITICAL-*"]},
        }])
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="ExclFlat")
        target_perm = ProfileTargetPermission.objects.get(profile=profile)
        self.assertEqual(target_perm.get_exclusion_patterns(), ["PROD-CRITICAL-*"])

    def test_import_flat_filter_by_attribute(self):
        """AC#6: filter_by_attribute imported in flat format."""
        content = self._make_yaml([{
            "name": "FBAFlat",
            "ad_group": "GRP-FBAF",
            "actions": {"type": "all"},
            "targets": {"type": "all", "filter_by_attribute": {"engine_type": ["oracle"]}},
        }])
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="FBAFlat")
        target_perm = ProfileTargetPermission.objects.get(profile=profile)
        self.assertEqual(target_perm.get_filter_by_attribute(), {"engine_type": ["oracle"]})

    def test_import_mode_param_accepted(self):
        """mode parameter accepted without error."""
        content = self._make_yaml([{
            "name": "ModeTest",
            "ad_group": "GRP-MODE",
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        created, updated, unchanged = import_profiles_yaml(content, mode="additive")
        self.assertEqual(created, 1)

    def test_import_unchanged_when_no_fields_differ(self):
        """Importing a profile with identical data returns unchanged=1, not updated=1."""
        Profile.objects.create(name="Unchanged", ad_group="GRP-UNC", is_admin=False, is_auditor=False, is_approver=False)
        content = self._make_yaml([{
            "name": "Unchanged",
            "ad_group": "GRP-UNC",
            "is_admin": False,
            "is_auditor": False,
            "is_approver": False,
            "actions": {"type": "all"},
            "targets": {"type": "all"},
        }])
        created, updated, unchanged = import_profiles_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)


# ──────────────────────────────────────────────────────────────────
# import_profiles_yaml — envelope format (new)
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestImportProfileEnvelopeFormat(TestCase):
    """Tests for import_profiles_yaml() — new IaC envelope format."""

    def _make_envelope(self, name, ad_group="GRP-TEST", spec=None, description=None):
        metadata = {"name": name, "ad_group": ad_group}
        if description:
            metadata["description"] = description
        doc = {
            "apiVersion": "idp/v1",
            "kind": "Profile",
            "metadata": metadata,
            "spec": spec or {"is_admin": False, "is_auditor": False, "actions": {"type": "all"}, "targets": {"type": "all"}},
        }
        return yaml.dump(doc).encode("utf-8")

    def test_envelope_creates_profile(self):
        """AC#4: envelope format creates a new profile."""
        content = self._make_envelope("envelope-new", ad_group="GRP-ENV")
        created, updated, unchanged = import_profiles_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertTrue(Profile.objects.filter(name="envelope-new").exists())

    def test_envelope_updates_existing_profile(self):
        """AC#4: envelope format updates existing profile."""
        Profile.objects.create(name="envelope-update", ad_group="GRP-OLD")
        content = self._make_envelope("envelope-update", ad_group="GRP-NEW")
        created, updated, unchanged = import_profiles_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        profile = Profile.objects.get(name="envelope-update")
        self.assertEqual(profile.ad_group, "GRP-NEW")

    def test_envelope_is_approver(self):
        """AC#6: is_approver imported from envelope spec."""
        content = self._make_envelope(
            "approver-env",
            spec={"is_admin": False, "is_auditor": False, "is_approver": True,
                  "actions": {"type": "all"}, "targets": {"type": "all"}},
        )
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="approver-env")
        self.assertEqual(profile.is_approver, 1)

    def test_envelope_action_names_resolved(self):
        """AC#5: action_names in envelope resolved to IDs."""
        action = Action.objects.create(name="oracle-patching-quarterly")
        content = self._make_envelope(
            "env-action-names",
            spec={
                "actions": {"type": "list", "action_names": ["oracle-patching-quarterly"]},
                "targets": {"type": "all"},
            },
        )
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="env-action-names")
        action_perm = ProfileActionPermission.objects.get(profile=profile)
        self.assertIn(action.id, action_perm.get_action_ids())

    def test_envelope_unknown_action_name_raises(self):
        """AC#5: unknown action_name raises REF_NOT_FOUND."""
        content = self._make_envelope(
            "env-bad-action",
            spec={"actions": {"type": "list", "action_names": ["nonexistent-action"]}, "targets": {"type": "all"}},
        )
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(content)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")
        self.assertIn("nonexistent-action", ctx.exception.details["missing_actions"])

    def test_envelope_multiple_unknown_action_names(self):
        """AC#5: all missing action names reported."""
        content = self._make_envelope(
            "env-multi-bad",
            spec={"actions": {"type": "list", "action_names": ["missing-1", "missing-2"]}, "targets": {"type": "all"}},
        )
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(content)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")
        missing = ctx.exception.details["missing_actions"]
        self.assertIn("missing-1", missing)
        self.assertIn("missing-2", missing)

    def test_envelope_exclusion_patterns_imported(self):
        """AC#6: exclusion_patterns in spec.targets imported."""
        content = self._make_envelope(
            "env-excl",
            spec={
                "actions": {"type": "all"},
                "targets": {"type": "pattern", "patterns": ["PROD-*"], "exclusion_patterns": ["PROD-CRITICAL-*"]},
            },
        )
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="env-excl")
        target_perm = ProfileTargetPermission.objects.get(profile=profile)
        self.assertEqual(target_perm.get_exclusion_patterns(), ["PROD-CRITICAL-*"])

    def test_envelope_filter_by_attribute_imported(self):
        """AC#6: filter_by_attribute in spec.targets imported."""
        content = self._make_envelope(
            "env-fba",
            spec={
                "actions": {"type": "all"},
                "targets": {"type": "all", "filter_by_attribute": {"engine_type": ["oracle"]}},
            },
        )
        import_profiles_yaml(content)
        profile = Profile.objects.get(name="env-fba")
        target_perm = ProfileTargetPermission.objects.get(profile=profile)
        self.assertEqual(target_perm.get_filter_by_attribute(), {"engine_type": ["oracle"]})

    def test_envelope_missing_ad_group_raises(self):
        """Envelope without ad_group raises INVALID_METADATA."""
        doc = {
            "apiVersion": "idp/v1",
            "kind": "Profile",
            "metadata": {"name": "no-ad-group"},
            "spec": {"actions": {"type": "all"}, "targets": {"type": "all"}},
        }
        content = yaml.dump(doc).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")

    def test_envelope_wrong_kind_raises(self):
        """validate_envelope rejects wrong kind."""
        doc = {
            "apiVersion": "idp/v1",
            "kind": "Action",
            "metadata": {"name": "test"},
            "spec": {},
        }
        content = yaml.dump(doc).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(content)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_envelope_missing_name_raises(self):
        doc = {
            "apiVersion": "idp/v1",
            "kind": "Profile",
            "metadata": {"ad_group": "GRP-TEST"},
            "spec": {},
        }
        content = yaml.dump(doc).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_profiles_yaml(content)
        self.assertEqual(ctx.exception.code, "MISSING_NAME")


# ──────────────────────────────────────────────────────────────────
# Round-trip test
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRoundTrip(TestCase):
    """AC#8: export_profile_yaml → import_profiles_yaml produces identical profile."""

    def test_round_trip_all_fields(self):
        """Full round-trip: create profile, export, import, verify identical."""
        action1 = Action.objects.create(name="rt-action-alpha")
        action2 = Action.objects.create(name="rt-action-beta")

        # Create original profile
        profile = Profile.objects.create(
            name="rt-profile",
            ad_group="GRP-RT",
            description="Round-trip test",
            is_admin=0,
            is_auditor=0,
            is_approver=1,
        )
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type="LIST",
            action_ids_json=f"[{action1.id}, {action2.id}]",
            tag_patterns_json="[]",
            environments_json='["production"]',
        )
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type="PATTERN",
            target_names_json="[]",
            target_patterns_json='["PROD-*"]',
            exclusion_patterns_json='["PROD-CRITICAL-*"]',
            filter_by_attribute_json='{"engine_type": ["oracle"]}',
        )

        # Export
        exported = export_profile_yaml("rt-profile")

        # Delete original to test import-as-create
        ProfileActionPermission.objects.filter(profile=profile).delete()
        ProfileTargetPermission.objects.filter(profile=profile).delete()
        profile.delete()

        # Import
        created, updated, unchanged = import_profiles_yaml(exported)
        self.assertEqual(created, 1)

        # Verify
        reimported = Profile.objects.get(name="rt-profile")
        self.assertEqual(reimported.ad_group, "GRP-RT")
        self.assertEqual(reimported.description, "Round-trip test")
        self.assertEqual(reimported.is_approver, 1)

        action_perm = ProfileActionPermission.objects.get(profile=reimported)
        self.assertEqual(action_perm.permission_type, "LIST")
        reimported_ids = sorted(action_perm.get_action_ids())
        self.assertEqual(reimported_ids, sorted([action1.id, action2.id]))

        target_perm = ProfileTargetPermission.objects.get(profile=reimported)
        self.assertEqual(target_perm.permission_type, "PATTERN")
        self.assertEqual(target_perm.get_target_patterns(), ["PROD-*"])
        self.assertEqual(target_perm.get_exclusion_patterns(), ["PROD-CRITICAL-*"])
        self.assertEqual(target_perm.get_filter_by_attribute(), {"engine_type": ["oracle"]})


# ──────────────────────────────────────────────────────────────────
# _resolve_action_ids_to_names / _resolve_action_names_to_ids
# ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestResolveActionHelpers(TestCase):
    """Tests for _resolve_action_ids_to_names and _resolve_action_names_to_ids."""

    def test_resolve_ids_to_names_sorted(self):
        a1 = Action.objects.create(name="z-resolve")
        a2 = Action.objects.create(name="a-resolve")
        result = _resolve_action_ids_to_names([a1.id, a2.id])
        self.assertEqual(result, ["a-resolve", "z-resolve"])

    def test_resolve_ids_orphan_skipped(self):
        """Orphan ID (no corresponding Action) is skipped with a warning."""
        with self.assertLogs("profiles.services_export_import", level="WARNING") as log_ctx:
            result = _resolve_action_ids_to_names([999999])
        self.assertEqual(result, [])
        self.assertTrue(any("action_id_not_found_at_export" in msg for msg in log_ctx.output))

    def test_resolve_ids_empty_list(self):
        result = _resolve_action_ids_to_names([])
        self.assertEqual(result, [])

    def test_resolve_names_to_ids(self):
        a = Action.objects.create(name="named-resolve")
        result = _resolve_action_names_to_ids(["named-resolve"])
        self.assertEqual(result, [a.id])

    def test_resolve_names_unknown_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            _resolve_action_names_to_ids(["does-not-exist"])
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")
        self.assertIn("does-not-exist", ctx.exception.details["missing_actions"])

    def test_resolve_names_partial_missing_reports_all(self):
        Action.objects.create(name="valid-action")
        with self.assertRaises(InvalidStateError) as ctx:
            _resolve_action_names_to_ids(["valid-action", "missing-one", "missing-two"])
        missing = ctx.exception.details["missing_actions"]
        self.assertIn("missing-one", missing)
        self.assertIn("missing-two", missing)
        self.assertNotIn("valid-action", missing)

    def test_resolve_names_empty_list(self):
        result = _resolve_action_names_to_ids([])
        self.assertEqual(result, [])
