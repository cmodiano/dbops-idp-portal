"""
URL configuration for public integrations API only.
Only integration types catalogue (read-only), excludes admin CRUD.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from integrations.catalogue_views import IntegrationTypeCatalogueViewSet

app_name = 'integrations'

catalogue_router = DefaultRouter()
catalogue_router.register(r'', IntegrationTypeCatalogueViewSet, basename='integration-type')

urlpatterns = [
    path('integrations/types/', include(catalogue_router.urls)),
]
