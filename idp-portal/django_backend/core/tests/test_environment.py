"""
Tests for EnvironmentHelper — Story 26.7.

Unit tests for centralized case-insensitive environment comparison helper.
"""
from core.environment import EnvironmentHelper


# --- normalize() ---


class TestNormalize:
    def test_lowercase(self):
        assert EnvironmentHelper.normalize('DEV') == 'dev'
        assert EnvironmentHelper.normalize('PROD') == 'prod'
        assert EnvironmentHelper.normalize('Staging') == 'staging'

    def test_trim(self):
        assert EnvironmentHelper.normalize('  staging  ') == 'staging'
        assert EnvironmentHelper.normalize('\tdev\n') == 'dev'

    def test_none(self):
        assert EnvironmentHelper.normalize(None) == ''

    def test_empty(self):
        assert EnvironmentHelper.normalize('') == ''

    def test_already_lowercase(self):
        assert EnvironmentHelper.normalize('dev') == 'dev'

    def test_numeric_coercion(self):
        """Non-string input is coerced via str()."""
        assert EnvironmentHelper.normalize(123) == '123'


# --- matches() ---


class TestMatches:
    def test_case_insensitive(self):
        assert EnvironmentHelper.matches('DEV', 'dev') is True
        assert EnvironmentHelper.matches('Staging', 'STAGING') is True

    def test_different(self):
        assert EnvironmentHelper.matches('dev', 'prod') is False

    def test_none_vs_empty(self):
        assert EnvironmentHelper.matches(None, '') is True

    def test_none_vs_value(self):
        assert EnvironmentHelper.matches(None, 'dev') is False

    def test_both_none(self):
        assert EnvironmentHelper.matches(None, None) is True

    def test_whitespace(self):
        assert EnvironmentHelper.matches('  dev  ', 'DEV') is True


# --- is_in() ---


class TestIsIn:
    def test_found(self):
        assert EnvironmentHelper.is_in('DEV', ['dev', 'staging', 'prod']) is True
        assert EnvironmentHelper.is_in('Staging', ['DEV', 'STAGING', 'PROD']) is True

    def test_not_found(self):
        assert EnvironmentHelper.is_in('qa', ['dev', 'prod']) is False

    def test_none(self):
        assert EnvironmentHelper.is_in(None, ['dev']) is False

    def test_empty_string(self):
        assert EnvironmentHelper.is_in('', ['dev']) is False

    def test_empty_list(self):
        assert EnvironmentHelper.is_in('dev', []) is False

    def test_whitespace_in_list(self):
        assert EnvironmentHelper.is_in('dev', ['  DEV  ', 'prod']) is True


# --- find_in_dict() ---


class TestFindInDict:
    def test_found(self):
        config = {'DEV': {'required': False}, 'PROD': {'required': True}}
        result = EnvironmentHelper.find_in_dict(config, 'dev')
        assert result == {'required': False}

    def test_case_insensitive(self):
        config = {'STAGING': {'change': True}}
        result = EnvironmentHelper.find_in_dict(config, 'staging')
        assert result == {'change': True}

    def test_not_found(self):
        config = {'DEV': {'x': 1}}
        result = EnvironmentHelper.find_in_dict(config, 'prod')
        assert result is None

    def test_none_env(self):
        config = {'DEV': {'x': 1}}
        result = EnvironmentHelper.find_in_dict(config, None)
        assert result is None

    def test_empty_config(self):
        result = EnvironmentHelper.find_in_dict({}, 'dev')
        assert result is None

    def test_none_config(self):
        result = EnvironmentHelper.find_in_dict(None, 'dev')
        assert result is None

    def test_returns_non_dict_value(self):
        """find_in_dict returns whatever value is stored, even if not a dict."""
        config = {'DEV': 'string_value'}
        result = EnvironmentHelper.find_in_dict(config, 'dev')
        assert result == 'string_value'

    def test_whitespace_key(self):
        config = {'  DEV  ': {'x': 1}}
        result = EnvironmentHelper.find_in_dict(config, 'dev')
        assert result == {'x': 1}
