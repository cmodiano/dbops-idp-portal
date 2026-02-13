"""
URL configuration for integrations endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from integrations.views import IntegrationViewSet
from integrations.upload_views import UploadIconView
from integrations.catalogue_views import IntegrationTypeCatalogueViewSet

app_name = 'integrations'

router = DefaultRouter()
router.register(r'', IntegrationViewSet, basename='integration')

catalogue_router = DefaultRouter()
catalogue_router.register(r'', IntegrationTypeCatalogueViewSet, basename='integration-type')

urlpatterns = [
    # Upload icon: MUST be before router to avoid matching as detail route
    path('admin/integrations/upload-icon/', UploadIconView.as_view(), name='upload-icon'),
    # Integrations CRUD: /api/v1/admin/integrations/*
    path('admin/integrations/', include(router.urls)),
    # Story 24.1: Integration Type Catalogue (read-only)
    path('integrations/types/', include(catalogue_router.urls)),
]
