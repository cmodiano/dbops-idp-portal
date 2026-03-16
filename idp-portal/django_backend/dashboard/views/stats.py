"""Dashboard stats views: main stats, by technology, by environment."""
from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, Count
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from dashboard.utils import (
    DASHBOARD_PARAMS,
    apply_common_filters,
    filter_queryset_by_ownership,
    get_period_bounds,
)
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus


class DashboardStatsView(APIView):
    """GET /dashboard/stats -> {data: DashboardStats}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques du dashboard',
        parameters=DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        # Base queryset: scope = all for DBA/DBOPS, else mine
        qs_base = Execution.objects.select_related("action")
        qs_base = filter_queryset_by_ownership(qs_base, request)  # AC3: Story 26.8

        # For dashboard stats, ignore status filter for consistency
        qs_base = apply_common_filters(qs_base, request=request, include_status=False)

        period_start, period_end_exclusive = get_period_bounds(request)
        qs_period = qs_base.filter(created_at__gte=period_start, created_at__lt=period_end_exclusive)

        # executions_jour: always today (regardless of period) but with engine/environment/tags filters
        from django.utils import timezone

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


class DashboardStatsByTechnologyView(APIView):
    """GET /dashboard/stats-by-technology -> {data: TechnologyStats[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques par technologie',
        parameters=DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = apply_common_filters(qs, request=request, include_status=True)

        period_start, period_end_exclusive = get_period_bounds(request)
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
        parameters=DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = apply_common_filters(qs, request=request, include_status=True)

        period_start, period_end_exclusive = get_period_bounds(request)
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
        rows.sort(key=lambda r: (order_rank.get((r["environment"] or "").lower(), 99), r["environment"] or ""))

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
