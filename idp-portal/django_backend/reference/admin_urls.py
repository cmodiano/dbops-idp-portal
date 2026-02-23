"""
Admin URL configuration for reference categories CRUD.
Story 2.30 - Admin CRUD categories (DBOPS only).
Mounted at /api/v1/admin/ in main urls.py.
"""

from django.urls import path
from reference.views import create_category, update_category, delete_category, update_engine

urlpatterns = [
    path('categories/', create_category, name='admin-category-create'),
    path('categories/<int:pk>/', update_category, name='admin-category-update'),
    path('categories/<int:pk>/delete/', delete_category, name='admin-category-delete'),
    path('engines/<int:pk>/', update_engine, name='admin-engine-update'),
]
