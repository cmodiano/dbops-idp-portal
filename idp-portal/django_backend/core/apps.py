from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Initialize structlog configuration and validate secrets on app startup."""
        from core.logging import configure_structlog
        configure_structlog()

        # Story 17.5: Validate secrets at startup
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        from core.startup_checks import validate_required_secrets

        try:
            validate_required_secrets(
                app_env=settings.APP_ENV,
                auth_dev_bypass=settings.AUTH_DEV_BYPASS,
            )
        except ImproperlyConfigured:
            # Re-raise to stop application startup
            raise

        # Story 17.11: Validate rate limit configuration at startup
        from core.startup_checks import validate_rate_limit_config
        try:
            validate_rate_limit_config()
        except ImproperlyConfigured:
            raise

        # Story 17.12: Validate feature flags configuration at startup
        from core.startup_checks import validate_feature_flags_config
        try:
            validate_feature_flags_config()
        except ImproperlyConfigured:
            raise
