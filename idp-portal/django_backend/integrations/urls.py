"""
URL configuration for integrations endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from integrations.views import IntegrationViewSet
from integrations.upload_views import UploadIconView
from integrations.catalogue_views import IntegrationTypeCatalogueViewSet
from integrations.iac_views import (
    export_integrations, sync_integrations,
    export_integration_by_id,
    export_integration_types, sync_integration_types,
)

app_name = 'integrations'

router = DefaultRouter()
router.register(r'', IntegrationViewSet, basename='integration')

catalogue_router = DefaultRouter()
catalogue_router.register(r'', IntegrationTypeCatalogueViewSet, basename='integration-type')

urlpatterns = [
    # IaC endpoints: MUST be before router includes to avoid conflicts
    path('admin/integrations/export/yaml/', export_integrations, name='integration-export-yaml'),
    path('admin/integrations/<int:pk>/export/yaml/', export_integration_by_id, name='integration-export-yaml-by-id'),
    path('admin/integrations/sync/', sync_integrations, name='integration-sync'),
    path('admin/integration-types/export/yaml/', export_integration_types, name='integration-type-export-yaml'),
    path('admin/integration-types/sync/', sync_integration_types, name='integration-type-sync'),

    # Upload icon: MUST be before router to avoid matching as detail route
    path('admin/integrations/upload-icon/', UploadIconView.as_view(), name='upload-icon'),
    # Integrations CRUD: /api/v1/admin/integrations/*
    path('admin/integrations/', include(router.urls)),
    # Story 24.1: Integration Type Catalogue (read-only)
    path('integrations/types/', include(catalogue_router.urls)),
]
