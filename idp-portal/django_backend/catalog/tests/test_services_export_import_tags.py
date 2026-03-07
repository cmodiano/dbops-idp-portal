"""
Tests for catalog/services_export_import_tags.py.
Story 64.2 - AC#11: export, import create/unchanged, round-trip,
invalid tag name, envelope invalide.
"""

import yaml
from unittest.mock import patch

from django.test import TestCase

from catalog.models import Tag
from catalog.services_export_import_tags import export_tags_yaml, import_tags_yaml
from core.exceptions import InvalidStateError


def _make_tags_yaml(tags, kind="Tags", api_version="idp/v1", metadata=None):
    """Helper to build tags YAML bytes."""
    if metadata is None:
        metadata = {}
    data = {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": metadata,
        "spec": tags,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


class ExportTagsYamlTests(TestCase):
    def setUp(self):
        Tag.objects.create(name="oracle")
        Tag.objects.create(name="sqlserver")

    def test_export_returns_bytes(self):
        self.assertIsInstance(export_tags_yaml(), bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_tags_yaml())
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "Tags")

    def test_export_spec_is_list_of_strings(self):
        parsed = yaml.safe_load(export_tags_yaml())
        self.assertIsInstance(parsed["spec"], list)
        for item in parsed["spec"]:
            self.assertIsInstance(item, str)

    def test_export_contains_all_tags(self):
        parsed = yaml.safe_load(export_tags_yaml())
        self.assertIn("oracle", parsed["spec"])
        self.assertIn("sqlserver", parsed["spec"])

    def test_export_ordered_by_name(self):
        parsed = yaml.safe_load(export_tags_yaml())
        names = parsed["spec"]
        self.assertEqual(names, sorted(names))

    def test_export_envelope_contains_metadata(self):
        parsed = yaml.safe_load(export_tags_yaml())
        self.assertIn("metadata", parsed)
        self.assertIsInstance(parsed["metadata"], dict)

    def test_export_empty_db_returns_empty_spec(self):
        Tag.objects.all().delete()
        parsed = yaml.safe_load(export_tags_yaml())
        self.assertEqual(parsed["spec"], [])


class ImportTagsYamlCreateTests(TestCase):

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_create(self, mock_audit):
        content = _make_tags_yaml(["oracle", "sqlserver"])
        created, updated, unchanged = import_tags_yaml(content)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertEqual(Tag.objects.count(), 2)

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_unchanged_idempotent(self, mock_audit):
        Tag.objects.create(name="oracle")
        content = _make_tags_yaml(["oracle"])
        created, updated, unchanged = import_tags_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)
        self.assertEqual(Tag.objects.count(), 1)

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_normalizes_case(self, mock_audit):
        content = _make_tags_yaml(["Oracle", "SQLSERVER"])
        import_tags_yaml(content)
        self.assertTrue(Tag.objects.filter(name="oracle").exists())
        self.assertTrue(Tag.objects.filter(name="sqlserver").exists())

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_normalizes_strips_whitespace(self, mock_audit):
        content = _make_tags_yaml(["  oracle  "])
        import_tags_yaml(content)
        self.assertTrue(Tag.objects.filter(name="oracle").exists())

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_mixed_create_and_unchanged(self, mock_audit):
        Tag.objects.create(name="oracle")
        content = _make_tags_yaml(["oracle", "backup"])
        created, updated, unchanged = import_tags_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(unchanged, 1)

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_import_empty_spec_returns_zeros(self, mock_audit):
        content = _make_tags_yaml([])
        created, updated, unchanged = import_tags_yaml(content)
        self.assertEqual((created, updated, unchanged), (0, 0, 0))


class ImportTagsYamlRoundTripTests(TestCase):

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_round_trip_idempotent(self, mock_audit):
        import_tags_yaml(_make_tags_yaml(["oracle", "backup"]))
        exported = export_tags_yaml()
        created2, _, unchanged2 = import_tags_yaml(exported)
        self.assertEqual(created2, 0)
        self.assertEqual(unchanged2, 2)

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_round_trip_yaml_identical(self, mock_audit):
        import_tags_yaml(_make_tags_yaml(["backup", "oracle"]))
        first_export = export_tags_yaml()
        import_tags_yaml(first_export)
        second_export = export_tags_yaml()
        self.assertEqual(first_export, second_export)


class ImportTagsYamlValidationTests(TestCase):

    def test_empty_string_tag_raises(self):
        content = _make_tags_yaml(["oracle", ""])
        with self.assertRaises(InvalidStateError) as ctx:
            import_tags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_TAG_NAME")

    def test_whitespace_only_tag_raises(self):
        content = _make_tags_yaml(["oracle", "   "])
        with self.assertRaises(InvalidStateError) as ctx:
            import_tags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_TAG_NAME")

    def test_wrong_kind_raises(self):
        content = _make_tags_yaml(["oracle"], kind="FeatureFlags")
        with self.assertRaises(InvalidStateError) as ctx:
            import_tags_yaml(content)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_invalid_api_version_raises(self):
        content = _make_tags_yaml(["oracle"], api_version="idp/v2")
        with self.assertRaises(InvalidStateError) as ctx:
            import_tags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_API_VERSION")

    def test_missing_metadata_raises(self):
        data = {"apiVersion": "idp/v1", "kind": "Tags", "spec": ["oracle"]}
        content = yaml.dump(data).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_tags_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")


class ImportTagsYamlTransactionTests(TestCase):

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_transaction_rollback_on_audit_error(self, mock_audit):
        mock_audit.side_effect = Exception("Simulated audit failure")
        content = _make_tags_yaml(["oracle"])
        with self.assertRaises(Exception):
            import_tags_yaml(content)
        self.assertFalse(Tag.objects.filter(name="oracle").exists())


class ImportTagsYamlAuditTests(TestCase):

    @patch("catalog.services_export_import_tags.AuditService.create_entry")
    def test_audit_called_with_correct_params(self, mock_audit):
        from core.models import AuditActionType, AuditEntityType
        content = _make_tags_yaml(["oracle"])
        import_tags_yaml(content)
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args[1]
        self.assertEqual(kwargs["action_type"], AuditActionType.CONFIG_SYNC_TAGS_IMPORT)
        self.assertEqual(kwargs["entity_type"], AuditEntityType.TAGS)
        self.assertEqual(kwargs["entity_id"], 0)
        self.assertEqual(kwargs["details"]["source"], "yaml_import")
        self.assertEqual(kwargs["details"]["created"], 1)
        self.assertEqual(kwargs["details"]["unchanged"], 0)
