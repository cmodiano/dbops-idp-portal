"""
Tests for integrations/services_export_import_types.py
Story 64.3 - IaC Integration Type Catalogue export/import.
"""

from unittest.mock import patch

import yaml
from django.test import TestCase

from core.exceptions import InvalidStateError
from integrations.models import IntegrationAction, IntegrationTypeCatalogue
from integrations.services_export_import_types import (
    export_integration_types_yaml,
    import_integration_types_yaml,
)


def _make_type_yaml(code="aap", name="AAP", actions=None, is_active=True):
    """Helper pour créer un YAML de type d'intégration."""
    data = {
        "apiVersion": "idp/v1",
        "kind": "IntegrationTypeCatalogue",
        "metadata": {"code": code, "name": name},
        "spec": {
            "description": "Test",
            "version": "1.0",
            "is_active": is_active,
            "integration_role": "platform",
            "actions": actions or [],
        },
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


def _make_action(code="launch_job", label="Launch Job", is_active=True):
    return {
        "action_code": code,
        "action_label": label,
        "description": "",
        "is_active": is_active,
        "required_params": {},
        "optional_params": {},
        "response_format": {},
    }


class ExportIntegrationTypesYamlNotFoundTests(TestCase):
    def test_export_not_found_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_integration_types_yaml("does_not_exist")
        self.assertEqual(ctx.exception.code, "INTEGRATION_TYPE_NOT_FOUND")


class ExportIntegrationTypesYamlTests(TestCase):
    def setUp(self):
        self.obj = IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="Test",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=self.obj,
            action_code="launch_job",
            action_label="Launch Job",
            required_params="{}",
            optional_params="{}",
            response_format="{}",
            is_active=True,
        )

    def test_export_returns_bytes(self):
        self.assertIsInstance(export_integration_types_yaml("aap"), bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_integration_types_yaml("aap"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "IntegrationTypeCatalogue")
        self.assertEqual(parsed["metadata"]["code"], "aap")
        self.assertEqual(parsed["metadata"]["name"], "AAP")

    def test_export_includes_actions(self):
        parsed = yaml.safe_load(export_integration_types_yaml("aap"))
        self.assertEqual(len(parsed["spec"]["actions"]), 1)
        self.assertEqual(parsed["spec"]["actions"][0]["action_code"], "launch_job")

    def test_export_json_fields_deserialized(self):
        parsed = yaml.safe_load(export_integration_types_yaml("aap"))
        action = parsed["spec"]["actions"][0]
        self.assertIsInstance(action["required_params"], dict)
        self.assertIsInstance(action["optional_params"], dict)
        self.assertIsInstance(action["response_format"], dict)


class ImportIntegrationTypesYamlTests(TestCase):
    def test_import_create_type_and_actions(self):
        content = _make_type_yaml(actions=[_make_action()])
        created, updated, unchanged = import_integration_types_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertTrue(IntegrationTypeCatalogue.objects.filter(code="aap").exists())
        self.assertTrue(IntegrationAction.objects.filter(action_code="launch_job").exists())

    def test_import_update_type(self):
        IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="Old Name",
            description="",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        content = _make_type_yaml(name="New Name")
        created, updated, unchanged = import_integration_types_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(unchanged, 0)
        self.assertEqual(IntegrationTypeCatalogue.objects.get(code="aap").name, "New Name")

    def test_import_unchanged(self):
        IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="Test",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        content = _make_type_yaml()
        created, updated, unchanged = import_integration_types_yaml(content)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)

    def test_import_create_new_action(self):
        obj = IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=obj,
            action_code="existing_action",
            action_label="Existing",
            required_params="{}",
            optional_params="{}",
            response_format="{}",
            is_active=True,
        )
        content = _make_type_yaml(
            actions=[_make_action("existing_action", "Existing"), _make_action("new_action", "New")]
        )
        import_integration_types_yaml(content)
        self.assertTrue(IntegrationAction.objects.filter(action_code="new_action").exists())

    def test_import_update_action(self):
        obj = IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=obj,
            action_code="launch_job",
            action_label="Old Label",
            required_params="{}",
            optional_params="{}",
            response_format="{}",
            is_active=True,
        )
        content = _make_type_yaml(actions=[_make_action("launch_job", "New Label")])
        import_integration_types_yaml(content)
        self.assertEqual(
            IntegrationAction.objects.get(action_code="launch_job").action_label, "New Label"
        )

    def test_import_additive_leaves_orphan_actions(self):
        obj = IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=obj,
            action_code="orphan",
            action_label="Orphan",
            required_params="{}",
            optional_params="{}",
            response_format="{}",
            is_active=True,
        )
        content = _make_type_yaml(actions=[_make_action("launch_job")])
        import_integration_types_yaml(content, mode="additive")
        self.assertTrue(IntegrationAction.objects.get(action_code="orphan").is_active)

    def test_import_full_deactivates_orphan_actions(self):
        obj = IntegrationTypeCatalogue.objects.create(
            code="aap",
            name="AAP",
            description="",
            version="1.0",
            is_active=True,
            integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=obj,
            action_code="orphan",
            action_label="Orphan",
            required_params="{}",
            optional_params="{}",
            response_format="{}",
            is_active=True,
        )
        content = _make_type_yaml(actions=[_make_action("launch_job")])
        import_integration_types_yaml(content, mode="full")
        self.assertFalse(IntegrationAction.objects.get(action_code="orphan").is_active)

    def test_missing_action_code_raises(self):
        action_no_code = {"action_label": "No Code", "required_params": {}}
        content = _make_type_yaml(actions=[action_no_code])
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_types_yaml(content)
        self.assertEqual(ctx.exception.code, "MISSING_ACTION_CODE")

    def test_envelope_invalid_raises(self):
        bad_yaml = yaml.dump(
            {"apiVersion": "idp/v1", "kind": "Tags", "metadata": {}, "spec": []},
        ).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_types_yaml(bad_yaml)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_round_trip(self):
        content = _make_type_yaml(actions=[_make_action()])
        import_integration_types_yaml(content)
        exported = export_integration_types_yaml("aap")
        # 2e import : rien à changer
        created, updated, unchanged = import_integration_types_yaml(exported)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)
        self.assertEqual(IntegrationAction.objects.filter(action_code="launch_job").count(), 1)

    def test_import_invalid_mode_raises(self):
        content = _make_type_yaml()
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_types_yaml(content, mode="invalid")
        self.assertEqual(ctx.exception.code, "INVALID_IMPORT_MODE")

    def test_import_audit_log_created(self):
        from core.models import AuditActionType
        content = _make_type_yaml(actions=[_make_action()])
        with patch("integrations.services_export_import_types.AuditService.create_entry") as mock_audit:
            import_integration_types_yaml(content)
            # AuditService peut être appelé plusieurs fois (signals sur save())
            # On cherche l'appel CONFIG_SYNC_INTEGRATION_TYPE_IMPORT spécifiquement
            sync_calls = [
                c for c in mock_audit.call_args_list
                if c.kwargs.get("action_type") == AuditActionType.CONFIG_SYNC_INTEGRATION_TYPE_IMPORT
            ]
            self.assertEqual(len(sync_calls), 1, "Exactement un appel CONFIG_SYNC_INTEGRATION_TYPE_IMPORT attendu")
            details = sync_calls[0].kwargs["details"]
            self.assertEqual(details["created"], 1)
            self.assertEqual(details["updated"], 0)
            self.assertEqual(details["unchanged"], 0)
            self.assertEqual(details["actions_created"], 1)
            self.assertEqual(details["code"], "aap")

    def test_import_full_skips_already_inactive_orphans(self):
        obj = IntegrationTypeCatalogue.objects.create(
            code="aap", name="AAP", description="", version="1.0",
            is_active=True, integration_role="platform",
        )
        IntegrationAction.objects.create(
            integration_type=obj, action_code="already_inactive",
            action_label="Inactive", required_params="{}",
            optional_params="{}", response_format="{}", is_active=False,
        )
        content = _make_type_yaml(actions=[])
        import_integration_types_yaml(content, mode="full")
        # L'action déjà inactive ne doit pas être re-sauvegardée
        action = IntegrationAction.objects.get(action_code="already_inactive")
        self.assertFalse(action.is_active)
