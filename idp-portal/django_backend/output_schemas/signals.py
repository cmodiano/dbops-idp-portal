"""
Signal handlers for OutputSchema model.
Invalidate registry cache on save/delete so all processes see updates.
Story 63.2 - Registre des Schémas & Résolution.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from output_schemas.models import OutputSchema


@receiver(post_save, sender=OutputSchema)
@receiver(post_delete, sender=OutputSchema)
def invalidate_output_schema_registry(sender, **kwargs):
    """Invalidate the registry cache when OutputSchema is created, updated, or deleted."""
    from output_schemas.registry import schema_registry
    schema_registry.invalidate()
