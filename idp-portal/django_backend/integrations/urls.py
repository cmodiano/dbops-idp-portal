"""
URL configuration for integrations endpoints.
Matches FastAPI /admin/integrations routes.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from integrations.views import IntegrationViewSet
from integrations.upload_views import UploadIconView

app_name = 'integrations'

router = DefaultRouter()
router.register(r'', IntegrationViewSet, basename='integration')

urlpatterns = [
    # Integrations CRUD: /api/v1/admin/integrations/*
    path('admin/integrations/', include(router.urls)),
    # Upload icon: /api/v1/admin/integrations/upload-icon
    path('admin/integrations/upload-icon', UploadIconView.as_view(), name='upload-icon'),
]
