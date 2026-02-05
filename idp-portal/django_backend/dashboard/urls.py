"""
URL configuration for dashboard endpoints.
Matches FastAPI /api/v1/dashboard/* routes used by the frontend.
"""

from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/stats", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path("dashboard/recent", views.DashboardRecentView.as_view(), name="dashboard-recent"),
    path("dashboard/timeseries", views.DashboardTimeSeriesView.as_view(), name="dashboard-timeseries"),
    path("dashboard/stats-by-technology", views.DashboardStatsByTechnologyView.as_view(), name="dashboard-stats-by-technology"),
    path("dashboard/stats-by-environment", views.DashboardStatsByEnvironmentView.as_view(), name="dashboard-stats-by-environment"),
    path("dashboard/compare", views.DashboardCompareView.as_view(), name="dashboard-compare"),
    # NOTE: This endpoint returns the object directly (no {"data": ...}) per frontend apiFetchRaw usage.
    path("dashboard/filter-options", views.DashboardFilterOptionsView.as_view(), name="dashboard-filter-options"),
]

