"""URL configuration for core app."""

from django.urls import path
from . import views
from .feature_flag_views import (
    FeatureFlagListView,
    FeatureFlagStatusView,
    FeatureFlagUpdateView,
)

app_name = 'core'

urlpatterns = [
    path('health/', views.health_check, name='health'),
    # Story 17.12: Feature flags endpoints
    path('feature-flags/', FeatureFlagListView.as_view(), name='feature-flag-list'),
    path('feature-flags/status/', FeatureFlagStatusView.as_view(), name='feature-flag-status'),
    path('feature-flags/<str:flag_key>/', FeatureFlagUpdateView.as_view(), name='feature-flag-update'),
]
