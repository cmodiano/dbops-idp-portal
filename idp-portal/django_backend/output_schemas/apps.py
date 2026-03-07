"""
Django app configuration for output_schemas module.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from django.apps import AppConfig


class OutputSchemasConfig(AppConfig):
    """Configuration for the output_schemas app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'output_schemas'
    verbose_name = 'Output Schemas'

    def ready(self) -> None:
        import output_schemas.signals  # noqa: F401
