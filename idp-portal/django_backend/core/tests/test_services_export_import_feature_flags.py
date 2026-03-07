"""
Tests for core/services_export_import.py (FeatureFlags).
Story 64.2 - AC#11: export, import create/update/unchanged, round-trip,
missing flag_key, envelope invalide, transaction rollback.
"""

import yaml
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.exceptions import InvalidStateError
from core.models import FeatureFlag
from core.services_export_import import export_feature_flags_yaml, import_feature_flags_yaml


def _make_flags_yaml(flags, kind="FeatureFlags", api_version="idp/v1", metadata=None):
    """Helper to build feature flags YAML bytes."""
    if metadata is None:
        metadata = {}
    data = {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": metadata,
        "spec": flags,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


def _flag_spec(flag_key="my_flag", enabled=True, rollout_percent=100, description="Desc"):
    return {
        "flag_key": flag_key,
        "enabled": enabled,
        "rollout_percent": rollout_percent,
        "description": description,
    }


class ExportFeatureFlagsYamlTests(TestCase):
    def setUp(self):
        FeatureFlag.objects.create(
            flag_key="new_workflow_builder", enabled=True, rollout_percent=100,
            description="Enable new visual workflow builder",
        )
        FeatureFlag.objects.create(
            flag_key="inventory_multi_table", enabled=False, rollout_percent=0,
            description="Enable multi-table inventory support",
        )

    def test_export_returns_bytes(self):
        self.assertIsInstance(export_feature_flags_yaml(), bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "FeatureFlags")

    def test_export_spec_contains_all_flags(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        keys = [f["flag_key"] for f in parsed["spec"]]
        self.assertIn("new_workflow_builder", keys)
        self.assertIn("inventory_multi_table", keys)

    def test_export_spec_dicts_have_required_fields(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        for item in parsed["spec"]:
            self.assertIn("flag_key", item)
            self.assertIn("enabled", item)
            self.assertIn("rollout_percent", item)
            self.assertIn("description", item)

    def test_export_enabled_is_bool(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        flag = next(f for f in parsed["spec"] if f["flag_key"] == "new_workflow_builder")
        self.assertIsInstance(flag["enabled"], bool)
        self.assertTrue(flag["enabled"])

    def test_export_ordered_by_flag_key(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        keys = [f["flag_key"] for f in parsed["spec"]]
        self.assertEqual(keys, sorted(keys))

    def test_export_envelope_contains_metadata(self):
        parsed = yaml.safe_load(export_feature_flags_yaml())
        self.assertIn("metadata", parsed)
        self.assertIsInstance(parsed["metadata"], dict)

    def test_export_empty_db_returns_empty_spec(self):
        FeatureFlag.objects.all().delete()
        parsed = yaml.safe_load(export_feature_flags_yaml())
        self.assertEqual(parsed["spec"], [])


class ImportFeatureFlagsCreateTests(TestCase):

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_create(self, mock_audit):
        content = _make_flags_yaml([_flag_spec("new_workflow_builder")])
        created, updated, unchanged = import_feature_flags_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertTrue(FeatureFlag.objects.filter(flag_key="new_workflow_builder").exists())

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_create_multiple(self, mock_audit):
        content = _make_flags_yaml([
            _flag_spec("flag_a"),
            _flag_spec("flag_b", enabled=False, rollout_percent=0),
        ])
        created, updated, unchanged = import_feature_flags_yaml(content)
        self.assertEqual(created, 2)
        self.assertEqual(FeatureFlag.objects.count(), 2)

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_sets_fields_correctly(self, mock_audit):
        content = _make_flags_yaml([
            _flag_spec("my_flag", enabled=False, rollout_percent=50, description="Hello")
        ])
        import_feature_flags_yaml(content)
        flag = FeatureFlag.objects.get(flag_key="my_flag")
        self.assertFalse(flag.enabled)
        self.assertEqual(flag.rollout_percent, 50)
        self.assertEqual(flag.description, "Hello")


class ImportFeatureFlagsUpdateTests(TestCase):
    def setUp(self):
        FeatureFlag.objects.create(
            flag_key="my_flag", enabled=False, rollout_percent=0,
            description="Old description",
        )

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_updates_existing(self, mock_audit):
        content = _make_flags_yaml([
            _flag_spec("my_flag", enabled=True, rollout_percent=100, description="New description")
        ])
        created, updated, unchanged = import_feature_flags_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(unchanged, 0)
        flag = FeatureFlag.objects.get(flag_key="my_flag")
        self.assertTrue(flag.enabled)
        self.assertEqual(flag.rollout_percent, 100)
        self.assertEqual(flag.description, "New description")

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_unchanged(self, mock_audit):
        content = _make_flags_yaml([
            _flag_spec("my_flag", enabled=False, rollout_percent=0, description="Old description")
        ])
        created, updated, unchanged = import_feature_flags_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_updated_by_set_on_create(self, mock_audit):
        user = MagicMock()
        user.username = "cyrille"
        user.id = 42
        content = _make_flags_yaml([_flag_spec("new_flag")])
        created, updated, unchanged = import_feature_flags_yaml(content, user=user)
        self.assertEqual(created, 1)
        flag = FeatureFlag.objects.get(flag_key="new_flag")
        self.assertEqual(flag.updated_by, "cyrille")

    @patch("core.services_export_import.AuditService.create_entry")
    def test_import_updated_by_set_when_user_provided(self, mock_audit):
        user = MagicMock()
        user.username = "cyrille"
        user.id = 42
        content = _make_flags_yaml([
            _flag_spec("my_flag", enabled=True, rollout_percent=100, description="Updated")
        ])
        import_feature_flags_yaml(content, user=user)
        flag = FeatureFlag.objects.get(flag_key="my_flag")
        self.assertEqual(flag.updated_by, "cyrille")


class ImportFeatureFlagsRoundTripTests(TestCase):

    @patch("core.services_export_import.AuditService.create_entry")
    def test_round_trip_idempotent(self, mock_audit):
        import_feature_flags_yaml(_make_flags_yaml([
            _flag_spec("flag_a"),
            _flag_spec("flag_b", enabled=False, rollout_percent=0),
        ]))
        exported = export_feature_flags_yaml()
        created2, updated2, unchanged2 = import_feature_flags_yaml(exported)
        self.assertEqual(created2, 0)
        self.assertEqual(updated2, 0)
        self.assertEqual(unchanged2, 2)

    @patch("core.services_export_import.AuditService.create_entry")
    def test_round_trip_yaml_identical(self, mock_audit):
        content = _make_flags_yaml([_flag_spec("flag_a")])
        import_feature_flags_yaml(content)
        first_export = export_feature_flags_yaml()
        import_feature_flags_yaml(first_export)
        second_export = export_feature_flags_yaml()
        self.assertEqual(first_export, second_export)


class ImportFeatureFlagsValidationTests(TestCase):

    def test_missing_flag_key_raises(self):
        content = _make_flags_yaml([{"enabled": True, "rollout_percent": 100}])
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "MISSING_FLAG_KEY")

    def test_empty_flag_key_raises(self):
        content = _make_flags_yaml([_flag_spec(""), ])
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "MISSING_FLAG_KEY")

    def test_whitespace_flag_key_raises(self):
        content = _make_flags_yaml([_flag_spec("   ")])
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "MISSING_FLAG_KEY")

    def test_wrong_kind_raises(self):
        content = _make_flags_yaml([_flag_spec()], kind="Tags")
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_invalid_api_version_raises(self):
        content = _make_flags_yaml([_flag_spec()], api_version="idp/v2")
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_API_VERSION")

    def test_missing_metadata_raises(self):
        data = {"apiVersion": "idp/v1", "kind": "FeatureFlags", "spec": [_flag_spec()]}
        content = yaml.dump(data).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_feature_flags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")


class ImportFeatureFlagsTransactionTests(TestCase):

    @patch("core.services_export_import.AuditService.create_entry")
    def test_transaction_rollback_on_audit_error(self, mock_audit):
        mock_audit.side_effect = Exception("Simulated audit failure")
        content = _make_flags_yaml([_flag_spec("my_flag")])
        with self.assertRaises(Exception):
            import_feature_flags_yaml(content)
        self.assertFalse(FeatureFlag.objects.filter(flag_key="my_flag").exists())

    @patch("core.services_export_import.AuditService.create_entry")
    def test_transaction_rollback_on_validation_error(self, mock_audit):
        content = _make_flags_yaml([
            _flag_spec("valid_flag"),
            {"enabled": True},  # missing flag_key → raises mid-loop
        ])
        with self.assertRaises(InvalidStateError):
            import_feature_flags_yaml(content)
        self.assertFalse(FeatureFlag.objects.filter(flag_key="valid_flag").exists())


class ImportFeatureFlagsAuditTests(TestCase):

    @patch("core.services_export_import.AuditService.create_entry")
    def test_audit_called_with_correct_params(self, mock_audit):
        from core.models import AuditActionType, AuditEntityType
        content = _make_flags_yaml([_flag_spec("my_flag")])
        import_feature_flags_yaml(content)
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args[1]
        self.assertEqual(kwargs["action_type"], AuditActionType.CONFIG_SYNC_FEATURE_FLAGS_IMPORT)
        self.assertEqual(kwargs["entity_type"], AuditEntityType.FEATURE_FLAG)
        self.assertEqual(kwargs["entity_id"], 0)
        self.assertEqual(kwargs["details"]["source"], "yaml_import")
        self.assertEqual(kwargs["details"]["created"], 1)
        self.assertEqual(kwargs["details"]["updated"], 0)
        self.assertEqual(kwargs["details"]["unchanged"], 0)

    @patch("core.services_export_import.AuditService.create_entry")
    def test_audit_user_id_set_from_user(self, mock_audit):
        user = MagicMock()
        user.id = 99
        user.username = "cyrille"
        content = _make_flags_yaml([_flag_spec("my_flag")])
        import_feature_flags_yaml(content, user=user)
        kwargs = mock_audit.call_args[1]
        self.assertEqual(kwargs["user_id"], "99")
