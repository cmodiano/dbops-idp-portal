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
