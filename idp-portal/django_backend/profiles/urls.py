"""URL configuration for profiles app."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from profiles import views

app_name = 'profiles'

# Create router for profiles CRUD
profiles_router = DefaultRouter()
profiles_router.register(r'profiles', views.ProfileViewSet, basename='profile')

urlpatterns = [
    # Profiles CRUD: /api/v1/admin/profiles/*
    path('', include(profiles_router.urls)),
    
    # Export YAML: /api/v1/admin/profiles/export
    path('profiles/export', views.ProfileExportView.as_view(), name='profile-export'),
    
    # Import YAML: /api/v1/admin/profiles/import
    path('profiles/import', views.ProfileImportView.as_view(), name='profile-import'),
]
