"""
URL configuration for dashboard endpoints.
"""

from django.urls import path

from dashboard import views
from dashboard.export_views import DashboardExportCSVView, DashboardExportPDFView

app_name = "dashboard"

urlpatterns = [
    path("dashboard/stats/", views.DashboardStatsView.as_view(), name="dashboard-stats"),
    path("dashboard/recent/", views.DashboardRecentView.as_view(), name="dashboard-recent"),
    path("dashboard/timeseries/", views.DashboardTimeSeriesView.as_view(), name="dashboard-timeseries"),
    path("dashboard/stats-by-technology/", views.DashboardStatsByTechnologyView.as_view(), name="dashboard-stats-by-technology"),
    path("dashboard/stats-by-environment/", views.DashboardStatsByEnvironmentView.as_view(), name="dashboard-stats-by-environment"),
    path("dashboard/compare/", views.DashboardCompareView.as_view(), name="dashboard-compare"),
    # Story 60.1: Stats catalogue admin (actions par statut/type/engine/catégorie + évolution)
    path("dashboard/stats-catalogue/", views.DashboardStatsCatalogueView.as_view(), name="dashboard-stats-catalogue"),
    # Story 60.2: Stats adoption par profil (exécutions/utilisateurs actifs/tendance hebdo)
    path("dashboard/stats-adoption/", views.DashboardStatsAdoptionView.as_view(), name="dashboard-stats-adoption"),
    # Story 60.5: Stats opérations enrichies (durée moyenne, top actions, plateformes)
    path("dashboard/stats-operations/", views.DashboardStatsOperationsView.as_view(), name="dashboard-stats-operations"),
    # Story 60.6: Stats approbations (volume approuvé/rejeté, taux, délai moyen)
    path("dashboard/stats-approbations/", views.DashboardStatsApprobationsView.as_view(), name="dashboard-stats-approbations"),
    # NOTE: This endpoint returns the object directly (no {"data": ...}) per frontend apiFetchRaw usage.
    path("dashboard/filter-options/", views.DashboardFilterOptionsView.as_view(), name="dashboard-filter-options"),
    # Story 30.2: Dashboard export endpoints
    path("dashboard/export/csv", DashboardExportCSVView.as_view(), name="dashboard-export-csv"),
    path("dashboard/export/pdf", DashboardExportPDFView.as_view(), name="dashboard-export-pdf"),
]

