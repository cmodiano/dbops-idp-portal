"""Dashboard API (Story 5.1, Task 1.1, 1.3, 1.4; Story 8.3; Story 8.4; Story 8.5).

Provides endpoints for dashboard statistics and recent activity:
- GET /api/v1/dashboard/stats: Aggregated statistics (AC1, Story 8.3 AC6 period filter, Story 8.4 AC7 advanced filters)
- GET /api/v1/dashboard/recent: Executions from last 24h (AC2, same window as stats)
- GET /api/v1/dashboard/stats-by-technology: Executions by engine (Story 8.3, AC3, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/stats-by-environment: Executions by env (Story 8.3, AC4, AC7; Story 8.4 filters)
- GET /api/v1/dashboard/timeseries: Executions over time (Story 8.4 filters)
- GET /api/v1/dashboard/filter-options: Available filter values (Story 8.4, AC1)
- GET /api/v1/dashboard/export/csv: Export dashboard data as CSV (Story 8.5, AC2, AC6)
- GET /api/v1/dashboard/export/pdf: Export dashboard data as PDF (Story 8.5, AC3, AC7)

RBAC: Endpoints restricted to DBA and DBOPS profiles (Story 5.1 Dev Notes).
"""

from __future__ import annotations

import asyncio
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, Response
import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

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
    DashboardExportFiltersInfo,
    DashboardExportPeriodInfo,
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


# --- Story 8.5: Dashboard Export Endpoints ---


def _compute_period_info(
    days: int,
    from_date: date | None,
    to_date: date | None,
) -> DashboardExportPeriodInfo:
    """Compute period info for export (Story 8.5, Task 3.4)."""
    today = datetime.now().date()

    if from_date and to_date:
        # Custom date range
        period_days = (to_date - from_date).days + 1
        return DashboardExportPeriodInfo(
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            days=period_days,
        )
    else:
        # Use days parameter
        start = today - timedelta(days=days - 1)
        return DashboardExportPeriodInfo(
            from_date=start.strftime("%Y-%m-%d"),
            to_date=today.strftime("%Y-%m-%d"),
            days=days,
        )


def _compute_filters_info(
    engine: str | None,
    environment: str | None,
    tags: list[str] | None,
    status: str | None,
    from_date: date | None,
    to_date: date | None,
) -> DashboardExportFiltersInfo:
    """Build filters info for export (Story 8.5, Task 3.4)."""
    return DashboardExportFiltersInfo(
        engine=engine,
        environment=environment,
        tags=tags if tags else None,
        status=status,
        from_date=from_date.strftime("%Y-%m-%d") if from_date else None,
        to_date=to_date.strftime("%Y-%m-%d") if to_date else None,
    )


@router.get("/export/csv")
async def export_dashboard_csv(
    user: UserProfile = Depends(get_current_user),
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> StreamingResponse:
    """GET /api/v1/dashboard/export/csv - Export dashboard data as CSV (Story 8.5, AC2, AC4, AC5, AC6).

    Exports dashboard statistics to CSV with:
    - Paramètres d'analyse section (date, period, filters)
    - Statistiques globales section
    - Répartition par technologie section
    - Répartition par environnement section
    - Tendances temporelles section

    Query Parameters:
        days: Period filter in days (7, 14, 30, 90). Default 14. Ignored if from_date/to_date provided.
        engine: Filter by database engine
        environment: Filter by environment
        tags: Filter by action tags
        status: Filter by execution status
        from_date: Custom period start - overrides days
        to_date: Custom period end - overrides days

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)

    logger.info(
        "dashboard_export_csv_requested",
        user_id=user.id,
        days=days,
        engine=engine,
        environment=environment,
        from_date=str(from_date) if from_date else None,
        to_date=str(to_date) if to_date else None,
    )

    # Generate filename with timestamp (AC4)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    filename = f"dashboard-report-{timestamp}.csv"

    # Compute period and filters info
    period_info = _compute_period_info(days, from_date, to_date)
    filters_info = _compute_filters_info(engine, environment, tags, status, from_date, to_date)

    # Fetch all data in parallel
    stats_task = execution_repository.get_dashboard_stats(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    tech_task = execution_repository.get_stats_by_technology_for_export(
        days=days,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    env_task = execution_repository.get_stats_by_environment_for_export(
        days=days,
        engine=engine,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    timeseries_task = execution_repository.get_dashboard_timeseries(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )

    stats, tech_stats, env_stats, timeseries = await asyncio.gather(
        stats_task, tech_task, env_task, timeseries_task
    )

    # Generate CSV
    output = io.StringIO()
    output.write("\ufeff")  # BOM UTF-8 for Excel (AC5.1)

    # Section: Paramètres d'analyse (AC5)
    output.write("# Paramètres d'analyse\n")
    output.write(f"Date d'export,{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    output.write(f"Période,Du {period_info.from_date} au {period_info.to_date} ({period_info.days} jours)\n")
    output.write(f"Filtres appliqués,{filters_info.to_display_string()}\n")
    output.write("\n")

    # Section: Statistiques globales
    output.write("# Statistiques globales\n")
    output.write("Métrique,Valeur\n")
    output.write(f"Exécutions du jour,{stats['executions_jour']}\n")
    output.write(f"Taux de succès (%),{stats['taux_succes_pct']}\n")
    output.write(f"Exécutions en cours,{stats['executions_en_cours']}\n")
    output.write(f"Exécutions en erreur,{stats['executions_en_erreur']}\n")
    output.write("\n")

    # Section: Répartition par technologie
    output.write("# Répartition par technologie\n")
    output.write("Moteur,Exécutions,Succès,Échecs,Taux de succès (%)\n")
    for tech in tech_stats:
        success_rate = tech['success_rate'] if tech['success_rate'] is not None else "N/A"
        output.write(f"{tech['engine']},{tech['count']},{tech['success']},{tech['failed']},{success_rate}\n")
    output.write("\n")

    # Section: Répartition par environnement
    output.write("# Répartition par environnement\n")
    output.write("Environnement,Exécutions,Succès,Échecs,Taux de succès (%)\n")
    for env in env_stats:
        success_rate = env['success_rate'] if env['success_rate'] is not None else "N/A"
        output.write(f"{env['environment']},{env['count']},{env['success']},{env['failed']},{success_rate}\n")
    output.write("\n")

    # Section: Tendances temporelles
    output.write("# Tendances temporelles\n")
    output.write("Date,Succès,Échecs\n")
    for point in timeseries:
        output.write(f"{point['date']},{point['success']},{point['failed']}\n")

    output.seek(0)
    content = output.getvalue().encode("utf-8")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
async def export_dashboard_pdf(
    user: UserProfile = Depends(get_current_user),
    days: int = Query(14, description="Period filter in days"),
    engine: str | None = Query(None, description="Filter by engine"),
    environment: str | None = Query(None, description="Filter by environment"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
    status: str | None = Query(None, description="Filter by execution status"),
    from_date: date | None = Query(None, description="Custom period start (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Custom period end (YYYY-MM-DD)"),
) -> Response:
    """GET /api/v1/dashboard/export/pdf - Export dashboard data as PDF (Story 8.5, AC3, AC4, AC5, AC7).

    Exports dashboard statistics to PDF with:
    - Report title and generation date
    - Period and filters information
    - Global statistics table
    - Technology breakdown table
    - Environment breakdown table

    Query Parameters:
        days: Period filter in days (7, 14, 30, 90). Default 14. Ignored if from_date/to_date provided.
        engine: Filter by database engine
        environment: Filter by environment
        tags: Filter by action tags
        status: Filter by execution status
        from_date: Custom period start - overrides days
        to_date: Custom period end - overrides days

    Restricted to DBA and DBOPS profiles.
    """
    _require_dashboard_profile(user)

    logger.info(
        "dashboard_export_pdf_requested",
        user_id=user.id,
        days=days,
        engine=engine,
        environment=environment,
        from_date=str(from_date) if from_date else None,
        to_date=str(to_date) if to_date else None,
    )

    # Generate filename with timestamp (AC4)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    filename = f"dashboard-report-{timestamp}.pdf"

    # Compute period and filters info
    period_info = _compute_period_info(days, from_date, to_date)
    filters_info = _compute_filters_info(engine, environment, tags, status, from_date, to_date)

    # Fetch all data in parallel
    stats_task = execution_repository.get_dashboard_stats(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    tech_task = execution_repository.get_stats_by_technology_for_export(
        days=days,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    env_task = execution_repository.get_stats_by_environment_for_export(
        days=days,
        engine=engine,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )
    timeseries_task = execution_repository.get_dashboard_timeseries(
        days=days,
        engine=engine,
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
    )

    stats, tech_stats, env_stats, timeseries = await asyncio.gather(
        stats_task, tech_task, env_task, timeseries_task
    )

    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    story = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=12,
    )
    header_style = ParagraphStyle(
        "CustomHeader",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#666666"),
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8,
        spaceBefore=12,
    )

    # Title
    story.append(Paragraph("Rapport Dashboard Analytics", title_style))
    story.append(Spacer(1, 0.2 * inch))

    # Metadata (AC5)
    story.append(Paragraph(f"<b>Date d'export:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", header_style))
    story.append(Paragraph(f"<b>Période:</b> Du {period_info.from_date} au {period_info.to_date} ({period_info.days} jours)", header_style))
    story.append(Paragraph(f"<b>Filtres appliqués:</b> {filters_info.to_display_string()}", header_style))
    story.append(Spacer(1, 0.3 * inch))

    # Table style
    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90d9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ])

    # Section: Statistiques globales
    story.append(Paragraph("Statistiques globales", section_style))
    stats_table_data = [
        ["Métrique", "Valeur"],
        ["Exécutions du jour", str(stats["executions_jour"])],
        ["Taux de succès", f"{stats['taux_succes_pct']}%"],
        ["Exécutions en cours", str(stats["executions_en_cours"])],
        ["Exécutions en erreur", str(stats["executions_en_erreur"])],
    ]
    stats_table = Table(stats_table_data, colWidths=[200, 100])
    stats_table.setStyle(table_style)
    story.append(stats_table)
    story.append(Spacer(1, 0.3 * inch))

    # Section: Répartition par technologie
    story.append(Paragraph("Répartition par technologie", section_style))
    tech_table_data = [["Moteur", "Exécutions", "Succès", "Échecs", "Taux de succès"]]
    for tech in tech_stats:
        success_rate = f"{tech['success_rate']}%" if tech['success_rate'] is not None else "N/A"
        tech_table_data.append([
            tech["engine"],
            str(tech["count"]),
            str(tech["success"]),
            str(tech["failed"]),
            success_rate,
        ])
    if len(tech_table_data) == 1:
        tech_table_data.append(["Aucune donnée", "-", "-", "-", "-"])
    tech_table = Table(tech_table_data, colWidths=[150, 80, 80, 80, 100])
    tech_table.setStyle(table_style)
    story.append(tech_table)
    story.append(Spacer(1, 0.3 * inch))

    # Section: Répartition par environnement
    story.append(Paragraph("Répartition par environnement", section_style))
    env_table_data = [["Environnement", "Exécutions", "Succès", "Échecs", "Taux de succès"]]
    for env in env_stats:
        success_rate = f"{env['success_rate']}%" if env['success_rate'] is not None else "N/A"
        env_table_data.append([
            env["environment"],
            str(env["count"]),
            str(env["success"]),
            str(env["failed"]),
            success_rate,
        ])
    if len(env_table_data) == 1:
        env_table_data.append(["Aucune donnée", "-", "-", "-", "-"])
    env_table = Table(env_table_data, colWidths=[150, 80, 80, 80, 100])
    env_table.setStyle(table_style)
    story.append(env_table)
    story.append(Spacer(1, 0.3 * inch))

    # Section: Tendances temporelles (AC3 - graphiques remplacés par tableau)
    story.append(Paragraph("Tendances temporelles", section_style))
    timeseries_table_data = [["Date", "Succès", "Échecs"]]
    for point in timeseries:
        timeseries_table_data.append([
            point["date"],
            str(point["success"]),
            str(point["failed"]),
        ])
    if len(timeseries_table_data) == 1:
        timeseries_table_data.append(["Aucune donnée", "-", "-"])
    timeseries_table = Table(timeseries_table_data, colWidths=[120, 100, 100])
    timeseries_table.setStyle(table_style)
    story.append(timeseries_table)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    content = buffer.read()

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
