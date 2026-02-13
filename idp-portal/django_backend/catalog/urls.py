"""URL configuration for catalog app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalog import views

app_name = 'catalog'

# Create routers for different endpoint groups
admin_router = DefaultRouter()
admin_router.register(r'actions', views.ActionViewSet, basename='admin-actions')

catalog_router = DefaultRouter()
catalog_router.register(r'actions', views.CatalogActionViewSet, basename='catalog-actions')

tags_router = DefaultRouter()
tags_router.register(r'', views.TagViewSet, basename='tags')

urlpatterns = [
    # Admin endpoints: /api/v1/admin/actions/*
    path('admin/', include(admin_router.urls)),
    
    # Catalog endpoints: /api/v1/catalog/actions/*
    path('catalog/', include(catalog_router.urls)),
    
    # Tags endpoints: /api/v1/tags/*
    path('tags/', include(tags_router.urls)),
    
    # Catalog tags endpoint: /api/v1/catalog/tags (handled by TagViewSet.list_catalog_tags action)
    path('catalog/tags/', views.TagViewSet.as_view({'get': 'list_catalog_tags'}), name='catalog-tags-list'),
]
