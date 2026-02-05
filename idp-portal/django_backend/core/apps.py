from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Initialize structlog configuration on app startup."""
        from core.logging import configure_structlog
        configure_structlog()
