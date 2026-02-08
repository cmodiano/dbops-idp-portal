"""
Tests for integrations config JSON Schema validation.
Story 20.5: Cover validate_integration_config with and without jsonschema.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from core.exceptions import InvalidStateError


class TestValidateIntegrationConfig(TestCase):
    """Tests for validate_integration_config()."""

    def test_valid_dict_no_jsonschema(self):
        """When jsonschema is not available, accepts any dict."""
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', False):
            from integrations.validation import validate_integration_config
            # Should not raise
            validate_integration_config({'some': 'config'})

    def test_invalid_non_dict_no_jsonschema(self):
        """When jsonschema is not available, rejects non-dict."""
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', False):
            from integrations.validation import validate_integration_config
            with self.assertRaises(InvalidStateError) as ctx:
                validate_integration_config("not a dict")
            self.assertEqual(ctx.exception.code, "INVALID_CONFIG")

    def test_empty_schema_skips_validation(self):
        """When schema file not found (empty schema), validation is skipped."""
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', True), \
             patch('integrations.validation._load_schema', return_value={}):
            from integrations.validation import validate_integration_config
            # Should not raise — empty schema means skip validation
            validate_integration_config({'any': 'config'})

    def test_jsonschema_validation_error(self):
        """When jsonschema validates and fails, raises InvalidStateError."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")

        mock_schema = {
            "type": "object",
            "required": ["auth_flow"],
            "properties": {
                "auth_flow": {"type": "string"}
            }
        }
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', True), \
             patch('integrations.validation._load_schema', return_value=mock_schema):
            from integrations.validation import validate_integration_config
            with self.assertRaises(InvalidStateError) as ctx:
                validate_integration_config({})  # Missing required 'auth_flow'
            self.assertEqual(ctx.exception.code, "INVALID_CONFIG")

    def test_jsonschema_valid_config(self):
        """When jsonschema validates and passes, no exception."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")

        mock_schema = {
            "type": "object",
            "properties": {
                "auth_flow": {"type": "string"}
            }
        }
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', True), \
             patch('integrations.validation._load_schema', return_value=mock_schema):
            from integrations.validation import validate_integration_config
            validate_integration_config({"auth_flow": "token"})

    def test_jsonschema_schema_error(self):
        """When schema itself is invalid, raises InvalidStateError INVALID_SCHEMA."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")

        # A schema with an invalid "type" value triggers SchemaError
        bad_schema = {"type": "not_a_real_type"}
        with patch('integrations.validation.JSONSCHEMA_AVAILABLE', True), \
             patch('integrations.validation._load_schema', return_value=bad_schema):
            from integrations.validation import validate_integration_config
            with self.assertRaises(InvalidStateError) as ctx:
                validate_integration_config({"key": "value"})
            self.assertEqual(ctx.exception.code, "INVALID_SCHEMA")


class TestLoadSchema(TestCase):
    """Tests for _load_schema() thread-safe caching."""

    def test_load_schema_caches_result(self):
        """_load_schema() caches the schema after first load (file not found path)."""
        import integrations.validation as val
        original_cache = val._SCHEMA_CACHE
        original_path = val._SCHEMA_PATH
        try:
            val._SCHEMA_CACHE = None
            # Use a fake path that doesn't exist
            val._SCHEMA_PATH = MagicMock()
            val._SCHEMA_PATH.exists.return_value = False
            result = val._load_schema()
            self.assertEqual(result, {})
            # Second call should use cache (won't call exists again)
            result2 = val._load_schema()
            self.assertEqual(result2, {})
        finally:
            val._SCHEMA_CACHE = original_cache
            val._SCHEMA_PATH = original_path

    def test_load_schema_returns_cached(self):
        """_load_schema() returns cached value if available."""
        import integrations.validation as val
        original_cache = val._SCHEMA_CACHE
        try:
            val._SCHEMA_CACHE = {"cached": True}
            result = val._load_schema()
            self.assertEqual(result, {"cached": True})
        finally:
            val._SCHEMA_CACHE = original_cache

    def test_load_schema_reads_file(self):
        """_load_schema() reads JSON schema file when it exists."""
        import integrations.validation as val
        original_cache = val._SCHEMA_CACHE
        original_path = val._SCHEMA_PATH
        try:
            val._SCHEMA_CACHE = None
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            val._SCHEMA_PATH = mock_path
            mock_file_data = '{"type": "object"}'
            with patch('builtins.open', MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(
                    read=MagicMock(return_value=mock_file_data)
                )),
                __exit__=MagicMock(return_value=False),
            ))):
                with patch('json.load', return_value={"type": "object"}):
                    result = val._load_schema()
                    self.assertEqual(result, {"type": "object"})
        finally:
            val._SCHEMA_CACHE = original_cache
            val._SCHEMA_PATH = original_path
