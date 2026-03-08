"""URL configuration for catalog app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalog import views
from catalog.cac_views import (
    export_actions, sync_actions,
    export_action_by_id,
    export_policies, sync_policies,
    export_tags, sync_tags,
)

app_name = 'catalog'

# Create routers for different endpoint groups
admin_router = DefaultRouter()
admin_router.register(r'actions', views.ActionViewSet, basename='admin-actions')
admin_router.register(r'business-rule-policies', views.BusinessRulePolicyViewSet, basename='business-rule-policies')

catalog_router = DefaultRouter()
catalog_router.register(r'actions', views.CatalogActionViewSet, basename='catalog-actions')

tags_router = DefaultRouter()
tags_router.register(r'', views.TagViewSet, basename='tags')

urlpatterns = [
    # CaC endpoints: MUST be before router includes to avoid conflicts
    path('admin/actions/export/yaml/', export_actions, name='action-export-yaml'),
    path('admin/actions/<int:pk>/export/yaml/', export_action_by_id, name='action-export-yaml-by-id'),
    path('admin/actions/sync/', sync_actions, name='action-sync'),
    path('admin/policies/export/yaml/', export_policies, name='policy-export-yaml'),
    path('admin/policies/sync/', sync_policies, name='policy-sync'),
    path('admin/tags/export/yaml/', export_tags, name='tag-export-yaml'),
    path('admin/tags/sync/', sync_tags, name='tag-sync'),

    # Admin endpoints: /api/v1/admin/actions/*
    path('admin/', include(admin_router.urls)),

    # Catalog endpoints: /api/v1/catalog/actions/*
    path('catalog/', include(catalog_router.urls)),

    # Tags endpoints: /api/v1/tags/*
    path('tags/', include(tags_router.urls)),

    # Catalog tags endpoint: /api/v1/catalog/tags (handled by TagViewSet.list_catalog_tags action)
    path('catalog/tags/', views.TagViewSet.as_view({'get': 'list_catalog_tags'}), name='catalog-tags-list'),
]
