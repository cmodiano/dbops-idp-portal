from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Any

from django.db.models import Exists, OuterRef, Q, Count, QuerySet
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import ensure_utc_isoformat
import structlog

from catalog.models import Action, Tag
from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.models import AuditLog, AuditActionType, AuditEntityType
from core.permissions import IsAdminUser, AdminProfilePermission
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus, ExecutionStepType, ScheduledExecution

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


def _filter_queryset_by_ownership(qs: QuerySet, request, permission_class=IsAdminUser) -> QuerySet:
    """
    Filter queryset to user's own objects unless user has admin permission.

    Story 26.8 AC3: Extracted pattern from 6 dashboard views.
    Uses permission_class (default: IsAdminUser) to determine if user sees all executions.
    """
    permission = permission_class()
    if not permission.has_permission(request, None):
        qs = qs.filter(user_id=request.user.id)
    return qs


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


def _apply_common_filters(qs: QuerySet, *, request: Any, include_status: bool) -> QuerySet:
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


_DASHBOARD_PARAMS = [
    OpenApiParameter('from_date', str, description='Date de début (YYYY-MM-DD)'),
    OpenApiParameter('to_date', str, description='Date de fin (YYYY-MM-DD)'),
    OpenApiParameter('days', int, description='Nombre de jours (défaut: 14, si from_date/to_date non fournis)'),
    OpenApiParameter('engine', str, description='Filtrage par technologie'),
    OpenApiParameter('environment', str, description='Filtrage par environnement'),
    OpenApiParameter('tags', str, description='Tags (multi-valeur, OR)'),
    OpenApiParameter('status', str, description='Filtrage par statut (pour timeseries/stats-by-*)'),
]

_RETRY_ACTION_TYPES = [
    AuditActionType.EXECUTION_STEP_RETRY_ATTEMPT,
    AuditActionType.EXECUTION_STEP_RETRY_SUCCESS,
    AuditActionType.EXECUTION_STEP_RETRY_EXHAUSTED,
    AuditActionType.EXECUTION_STEP_RETRY_ABORTED,
]


class DashboardStatsView(APIView):
    """GET /dashboard/stats -> {data: DashboardStats}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques du dashboard',
        parameters=_DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        # Base queryset: scope = all for DBA/DBOPS, else mine
        qs_base = Execution.objects.select_related("action")
        qs_base = _filter_queryset_by_ownership(qs_base, request)  # AC3: Story 26.8

        # For dashboard stats, ignore status filter for consistency
        qs_base = _apply_common_filters(qs_base, request=request, include_status=False)

        period_start, period_end_exclusive = _get_period_bounds(request)
        qs_period = qs_base.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        # executions_jour: always today (regardless of period) but with engine/environment/tags filters
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        executions_jour = qs_base.filter(created_at__gte=today_start).count()

        # executions_en_cours: current running/pending (not period-scoped)
        # ADR-007: PENDING_APPROVAL removed — approval is now step-based.
        # Exclude child executions and executions where all steps are COMPLETED/FAILED
        # (stale Execution.status when workflow finished but parent was never updated).
        en_cours_base = qs_base.filter(
            status__in=[ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING],
            parent_execution__isnull=True,
        )
        has_no_steps = ~Exists(ExecutionStep.objects.filter(execution_id=OuterRef("id")))
        has_non_terminal_step = Exists(
            ExecutionStep.objects.filter(execution_id=OuterRef("id")).exclude(
                status__in=[ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED]
            )
        )
        executions_en_cours = en_cours_base.filter(has_no_steps | has_non_terminal_step).count()

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

    @extend_schema(tags=['dashboard'], summary='Exécutions récentes')
    def get(self, request):
        limit = 10
        qs = Execution.objects.select_related("action", "user").order_by("-created_at")
        qs = _filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

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

    @extend_schema(
        tags=['dashboard'],
        summary='Série temporelle du dashboard',
        parameters=_DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = _apply_common_filters(qs, request=request, include_status=True)

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

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques par technologie',
        parameters=_DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = _apply_common_filters(qs, request=request, include_status=True)

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

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques par environnement',
        parameters=_DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = _apply_common_filters(qs, request=request, include_status=True)

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

    @extend_schema(tags=['dashboard'], summary='Options de filtres pour le dashboard')
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


def _compute_avg_duration_s(qs) -> float | None:
    """
    Compute average execution duration in seconds for completed executions.

    DASH-MED-02: Extracted shared helper to avoid duplication between
    _stats_for_queryset() and DashboardStatsOperationsView.get().
    Pattern Python (compatibilité Oracle) — itération côté Python sur (started_at, completed_at).
    """
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


def _stats_for_queryset(qs) -> dict:
    """
    Compute ComparisonStats for a queryset of executions.
    """
    execution_count = qs.count()
    incident_count = qs.filter(status=ExecutionStatus.FAILED).count()

    finished = qs.filter(status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).count()
    completed = qs.filter(status=ExecutionStatus.COMPLETED).count()
    success_rate = round((completed / finished) * 100, 2) if finished > 0 else None

    avg_time = _compute_avg_duration_s(qs)  # DASH-MED-02: use shared helper

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

    @extend_schema(
        tags=['dashboard'],
        summary='Comparaison de statistiques',
        parameters=[
            OpenApiParameter('dimension', str, description='technology | environment | period'),
            OpenApiParameter('value1', str, description='Première valeur à comparer'),
            OpenApiParameter('value2', str, description='Deuxième valeur à comparer'),
            OpenApiParameter('days', int, description='Nombre de jours (pour dimension technology/environment)'),
            OpenApiParameter('period1_start', str, description='Début période 1 (YYYY-MM-DD)'),
            OpenApiParameter('period1_end', str, description='Fin période 1 (YYYY-MM-DD)'),
            OpenApiParameter('period2_start', str, description='Début période 2 (YYYY-MM-DD)'),
            OpenApiParameter('period2_end', str, description='Fin période 2 (YYYY-MM-DD)'),
        ],
    )
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
        qs_base = _filter_queryset_by_ownership(qs_base, request)  # AC3: Story 26.8

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


class DashboardStatsCatalogueView(APIView):
    """GET /dashboard/stats-catalogue/ -> {data: CatalogueStats}

    Story 60.1: Agrégations du catalogue Actions pour l'admin/DBOPS.
    """

    permission_classes = [IsAuthenticated, AdminProfilePermission]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques du catalogue (admin)',
        parameters=[
            OpenApiParameter('days', int, description='Période en jours (défaut: 14)'),
            OpenApiParameter('from_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('to_date', str, description='Date de fin (YYYY-MM-DD)'),
        ],
    )
    def get(self, request):
        qs_all = Action.objects.filter(deleted_at__isnull=True)

        by_status = list(
            qs_all.values("status").annotate(count=Count("id")).order_by("status")
        )
        by_item_type = list(
            qs_all.values("item_type").annotate(count=Count("id")).order_by("item_type")
        )
        by_engine = [
            {"engine": r["engine"] or "N/A", "count": r["count"]}
            for r in qs_all.values("engine").annotate(count=Count("id")).order_by("engine")
        ]
        by_category = [
            {"category": r["category"] or "N/A", "count": r["count"]}
            for r in qs_all.values("category").annotate(count=Count("id")).order_by("category")
        ]

        period_start, period_end = _get_period_bounds(request)
        qs_period = Action.objects.filter(
            deleted_at__isnull=True,
            created_at__gte=period_start,
            created_at__lt=period_end,
        )
        evolution_rows = (
            qs_period
            .annotate(week_start=TruncWeek("created_at"))
            .values("week_start")
            .annotate(
                created_count=Count("id"),
                published_count=Count("id", filter=Q(status="published")),
            )
            .order_by("week_start")
        )
        evolution = [
            {
                "week_start": r["week_start"].date().isoformat() if r["week_start"] else None,
                "created_count": int(r["created_count"] or 0),
                "published_count": int(r["published_count"] or 0),
            }
            for r in evolution_rows
            if r["week_start"] is not None
        ]

        return Response(
            {
                "data": {
                    "by_status": by_status,
                    "by_item_type": by_item_type,
                    "by_engine": by_engine,
                    "by_category": by_category,
                    "evolution": evolution,
                }
            }
        )


class DashboardStatsAdoptionView(APIView):
    """GET /dashboard/stats-adoption/ -> {data: AdoptionStats}

    Story 60.2: Statistiques d'adoption par profil utilisateur.
    - executions_by_profile: nombre d'exécutions par profil sur la période
    - active_users_by_profile: utilisateurs distincts (≥1 exécution) par profil
    - adoption_trend: série temporelle hebdomadaire par profil

    RBAC: DBOPS voient tout; utilisateurs standard voient uniquement leurs propres exécutions.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques adoption par profil (admin)',
        parameters=[
            OpenApiParameter('days', int, description='Période en jours (défaut: 14)'),
            OpenApiParameter('from_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('to_date', str, description='Date de fin (YYYY-MM-DD)'),
        ],
    )
    def get(self, request):
        period_start, period_end = _get_period_bounds(request)
        exec_qs = Execution.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end,
        )
        exec_qs = _filter_queryset_by_ownership(exec_qs, request, AdminProfilePermission)

        # executions_by_profile
        by_profile_rows = (
            exec_qs.values("user__profile")
            .annotate(count=Count("id"))
            .order_by("user__profile")
        )
        executions_by_profile = [
            {"profile": r["user__profile"] or "unknown", "count": int(r["count"] or 0)}
            for r in by_profile_rows
        ]

        # active_users_by_profile
        active_rows = (
            exec_qs.values("user__profile")
            .annotate(user_count=Count("user_id", distinct=True))
            .order_by("user__profile")
        )
        active_users_by_profile = [
            {"profile": r["user__profile"] or "unknown", "user_count": int(r["user_count"] or 0)}
            for r in active_rows
        ]

        # adoption_trend
        trend_rows = (
            exec_qs
            .annotate(week_start=TruncWeek("created_at"))
            .values("week_start", "user__profile")
            .annotate(count=Count("id"))
            .order_by("week_start", "user__profile")
        )
        adoption_trend = [
            {
                "week_start": r["week_start"].date().isoformat() if r["week_start"] else None,
                "profile": r["user__profile"] or "unknown",
                "count": int(r["count"] or 0),
            }
            for r in trend_rows
            if r["week_start"] is not None
        ]

        return Response(
            {
                "data": {
                    "executions_by_profile": executions_by_profile,
                    "active_users_by_profile": active_users_by_profile,
                    "adoption_trend": adoption_trend,
                }
            }
        )


class DashboardStatsOperationsView(APIView):
    """GET /dashboard/stats-operations/ -> {data: OperationsStats}

    Story 60.5: Métriques opérations enrichies sur les exécutions.
    - avg_execution_time_s: durée moyenne en secondes (COMPLETED, timestamps présents)
    - top_actions_by_execution: top N actions les plus exécutées
    - top_actions_by_failure: top N actions avec le plus d'échecs
    - by_platform: répartition par plateforme de l'action
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques opérations enrichies',
        parameters=[
            *_DASHBOARD_PARAMS[:6],  # sans status
            OpenApiParameter('top_n', int, description='Nombre de top actions (défaut: 5, max: 100)'),
        ],
    )
    def get(self, request):
        top_n = _parse_int(request.query_params.get("top_n"), 5, name="top_n")
        if top_n <= 0 or top_n > 100:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="top_n invalide (doit être entre 1 et 100)",
                details={"top_n": top_n},
            )

        period_start, period_end = _get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)
        qs = _apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # 1. Durée moyenne d'exécution en secondes
        # DASH-MED-02: use shared helper _compute_avg_duration_s() instead of duplicated loop
        avg_execution_time_s = _compute_avg_duration_s(qs)

        # 2. Top N actions les plus exécutées
        top_actions_rows = (
            qs.values("action_id", "action__name")
            .annotate(execution_count=Count("id"))
            .order_by("-execution_count")[:top_n]
        )
        top_actions_by_execution = [
            {
                "action_id": r["action_id"],
                "action_name": r["action__name"] or "N/A",
                "execution_count": int(r["execution_count"] or 0),
            }
            for r in top_actions_rows
        ]

        # 3. Top N actions avec le plus d'échecs
        top_failures_rows = (
            qs.filter(status=ExecutionStatus.FAILED)
            .values("action_id", "action__name")
            .annotate(failure_count=Count("id"))
            .order_by("-failure_count")[:top_n]
        )
        top_actions_by_failure = [
            {
                "action_id": r["action_id"],
                "action_name": r["action__name"] or "N/A",
                "failure_count": int(r["failure_count"] or 0),
            }
            for r in top_failures_rows
        ]

        # 4. Répartition par plateforme
        by_platform_rows = (
            qs.values("action__platform")
            .annotate(count=Count("id"))
            .order_by("action__platform")
        )
        by_platform = [
            {
                "platform": r["action__platform"] or "N/A",
                "count": int(r["count"] or 0),
            }
            for r in by_platform_rows
        ]

        return Response(
            {
                "data": {
                    "avg_execution_time_s": avg_execution_time_s,
                    "top_actions_by_execution": top_actions_by_execution,
                    "top_actions_by_failure": top_actions_by_failure,
                    "by_platform": by_platform,
                }
            }
        )


class DashboardStatsApprobationsView(APIView):
    """GET /dashboard/stats-approbations/ -> {data: ApprobationsStats}

    Story 60.6: Statistiques du workflow d'approbation des exécutions.
    Source duale ADR-007: Execution.approved_at (legacy) + ExecutionStep gate (nouveau).
    - approved_count: exécutions COMPLETED avec approbation (legacy ou gate step)
    - rejected_count: exécutions REJECTED
    - approval_rate: taux d'approbation en % (null si aucune décision)
    - avg_approval_delay_s: délai moyen créé→approuvé en secondes (null si aucun approuvé)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques approbations',
        parameters=_DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        period_start, period_end = _get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)
        qs = _apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # 1. Exécutions approuvées — source duale (legacy Execution.approved_at + gate step ADR-007)
        qs_approved = qs.filter(
            status=ExecutionStatus.COMPLETED
        ).filter(
            Q(approved_at__isnull=False)
            | Q(
                executionstep__step_type=ExecutionStepType.GATE,
                executionstep__status=ExecutionStepStatus.COMPLETED,
                executionstep__approved_at__isnull=False,
            )
        ).distinct()
        # Oracle: .count() on distinct() fails with ORA-22848 (CLOB in comparison).
        # Use values('id').distinct() so only numeric id is selected for DISTINCT.
        approved_count = qs_approved.values("id").distinct().count()

        # 2. Exécutions rejetées
        rejected_count = qs.filter(status=ExecutionStatus.REJECTED).values("id").distinct().count()

        # 3. Taux d'approbation
        total_decided = approved_count + rejected_count
        approval_rate = round((approved_count / total_decided) * 100, 1) if total_decided > 0 else None

        # 4. Délai moyen d'approbation en secondes (Python loop — compatibilité Oracle)
        delays = []

        # Chemin legacy: Execution.approved_at - created_at
        for created_at, approved_at in qs_approved.filter(
            approved_at__isnull=False
        ).values_list("created_at", "approved_at"):
            try:
                if approved_at is None or created_at is None:
                    continue
                delta = (approved_at - created_at).total_seconds()
                if delta >= 0:
                    delays.append(delta)
            except (TypeError, AttributeError) as e:
                logger.debug(
                    "approval_delay_calculation_skipped_legacy",
                    created_at=created_at,
                    approved_at=approved_at,
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=get_correlation_id(),
                )
                continue

        # Chemin nouveau (ADR-007): ExecutionStep.approved_at - Execution.created_at
        # Exclure les exécutions déjà traitées via legacy (approved_at non-null sur Execution)
        # Dédupliquer par execution_id : une exécution peut avoir plusieurs gate steps approuvés
        # (ex: retry). On prend le premier rencontré (ORDER BY par défaut sur created_at desc).
        gate_exec_seen: set[int] = set()
        for exec_id, exec_created_at, step_approved_at in qs_approved.filter(
            approved_at__isnull=True,
            executionstep__step_type=ExecutionStepType.GATE,
            executionstep__status=ExecutionStepStatus.COMPLETED,
            executionstep__approved_at__isnull=False,
        ).values_list("id", "created_at", "executionstep__approved_at").distinct():
            if exec_id in gate_exec_seen:
                continue
            gate_exec_seen.add(exec_id)
            try:
                if step_approved_at is None or exec_created_at is None:
                    continue
                delta = (step_approved_at - exec_created_at).total_seconds()
                if delta >= 0:
                    delays.append(delta)
            except (TypeError, AttributeError) as e:
                logger.debug(
                    "approval_delay_calculation_skipped_gate",
                    exec_created_at=exec_created_at,
                    step_approved_at=step_approved_at,
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=get_correlation_id(),
                )
                continue

        avg_approval_delay_s = round(sum(delays) / len(delays), 2) if delays else None

        return Response(
            {
                "data": {
                    "approved_count": approved_count,
                    "rejected_count": rejected_count,
                    "approval_rate": approval_rate,
                    "avg_approval_delay_s": avg_approval_delay_s,
                }
            }
        )


class DashboardStatsPlanifieesView(APIView):
    """GET /dashboard/stats-planifiees/ -> {data: PlanifieesStats}

    Story 60.7: Répartition des exécutions planifiées vs manuelles.
    Lien inversé : ScheduledExecution.execution_id (BigIntegerField) → Execution.id.
    - scheduled_count: exécutions dont l'ID figure dans ScheduledExecution.execution_id
    - manual_count: exécutions sans lien planifié
    - scheduled_rate: % planifiées (null si aucune exécution)
    - by_recurrence_type: ventilation par RecurringPattern.pattern_type
      (sans RecurringPattern → 'one_time')
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques planifiées vs manuelles',
        parameters=_DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        period_start, period_end = _get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)
        qs = _apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # 1. IDs des exécutions déclenchées par une planification
        #    Oracle-safe: matérialiser les IDs en Python set évite les sous-requêtes imbriquées
        #    instables sur Oracle. DASH-LOW-02: risque mémoire si volume très élevé (>50k exécutions).
        period_ids = set(qs.values_list('id', flat=True))
        if len(period_ids) > 50_000:
            logger.warning(
                "dashboard_planifiees_large_period_ids",
                period_ids_count=len(period_ids),
                correlation_id=get_correlation_id(),
            )
        #    Étape 2 : parmi les ScheduledExecution, celles dont execution_id est dans la période
        scheduled_ids = set(
            ScheduledExecution.objects.filter(
                execution_id__isnull=False,
                execution_id__in=period_ids,
            ).values_list('execution_id', flat=True)
        ) if period_ids else set()

        # Oracle: .count() on distinct() fails with ORA-22848 (CLOB in comparison).
        total = qs.values("id").distinct().count()
        scheduled_count = qs.filter(id__in=scheduled_ids).values("id").distinct().count()
        manual_count = total - scheduled_count
        scheduled_rate = round(scheduled_count / total * 100, 1) if total > 0 else None

        # 2. Ventilation par type de récurrence
        #    scheduled_ids est déjà limité aux exécutions de la période
        by_recurrence_type = []

        if scheduled_ids:
            # Exécutions planifiées sans RecurringPattern → one_time
            no_pattern_count = ScheduledExecution.objects.filter(
                execution_id__in=scheduled_ids,
                recurringpattern__isnull=True,
            ).count()
            if no_pattern_count > 0:
                by_recurrence_type.append({"pattern_type": "one_time", "count": no_pattern_count})

            # Exécutions planifiées avec RecurringPattern → par pattern_type
            pattern_rows = (
                ScheduledExecution.objects
                .filter(
                    execution_id__in=scheduled_ids,
                    recurringpattern__isnull=False,
                )
                .values('recurringpattern__pattern_type')
                .annotate(count=Count('id'))
                .order_by('recurringpattern__pattern_type')
            )
            for row in pattern_rows:
                by_recurrence_type.append({
                    "pattern_type": row['recurringpattern__pattern_type'],
                    "count": int(row['count']),
                })

        return Response(
            {
                "data": {
                    "scheduled_count": scheduled_count,
                    "manual_count": manual_count,
                    "scheduled_rate": scheduled_rate,
                    "by_recurrence_type": by_recurrence_type,
                }
            }
        )


class DashboardStatsRetriesView(APIView):
    """GET /dashboard/stats-retries/ -> {data: RetriesStats}

    Story 60.8: Statistiques sur les retries d'exécution.
    Les retries sont tracés dans AuditLog (entity_type='execution') via AuditService.
    - executions_with_retry_count: exécutions ayant au moins un AuditLog retry
    - retry_rate: % d'exécutions avec retry (null si aucune exécution)
    - by_action: top N actions avec le plus d'exécutions en retry
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques retries',
        parameters=[
            *_DASHBOARD_PARAMS[:6],  # sans status
            OpenApiParameter('top_n', int, description='Nombre de top actions (défaut: 5, max: 100)'),
        ],
    )
    def get(self, request):
        top_n = _parse_int(request.query_params.get("top_n"), 5, name="top_n")
        if top_n <= 0 or top_n > 100:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="top_n invalide (doit être entre 1 et 100)",
                details={"top_n": top_n},
            )

        period_start, period_end = _get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = _filter_queryset_by_ownership(qs, request)
        qs = _apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # Oracle-safe: matérialiser les IDs en Python avant de filtrer AuditLog (pas de sous-requête
        # imbriquée instable sur Oracle). DASH-LOW-02: risque mémoire si volume très élevé (>50k).
        # len(period_ids) == total_executions → pas besoin d'un qs.count() séparé
        period_ids = set(qs.values_list('id', flat=True))
        if len(period_ids) > 50_000:
            logger.warning(
                "dashboard_retries_large_period_ids",
                period_ids_count=len(period_ids),
                correlation_id=get_correlation_id(),
            )
        total_executions = len(period_ids)

        # Exécutions avec au moins un retry : chercher dans AuditLog
        retry_execution_ids = (
            set(
                AuditLog.objects.filter(
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id__in=period_ids,
                    action_type__in=_RETRY_ACTION_TYPES,
                ).values_list('entity_id', flat=True)
            )
            if period_ids
            else set()
        )

        executions_with_retry_count = len(retry_execution_ids)
        retry_rate = (
            round(executions_with_retry_count / total_executions * 100, 1)
            if total_executions > 0
            else None
        )

        # Top N actions avec le plus d'exécutions en retry
        by_action = []
        if retry_execution_ids:
            rows = (
                Execution.objects.filter(id__in=retry_execution_ids)
                .values('action_id', 'action__name')
                .annotate(retry_count=Count('id'))
                .order_by('-retry_count')[:top_n]
            )
            by_action = [
                {
                    'action_id': r['action_id'],
                    'action_name': r['action__name'] or 'N/A',
                    'retry_count': int(r['retry_count'] or 0),
                }
                for r in rows
            ]

        return Response(
            {
                'data': {
                    'total_executions': total_executions,
                    'executions_with_retry_count': executions_with_retry_count,
                    'retry_rate': retry_rate,
                    'by_action': by_action,
                }
            }
        )
