"""
Tests for integrations/models.py — coverage for previously uncovered branches.
Story 55-3: Augmenter la couverture de integrations/models.py vers ≥90%.
"""
from __future__ import annotations

import json
import unittest

from django.core.exceptions import ValidationError

from integrations.models import (
    Integration,
    IntegrationAction,
    _validate_json_schema,
)


# ---------------------------------------------------------------------------
# _validate_json_schema — pure unit tests (no DB)
# ---------------------------------------------------------------------------

class TestValidateJsonSchema(unittest.TestCase):
    """Tests for the _validate_json_schema helper function."""

    def test_raises_if_not_dict(self):
        """Line 18: value is not a dict → ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            _validate_json_schema("not a dict")
        self.assertIn("dictionary", str(ctx.exception))

    def test_raises_if_missing_type_field(self):
        """Line 22: dict without 'type' key → ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            _validate_json_schema({"properties": {}})
        self.assertIn("'type'", str(ctx.exception))

    def test_raises_if_invalid_type_value(self):
        """Line 26: 'type' not in valid_types → ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            _validate_json_schema({"type": "unsupported_type"})
        self.assertIn("must be one of", str(ctx.exception))

    def test_raises_if_properties_not_dict(self):
        """Line 31: type == 'object' + 'properties' present but not a dict → ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            _validate_json_schema({"type": "object", "properties": ["not", "a", "dict"]})
        self.assertIn("'properties' must be a dictionary", str(ctx.exception))

    def test_valid_object_schema_passes(self):
        """type == 'object' with dict properties → no exception."""
        _validate_json_schema({"type": "object", "properties": {"name": {"type": "string"}}})

    def test_valid_string_schema_passes(self):
        """type == 'string' (no properties check) → no exception."""
        _validate_json_schema({"type": "string"})

    def test_valid_object_without_properties_passes(self):
        """type == 'object' without 'properties' key → no exception."""
        _validate_json_schema({"type": "object"})


# ---------------------------------------------------------------------------
# Integration.get_config / set_config — no DB needed (use unsaved instance)
# ---------------------------------------------------------------------------

class TestIntegrationConfigMethods(unittest.TestCase):
    """Tests for Integration.get_config and set_config (no DB)."""

    def _make_instance(self, config_str=None):
        inst = Integration.__new__(Integration)
        inst.id = 1
        inst.config = config_str
        return inst

    def test_get_config_returns_none_when_config_is_null(self):
        """get_config() with config=None → returns None."""
        inst = self._make_instance(config_str=None)
        self.assertIsNone(inst.get_config())

    def test_get_config_returns_dict_for_valid_json(self):
        """get_config() with valid JSON → returns dict."""
        inst = self._make_instance(config_str='{"key": "value"}')
        self.assertEqual(inst.get_config(), {"key": "value"})

    def test_get_config_returns_none_on_invalid_json(self):
        """Lines 185-187: get_config() with invalid JSON → logs warning and returns None."""
        inst = self._make_instance(config_str="not valid json {{{")
        result = inst.get_config()
        self.assertIsNone(result)

    def test_set_config_with_dict_serializes_to_json(self):
        """set_config(dict) → self.config becomes JSON string."""
        inst = self._make_instance()
        inst.set_config({"foo": "bar"})
        self.assertEqual(json.loads(inst.config), {"foo": "bar"})

    def test_set_config_with_none_sets_config_to_none(self):
        """Line 195: set_config(None) → self.config = None."""
        inst = self._make_instance(config_str='{"old": "data"}')
        inst.set_config(None)
        self.assertIsNone(inst.config)


# ---------------------------------------------------------------------------
# IntegrationAction helpers — no DB needed (use unsaved instance)
# ---------------------------------------------------------------------------

class TestIntegrationActionHelpers(unittest.TestCase):
    """Tests for IntegrationAction JSON field helpers (no DB)."""

    def _make_action(self, required="", optional="", response=""):
        action = IntegrationAction.__new__(IntegrationAction)
        action.id = 1
        action.required_params = required
        action.optional_params = optional
        action.response_format = response
        return action

    # --- get_required_params ---

    def test_get_required_params_returns_dict_for_valid_json(self):
        action = self._make_action(required='{"type": "object"}')
        self.assertEqual(action.get_required_params(), {"type": "object"})

    def test_get_required_params_returns_empty_dict_when_blank(self):
        action = self._make_action(required="")
        self.assertEqual(action.get_required_params(), {})

    def test_get_required_params_returns_empty_dict_on_invalid_json(self):
        """Line 266: invalid JSON → logs warning and returns {}."""
        action = self._make_action(required="not json {{{")
        result = action.get_required_params()
        self.assertEqual(result, {})

    # --- set_required_params ---

    def test_set_required_params_with_valid_schema(self):
        """set_required_params with valid schema passes _validate_json_schema."""
        action = self._make_action()
        action.set_required_params({"type": "object", "properties": {}})
        self.assertIn("type", json.loads(action.required_params))

    def test_set_required_params_with_none_sets_empty_braces(self):
        action = self._make_action()
        action.set_required_params(None)
        self.assertEqual(action.required_params, "{}")

    def test_set_required_params_with_invalid_schema_raises(self):
        """set_required_params with invalid schema → ValidationError from _validate_json_schema."""
        action = self._make_action()
        with self.assertRaises(ValidationError):
            action.set_required_params({"missing_type_key": "value"})

    # --- get_optional_params ---

    def test_get_optional_params_returns_dict_for_valid_json(self):
        action = self._make_action(optional='{"type": "string"}')
        self.assertEqual(action.get_optional_params(), {"type": "string"})

    def test_get_optional_params_returns_empty_dict_when_blank(self):
        action = self._make_action(optional="")
        self.assertEqual(action.get_optional_params(), {})

    def test_get_optional_params_returns_empty_dict_on_invalid_json(self):
        """Lines 279-281: invalid JSON → logs warning and returns {}."""
        action = self._make_action(optional="bad json <<<")
        result = action.get_optional_params()
        self.assertEqual(result, {})

    # --- set_optional_params ---

    def test_set_optional_params_with_valid_schema(self):
        """Lines 286->288: set_optional_params with non-empty value triggers _validate_json_schema."""
        action = self._make_action()
        action.set_optional_params({"type": "object"})
        self.assertIn("type", json.loads(action.optional_params))

    def test_set_optional_params_with_invalid_schema_raises(self):
        """set_optional_params with invalid schema → ValidationError."""
        action = self._make_action()
        with self.assertRaises(ValidationError):
            action.set_optional_params({"no_type": True})

    def test_set_optional_params_with_none_sets_empty_braces(self):
        action = self._make_action()
        action.set_optional_params(None)
        self.assertEqual(action.optional_params, "{}")

    def test_set_optional_params_with_empty_dict_skips_validation(self):
        """set_optional_params({}) → no validation, just stores '{}'."""
        action = self._make_action()
        action.set_optional_params({})
        self.assertEqual(action.optional_params, "{}")

    # --- get_response_format ---

    def test_get_response_format_returns_dict_for_valid_json(self):
        action = self._make_action(response='{"type": "object"}')
        self.assertEqual(action.get_response_format(), {"type": "object"})

    def test_get_response_format_returns_empty_dict_when_blank(self):
        action = self._make_action(response="")
        self.assertEqual(action.get_response_format(), {})

    def test_get_response_format_returns_empty_dict_on_invalid_json(self):
        """Lines 295-297: invalid JSON → logs warning and returns {}."""
        action = self._make_action(response="definitely not json <<<")
        result = action.get_response_format()
        self.assertEqual(result, {})

    # --- set_response_format ---

    def test_set_response_format_with_dict(self):
        action = self._make_action()
        action.set_response_format({"result": "ok"})
        self.assertEqual(json.loads(action.response_format), {"result": "ok"})

    def test_set_response_format_with_none_sets_empty_braces(self):
        action = self._make_action()
        action.set_response_format(None)
        self.assertEqual(action.response_format, "{}")
