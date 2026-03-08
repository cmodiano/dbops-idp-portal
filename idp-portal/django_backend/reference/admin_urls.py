"""
Admin URL configuration for reference categories CRUD.
Story 2.30 - Admin CRUD categories (DBOPS only).
Mounted at /api/v1/admin/ in main urls.py.
"""

from django.urls import path
from reference.views import create_category, update_category, delete_category, update_engine
from reference.iac_views import (
    export_ref_engines, sync_ref_engines,
    export_ref_categories, sync_ref_categories,
)

urlpatterns = [
    # IaC endpoints (story 64.8)
    path('reference/engines/export/yaml/', export_ref_engines, name='ref-engines-export-yaml'),
    path('reference/engines/sync/', sync_ref_engines, name='ref-engines-sync'),
    path('reference/categories/export/yaml/', export_ref_categories, name='ref-categories-export-yaml'),
    path('reference/categories/sync/', sync_ref_categories, name='ref-categories-sync'),

    path('categories/', create_category, name='admin-category-create'),
    path('categories/<int:pk>/', update_category, name='admin-category-update'),
    path('categories/<int:pk>/delete/', delete_category, name='admin-category-delete'),
    path('engines/<int:pk>/', update_engine, name='admin-engine-update'),
]
