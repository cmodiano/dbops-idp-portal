"""
Tests for reference/services_export_import.py.
Story 64.1 - AC#11: export, import create/update/unchanged, round-trip,
type mismatch, envelope invalide, ref_type inconnu, transaction rollback.
"""

import yaml
from unittest.mock import patch

from django.test import TestCase

from core.exceptions import InvalidStateError
from reference.models import RefCategory, RefEngine
from reference.services_export_import import export_reference_yaml, import_reference_yaml


class ReferenceYamlTestMixin:
    """Mixin commun pour construire du YAML de référence dans les tests."""

    def _make_yaml(self, ref_type, spec):
        data = {
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "metadata": {"type": ref_type},
            "spec": spec,
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


class ExportEnginesTests(TestCase):
    def setUp(self):
        RefEngine.objects.create(code="Oracle", label="Oracle Database", display_order=1, is_active=1)
        RefEngine.objects.create(code="SQLServer", label="Microsoft SQL Server", display_order=2, is_active=1, icon_url="/icons/sqlserver.svg")

    def test_returns_bytes(self):
        result = export_reference_yaml("engines")
        self.assertIsInstance(result, bytes)

    def test_valid_yaml_envelope(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "ReferenceData")
        self.assertEqual(parsed["metadata"]["type"], "engines")

    def test_spec_contains_engines(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        codes = [e["code"] for e in parsed["spec"]]
        self.assertIn("Oracle", codes)
        self.assertIn("SQLServer", codes)

    def test_icon_url_included_when_present(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        sqlserver = next(e for e in parsed["spec"] if e["code"] == "SQLServer")
        self.assertEqual(sqlserver["icon_url"], "/icons/sqlserver.svg")

    def test_icon_url_omitted_when_null(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        oracle = next(e for e in parsed["spec"] if e["code"] == "Oracle")
        self.assertNotIn("icon_url", oracle)

    def test_is_active_exported_as_bool(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        oracle = next(e for e in parsed["spec"] if e["code"] == "Oracle")
        self.assertIsInstance(oracle["is_active"], bool)
        self.assertTrue(oracle["is_active"])

    def test_ordered_by_display_order(self):
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        orders = [e["display_order"] for e in parsed["spec"]]
        self.assertEqual(orders, sorted(orders))

    def test_empty_db_returns_empty_spec(self):
        RefEngine.objects.all().delete()
        parsed = yaml.safe_load(export_reference_yaml("engines"))
        self.assertEqual(parsed["spec"], [])


class ExportCategoriesTests(TestCase):
    def setUp(self):
        RefCategory.objects.create(code="Provisioning", label="Provisioning", display_order=1, is_active=1)
        RefCategory.objects.create(code="Decommission", label="Decommission", display_order=2, is_active=0)

    def test_returns_bytes(self):
        result = export_reference_yaml("categories")
        self.assertIsInstance(result, bytes)

    def test_valid_yaml_envelope(self):
        parsed = yaml.safe_load(export_reference_yaml("categories"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["metadata"]["type"], "categories")

    def test_spec_contains_categories(self):
        parsed = yaml.safe_load(export_reference_yaml("categories"))
        codes = [c["code"] for c in parsed["spec"]]
        self.assertIn("Provisioning", codes)
        self.assertIn("Decommission", codes)

    def test_inactive_category_is_active_false(self):
        parsed = yaml.safe_load(export_reference_yaml("categories"))
        decom = next(c for c in parsed["spec"] if c["code"] == "Decommission")
        self.assertFalse(decom["is_active"])


class ExportInvalidRefTypeTests(TestCase):
    def test_invalid_ref_type_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_reference_yaml("unknown_type")
        self.assertEqual(ctx.exception.code, "INVALID_REF_TYPE")


class ImportCreateTests(ReferenceYamlTestMixin, TestCase):

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_import_engines_creates_new(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        created, updated, unchanged = import_reference_yaml(content, "engines")
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertTrue(RefEngine.objects.filter(code="Oracle").exists())

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_import_categories_creates_new(self, mock_audit):
        content = self._make_yaml("categories", [
            {"code": "Provisioning", "label": "Provisioning", "display_order": 1, "is_active": True},
        ])
        created, updated, unchanged = import_reference_yaml(content, "categories")
        self.assertEqual(created, 1)
        self.assertTrue(RefCategory.objects.filter(code="Provisioning").exists())


class ImportUpdateTests(ReferenceYamlTestMixin, TestCase):
    def setUp(self):
        RefEngine.objects.create(code="Oracle", label="Old Label", display_order=1, is_active=1)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_import_updates_existing_engine(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "New Label", "display_order": 1, "is_active": True},
        ])
        created, updated, unchanged = import_reference_yaml(content, "engines")
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(unchanged, 0)
        engine = RefEngine.objects.get(code="Oracle")
        self.assertEqual(engine.label, "New Label")

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_import_unchanged_engine(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Old Label", "display_order": 1, "is_active": True},
        ])
        created, updated, unchanged = import_reference_yaml(content, "engines")
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)


class RoundTripTests(TestCase):
    def setUp(self):
        RefEngine.objects.create(code="Oracle", label="Oracle DB", display_order=1, is_active=1)
        RefEngine.objects.create(code="SQLServer", label="SQL Server", display_order=2, is_active=1, icon_url="/icons/sql.svg")
        RefCategory.objects.create(code="Provisioning", label="Provisioning", display_order=1, is_active=1)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_engines_round_trip(self, mock_audit):
        first_export = export_reference_yaml("engines")
        import_reference_yaml(first_export, "engines")
        second_export = export_reference_yaml("engines")
        self.assertEqual(first_export, second_export)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_categories_round_trip(self, mock_audit):
        first_export = export_reference_yaml("categories")
        import_reference_yaml(first_export, "categories")
        second_export = export_reference_yaml("categories")
        self.assertEqual(first_export, second_export)


class ImportEnvelopeValidationTests(TestCase):
    # Pas de @patch ici : validate_envelope échoue avant tout appel à AuditService

    def test_invalid_api_version_raises(self):
        content = yaml.dump({
            "apiVersion": "idp/v2",
            "kind": "ReferenceData",
            "metadata": {"type": "engines"},
            "spec": [],
        }).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "engines")
        self.assertEqual(ctx.exception.code, "INVALID_API_VERSION")

    def test_invalid_kind_raises(self):
        content = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "UnknownKind",
            "metadata": {"type": "engines"},
            "spec": [],
        }).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "engines")
        self.assertEqual(ctx.exception.code, "INVALID_KIND")

    def test_missing_metadata_raises(self):
        content = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "spec": [],
        }).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "engines")
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")


class ImportMissingCodeTests(ReferenceYamlTestMixin, TestCase):
    """HIGH-2 : item spec sans champ 'code' doit lever InvalidStateError."""

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_missing_code_raises_invalid_state_error(self, mock_audit):
        content = self._make_yaml("engines", [
            {"label": "Sans Code", "display_order": 1, "is_active": True},  # code absent
        ])
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "engines")
        self.assertEqual(ctx.exception.code, "MISSING_CODE")
        self.assertFalse(RefEngine.objects.exists())  # rollback via @transaction.atomic


class ImportIconUrlRemovalTests(ReferenceYamlTestMixin, TestCase):
    """MED-1 : icon_url absent du YAML doit effacer le champ en DB."""

    def setUp(self):
        RefEngine.objects.create(
            code="Oracle", label="Oracle DB", display_order=1, is_active=1,
            icon_url="/icons/oracle.svg",
        )

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_import_without_icon_url_clears_existing(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
            # icon_url absent intentionnellement
        ])
        import_reference_yaml(content, "engines")
        engine = RefEngine.objects.get(code="Oracle")
        self.assertIsNone(engine.icon_url)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_icon_url_removal_breaks_round_trip_without_fix(self, mock_audit):
        """Vérifie que le round-trip après suppression d'icône est cohérent."""
        # Exporter (inclut icon_url), puis modifier YAML pour retirer icon_url
        content_without_icon = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content_without_icon, "engines")
        # Deuxième export ne doit plus inclure icon_url
        second_export = export_reference_yaml("engines")
        parsed = yaml.safe_load(second_export)
        oracle = next(e for e in parsed["spec"] if e["code"] == "Oracle")
        self.assertNotIn("icon_url", oracle)


class ImportTypeMismatchTests(TestCase):
    @patch("reference.services_export_import.AuditService.create_entry")
    def test_type_mismatch_raises(self, mock_audit):
        content = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "metadata": {"type": "categories"},
            "spec": [],
        }).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "engines")
        self.assertEqual(ctx.exception.code, "TYPE_MISMATCH")


class ImportInvalidRefTypeTests(TestCase):
    @patch("reference.services_export_import.AuditService.create_entry")
    def test_unknown_ref_type_raises(self, mock_audit):
        # When both yaml_type and ref_type are "unknown" they match (no TYPE_MISMATCH),
        # so INVALID_REF_TYPE is raised when the Model lookup fails.
        content = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "metadata": {"type": "unknown"},
            "spec": [],
        }).encode("utf-8")
        with self.assertRaises(InvalidStateError) as ctx:
            import_reference_yaml(content, "unknown")
        self.assertEqual(ctx.exception.code, "INVALID_REF_TYPE")


class ImportTransactionRollbackTests(ReferenceYamlTestMixin, TestCase):

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_transaction_rollback_on_error(self, mock_audit):
        """If an error occurs mid-import, no records should be persisted."""
        mock_audit.side_effect = Exception("Simulated audit failure")

        content = self._make_yaml("engines", [
            {"code": "NewEngine", "label": "New", "display_order": 1, "is_active": True},
        ])

        with self.assertRaises(Exception):
            import_reference_yaml(content, "engines")

        # Transaction must have rolled back — no records created
        self.assertFalse(RefEngine.objects.filter(code="NewEngine").exists())


class ImportReferenceSyncTrackingTests(ReferenceYamlTestMixin, TestCase):
    """Story 64.11 - AC#8: Verify last_synced_hash/at are set after import for RefEngine/RefCategory."""

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_create_sets_last_synced_hash(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content, "engines")
        obj = RefEngine.objects.get(code="Oracle")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_create_sets_last_synced_at(self, mock_audit):
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content, "engines")
        obj = RefEngine.objects.get(code="Oracle")
        self.assertIsNotNone(obj.last_synced_at)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_update_sets_last_synced_hash(self, mock_audit):
        RefEngine.objects.create(code="Oracle", label="Old label", display_order=1, is_active=1)
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB Updated", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content, "engines")
        obj = RefEngine.objects.get(code="Oracle")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_unchanged_does_not_update_last_synced_hash(self, mock_audit):
        RefEngine.objects.create(code="Oracle", label="Oracle DB", display_order=1, is_active=1)
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        # Clear tracking to confirm unchanged path leaves it None
        RefEngine.objects.filter(code="Oracle").update(last_synced_hash=None, last_synced_at=None)
        created, updated, unchanged = import_reference_yaml(content, "engines")
        self.assertEqual(unchanged, 1)
        obj = RefEngine.objects.get(code="Oracle")
        self.assertIsNone(obj.last_synced_hash)

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_category_create_sets_last_synced_hash(self, mock_audit):
        content = self._make_yaml("categories", [
            {"code": "PATCH", "label": "Patching", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content, "categories")
        obj = RefCategory.objects.get(code="PATCH")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)


class ImportAuditLoggingTests(ReferenceYamlTestMixin, TestCase):

    @patch("reference.services_export_import.AuditService.create_entry")
    def test_audit_called_with_correct_action_type(self, mock_audit):
        from core.models import AuditActionType, AuditEntityType
        content = self._make_yaml("engines", [
            {"code": "Oracle", "label": "Oracle DB", "display_order": 1, "is_active": True},
        ])
        import_reference_yaml(content, "engines")
        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args[1]
        self.assertEqual(kwargs["action_type"], AuditActionType.CONFIG_SYNC_REFERENCE_IMPORT)
        self.assertEqual(kwargs["entity_type"], AuditEntityType.REFERENCE_DATA)
        self.assertEqual(kwargs["entity_id"], 0)  # 0 = opération groupée (BigIntegerField NOT NULL)
        self.assertEqual(kwargs["details"]["ref_type"], "engines")
