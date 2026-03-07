from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self) -> None:
        """Initialize structlog and validate startup configuration (secrets, rate limits, feature flags, CORS, superuser fallback)."""
        from core.logging import configure_structlog
        configure_structlog()

        # Story 22.20: Import OpenAPI schema extensions so drf-spectacular autodiscovers them
        import core.schema  # noqa: F401

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

        # SEC-4: Validate CORS configuration at startup
        from core.startup_checks import validate_cors_config
        try:
            validate_cors_config(debug=settings.DEBUG)
        except ImproperlyConfigured:
            raise

        # SEC-5: Validate ALLOW_SUPERUSER_FALLBACK configuration at startup
        from core.startup_checks import validate_superuser_fallback_config
        try:
            validate_superuser_fallback_config(
                debug=settings.DEBUG,
                allow_superuser_fallback=settings.ALLOW_SUPERUSER_FALLBACK,
            )
        except ImproperlyConfigured:
            raise
