"""
Django app configuration for inventory module.
Story 13.1 - Inventaire : source via intégration, association target-environnement.
"""

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Configuration for the inventory app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventory Management'
