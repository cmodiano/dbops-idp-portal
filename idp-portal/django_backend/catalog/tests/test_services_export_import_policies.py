"""
Tests for catalog/services_export_import_policies.py
Story 64.5 - CaC Business Rule Policy export/import.
"""
import json

import yaml
from django.test import TestCase

from catalog.models import BusinessRulePolicy
from catalog.services_export_import_policies import (
    export_policy_yaml,
    import_policy_yaml,
)
from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditLog
from tests.factories import UserFactory


VALID_POLICY_JSON = {
    "on_step_output": [
        {
            "when": {"step_type": "terraform_cloud", "output_key": "plan_output"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [{"resource_type": "azurerm_sql_database"}],
                "auto_approve_if_none_match": True,
            },
        }
    ]
}


def _make_policy_yaml(
    name="terraform-review",
    policy_json=None,
    is_active=True,
    description=None,
):
    data = {
        "apiVersion": "idp/v1",
        "kind": "BusinessRulePolicy",
        "metadata": {"name": name},
        "spec": {
            "is_active": is_active,
            "policy_json": policy_json or VALID_POLICY_JSON,
        },
    }
    if description is not None:
        data["spec"]["description"] = description
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


class ExportPolicyYamlTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.obj = BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            description="Test policy",
            created_by=self.user,
        )

    def test_export_returns_bytes(self):
        self.assertIsInstance(export_policy_yaml("terraform-review"), bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_policy_yaml("terraform-review"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "BusinessRulePolicy")
        self.assertEqual(parsed["metadata"]["name"], "terraform-review")

    def test_export_policy_json_is_dict(self):
        parsed = yaml.safe_load(export_policy_yaml("terraform-review"))
        self.assertIsInstance(parsed["spec"]["policy_json"], dict)
        self.assertIn("on_step_output", parsed["spec"]["policy_json"])

    def test_export_is_active(self):
        parsed = yaml.safe_load(export_policy_yaml("terraform-review"))
        self.assertTrue(parsed["spec"]["is_active"])

    def test_export_description_present(self):
        parsed = yaml.safe_load(export_policy_yaml("terraform-review"))
        self.assertEqual(parsed["spec"]["description"], "Test policy")

    def test_export_description_absent(self):
        BusinessRulePolicy.objects.create(
            name="no-desc-policy",
            policy_json=VALID_POLICY_JSON,
            created_by=self.user,
        )
        parsed = yaml.safe_load(export_policy_yaml("no-desc-policy"))
        self.assertNotIn("description", parsed["spec"])

    def test_export_not_found_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_policy_yaml("nonexistent-policy")
        self.assertEqual(ctx.exception.code, "POLICY_NOT_FOUND")


class ImportPolicyYamlTests(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def test_import_create(self):
        content = _make_policy_yaml()
        created, updated, unchanged = import_policy_yaml(content, user=self.user)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertTrue(BusinessRulePolicy.objects.filter(name="terraform-review").exists())

    def test_import_update(self):
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        content = _make_policy_yaml(is_active=False)
        created, updated, unchanged = import_policy_yaml(content, user=self.user)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(unchanged, 0)
        self.assertFalse(BusinessRulePolicy.objects.get(name="terraform-review").is_active)

    def test_import_unchanged(self):
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        content = _make_policy_yaml()
        created, updated, unchanged = import_policy_yaml(content, user=self.user)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)

    def test_import_create_no_user_raises(self):
        content = _make_policy_yaml()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(content, user=None)
        self.assertEqual(ctx.exception.code, "MISSING_USER")

    def test_import_update_no_user_ok(self):
        # Update should not require user (created_by not modified)
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        content = _make_policy_yaml(is_active=False)
        created, updated, unchanged = import_policy_yaml(content, user=None)
        self.assertEqual(updated, 1)

    def test_import_envelope_invalid_raises(self):
        bad_yaml = yaml.dump({
            "apiVersion": "idp/v1", "kind": "Tags", "metadata": {}, "spec": [],
        }).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_import_invalid_spec_not_dict_raises(self):
        bad_yaml = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "BusinessRulePolicy",
            "metadata": {"name": "test-policy"},
            "spec": [],
        }).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_SPEC")

    def test_import_invalid_mode_raises(self):
        content = _make_policy_yaml()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(content, mode="invalid", user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_IMPORT_MODE")

    def test_import_missing_policy_json_raises(self):
        bad_yaml = yaml.dump({
            "apiVersion": "idp/v1", "kind": "BusinessRulePolicy",
            "metadata": {"name": "test-policy"},
            "spec": {"is_active": True},
        }).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "MISSING_POLICY_JSON")

    def test_import_invalid_policy_json_type_raises(self):
        bad_yaml = yaml.dump({
            "apiVersion": "idp/v1", "kind": "BusinessRulePolicy",
            "metadata": {"name": "test-policy"},
            "spec": {"is_active": True, "policy_json": "not-a-dict"},
        }).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_POLICY_JSON")

    def test_import_audit_log_created(self):
        content = _make_policy_yaml()
        import_policy_yaml(content, user=self.user)
        log = AuditLog.objects.filter(
            action_type=AuditActionType.CONFIG_SYNC_POLICY_IMPORT
        ).first()
        self.assertIsNotNone(log)
        details = json.loads(log.details)
        self.assertEqual(details["name"], "terraform-review")
        self.assertEqual(details["created"], 1)

    def test_import_created_by_not_changed_on_update(self):
        original_user = self.user
        other_user = UserFactory()
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=original_user,
        )
        content = _make_policy_yaml(is_active=False)
        import_policy_yaml(content, user=other_user)
        obj = BusinessRulePolicy.objects.get(name="terraform-review")
        self.assertEqual(obj.created_by_id, original_user.id)

    def test_export_description_empty_string_absent(self):
        # description="" doit être traité comme absent (comme None) à l'export
        BusinessRulePolicy.objects.create(
            name="empty-desc-policy",
            policy_json=VALID_POLICY_JSON,
            description="",
            created_by=self.user,
        )
        parsed = yaml.safe_load(export_policy_yaml("empty-desc-policy"))
        self.assertNotIn("description", parsed["spec"])

    def test_round_trip(self):
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            description="Revue Terraform",
            created_by=self.user,
        )
        exported1 = export_policy_yaml("terraform-review")
        import_policy_yaml(exported1, user=self.user)
        exported2 = export_policy_yaml("terraform-review")
        parsed1 = yaml.safe_load(exported1.decode("utf-8"))
        parsed2 = yaml.safe_load(exported2.decode("utf-8"))
        self.assertEqual(parsed1, parsed2)

    def test_import_invalid_yaml_syntax_raises(self):
        """INVALID_YAML_SYNTAX levé quand le contenu YAML est syntaxiquement malformé (AC #3)."""
        bad_yaml = b"apiVersion: idp/v1\nkind: BusinessRulePolicy\nspec: [\nunclosed bracket"
        with self.assertRaises(InvalidStateError) as ctx:
            import_policy_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")
        self.assertIn("parser", ctx.exception.message.lower() if ctx.exception.message else "")

    def test_import_full_mode_accepted(self):
        """mode='full' est accepté et se comporte comme 'additive' pour les policies (AC #1)."""
        BusinessRulePolicy.objects.create(
            name="terraform-review",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        content = _make_policy_yaml(is_active=False)
        created, updated, unchanged = import_policy_yaml(content, mode="full", user=self.user)
        self.assertEqual(updated, 1)
        self.assertFalse(BusinessRulePolicy.objects.get(name="terraform-review").is_active)

    def test_import_full_mode_does_not_delete_other_policies(self):
        """En mode full, l'import d'une policy n'affecte pas les autres policies existantes (AC #1)."""
        BusinessRulePolicy.objects.create(
            name="other-policy",
            policy_json=VALID_POLICY_JSON,
            is_active=True,
            created_by=self.user,
        )
        content = _make_policy_yaml(name="terraform-review")
        import_policy_yaml(content, mode="full", user=self.user)
        self.assertTrue(BusinessRulePolicy.objects.filter(name="other-policy").exists())
