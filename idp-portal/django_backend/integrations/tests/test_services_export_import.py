"""
Tests unitaires pour integrations/services_export_import.py.
Story 64.4 - CaC Integration export/import.
"""

import json

import yaml
from django.test import TestCase

from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditLog
from integrations.models import Integration, IntegrationTypeCatalogue
from integrations.services_export_import import (
    _mask_credential_ref,
    export_integration_yaml,
    import_integration_yaml,
)


def _make_integration_yaml(
    name="aap-prod",
    type_code="aap",
    base_url="https://aap.example.com",
    auth_flow="token",
    credential_ref="secret/integrations/***",
    secret_service_ref=None,
    config=None,
):
    data = {
        "apiVersion": "idp/v1",
        "kind": "Integration",
        "metadata": {"name": name, "type": type_code},
        "spec": {
            "base_url": base_url,
            "auth_flow": auth_flow,
            "credential_ref": credential_ref,
        },
    }
    if secret_service_ref:
        data["spec"]["secret_service_ref"] = secret_service_ref
    if config:
        data["spec"]["config"] = config
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


class MaskCredentialRefTests(TestCase):
    def test_masks_last_segment(self):
        self.assertEqual(_mask_credential_ref("secret/integrations/aap-prod"), "secret/integrations/***")

    def test_no_slash_returns_stars(self):
        self.assertEqual(_mask_credential_ref("simple-secret"), "***")

    def test_none_returns_none(self):
        self.assertIsNone(_mask_credential_ref(None))

    def test_empty_returns_none(self):
        self.assertIsNone(_mask_credential_ref(""))


class ExportIntegrationYamlTests(TestCase):
    def setUp(self):
        self.type_obj = IntegrationTypeCatalogue.objects.create(
            code="aap", name="AAP", is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code="vault", name="Vault", is_active=True
        )
        self.vault = Integration.objects.create(
            name="vault-prod",
            type="vault",
            base_url="https://vault.example.com",
        )
        self.obj = Integration.objects.create(
            name="aap-prod",
            type="aap",
            base_url="https://aap.example.com",
            auth_flow="token",
            credential_ref="secret/integrations/aap-prod",
            secret_service=self.vault,
            config=json.dumps({"verify_ssl": True}),
        )

    def test_export_returns_bytes(self):
        result = export_integration_yaml("aap-prod")
        self.assertIsInstance(result, bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_integration_yaml("aap-prod"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "Integration")
        self.assertEqual(parsed["metadata"]["name"], "aap-prod")
        self.assertEqual(parsed["metadata"]["type"], "aap")

    def test_export_masks_credential_ref(self):
        parsed = yaml.safe_load(export_integration_yaml("aap-prod"))
        self.assertEqual(parsed["spec"]["credential_ref"], "secret/integrations/***")

    def test_export_no_credential_ref(self):
        parsed = yaml.safe_load(export_integration_yaml("vault-prod"))
        self.assertIsNone(parsed["spec"]["credential_ref"])

    def test_export_secret_service_ref_by_name(self):
        parsed = yaml.safe_load(export_integration_yaml("aap-prod"))
        self.assertEqual(parsed["spec"]["secret_service_ref"], "vault-prod")

    def test_export_no_secret_service_ref(self):
        parsed = yaml.safe_load(export_integration_yaml("vault-prod"))
        self.assertNotIn("secret_service_ref", parsed["spec"])

    def test_export_config_deserialized(self):
        parsed = yaml.safe_load(export_integration_yaml("aap-prod"))
        self.assertIsInstance(parsed["spec"]["config"], dict)
        self.assertTrue(parsed["spec"]["config"]["verify_ssl"])

    def test_export_not_found_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_integration_yaml("nonexistent")
        self.assertEqual(ctx.exception.code, "INTEGRATION_NOT_FOUND")


class ImportIntegrationYamlTests(TestCase):
    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code="aap", name="AAP", is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code="vault", name="Vault", is_active=True
        )

    def test_import_create(self):
        content = _make_integration_yaml()
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 0)
        self.assertTrue(Integration.objects.filter(name="aap-prod").exists())

    def test_import_update(self):
        Integration.objects.create(name="aap-prod", type="aap", base_url="https://old.example.com")
        content = _make_integration_yaml(base_url="https://new.example.com")
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(updated, 1)
        self.assertEqual(created, 0)
        self.assertEqual(Integration.objects.get(name="aap-prod").base_url, "https://new.example.com")

    def test_import_unchanged(self):
        Integration.objects.create(
            name="aap-prod",
            type="aap",
            base_url="https://aap.example.com",
            auth_flow="token",
            credential_ref="secret/integrations/***",
        )
        content = _make_integration_yaml()
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(unchanged, 1)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)

    def test_import_unchanged_with_real_credential(self):
        """Import with masked YAML must not overwrite real credential_ref in DB."""
        real_credential_ref = "secret/integrations/aap-prod"
        Integration.objects.create(
            name="aap-prod",
            type="aap",
            base_url="https://aap.example.com",
            auth_flow="token",
            credential_ref=real_credential_ref,
        )
        content = _make_integration_yaml()  # credential_ref is masked in YAML
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(unchanged, 1)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        obj = Integration.objects.get(name="aap-prod")
        self.assertEqual(obj.credential_ref, real_credential_ref)

    def test_import_invalid_type_raises(self):
        content = _make_integration_yaml(type_code="nonexistent-type")
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(content)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")

    def test_import_empty_base_url_raises(self):
        content = _make_integration_yaml(base_url="")
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(content)
        self.assertEqual(ctx.exception.code, "INVALID_SPEC")

    def test_import_secret_service_ref_resolved(self):
        vault = Integration.objects.create(
            name="vault-prod", type="vault", base_url="https://vault.example.com"
        )
        content = _make_integration_yaml(secret_service_ref="vault-prod")
        import_integration_yaml(content)
        obj = Integration.objects.get(name="aap-prod")
        self.assertEqual(obj.secret_service_id, vault.id)

    def test_import_secret_service_ref_not_found_raises(self):
        content = _make_integration_yaml(secret_service_ref="nonexistent-vault")
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(content)
        self.assertEqual(ctx.exception.code, "REF_NOT_FOUND")

    def test_import_envelope_invalid_raises(self):
        bad_yaml = yaml.dump({
            "apiVersion": "idp/v1",
            "kind": "Tags",
            "metadata": {},
            "spec": [],
        }).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(bad_yaml)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_import_invalid_mode_raises(self):
        content = _make_integration_yaml()
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(content, mode="invalid")
        self.assertEqual(ctx.exception.code, "INVALID_IMPORT_MODE")

    def test_import_audit_log_created(self):
        content = _make_integration_yaml()
        import_integration_yaml(content)
        log = AuditLog.objects.filter(
            action_type=AuditActionType.CONFIG_SYNC_INTEGRATION_IMPORT
        ).first()
        self.assertIsNotNone(log)
        details = json.loads(log.details)
        self.assertEqual(details["name"], "aap-prod")
        self.assertEqual(details["created"], 1)

    def test_import_secret_service_ref_unchanged(self):
        vault = Integration.objects.create(
            name="vault-prod", type="vault", base_url="https://vault.example.com"
        )
        # First import sets the FK
        content = _make_integration_yaml(secret_service_ref="vault-prod")
        import_integration_yaml(content)
        # Second import with same secret_service_ref → unchanged
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(unchanged, 1)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(Integration.objects.get(name="aap-prod").secret_service_id, vault.id)

    def test_import_clears_secret_service_ref(self):
        Integration.objects.create(
            name="vault-prod", type="vault", base_url="https://vault.example.com"
        )
        # Import with secret_service_ref set
        content_with = _make_integration_yaml(secret_service_ref="vault-prod")
        import_integration_yaml(content_with)
        # Import without secret_service_ref → FK cleared, updated=1
        content_without = _make_integration_yaml()
        created, updated, unchanged = import_integration_yaml(content_without)
        self.assertEqual(updated, 1)
        self.assertIsNone(Integration.objects.get(name="aap-prod").secret_service_id)

    def test_round_trip(self):
        IntegrationTypeCatalogue.objects.get_or_create(code="aap", defaults={"name": "AAP"})
        original_credential_ref = "secret/integrations/aap-prod"
        Integration.objects.create(
            name="aap-prod",
            type="aap",
            base_url="https://aap.example.com",
            credential_ref=original_credential_ref,
            config=json.dumps({"verify_ssl": True}, sort_keys=True),
        )
        exported1 = export_integration_yaml("aap-prod")
        import_integration_yaml(exported1)
        exported2 = export_integration_yaml("aap-prod")
        self.assertEqual(exported1, exported2)
        # Ensure import did not overwrite/mask credential_ref in DB
        obj = Integration.objects.get(name="aap-prod")
        self.assertEqual(obj.credential_ref, original_credential_ref)

    def test_import_full_mode_accepted(self):
        """mode='full' est accepté et se comporte comme 'additive' (suppression orphelins réservée) (AC #1)."""
        Integration.objects.create(name="aap-prod", type="aap", base_url="https://old.example.com")
        content = _make_integration_yaml(base_url="https://new.example.com")
        created, updated, unchanged = import_integration_yaml(content, mode="full")
        self.assertEqual(updated, 1)
        self.assertEqual(Integration.objects.get(name="aap-prod").base_url, "https://new.example.com")

    def test_import_full_mode_does_not_delete_other_integrations(self):
        """En mode full, l'import d'une intégration ne supprime pas les autres (AC #1)."""
        Integration.objects.create(name="other-integration", type="vault", base_url="https://other.example.com")
        content = _make_integration_yaml()
        import_integration_yaml(content, mode="full")
        self.assertTrue(Integration.objects.filter(name="other-integration").exists())

    def test_import_invalid_yaml_syntax_raises(self):
        """INVALID_YAML_SYNTAX levé quand le contenu YAML est syntaxiquement malformé (AC #3)."""
        bad_yaml = b"apiVersion: idp/v1\nkind: Integration\nspec: [\nunclosed"
        with self.assertRaises(InvalidStateError) as ctx:
            import_integration_yaml(bad_yaml)
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")


class ImportIntegrationSyncTrackingTests(TestCase):
    """Story 64.11 - AC#8: Verify last_synced_hash/at are set after import for Integration."""

    def setUp(self):
        IntegrationTypeCatalogue.objects.get_or_create(code="aap", defaults={"name": "AAP"})
        IntegrationTypeCatalogue.objects.get_or_create(code="vault", defaults={"name": "Vault"})

    def test_create_sets_last_synced_hash(self):
        content = _make_integration_yaml()
        import_integration_yaml(content)
        obj = Integration.objects.get(name="aap-prod")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)

    def test_create_sets_last_synced_at(self):
        content = _make_integration_yaml()
        import_integration_yaml(content)
        obj = Integration.objects.get(name="aap-prod")
        self.assertIsNotNone(obj.last_synced_at)

    def test_update_sets_last_synced_hash(self):
        Integration.objects.create(
            name="aap-prod", type="aap", base_url="https://old.example.com"
        )
        content = _make_integration_yaml(base_url="https://new.example.com")
        import_integration_yaml(content)
        obj = Integration.objects.get(name="aap-prod")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)

    def test_unchanged_does_not_update_last_synced_hash(self):
        content = _make_integration_yaml()
        import_integration_yaml(content)
        # Clear tracking to verify unchanged path leaves it alone
        Integration.objects.filter(name="aap-prod").update(
            last_synced_hash=None, last_synced_at=None
        )
        # Re-import same content → unchanged
        created, updated, unchanged = import_integration_yaml(content)
        self.assertEqual(unchanged, 1)
        obj = Integration.objects.get(name="aap-prod")
        self.assertIsNone(obj.last_synced_hash)

    def test_secret_service_ref_only_change_sets_last_synced_hash(self):
        """Story 64.11 fix: secret_service_ref-only change in pass 2 must update hash."""
        Integration.objects.create(
            name="vault-prod", type="vault", base_url="https://vault.example.com"
        )
        # First import without secret_service_ref
        content_without = _make_integration_yaml()
        import_integration_yaml(content_without)
        # Clear tracking
        Integration.objects.filter(name="aap-prod").update(
            last_synced_hash=None, last_synced_at=None
        )
        # Import with secret_service_ref changed only
        content_with = _make_integration_yaml(secret_service_ref="vault-prod")
        created, updated, unchanged = import_integration_yaml(content_with)
        self.assertEqual(updated, 1)
        obj = Integration.objects.get(name="aap-prod")
        self.assertIsNotNone(obj.last_synced_hash)
        self.assertEqual(len(obj.last_synced_hash), 64)
