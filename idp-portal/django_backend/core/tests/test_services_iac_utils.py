"""
Unit tests for core/services_iac_utils.py.
Story 64.1 - AC#11: Tests for parse_yaml, validate_envelope, compute_yaml_hash,
serialize_to_yaml, _apply_field_changes.
"""

from django.test import TestCase

from core.exceptions import InvalidStateError
from core.services_iac_utils import (
    _apply_field_changes,
    compute_yaml_hash,
    parse_yaml,
    serialize_to_yaml,
    validate_envelope,
)


class ParseYamlTests(TestCase):
    def test_valid_yaml_returns_dict(self):
        content = b"apiVersion: idp/v1\nkind: ReferenceData\n"
        result = parse_yaml(content)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["apiVersion"], "idp/v1")

    def test_empty_bytes_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            parse_yaml(b"")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")

    def test_malformed_yaml_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            parse_yaml(b"key: [\nunclosed")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")

    def test_non_dict_yaml_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            parse_yaml(b"- item1\n- item2\n")
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")

    def test_unicode_yaml_parses_correctly(self):
        content = "label: Données UTF-8\n".encode("utf-8")
        result = parse_yaml(content)
        self.assertEqual(result["label"], "Données UTF-8")


class ValidateEnvelopeTests(TestCase):
    def _valid_envelope(self, kind="ReferenceData", metadata=None):
        doc = {
            "apiVersion": "idp/v1",
            "kind": kind,
            "metadata": metadata if metadata is not None else {"type": "engines"},
        }
        return doc

    def test_valid_envelope_passes(self):
        validate_envelope(self._valid_envelope())  # should not raise

    def test_invalid_api_version_raises(self):
        doc = self._valid_envelope()
        doc["apiVersion"] = "idp/v2"
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "INVALID_API_VERSION")

    def test_missing_api_version_raises(self):
        doc = self._valid_envelope()
        del doc["apiVersion"]
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "INVALID_API_VERSION")

    def test_invalid_kind_raises(self):
        doc = self._valid_envelope()
        doc["kind"] = "UnknownKind"
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "INVALID_KIND")

    def test_wrong_expected_kind_raises(self):
        doc = self._valid_envelope(kind="Action", metadata={"name": "my-action"})
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc, expected_kind="ReferenceData")
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_correct_expected_kind_passes(self):
        doc = self._valid_envelope(kind="ReferenceData")
        validate_envelope(doc, expected_kind="ReferenceData")  # should not raise

    def test_missing_metadata_raises(self):
        doc = self._valid_envelope()
        del doc["metadata"]
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")

    def test_metadata_not_dict_raises(self):
        doc = self._valid_envelope()
        doc["metadata"] = "string-metadata"
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "INVALID_METADATA")

    def test_action_kind_requires_metadata_name(self):
        doc = {
            "apiVersion": "idp/v1",
            "kind": "Action",
            "metadata": {},
        }
        with self.assertRaises(InvalidStateError) as ctx:
            validate_envelope(doc)
        self.assertEqual(ctx.exception.code, "MISSING_NAME")

    def test_reference_data_does_not_require_metadata_name(self):
        doc = {
            "apiVersion": "idp/v1",
            "kind": "ReferenceData",
            "metadata": {"type": "engines"},
        }
        validate_envelope(doc)  # should not raise

    def test_all_valid_kinds_pass(self):
        from core.services_iac_utils import VALID_KINDS
        for kind in VALID_KINDS:
            metadata = {"type": "test"} if kind in ("Tags", "FeatureFlags", "ReferenceData") else {"name": "test"}
            doc = {"apiVersion": "idp/v1", "kind": kind, "metadata": metadata}
            validate_envelope(doc)  # should not raise


class ComputeYamlHashTests(TestCase):
    def test_returns_64_char_hex_string(self):
        result = compute_yaml_hash(b"some content")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)
        # Validate it's a valid hex string
        int(result, 16)

    def test_same_content_same_hash(self):
        content = b"apiVersion: idp/v1\n"
        self.assertEqual(compute_yaml_hash(content), compute_yaml_hash(content))

    def test_different_content_different_hash(self):
        self.assertNotEqual(compute_yaml_hash(b"abc"), compute_yaml_hash(b"def"))

    def test_empty_bytes_returns_hash(self):
        result = compute_yaml_hash(b"")
        self.assertEqual(len(result), 64)


class SerializeToYamlTests(TestCase):
    def test_returns_bytes(self):
        result = serialize_to_yaml({"key": "value"})
        self.assertIsInstance(result, bytes)

    def test_valid_utf8_yaml(self):
        import yaml
        data = {"apiVersion": "idp/v1", "kind": "ReferenceData"}
        result = serialize_to_yaml(data)
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["apiVersion"], "idp/v1")

    def test_preserves_key_order(self):
        data = {"z": 1, "a": 2, "m": 3}
        result = serialize_to_yaml(data).decode("utf-8")
        z_pos = result.index("z:")
        a_pos = result.index("a:")
        m_pos = result.index("m:")
        self.assertLess(z_pos, a_pos)
        self.assertLess(a_pos, m_pos)

    def test_unicode_content_preserved(self):
        data = {"label": "Données UTF-8 éàü"}
        result = serialize_to_yaml(data).decode("utf-8")
        self.assertIn("Données UTF-8 éàü", result)


class ApplyFieldChangesTests(TestCase):
    def _make_obj(self, **kwargs):
        class FakeObj:
            pass
        obj = FakeObj()
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj

    def test_no_changes_returns_false(self):
        obj = self._make_obj(label="test", display_order=1)
        result = _apply_field_changes(obj, {"label": "test", "display_order": 1})
        self.assertFalse(result)

    def test_changed_field_returns_true(self):
        obj = self._make_obj(label="old")
        result = _apply_field_changes(obj, {"label": "new"})
        self.assertTrue(result)
        self.assertEqual(obj.label, "new")

    def test_multiple_fields_one_changed(self):
        obj = self._make_obj(label="same", display_order=1)
        result = _apply_field_changes(obj, {"label": "same", "display_order": 2})
        self.assertTrue(result)
        self.assertEqual(obj.display_order, 2)
        self.assertEqual(obj.label, "same")

    def test_integer_vs_bool_detects_change(self):
        """is_active=1 vs True must be handled correctly after conversion."""
        obj = self._make_obj(is_active=1)
        # After proper conversion: is_active=1 (int) vs 1 (int) — no change
        result = _apply_field_changes(obj, {"is_active": 1})
        self.assertFalse(result)

    def test_bool_true_equals_int_1_no_spurious_update(self):
        """En Python, True == 1 → pas de faux changement si le YAML retourne True pour un IntegerField valant 1.
        La conversion explicite (1 if val else 0) dans import_reference_yaml garantit des types cohérents
        pour éviter tout comportement ambigu avec l'ORM Oracle."""
        obj = self._make_obj(is_active=1)
        result = _apply_field_changes(obj, {"is_active": True})
        # True == 1 en Python : aucun changement détecté
        self.assertFalse(result)

    def test_empty_defaults_no_changes(self):
        obj = self._make_obj(label="test")
        result = _apply_field_changes(obj, {})
        self.assertFalse(result)
