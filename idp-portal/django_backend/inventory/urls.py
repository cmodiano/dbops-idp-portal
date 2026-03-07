"""
URL configuration for inventory API.
Story 13.1 - Target endpoints.
Story 13.7 - Environment endpoint.
Story 23.3 - Multi-table inventory endpoints.

⚠️  INTERNAL USE ONLY — Usage interne uniquement (frontend).
Ces routes ne sont pas documentées dans l'API publique (Swagger/ReDoc).
Cf. Story 44.3 - @extend_schema(exclude=True) sur toutes les vues.
"""

from django.urls import path
from inventory.views import (
    list_targets, list_all_targets, list_environments,
    list_servers, list_instances, list_databases,
    get_inventory_schema,
)

urlpatterns = [
    path('targets/', list_targets, name='inventory-targets'),
    path('targets/all/', list_all_targets, name='inventory-targets-all'),
    path('environments/', list_environments, name='inventory-environments'),
    # Story 23.3: Multi-table inventory
    path('servers/', list_servers, name='inventory-servers'),
    path('instances/', list_instances, name='inventory-instances'),
    path('databases/', list_databases, name='inventory-databases'),
    # Story 62.3: Inventory schema — available columns per entity type
    path('schema/', get_inventory_schema, name='inventory-schema'),
]
