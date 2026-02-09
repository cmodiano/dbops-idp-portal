"""
URL configuration for inventory API.
Story 13.1 - Target endpoints.
Story 13.7 - Environment endpoint.
Story 23.3 - Multi-table inventory endpoints.
"""

from django.urls import path
from inventory.views import (
    list_targets, list_all_targets, list_environments,
    list_servers, list_instances, list_databases,
)

urlpatterns = [
    path('targets/', list_targets, name='inventory-targets'),
    path('targets/all/', list_all_targets, name='inventory-targets-all'),
    path('environments/', list_environments, name='inventory-environments'),
    # Story 23.3: Multi-table inventory
    path('servers/', list_servers, name='inventory-servers'),
    path('instances/', list_instances, name='inventory-instances'),
    path('databases/', list_databases, name='inventory-databases'),
]
