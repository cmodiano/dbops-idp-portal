"""Dashboard views package — re-exports for backward compatibility.

Refactored from monolithic views.py into thematic modules.
"""
from core.utils import ensure_utc_isoformat  # noqa: F401 — used by submodules for datetime serialization
from dashboard.views.stats import (
    DashboardStatsView,
    DashboardStatsByTechnologyView,
    DashboardStatsByEnvironmentView,
)
from dashboard.views.timeseries import DashboardTimeSeriesView
from dashboard.views.recent_filter_compare import (
    DashboardRecentView,
    DashboardFilterOptionsView,
    DashboardCompareView,
)
from dashboard.views.catalogue_adoption import (
    DashboardStatsCatalogueView,
    DashboardStatsAdoptionView,
)
from dashboard.views.operations_approbations import (
    DashboardStatsOperationsView,
    DashboardStatsApprobationsView,
)
from dashboard.views.planifiees_retries import (
    DashboardStatsPlanifieesView,
    DashboardStatsRetriesView,
)

__all__ = [
    "DashboardStatsView",
    "DashboardRecentView",
    "DashboardTimeSeriesView",
    "DashboardStatsByTechnologyView",
    "DashboardStatsByEnvironmentView",
    "DashboardFilterOptionsView",
    "DashboardCompareView",
    "DashboardStatsCatalogueView",
    "DashboardStatsAdoptionView",
    "DashboardStatsOperationsView",
    "DashboardStatsApprobationsView",
    "DashboardStatsPlanifieesView",
    "DashboardStatsRetriesView",
]
