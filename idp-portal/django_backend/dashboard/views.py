from __future__ import annotations

from datetime import datetime, timedelta, date

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import ensure_utc_isoformat
import structlog

from catalog.models import Action, Tag
from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from executions.models import Execution, ExecutionStatus

logger = structlog.get_logger(__name__)


def _parse_int(value: str | None, default: int, *, name: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide", details={name: value})


def _parse_date(value: str | None, *, name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide (YYYY-MM-DD)", details={name: value})


def _is_dba_or_dbops(user) -> bool:
    profile = (getattr(user, "profile", "") or "").lower()
    return profile == "dbops" or profile == "dba" or profile.startswith("dba")


def _get_period_bounds(request) -> tuple[datetime, datetime]:
    """
    Determine period bounds for dashboard aggregations.
    Uses from_date/to_date (YYYY-MM-DD) if provided; else uses days (default 14).
    Returns [start_dt, end_exclusive_dt] in timezone-aware datetimes.
    """
    from_date = _parse_date(request.query_params.get("from_date"), name="from_date")
    to_date = _parse_date(request.query_params.get("to_date"), name="to_date")
    if from_date and to_date:
        start_dt = timezone.make_aware(datetime.combine(from_date, datetime.min.time()))
        end_exclusive = timezone.make_aware(datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
        return start_dt, end_exclusive

    days = _parse_int(request.query_params.get("days"), 14, name="days")
    if days <= 0:
        raise BadRequestError(code="BAD_REQUEST", message="days invalide", details={"days": days})
    end_exclusive = timezone.now()
    start_dt = end_exclusive - timedelta(days=days)
    return start_dt, end_exclusive


def _apply_common_filters(qs, *, request, include_status: bool) -> object:
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
        qs = qs.filter(environment=environment)

    tags = request.query_params.getlist("tags")
    tags = [t.strip() for t in tags if t and t.strip()]
    if tags:
        qs = qs.filter(action__actiontag__tag__name__in=tags)

    if include_status:
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

    return qs


class DashboardStatsView(APIView):
    """GET /dashboard/stats -> {data: DashboardStats}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Base queryset: scope = all for DBA/DBOPS, else mine
        qs_base = Execution.objects.select_related("action")
        if not _is_dba_or_dbops(request.user):
            qs_base = qs_base.filter(user_id=request.user.id)

        # For dashboard stats, ignore status filter for consistency
        qs_base = _apply_common_filters(qs_base, request=request, include_status=False)

        period_start, period_end_exclusive = _get_period_bounds(request)
        qs_period = qs_base.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        # executions_jour: always today (regardless of period) but with engine/environment/tags filters
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        executions_jour = qs_base.filter(created_at__gte=today_start).count()

        # executions_en_cours: current running/pending (not period-scoped)
        executions_en_cours = qs_base.filter(
            status__in=[ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING, ExecutionStatus.PENDING_APPROVAL]
        ).count()

        # executions_en_erreur + taux_succes_pct: period-scoped
        executions_en_erreur = qs_period.filter(status=ExecutionStatus.FAILED).count()
        completed_period = qs_period.filter(status=ExecutionStatus.COMPLETED).count()
        failed_period = executions_en_erreur
        total_finished = completed_period + failed_period
        taux_succes_pct = round((completed_period / total_finished) * 100, 1) if total_finished > 0 else 0.0

        return Response(
            {
                "data": {
                    "executions_jour": executions_jour,
                    "taux_succes_pct": taux_succes_pct,
                    "executions_en_cours": executions_en_cours,
                    "executions_en_erreur": executions_en_erreur,
                }
            }
        )


class DashboardRecentView(APIView):
    """GET /dashboard/recent -> {data: DashboardRecentExecution[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = 10
        qs = Execution.objects.select_related("action", "user").order_by("-created_at")
        if not _is_dba_or_dbops(request.user):
            qs = qs.filter(user_id=request.user.id)

        items = list(qs[:limit])
        data = []
        for e in items:
            action = getattr(e, "action", None)
            user = getattr(e, "user", None)
            data.append(
                {
                    "id": e.id,
                    "action_name": action.name if action else None,
                    "user_display_name": getattr(user, "display_name", None) or "Unknown",
                    "environment": e.environment,
                    "status": e.status,
                    "created_at": ensure_utc_isoformat(e.created_at),
                    "platform": getattr(action, "platform", None) if action else None,
                    "engine": getattr(action, "engine", None) if action else None,
                }
            )
        return Response({"data": data})


class DashboardTimeSeriesView(APIView):
    """GET /dashboard/timeseries -> {data: DashboardTimeSeriesPoint[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Execution.objects.select_related("action")
        if not _is_dba_or_dbops(request.user):
            qs = qs.filter(user_id=request.user.id)

        # Ignore status filter (timeseries always success/failed)
        qs = _apply_common_filters(qs, request=request, include_status=False)

        period_start, period_end_exclusive = _get_period_bounds(request)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        points = (
            qs.annotate(exec_date=TruncDate("created_at"))
            .values("exec_date")
            .annotate(
                success=Count("id", filter=Q(status=ExecutionStatus.COMPLETED)),
                failed=Count("id", filter=Q(status=ExecutionStatus.FAILED)),
            )
            .order_by("exec_date")
        )

        data = [
            {
                "date": p["exec_date"].strftime("%Y-%m-%d") if p["exec_date"] else None,
                "success": int(p["success"] or 0),
                "failed": int(p["failed"] or 0),
            }
            for p in points
            if p["exec_date"] is not None
        ]
        return Response({"data": data})


class DashboardStatsByTechnologyView(APIView):
    """GET /dashboard/stats-by-technology -> {data: TechnologyStats[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Execution.objects.select_related("action")
        if not _is_dba_or_dbops(request.user):
            qs = qs.filter(user_id=request.user.id)

        # Ignore status filter; engine is grouping key
        qs = _apply_common_filters(qs, request=request, include_status=False)

        period_start, period_end_exclusive = _get_period_bounds(request)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        grouped = (
            qs.values("action__engine")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status=ExecutionStatus.COMPLETED)),
                failed=Count("id", filter=Q(status=ExecutionStatus.FAILED)),
            )
            .order_by("action__engine")
        )

        data = []
        for row in grouped:
            engine = row["action__engine"] or "N/A"
            completed = int(row["completed"] or 0)
            failed = int(row["failed"] or 0)
            finished = completed + failed
            success_rate = round((completed / finished) * 100, 1) if finished > 0 else None
            data.append(
                {
                    "engine": engine,
                    "count": int(row["count"] or 0),
                    "success_rate": success_rate,
                }
            )
        return Response({"data": data})


class DashboardStatsByEnvironmentView(APIView):
    """GET /dashboard/stats-by-environment -> {data: EnvironmentStats[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Execution.objects.select_related("action")
        if not _is_dba_or_dbops(request.user):
            qs = qs.filter(user_id=request.user.id)

        # Ignore status filter; environment is grouping key
        qs = _apply_common_filters(qs, request=request, include_status=False)

        period_start, period_end_exclusive = _get_period_bounds(request)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        grouped = (
            qs.values("environment")
            .annotate(
                count=Count("id"),
                completed=Count("id", filter=Q(status=ExecutionStatus.COMPLETED)),
                failed=Count("id", filter=Q(status=ExecutionStatus.FAILED)),
            )
        )

        # Custom ordering: dev, staging, prod, then alpha
        order_rank = {"dev": 0, "staging": 1, "prod": 2}
        rows = list(grouped)
        rows.sort(key=lambda r: (order_rank.get((r["environment"] or "").lower(), 99), (r["environment"] or "")))

        data = []
        for row in rows:
            env = row["environment"]
            completed = int(row["completed"] or 0)
            failed = int(row["failed"] or 0)
            finished = completed + failed
            success_rate = round((completed / finished) * 100, 1) if finished > 0 else None
            data.append(
                {
                    "environment": env,
                    "count": int(row["count"] or 0),
                    "success_rate": success_rate,
                }
            )
        return Response({"data": data})


class DashboardFilterOptionsView(APIView):
    """GET /dashboard/filter-options -> FilterOptions (NOT wrapped in {"data": ...})."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Engines from published actions
        engines = (
            Action.objects.filter(status="published")
            .values_list("engine", flat=True)
            .distinct()
            .order_by("engine")
        )
        engines_list = sorted({e for e in engines if e and str(e).strip()})

        # Environments used in executions
        envs = Execution.objects.values_list("environment", flat=True).distinct()
        order_rank = {"dev": 0, "staging": 1, "prod": 2}
        envs_list = sorted({e for e in envs if e and str(e).strip()}, key=lambda e: (order_rank.get(str(e).lower(), 99), str(e)))

        # All tags
        tags = Tag.objects.values_list("name", flat=True).distinct().order_by("name")
        tags_list = [t for t in tags if t and str(t).strip()]

        # All possible statuses
        statuses_list = [choice[0] for choice in ExecutionStatus.choices]

        return Response(
            {
                "engines": engines_list,
                "environments": envs_list,
                "tags": tags_list,
                "statuses": statuses_list,
            }
        )


def _stats_for_queryset(qs) -> dict:
    """
    Compute ComparisonStats for a queryset of executions.
    """
    execution_count = qs.count()
    incident_count = qs.filter(status=ExecutionStatus.FAILED).count()

    finished = qs.filter(status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).count()
    completed = qs.filter(status=ExecutionStatus.COMPLETED).count()
    success_rate = round((completed / finished) * 100, 2) if finished > 0 else None

    # Average execution time in seconds for completed executions (only if timestamps are present)
    durations = []
    for started_at, completed_at in qs.filter(
        status=ExecutionStatus.COMPLETED,
        started_at__isnull=False,
        completed_at__isnull=False,
    ).values_list("started_at", "completed_at"):
        try:
            delta = (completed_at - started_at).total_seconds()
            if delta >= 0:
                durations.append(delta)
        except (TypeError, AttributeError) as e:
            # Story 17.6: Specific catch for invalid timestamp data
            logger.debug(
                "execution_duration_calculation_skipped",
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=get_correlation_id(),
            )
            continue

    avg_time = round(sum(durations) / len(durations), 2) if durations else None

    return {
        "success_rate": success_rate,
        "avg_time": avg_time,
        "execution_count": int(execution_count or 0),
        "incident_count": int(incident_count or 0),
    }


def _delta_pct(v1: float | int | None, v2: float | int | None) -> float | None:
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


class DashboardCompareView(APIView):
    """
    GET /dashboard/compare (Story 8.6)

    Query params:
    - dimension: technology|environment|period
    - value1, value2: labels / values
    - metrics: optional repeated param (ignored for now; we compute all)
    - days: for technology/environment
    - period1_start, period1_end, period2_start, period2_end: for period dimension (YYYY-MM-DD)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        dimension = (request.query_params.get("dimension") or "").strip()
        value1 = (request.query_params.get("value1") or "").strip()
        value2 = (request.query_params.get("value2") or "").strip()

        if dimension not in ("technology", "environment", "period"):
            raise BadRequestError(
                code="BAD_REQUEST",
                message="dimension invalide",
                details={"dimension": dimension},
            )
        if not value1 or not value2:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="value1 et value2 sont requis",
                details={"value1": value1, "value2": value2},
            )

        qs_base = Execution.objects.select_related("action")
        if not _is_dba_or_dbops(request.user):
            qs_base = qs_base.filter(user_id=request.user.id)

        if dimension in ("technology", "environment"):
            days = _parse_int(request.query_params.get("days"), 14, name="days")
            if days <= 0 or days > 3650:
                raise BadRequestError(code="BAD_REQUEST", message="days invalide", details={"days": days})
            date_from = timezone.now() - timedelta(days=days)

            def _side_qs(value: str):
                qs = qs_base.filter(created_at__gte=date_from)
                if dimension == "technology":
                    qs = qs.filter(action__engine=value)
                else:
                    qs = qs.filter(environment=value)
                return qs

            qs1 = _side_qs(value1)
            qs2 = _side_qs(value2)

        else:
            p1s = _parse_date(request.query_params.get("period1_start"), name="period1_start")
            p1e = _parse_date(request.query_params.get("period1_end"), name="period1_end")
            p2s = _parse_date(request.query_params.get("period2_start"), name="period2_start")
            p2e = _parse_date(request.query_params.get("period2_end"), name="period2_end")

            if not (p1s and p1e and p2s and p2e):
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="period1_start/period1_end/period2_start/period2_end sont requis",
                    details={
                        "period1_start": request.query_params.get("period1_start"),
                        "period1_end": request.query_params.get("period1_end"),
                        "period2_start": request.query_params.get("period2_start"),
                        "period2_end": request.query_params.get("period2_end"),
                    },
                )

            p1_start_dt = timezone.make_aware(datetime.combine(p1s, datetime.min.time()))
            p1_end_excl = timezone.make_aware(datetime.combine(p1e + timedelta(days=1), datetime.min.time()))
            p2_start_dt = timezone.make_aware(datetime.combine(p2s, datetime.min.time()))
            p2_end_excl = timezone.make_aware(datetime.combine(p2e + timedelta(days=1), datetime.min.time()))

            qs1 = qs_base.filter(created_at__gte=p1_start_dt, created_at__lt=p1_end_excl)
            qs2 = qs_base.filter(created_at__gte=p2_start_dt, created_at__lt=p2_end_excl)

        v1_stats = _stats_for_queryset(qs1)
        v2_stats = _stats_for_queryset(qs2)

        deltas = {
            "success_rate": _delta_pct(v1_stats["success_rate"], v2_stats["success_rate"]),
            "avg_time": _delta_pct(v1_stats["avg_time"], v2_stats["avg_time"]),
            "execution_count": _delta_pct(v1_stats["execution_count"], v2_stats["execution_count"]),
            "incident_count": _delta_pct(v1_stats["incident_count"], v2_stats["incident_count"]),
        }

        return Response(
            {
                "data": {
                    "dimension": dimension,
                    "value1": value1,
                    "value2": value2,
                    "value1_stats": v1_stats,
                    "value2_stats": v2_stats,
                    "deltas": deltas,
                }
            }
        )

