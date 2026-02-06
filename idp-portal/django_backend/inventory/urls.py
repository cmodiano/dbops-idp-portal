"""
URL configuration for inventory API.
Story 13.1 - Target endpoints.
"""

from django.urls import path
from inventory.views import list_targets, list_all_targets

urlpatterns = [
    path('targets', list_targets, name='inventory-targets'),
    path('targets/all', list_all_targets, name='inventory-targets-all'),
]
