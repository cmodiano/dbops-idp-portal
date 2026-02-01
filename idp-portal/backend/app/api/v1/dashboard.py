"""Dashboard API (Story 5.1, Task 1.1, 1.3, 1.4; Story 8.3; Story 8.4).

Provides endpoints for dashboard statistics and recent activity:
- GET /api/v1/dashboard/stats: Aggregated statistics (AC1, Story 8.3 AC6 period filter, Story 8.4 AC7 advanced filters)
- GET /api/v1/dashboard/recent: Executions from last 24h (AC2, same window as stats)
- GET /api/v1/dashboard/stats-by-technology: Executions by engine (Story 8.3, AC3, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/stats-by-environment: Executions by env (Story 8.3, AC4, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/timeseries: Executions over time (Story 8.4 filters)
- GET /api/v1/dashboard/filter-options: Available filter values (Story 8.4, AC1)

RBAC: Endpoints restricted to DBA and DBOPS profiles (Story 5.1 Dev Notes).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
import structlog

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenError
from app.models.auth import UserProfile
from app.models.dashboard import (
    DashboardStatsData,
    DashboardStatsResponse,
    TechnologyStats,
    EnvironmentStats,
    DashboardStatsByTechnologyResponse,
    DashboardStatsByEnvironmentResponse,
    FilterOptionsResponse,
)
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


# DashboardStatsData, DashboardStatsResponse imported from app.models.dashboard


from pydantic import BaseModel


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
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> DashboardStatsResponse:
    """GET /api/v1/dashboard/stats - Dashboard statistics (Story 5.1, AC1, AC4; Story 8.3, AC6; Story 8.4, AC7).

    Returns aggregated metrics for the dashboard:
    - executions_jour: Executions created today (always current day)
    - taux_succes_pct: Success rate (%) over selected period
    - executions_en_cours: Currently running executions
    - executions_en_erreur: Failed executions in selected period

    Query Parameters:
        days: Period filter in days (7, 14, 30, 90). Default 14. Ignored if from_date/to_date provided.
        engine: Filter by database engine (Story 8.4)
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days (Story 8.4)
        to_date: Custom period end - overrides days (Story 8.4)

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info(
        "dashboard_stats_requested",
        user_id=user.id,
        profile=user.profile,
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=str(from_date) if from_date else None,
        to_date=str(to_date) if to_date else None,
    )

    stats = await execution_repository.get_dashboard_stats(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
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
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> DashboardTimeSeriesResponse:
    """GET /api/v1/dashboard/timeseries - Executions over time for line chart (Story 8.4, AC7).

    Returns daily success and failed counts for the last N days (default 14).

    Query Parameters:
        days: Period filter in days. Default 14. Ignored if from_date/to_date provided.
        engine: Filter by database engine (Story 8.4)
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        from_date: Custom period start - overrides days (Story 8.4)
        to_date: Custom period end - overrides days (Story 8.4)

    Note: status filter is not available for timeseries since it always tracks
    success (COMPLETED) vs failed (FAILED) counts regardless of other statuses.

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info(
        "dashboard_timeseries_requested",
        user_id=user.id,
        days=days,
        engine=engine,
        environment=environment,
    )
    points = await execution_repository.get_dashboard_timeseries(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=None,  # Not used for timeseries - always tracks success/failed
        from_date=from_date,
        to_date=to_date,
    )
    return DashboardTimeSeriesResponse(data=points)


# --- Story 8.3: Stats by Technology and Environment ---
# TechnologyStats, EnvironmentStats, response wrappers imported from app.models.dashboard


@router.get("/stats-by-technology", response_model=DashboardStatsByTechnologyResponse)
async def get_stats_by_technology(
    user: UserProfile = Depends(get_current_user),
    days: int = Query(14, description="Period filter in days"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> DashboardStatsByTechnologyResponse:
    """GET /api/v1/dashboard/stats-by-technology - Executions grouped by engine (Story 8.3, AC3, AC7; Story 8.4, AC7).

    Returns execution counts and success rates aggregated by database engine.

    Query Parameters:
        days: Period filter in days (7, 14, 30, 90). Default 14. Ignored if from_date/to_date provided.
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days (Story 8.4)
        to_date: Custom period end - overrides days (Story 8.4)

    Note: engine is not a filter since it's the grouping key.

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info(
        "dashboard_stats_by_technology_requested",
        user_id=user.id,
        days=days,
        environment=environment,
    )

    stats = await execution_repository.get_stats_by_technology(
        days=days,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    return DashboardStatsByTechnologyResponse(data=[TechnologyStats(**s) for s in stats])


@router.get("/stats-by-environment", response_model=DashboardStatsByEnvironmentResponse)
async def get_stats_by_environment(
    user: UserProfile = Depends(get_current_user),
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> DashboardStatsByEnvironmentResponse:
    """GET /api/v1/dashboard/stats-by-environment - Executions grouped by environment (Story 8.3, AC4, AC7; Story 8.4, AC7).

    Returns execution counts and success rates aggregated by environment.
    Results are ordered: dev, staging, prod, then alphabetical for custom envs.

    Query Parameters:
        days: Period filter in days (7, 14, 30, 90). Default 14. Ignored if from_date/to_date provided.
        engine: Filter by database engine (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days (Story 8.4)
        to_date: Custom period end - overrides days (Story 8.4)

    Note: environment is not a filter since it's the grouping key.

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info(
        "dashboard_stats_by_environment_requested",
        user_id=user.id,
        days=days,
        engine=engine,
    )

    stats = await execution_repository.get_stats_by_environment(
        days=days,
        engine=engine,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    return DashboardStatsByEnvironmentResponse(data=[EnvironmentStats(**s) for s in stats])


@router.get("/filter-options", response_model=FilterOptionsResponse)
async def get_filter_options(
    user: UserProfile = Depends(get_current_user),
) -> FilterOptionsResponse:
    """GET /api/v1/dashboard/filter-options - Available filter values (Story 8.4, Task 14).

    Returns distinct values for each filter type based on actual data:
    - engines: Available database engines from published actions
    - environments: Used environments from executions
    - tags: All available tags
    - statuses: All possible execution statuses

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)
    logger.info("dashboard_filter_options_requested", user_id=user.id)

    options = await execution_repository.get_filter_options()
    return FilterOptionsResponse(**options)
