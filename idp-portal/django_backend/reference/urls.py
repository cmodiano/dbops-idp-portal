"""
URL configuration for reference API.
Story 13.7 - Reference endpoints.
Story 2.30 - Category list endpoint.
"""

from django.urls import path
from reference.views import list_engines, list_platforms, list_categories

urlpatterns = [
    path('engines/', list_engines, name='reference-engines'),
    path('platforms/', list_platforms, name='reference-platforms'),
    # Story 2.30: Categories (GET for all authenticated users)
    path('categories/', list_categories, name='reference-categories'),
]
