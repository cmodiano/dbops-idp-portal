"""Dashboard API (Story 5.1, Task 1.1, 1.3, 1.4).

Provides endpoints for dashboard statistics and recent activity:
- GET /api/v1/dashboard/stats: Aggregated statistics (AC1)
- GET /api/v1/dashboard/recent: Executions from last 24h (AC2, same window as stats)

RBAC: Endpoints restricted to DBA and DBOPS profiles (Story 5.1 Dev Notes).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
import structlog

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError
from app.models.auth import UserProfile
from app.repositories import execution_repository

logger = structlog.get_logger()

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Allowed profiles for dashboard (Story 5.1 Dev Notes)
_DASHBOARD_ALLOWED_PROFILES = frozenset({"dba", "dbops"})


def _require_dashboard_profile(user: UserProfile) -> None:
    """Raise 403 if user profile is not DBA or DBOPS."""
    if (user.profile or "").lower() not in _DASHBOARD_ALLOWED_PROFILES:
        raise ForbiddenError(
            code="DASHBOARD_ACCESS_DENIED",
            message="Accès réservé aux profils DBA et DBOPS.",
        )


class DashboardStatsData(BaseModel):
    """Dashboard statistics (Story 5.1, AC1, AC4)."""

    executions_jour: int
    taux_succes_pct: float
    executions_en_cours: int
    executions_en_erreur: int


class DashboardStatsResponse(BaseModel):
    """Response wrapper for GET /dashboard/stats."""

    data: DashboardStatsData


class DashboardRecentItem(BaseModel):
    """Single recent execution for dashboard (Story 5.1, AC2)."""

    id: int
    action_name: str | None
    user_display_name: str
    environment: str
    status: str
    created_at: str | None
    platform: str | None = None
    engine: str | None = None


class DashboardRecentResponse(BaseModel):
    """Response wrapper for GET /dashboard/recent."""

    data: list[DashboardRecentItem]


class DashboardTimeSeriesPoint(BaseModel):
    """One day in the executions time series."""

    date: str  # YYYY-MM-DD
    success: int
    failed: int


class DashboardTimeSeriesResponse(BaseModel):
    """Response wrapper for GET /dashboard/timeseries."""

    data: list[DashboardTimeSeriesPoint]


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    user: UserProfile = Depends(get_current_user),
) -> DashboardStatsResponse:
    """GET /api/v1/dashboard/stats - Dashboard statistics (Story 5.1, AC1, AC4).

    Returns aggregated metrics for the dashboard:
    - executions_jour: Executions created today
    - taux_succes_pct: Success rate (%) over last 24h
    - executions_en_cours: Currently running executions
    - executions_en_erreur: Failed executions in last 24h

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info("dashboard_stats_requested", user_id=user.id, profile=user.profile)

    stats = await execution_repository.get_dashboard_stats()
    return DashboardStatsResponse(data=DashboardStatsData(**stats))


# Limit for recent executions (same 24h window as stats so table counts match)
DASHBOARD_RECENT_LIMIT = 100


@router.get("/recent", response_model=DashboardRecentResponse)
async def get_dashboard_recent(
    user: UserProfile = Depends(get_current_user),
) -> DashboardRecentResponse:
    """GET /api/v1/dashboard/recent - Recent executions (Story 5.1, AC2, AC4).

    Returns executions from the **last 24 hours** (same window as stats), so the table
    shows exactly the set used for executions_en_erreur and taux_succes_pct. Up to 100 rows.
    Each execution includes: action_name, user_display_name, environment, status, created_at, platform, engine.

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info("dashboard_recent_requested", user_id=user.id, profile=user.profile)

    executions = await execution_repository.list_recent_executions(limit=DASHBOARD_RECENT_LIMIT)
    return DashboardRecentResponse(data=[DashboardRecentItem(**e) for e in executions])


@router.get("/timeseries", response_model=DashboardTimeSeriesResponse)
async def get_dashboard_timeseries(
    user: UserProfile = Depends(get_current_user),
    days: int = 14,
) -> DashboardTimeSeriesResponse:
    """GET /api/v1/dashboard/timeseries - Executions over time for line chart.

    Returns daily success and failed counts for the last N days (default 14).
    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info("dashboard_timeseries_requested", user_id=user.id, days=days)
    points = await execution_repository.get_dashboard_timeseries(days=days)
    return DashboardTimeSeriesResponse(data=points)
