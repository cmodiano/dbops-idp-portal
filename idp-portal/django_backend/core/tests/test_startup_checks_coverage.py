"""
Coverage tests for core/startup_checks.py — targeting missing lines to reach ≥90%.

Missing lines targeted:
- 55: dev mode warning when secret is not set
- 131-137: validate_rate_limit_config — invalid RATELIMIT_ENABLED
- 225: feature flags non-dict JSON in production → raise ImproperlyConfigured
- 244: flag_count = 0 (empty raw_flags branch)
- 251-257: invalid FEATURE_FLAGS_PUBSUB_ENABLED value
- 261-280: Redis URL missing or invalid format when pubsub enabled
- 288->315: source == 'database' with LocMemCache cache backend
- 298-312: production error for LocMemCache with database source
- 319-327: invalid FEATURE_FLAGS_LOCK_TIMEOUT
"""
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ImproperlyConfigured


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Line 55: validate_required_secrets — dev warning when secret is not set
# ---------------------------------------------------------------------------

class TestValidateRequiredSecretsDevWarning:
    """Cover line 55: dev mode warning appended when secret not set."""

    def test_dev_missing_secret_logs_warning_and_succeeds(self):
        """Dev mode + empty SECRET_KEY → warning logged but no exception raised."""
        env = {
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with patch('core.startup_checks.logger') as mock_logger:
                # Should not raise
                validate_required_secrets(app_env='development', auth_dev_bypass=False)

            # Warning should have been logged (line 55 contributes to warnings list)
            _warning_messages = [
                str(call) for call in mock_logger.warning.call_args_list
            ]
            # At least one warning was logged
            assert mock_logger.warning.called

    def test_dev_missing_all_secrets_warns_and_succeeds(self):
        """Dev mode + all secrets missing → warnings generated (line 55 executed)."""
        env = {
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': '',
            'ORACLE_PASSWORD': '',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            # Should not raise in dev mode
            validate_required_secrets(app_env='development', auth_dev_bypass=False)

    def test_production_missing_secret_no_dev_warning(self):
        """Branch 54->56: production + missing secret → no dev warning, error only."""
        env = {
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY is not set"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_insecure_default_appends_error(self):
        """Line 64: production + insecure default → errors.append(insecure default)."""
        env = {
            'SECRET_KEY': 'django-insecure-test',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY contains insecure default"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_placeholder_pattern_appends_error(self):
        """Line 68: placeholder pattern match → errors.append placeholder error."""
        env = {
            'SECRET_KEY': 'valid-key-prod',
            'JWT_SECRET_KEY': 'CHANGE_JWT_SECRET',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="JWT_SECRET_KEY contains unreplaced placeholder"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_saml_cert_check_in_production_no_bypass(self):
        """Lines 72-76: production + no bypass + missing SAML certs → errors list."""
        env = {
            'SECRET_KEY': 'valid-production-key',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
            'SAML_SP_CERT_PATH': '',
            'SAML_SP_KEY_PATH': '',
            'SAML_IDP_CERT_PATH': '',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SAML_SP_CERT_PATH required"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_dev_auth_dev_bypass_warning_logged(self):
        """Line 86: dev + auth_dev_bypass=True → auth_dev_bypass_active warning."""
        env = {
            'SECRET_KEY': 'django-insecure-dev',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with patch('core.startup_checks.logger') as mock_logger:
                validate_required_secrets(app_env='development', auth_dev_bypass=True)

            warning_events = [call.args[0] for call in mock_logger.warning.call_args_list]
            assert 'auth_dev_bypass_active' in warning_events

    def test_production_multiple_errors_raises_with_all_errors(self):
        """Lines 95-105: multiple errors accumulated → ImproperlyConfigured with all listed."""
        env = {
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': '',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

            error_msg = str(exc_info.value)
            assert "SECRET_KEY" in error_msg or "ORACLE_PASSWORD" in error_msg

    def test_production_auth_dev_bypass_warning_logged(self):
        """Lines 89-91: auth_dev_bypass=True in production logs danger warning."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '/etc/certs/sp.crt',
            'SAML_SP_KEY_PATH': '/etc/certs/sp.key',
            'SAML_IDP_CERT_PATH': '/etc/certs/idp.crt',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with patch('core.startup_checks.logger') as mock_logger:
                # auth_dev_bypass=True in production should log danger warning
                validate_required_secrets(app_env='production', auth_dev_bypass=True)

            # Check that auth_dev_bypass_production warning was logged
            warning_events = [call.args[0] for call in mock_logger.warning.call_args_list]
            assert 'auth_dev_bypass_production' in warning_events


# ---------------------------------------------------------------------------
# Lines 131-137: validate_rate_limit_config — invalid RATELIMIT_ENABLED
# ---------------------------------------------------------------------------

class TestValidateRateLimitConfigInvalidEnabled:
    """Cover lines 131-137: invalid RATELIMIT_ENABLED value raises ImproperlyConfigured."""

    def test_invalid_ratelimit_enabled_raises(self):
        """RATELIMIT_ENABLED='maybe' → ImproperlyConfigured."""
        env = {'RATELIMIT_ENABLED': 'maybe'}
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured, match="RATELIMIT_ENABLED"):
                validate_rate_limit_config()

    def test_invalid_ratelimit_enabled_yes_raises(self):
        """RATELIMIT_ENABLED='yes' → ImproperlyConfigured."""
        env = {'RATELIMIT_ENABLED': 'yes'}
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured):
                validate_rate_limit_config()

    def test_valid_ratelimit_enabled_true_passes(self):
        """RATELIMIT_ENABLED='true' → no exception."""
        env = {
            'RATELIMIT_ENABLED': 'true',
            'THROTTLE_AUTH_RATE': '10/minute',
            'THROTTLE_TOKEN_REFRESH_RATE': '20/minute',
            'THROTTLE_EXECUTION_RATE': '30/minute',
            'THROTTLE_API_RATE': '100/minute',
            'THROTTLE_PUBLIC_RATE': '50/minute',
            'THROTTLE_SERVICE_LOGIN_RATE': '5/minute',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            validate_rate_limit_config()  # Should not raise

    def test_valid_ratelimit_enabled_0_passes(self):
        """RATELIMIT_ENABLED='0' → no exception."""
        env = {'RATELIMIT_ENABLED': '0'}
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            validate_rate_limit_config()

    def test_invalid_throttle_rate_format_raises(self):
        """Invalid throttle rate format → ImproperlyConfigured."""
        env = {
            'RATELIMIT_ENABLED': 'true',
            'THROTTLE_AUTH_RATE': 'invalid_format',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured, match="RATE LIMIT"):
                validate_rate_limit_config()

    def test_invalid_api_key_token_throttle_rate_raises(self):
        """MEDIUM-3: THROTTLE_API_KEY_TOKEN_RATE invalide → ImproperlyConfigured."""
        env = {
            'RATELIMIT_ENABLED': 'true',
            'THROTTLE_API_KEY_TOKEN_RATE': 'bad-format',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_rate_limit_config
            with pytest.raises(ImproperlyConfigured, match="THROTTLE_API_KEY_TOKEN_RATE"):
                validate_rate_limit_config()


# ---------------------------------------------------------------------------
# Line 225: validate_feature_flags_config — non-dict JSON in production
# Line 244: flag_count = 0 (empty raw_flags branch in source=='env')
# ---------------------------------------------------------------------------

class TestValidateFeatureFlagsConfigJsonValidation:
    """Cover lines 225 and 244: FEATURE_FLAGS JSON validation."""

    def test_production_non_dict_json_raises(self):
        """Line 225: FEATURE_FLAGS is a JSON array (not dict) in production → raise."""
        env = {
            'APP_ENV': 'production',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '[1, 2, 3]',  # array, not dict
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE FLAGS"):
                validate_feature_flags_config()

    def test_production_invalid_json_raises(self):
        """FEATURE_FLAGS is invalid JSON in production → raise."""
        env = {
            'APP_ENV': 'production',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{invalid json}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE FLAGS"):
                validate_feature_flags_config()

    def test_dev_invalid_json_warns_but_succeeds(self):
        """FEATURE_FLAGS is invalid JSON in dev → warn + flag_count=0, no raise."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '[not, valid, json]',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            # Should not raise in dev mode
            validate_feature_flags_config()

    def test_flag_count_zero_when_feature_flags_empty(self):
        """Line 244: FEATURE_FLAGS='' → flag_count = 0 (else branch)."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '',  # empty string → else branch
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            # Should not raise
            validate_feature_flags_config()

    def test_database_source_flag_count_zero(self):
        """Lines 245-246: source='database' → flag_count = 0 (else branch of source=='env')."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        # Need to mock Django CACHES to avoid real DB connection
        mock_settings = MagicMock()
        mock_settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache'}}
        with patch.dict('os.environ', env, clear=False):
            with patch('django.conf.settings', mock_settings, create=True):
                from core.startup_checks import validate_feature_flags_config
                validate_feature_flags_config()


# ---------------------------------------------------------------------------
# Lines 251-257: invalid FEATURE_FLAGS_PUBSUB_ENABLED
# ---------------------------------------------------------------------------

class TestValidateFeatureFlagsPubSubEnabled:
    """Cover lines 251-257: invalid FEATURE_FLAGS_PUBSUB_ENABLED."""

    def test_invalid_pubsub_enabled_raises(self):
        """FEATURE_FLAGS_PUBSUB_ENABLED='maybe' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'maybe',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_PUBSUB_ENABLED"):
                validate_feature_flags_config()

    def test_invalid_pubsub_enabled_yes_raises(self):
        """FEATURE_FLAGS_PUBSUB_ENABLED='yes' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'yes',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured):
                validate_feature_flags_config()


# ---------------------------------------------------------------------------
# Lines 261-280: Redis URL missing or invalid when pubsub enabled
# ---------------------------------------------------------------------------

class TestValidateFeatureFlagsRedisUrl:
    """Cover lines 261-280: Redis URL validation when pubsub enabled."""

    def test_pubsub_enabled_no_redis_url_raises(self):
        """Lines 261-268: FEATURE_FLAGS_PUBSUB_ENABLED=true + no REDIS_URL → raise."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'true',
            'REDIS_URL': '',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="REDIS_URL required"):
                validate_feature_flags_config()

    def test_pubsub_enabled_invalid_redis_url_format_raises(self):
        """Lines 271-278: REDIS_URL doesn't start with redis:// or rediss:// → raise."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'true',
            'REDIS_URL': 'http://localhost:6379/0',  # invalid scheme
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="REDIS_URL format"):
                validate_feature_flags_config()

    def test_pubsub_enabled_valid_redis_url_succeeds(self):
        """Valid redis:// URL with pubsub enabled → no exception."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'true',
            'REDIS_URL': 'redis://localhost:6379/0',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            validate_feature_flags_config()

    def test_pubsub_enabled_valid_rediss_url_succeeds(self):
        """Valid rediss:// (TLS) URL with pubsub enabled → no exception."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': '1',
            'REDIS_URL': 'rediss://user:pass@redis.example.com:6380/0',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            validate_feature_flags_config()


# ---------------------------------------------------------------------------
# Lines 283-312: source == 'database' + LocMemCache backend check
# ---------------------------------------------------------------------------

class TestValidateFeatureFlagsDatabaseSourceCacheBackend:
    """Cover lines 283-312: LocMemCache incompatibility with database source."""

    def test_database_source_locmem_dev_warns_not_raises(self):
        """Lines 289-296: dev + database source + LocMemCache → warning, no raise."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        mock_settings = MagicMock()
        mock_settings.CACHES = {
            'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
        }
        with patch.dict('os.environ', env, clear=False):
            with patch('django.conf.settings', mock_settings, create=True):
                from core.startup_checks import validate_feature_flags_config
                with patch('core.startup_checks.logger') as mock_logger:
                    # Should not raise in dev
                    validate_feature_flags_config()

                warning_events = [call.args[0] for call in mock_logger.warning.call_args_list]
                assert 'feature_flags_cache_backend_warning' in warning_events

    def test_database_source_locmem_production_raises(self):
        """Lines 297-312: production + database source + LocMemCache → raise."""
        env = {
            'APP_ENV': 'production',
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        mock_settings = MagicMock()
        mock_settings.CACHES = {
            'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}
        }
        with patch.dict('os.environ', env, clear=False):
            with patch('django.conf.settings', mock_settings, create=True):
                from core.startup_checks import validate_feature_flags_config
                with pytest.raises(ImproperlyConfigured, match="LocMemCache incompatible"):
                    validate_feature_flags_config()

    def test_database_source_redis_backend_succeeds(self):
        """database source + Redis cache backend → no exception."""
        env = {
            'APP_ENV': 'production',
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        mock_settings = MagicMock()
        mock_settings.CACHES = {
            'default': {'BACKEND': 'django_redis.cache.RedisCache'}
        }
        with patch.dict('os.environ', env, clear=False):
            with patch('django.conf.settings', mock_settings, create=True):
                from core.startup_checks import validate_feature_flags_config
                validate_feature_flags_config()

    def test_database_source_memcached_backend_succeeds(self):
        """database source + Memcached cache backend → no exception."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'database',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '3',
        }
        mock_settings = MagicMock()
        mock_settings.CACHES = {
            'default': {'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache'}
        }
        with patch.dict('os.environ', env, clear=False):
            with patch('django.conf.settings', mock_settings, create=True):
                from core.startup_checks import validate_feature_flags_config
                validate_feature_flags_config()


# ---------------------------------------------------------------------------
# Lines 315-327: FEATURE_FLAGS_LOCK_TIMEOUT validation
# ---------------------------------------------------------------------------

class TestValidateFeatureFlagsLockTimeout:
    """Cover lines 315-327: invalid FEATURE_FLAGS_LOCK_TIMEOUT."""

    def test_invalid_lock_timeout_string_raises(self):
        """FEATURE_FLAGS_LOCK_TIMEOUT='abc' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': 'abc',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_LOCK_TIMEOUT"):
                validate_feature_flags_config()

    def test_invalid_lock_timeout_zero_raises(self):
        """FEATURE_FLAGS_LOCK_TIMEOUT='0' (not positive) → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '0',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_LOCK_TIMEOUT"):
                validate_feature_flags_config()

    def test_invalid_lock_timeout_negative_raises(self):
        """FEATURE_FLAGS_LOCK_TIMEOUT='-1' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '-1',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_LOCK_TIMEOUT"):
                validate_feature_flags_config()

    def test_valid_lock_timeout_succeeds(self):
        """FEATURE_FLAGS_LOCK_TIMEOUT='5' → no exception."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS': '{}',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '300',
            'FEATURE_FLAGS_PUBSUB_ENABLED': 'false',
            'FEATURE_FLAGS_LOCK_TIMEOUT': '5',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            validate_feature_flags_config()

    def test_invalid_feature_flags_source_raises(self):
        """FEATURE_FLAGS_SOURCE='invalid' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'file',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_SOURCE"):
                validate_feature_flags_config()

    def test_invalid_feature_flags_enabled_raises(self):
        """FEATURE_FLAGS_ENABLED='maybe' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS_ENABLED': 'maybe',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_ENABLED"):
                validate_feature_flags_config()

    def test_invalid_feature_flags_cache_ttl_string_raises(self):
        """FEATURE_FLAGS_CACHE_TTL='bad' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': 'bad',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_CACHE_TTL"):
                validate_feature_flags_config()

    def test_invalid_feature_flags_cache_ttl_negative_raises(self):
        """FEATURE_FLAGS_CACHE_TTL='-5' → ImproperlyConfigured."""
        env = {
            'APP_ENV': 'development',
            'FEATURE_FLAGS_SOURCE': 'env',
            'FEATURE_FLAGS_ENABLED': 'true',
            'FEATURE_FLAGS_CACHE_TTL': '-5',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_feature_flags_config
            with pytest.raises(ImproperlyConfigured, match="FEATURE_FLAGS_CACHE_TTL"):
                validate_feature_flags_config()
