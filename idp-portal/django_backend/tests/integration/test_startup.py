"""
Story 17.5: Integration tests for application startup secret validation.

Tests that CoreConfig.ready() properly triggers secret validation
and behaves correctly in dev vs production environments.
"""

import pytest
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured


pytestmark = pytest.mark.integration


class TestApplicationStartup:
    """Story 17.5: Tests d'intégration du démarrage de l'application."""

    def test_validate_secrets_called_from_app_ready(self):
        """CoreConfig.ready() must call validate_required_secrets."""
        with patch('core.startup_checks.validate_required_secrets') as mock_validate:
            with patch('core.logging.configure_structlog'):
                from django.apps import apps
                core_config = apps.get_app_config('core')
                core_config.ready()
                mock_validate.assert_called_once()

    def test_app_startup_fails_without_secrets_in_production(self):
        """L'application refuse de démarrer en production sans secrets."""
        env = {
            'APP_ENV': 'production',
            'SECRET_KEY': '',
            'JWT_SECRET_KEY': '',
            'ORACLE_PASSWORD': '',
        }
        with patch.dict('os.environ', env, clear=False):
            with patch('core.logging.configure_structlog'):
                with pytest.raises(ImproperlyConfigured):
                    from core.startup_checks import validate_required_secrets
                    validate_required_secrets(app_env='production', auth_dev_bypass=False)

    def test_app_startup_succeeds_in_development(self):
        """L'application démarre en dev avec secrets par défaut."""
        env = {
            'APP_ENV': 'development',
            'SECRET_KEY': 'django-insecure-dev',
            'JWT_SECRET_KEY': 'change-me-in-production',
            'ORACLE_PASSWORD': 'changeme',
        }
        with patch.dict('os.environ', env, clear=False):
            from core.startup_checks import validate_required_secrets
            # Ne doit pas lever d'exception en dev
            validate_required_secrets(app_env='development', auth_dev_bypass=True)
