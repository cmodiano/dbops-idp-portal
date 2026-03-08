"""URL configuration for core app."""

from django.urls import path
from . import views
from .feature_flag_views import (
    FeatureFlagListView,
    FeatureFlagStatusView,
    FeatureFlagUpdateView,
)
from .iac_views import export_feature_flags, sync_feature_flags, get_config_sync_status

app_name = 'core'

urlpatterns = [
    path('health/', views.health_check, name='health'),
    # Story 17.12: Feature flags endpoints
    path('feature-flags/', FeatureFlagListView.as_view(), name='feature-flag-list'),
    path('feature-flags/status/', FeatureFlagStatusView.as_view(), name='feature-flag-status'),
    path('feature-flags/<str:flag_key>/', FeatureFlagUpdateView.as_view(), name='feature-flag-update'),
    # IaC endpoints (story 64.8)
    path('admin/feature-flags/export/yaml/', export_feature_flags, name='feature-flags-export-yaml'),
    path('admin/feature-flags/sync/', sync_feature_flags, name='feature-flags-sync'),
    # Config sync dashboard (story 64.14)
    path('admin/config-sync/status/', get_config_sync_status, name='config-sync-status'),
]
