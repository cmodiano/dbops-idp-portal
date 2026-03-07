"""
Story 17.5: Unit tests for startup secret validation.

Tests validate_required_secrets() in isolation using mocked environment variables.
"""

import pytest
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured


pytestmark = pytest.mark.security


class TestValidateRequiredSecrets:
    """Tests for validate_required_secrets() function."""

    def test_production_missing_secret_key_fails(self):
        """Production sans SECRET_KEY doit lever ImproperlyConfigured."""
        env = {
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY is not set"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_insecure_secret_key_fails(self):
        """Production avec SECRET_KEY django-insecure doit lever ImproperlyConfigured."""
        env = {
            'SECRET_KEY': 'django-insecure-test-value',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SECRET_KEY contains insecure default"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_placeholder_jwt_secret_fails(self):
        """Production avec placeholder JWT_SECRET_KEY doit lever ImproperlyConfigured."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'CHANGE_JWT_SECRET',
            'ORACLE_PASSWORD': 'valid-oracle-password',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="JWT_SECRET_KEY contains unreplaced placeholder"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_changeme_oracle_password_fails(self):
        """Production avec ORACLE_PASSWORD='changeme' doit lever ImproperlyConfigured."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="ORACLE_PASSWORD contains insecure default"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_missing_saml_certs_with_saml_active_fails(self):
        """Production + AUTH_DEV_BYPASS=false + SAML certs manquants doit lever ImproperlyConfigured."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '',
            'SAML_SP_KEY_PATH': '',
            'SAML_IDP_CERT_PATH': '',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured, match="SAML_SP_CERT_PATH required"):
                validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_production_all_valid_secrets_succeeds(self):
        """Production avec tous les secrets valides ne doit pas lever d'exception."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '/etc/idp/certs/sp.crt',
            'SAML_SP_KEY_PATH': '/etc/idp/certs/sp.key',
            'SAML_IDP_CERT_PATH': '/etc/idp/certs/idp.crt',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_development_insecure_secrets_warns_but_succeeds(self):
        """Dev mode avec secrets par défaut doit avertir mais pas lever d'exception."""
        env = {
            'SECRET_KEY': 'django-insecure-dev-only',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            # Ne doit pas lever d'exception en dev
            validate_required_secrets(app_env='development', auth_dev_bypass=True)

    def test_staging_treated_as_production(self):
        """Staging doit être traité comme production (fail-fast)."""
        env = {
            'SECRET_KEY': 'changeme',
            'JWT_SECRET_KEY': 'valid-jwt-key',
            'ORACLE_PASSWORD': 'valid-oracle-pw',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            with pytest.raises(ImproperlyConfigured):
                validate_required_secrets(app_env='staging', auth_dev_bypass=False)

    def test_dev_bypass_warning_logged(self):
        """Dev + AUTH_DEV_BYPASS=true doit logger un avertissement."""
        env = {
            'SECRET_KEY': 'django-insecure-dev-only',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            # Should not raise - dev mode allows insecure defaults
            validate_required_secrets(app_env='development', auth_dev_bypass=True)

    def test_production_saml_bypass_skips_cert_validation(self):
        """Production + AUTH_DEV_BYPASS=true doit ignorer la validation SAML certs."""
        env = {
            'SECRET_KEY': 'valid-production-secret-key-abc123',
            'JWT_SECRET_KEY': 'valid-jwt-secret-key-xyz789',
            'ORACLE_PASSWORD': 'valid-oracle-password',
            'SAML_SP_CERT_PATH': '',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            # Should not raise because auth_dev_bypass=True skips SAML cert check
            validate_required_secrets(app_env='production', auth_dev_bypass=True)


class TestValidateCorsConfig:
    """Tests SEC-4: CORS config validated at startup in production."""

    def test_59_4_a_production_cors_origin_missing_raises(self):
        """59-4-a: DEBUG=False, CORS_ORIGIN absent → ImproperlyConfigured."""
        with patch.dict('os.environ', {'CORS_ORIGIN': ''}, clear=False):
            from core.startup_checks import validate_cors_config
            with pytest.raises(ImproperlyConfigured, match="CORS_ORIGIN"):
                validate_cors_config(debug=False)

    def test_59_4_b_production_cors_origin_set_succeeds(self):
        """59-4-b: DEBUG=False, CORS_ORIGIN défini → pas d'exception."""
        with patch.dict('os.environ', {'CORS_ORIGIN': 'https://idp.internal'}, clear=False):
            from core.startup_checks import validate_cors_config
            validate_cors_config(debug=False)  # Should not raise

    def test_59_4_c_development_cors_origin_missing_succeeds(self):
        """59-4-c: DEBUG=True (dev mode), CORS_ORIGIN absent → pas d'exception."""
        with patch.dict('os.environ', {'CORS_ORIGIN': ''}, clear=False):
            from core.startup_checks import validate_cors_config
            validate_cors_config(debug=True)  # Should not raise in dev

    def test_59_4_d_production_cors_origin_whitespace_only_raises(self):
        """59-4-d: DEBUG=False, CORS_ORIGIN='   ' (whitespace) → ImproperlyConfigured."""
        with patch.dict('os.environ', {'CORS_ORIGIN': '   '}, clear=False):
            from core.startup_checks import validate_cors_config
            with pytest.raises(ImproperlyConfigured, match="CORS_ORIGIN"):
                validate_cors_config(debug=False)


class TestValidateSuperuserFallbackConfig:
    """Tests SEC-5: ALLOW_SUPERUSER_FALLBACK interdit en production."""

    def test_59_5_a_production_fallback_enabled_raises(self):
        """59-5-a: DEBUG=False, ALLOW_SUPERUSER_FALLBACK=True → ImproperlyConfigured."""
        from core.startup_checks import validate_superuser_fallback_config
        with pytest.raises(ImproperlyConfigured, match="ALLOW_SUPERUSER_FALLBACK"):
            validate_superuser_fallback_config(debug=False, allow_superuser_fallback=True)

    def test_59_5_b_production_fallback_disabled_succeeds(self):
        """59-5-b: DEBUG=False, ALLOW_SUPERUSER_FALLBACK=False → pas d'exception."""
        from core.startup_checks import validate_superuser_fallback_config
        validate_superuser_fallback_config(debug=False, allow_superuser_fallback=False)

    def test_59_5_c_development_fallback_enabled_succeeds(self):
        """59-5-c: DEBUG=True (dev mode), ALLOW_SUPERUSER_FALLBACK=True → pas d'exception."""
        from core.startup_checks import validate_superuser_fallback_config
        validate_superuser_fallback_config(debug=True, allow_superuser_fallback=True)

    def test_59_5_d_development_fallback_disabled_succeeds(self):
        """59-5-d: DEBUG=True (dev mode), ALLOW_SUPERUSER_FALLBACK=False → pas d'exception."""
        from core.startup_checks import validate_superuser_fallback_config
        validate_superuser_fallback_config(debug=True, allow_superuser_fallback=False)
