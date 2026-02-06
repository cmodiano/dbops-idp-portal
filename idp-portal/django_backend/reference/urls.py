"""
URL configuration for reference API.
Story 13.7 - Reference endpoints.
"""

from django.urls import path
from reference.views import list_engines, list_platforms

urlpatterns = [
    path('engines', list_engines, name='reference-engines'),
    path('platforms', list_platforms, name='reference-platforms'),
]
