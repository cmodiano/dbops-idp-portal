"""
URL configuration for inventory API.
Story 13.1 - Target endpoints.
Story 13.7 - Environment endpoint.
"""

from django.urls import path
from inventory.views import list_targets, list_all_targets, list_environments

urlpatterns = [
    path('targets', list_targets, name='inventory-targets'),
    path('targets/all', list_all_targets, name='inventory-targets-all'),
    path('environments', list_environments, name='inventory-environments'),
]
