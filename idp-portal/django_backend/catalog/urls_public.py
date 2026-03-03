"""
URL configuration for public catalog API only.
Excludes admin endpoints (actions CRUD, business-rule-policies).
Used by Swagger UI public schema.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from catalog import views

app_name = 'catalog'

catalog_router = DefaultRouter()
catalog_router.register(r'actions', views.CatalogActionViewSet, basename='catalog-actions')

tags_router = DefaultRouter()
tags_router.register(r'', views.TagViewSet, basename='tags')

urlpatterns = [
    path('catalog/', include(catalog_router.urls)),
    path('tags/', include(tags_router.urls)),
    path('catalog/tags/', views.TagViewSet.as_view({'get': 'list_catalog_tags'}), name='catalog-tags-list'),
]
