"""URL configuration for profiles app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from profiles import views

app_name = 'profiles'

# Create router for profiles CRUD
profiles_router = DefaultRouter()
profiles_router.register(r'profiles', views.ProfileViewSet, basename='profile')

urlpatterns = [
    # Export/Import YAML: MUST be before router to avoid matching as detail routes
    path('profiles/export/', views.ProfileExportView.as_view(), name='profile-export'),
    path('profiles/import/', views.ProfileImportView.as_view(), name='profile-import'),
    # CaC-aligned aliases (story 64.8)
    path('profiles/export/yaml/', views.ProfileExportView.as_view(), name='profile-export-yaml'),
    path('profiles/sync/', views.ProfileImportView.as_view(), name='profile-sync'),
    # Story 64.13: Single-entity export
    path('profiles/<int:pk>/export/yaml/', views.export_profile_by_id, name='profile-export-yaml-by-id'),

    # Profiles CRUD: /api/v1/admin/profiles/*
    path('', include(profiles_router.urls)),
]
