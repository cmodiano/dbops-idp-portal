"""Shared helpers for dashboard views.

Story 26.8 AC3: Extracted from dashboard views for reuse across modules.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter

from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.permissions import IsAdminUser
from core.models import AuditActionType
from executions.models import ExecutionStatus

import structlog

RETRY_ACTION_TYPES = [
    AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT,
    AuditActionType.EXECUTION_STEP_RETRY_SUCCESS,
    AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED,
    AuditActionType.EXECUTION_STEP_RETRY_ABORTED,
]

logger = structlog.get_logger(__name__)

DASHBOARD_PARAMS = [
    OpenApiParameter('from_date', str, description='Date de début (YYYY-MM-DD)'),
    OpenApiParameter('to_date', str, description='Date de fin (YYYY-MM-DD)'),
    OpenApiParameter('days', int, description='Nombre de jours (défaut: 14, si from_date/to_date non fournis)'),
    OpenApiParameter('engine', str, description='Filtrage par technologie'),
    OpenApiParameter('environment', str, description='Filtrage par environnement'),
    OpenApiParameter('tags', str, description='Tags (multi-valeur, OR)'),
    OpenApiParameter('status', str, description='Filtrage par statut (pour timeseries/stats-by-*)'),
]


def parse_int(value: str | None, default: int, *, name: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide", details={name: value})


def parse_date(value: str | None, *, name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide (YYYY-MM-DD)", details={name: value})


def filter_queryset_by_ownership(qs: QuerySet, request, permission_class=IsAdminUser) -> QuerySet:
    """
    Filter queryset to user's own objects unless user has admin permission.

    Story 26.8 AC3: Extracted pattern from 6 dashboard views.
    Uses permission_class (default: IsAdminUser) to determine if user sees all executions.
    """
    permission = permission_class()
    if not permission.has_permission(request, None):
        qs = qs.filter(user_id=request.user.id)
    return qs


def get_period_bounds(request) -> tuple[datetime, datetime]:
    """
    Determine period bounds for dashboard aggregations.
    Uses from_date/to_date (YYYY-MM-DD) if provided; else uses days (default 14).
    Returns [start_dt, end_exclusive_dt] in timezone-aware datetimes.
    """
    from_date = parse_date(request.query_params.get("from_date"), name="from_date")
    to_date = parse_date(request.query_params.get("to_date"), name="to_date")
    if from_date and to_date:
        start_dt = timezone.make_aware(datetime.combine(from_date, datetime.min.time()))
        end_exclusive = timezone.make_aware(datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
        return start_dt, end_exclusive

    days = parse_int(request.query_params.get("days"), 14, name="days")
    if days <= 0:
        raise BadRequestError(code="BAD_REQUEST", message="days invalide", details={"days": days})
    end_exclusive = timezone.now()
    start_dt = end_exclusive - timedelta(days=days)
    return start_dt, end_exclusive


def apply_common_filters(qs: QuerySet, *, request: Any, include_status: bool) -> QuerySet:
    """
    Apply common dashboard filters:
    - engine (Action.engine)
    - environment (Execution.environment)
    - tags (multi query params, OR semantics)
    - status (Execution.status) (optional; historically ignored for dashboard stats)
    """
    engine = request.query_params.get("engine")
    if engine:
        qs = qs.filter(action__engine=engine)

    environment = request.query_params.get("environment")
    if environment:
        qs = qs.filter(environment__iexact=environment)

    tags = request.query_params.getlist("tags")
    tags = [t.strip() for t in tags if t and t.strip()]
    if tags:
        qs = qs.filter(action__actiontag__tag__name__in=tags)

    if include_status:
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

    return qs


def compute_avg_duration_s(qs) -> float | None:
    """
    Compute average execution duration in seconds for completed executions.

    DASH-MED-02: Extracted shared helper to avoid duplication between
    stats_for_queryset() and DashboardStatsOperationsView.get().
    Pattern Python (compatibilité Oracle) — itération côté Python sur (started_at, completed_at).

    NEW-BE-J: Added row count guard to avoid unbounded memory materialisation for large
    datasets. When the count exceeds the threshold, a warning is logged and None is returned
    rather than loading tens of thousands of rows into Python memory.
    """

    _MAX_DURATION_ROWS = 10_000
    completed_qs = qs.filter(
        status=ExecutionStatus.COMPLETED,
        started_at__isnull=False,
        completed_at__isnull=False,
    )
    row_count = completed_qs.count()
    if row_count > _MAX_DURATION_ROWS:
        logger.warning(
            "dashboard_avg_duration_skipped_too_many_rows",
            row_count=row_count,
            threshold=_MAX_DURATION_ROWS,
            correlation_id=get_correlation_id(),
        )
        return None
    durations = []
    for started_at, completed_at in completed_qs.values_list("started_at", "completed_at"):
        try:
            delta = (completed_at - started_at).total_seconds()
            if delta >= 0:
                durations.append(delta)
        except (TypeError, AttributeError) as e:
            logger.debug(
                "execution_duration_calculation_skipped",
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=get_correlation_id(),
            )
            continue
    return round(sum(durations) / len(durations), 2) if durations else None


def stats_for_queryset(qs) -> dict:
    """
    Compute ComparisonStats for a queryset of executions.
    """
    execution_count = qs.count()
    incident_count = qs.filter(status=ExecutionStatus.FAILED).count()

    finished = qs.filter(status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).count()
    completed = qs.filter(status=ExecutionStatus.COMPLETED).count()
    success_rate = round((completed / finished) * 100, 2) if finished > 0 else None

    avg_time = compute_avg_duration_s(qs)  # DASH-MED-02: use shared helper

    return {
        "success_rate": success_rate,
        "avg_time": avg_time,
        "execution_count": int(execution_count or 0),
        "incident_count": int(incident_count or 0),
    }


def delta_pct(v1: float | int | None, v2: float | int | None) -> float | None:
    if v1 is None or v2 is None:
        return None
    try:
        v1f = float(v1)
        v2f = float(v2)
    except (ValueError, TypeError):
        return None
    if v1f == 0:
        return None
    return round(((v2f - v1f) / v1f) * 100.0, 2)
