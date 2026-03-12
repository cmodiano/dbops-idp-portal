"""Dashboard recent, filter options, and compare views."""
from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError
from core.utils import ensure_utc_isoformat
from dashboard.utils import (
    delta_pct,
    filter_queryset_by_ownership,
    parse_date,
    parse_int,
    stats_for_queryset,
)
from catalog.models import Action, Tag
from executions.models import Execution, ExecutionStatus


class DashboardRecentView(APIView):
    """GET /dashboard/recent -> {data: DashboardRecentExecution[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['dashboard'], summary='Exécutions récentes')
    def get(self, request):
        limit = 10
        qs = Execution.objects.select_related("action", "user").order_by("-created_at")
        qs = filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

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


class DashboardFilterOptionsView(APIView):
    """GET /dashboard/filter-options -> FilterOptions (NOT wrapped in {"data": ...})."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['dashboard'], summary='Options de filtres pour le dashboard')
    def get(self, request):
        # Scope to caller's visible executions (ownership/visibility filtered)
        visible_qs = Execution.objects.all()
        visible_qs = filter_queryset_by_ownership(visible_qs, request)
        visible_action_ids = visible_qs.values_list("action_id", flat=True).distinct()

        # Engines from published actions linked to visible executions
        engines = (
            Action.objects.filter(
                id__in=visible_action_ids,
                status="published",
            )
            .values_list("engine", flat=True)
            .distinct()
            .order_by("engine")
        )
        engines_list = sorted({e for e in engines if e and str(e).strip()})

        # Environments from visible executions
        envs = visible_qs.values_list("environment", flat=True).distinct()
        order_rank = {"dev": 0, "staging": 1, "prod": 2}
        envs_list = sorted(
            {e for e in envs if e and str(e).strip()},
            key=lambda e: (order_rank.get(str(e).lower(), 99), str(e)),
        )

        # Tags from actions linked to visible executions
        tags = (
            Tag.objects.filter(actiontag__action_id__in=visible_action_ids)
            .values_list("name", flat=True)
            .distinct()
            .order_by("name")
        )
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
        qs_base = filter_queryset_by_ownership(qs_base, request)  # AC3: Story 26.8

        if dimension in ("technology", "environment"):
            days = parse_int(request.query_params.get("days"), 14, name="days")
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
            p1s = parse_date(request.query_params.get("period1_start"), name="period1_start")
            p1e = parse_date(request.query_params.get("period1_end"), name="period1_end")
            p2s = parse_date(request.query_params.get("period2_start"), name="period2_start")
            p2e = parse_date(request.query_params.get("period2_end"), name="period2_end")

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

            if p1s > p1e:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="period1_start ne peut pas être postérieure à period1_end",
                    details={
                        "period1_start": str(p1s),
                        "period1_end": str(p1e),
                    },
                )
            if p2s > p2e:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="period2_start ne peut pas être postérieure à period2_end",
                    details={
                        "period2_start": str(p2s),
                        "period2_end": str(p2e),
                    },
                )

            p1_start_dt = timezone.make_aware(datetime.combine(p1s, datetime.min.time()))
            p1_end_excl = timezone.make_aware(datetime.combine(p1e + timedelta(days=1), datetime.min.time()))
            p2_start_dt = timezone.make_aware(datetime.combine(p2s, datetime.min.time()))
            p2_end_excl = timezone.make_aware(datetime.combine(p2e + timedelta(days=1), datetime.min.time()))

            qs1 = qs_base.filter(created_at__gte=p1_start_dt, created_at__lt=p1_end_excl)
            qs2 = qs_base.filter(created_at__gte=p2_start_dt, created_at__lt=p2_end_excl)

        v1_stats = stats_for_queryset(qs1)
        v2_stats = stats_for_queryset(qs2)

        deltas = {
            "success_rate": delta_pct(v1_stats["success_rate"], v2_stats["success_rate"]),
            "avg_time": delta_pct(v1_stats["avg_time"], v2_stats["avg_time"]),
            "execution_count": delta_pct(v1_stats["execution_count"], v2_stats["execution_count"]),
            "incident_count": delta_pct(v1_stats["incident_count"], v2_stats["incident_count"]),
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
