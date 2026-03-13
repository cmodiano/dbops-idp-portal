"""Dashboard stats operations and approbations views."""
from __future__ import annotations

from django.db.models import Count, Min
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import structlog

from core.middleware import get_correlation_id
from core.exceptions import BadRequestError
from dashboard.utils import (
    DASHBOARD_PARAMS,
    apply_common_filters,
    compute_avg_duration_s,
    filter_queryset_by_ownership,
    get_period_bounds,
    parse_int,
)
from executions.models import Execution, ExecutionStatus, ExecutionStepStatus, ExecutionStepType

logger = structlog.get_logger(__name__)


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
            *DASHBOARD_PARAMS[:6],  # sans status
            OpenApiParameter('top_n', int, description='Nombre de top actions (défaut: 5, max: 100)'),
        ],
    )
    def get(self, request):
        top_n = parse_int(request.query_params.get("top_n"), 5, name="top_n")
        if top_n <= 0 or top_n > 100:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="top_n invalide (doit être entre 1 et 100)",
                details={"top_n": top_n},
            )

        period_start, period_end = get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)
        qs = apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # 1. Durée moyenne d'exécution en secondes
        # DASH-MED-02: use shared helper compute_avg_duration_s() instead of duplicated loop
        avg_execution_time_s = compute_avg_duration_s(qs)

        # 2. Top N actions les plus exécutées
        top_actions_rows = (
            qs.values("action_id", "action__name")
            .annotate(execution_count=Count("id", distinct=True))
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
            .annotate(failure_count=Count("id", distinct=True))
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
            .annotate(count=Count("id", distinct=True))
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
    Source ADR-007: ExecutionStep gate uniquement (Story 78.15 — Execution.approved_at supprimé).
    - approved_count: exécutions COMPLETED avec gate step approuvé
    - rejected_count: exécutions REJECTED
    - approval_rate: taux d'approbation en % (null si aucune décision)
    - avg_approval_delay_s: délai moyen créé→approuvé en secondes (null si aucun approuvé)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques approbations',
        parameters=DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        period_start, period_end = get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)
        qs = apply_common_filters(qs, request=request, include_status=False)
        qs = qs.filter(created_at__gte=period_start, created_at__lt=period_end).distinct()

        # 1. Exécutions approuvées — ADR-007: ExecutionStep gate step (Story 78.15)
        qs_approved = qs.filter(
            status=ExecutionStatus.COMPLETED,
            executionstep__step_type=ExecutionStepType.GATE,
            executionstep__status=ExecutionStepStatus.COMPLETED,
            executionstep__approved_at__isnull=False,
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
        # ADR-007: ExecutionStep.approved_at - Execution.created_at
        delays = []
        qs_gate = qs_approved.filter(
            executionstep__step_type=ExecutionStepType.GATE,
            executionstep__status=ExecutionStepStatus.COMPLETED,
            executionstep__approved_at__isnull=False,
        ).annotate(first_approved_at=Min("executionstep__approved_at"))
        for exec_id, exec_created_at, step_approved_at in qs_gate.values_list(
            "id", "created_at", "first_approved_at"
        ):
            try:
                if step_approved_at is None or exec_created_at is None:
                    continue
                delta = (step_approved_at - exec_created_at).total_seconds()
                if delta >= 0:
                    delays.append(delta)
            except (TypeError, AttributeError) as e:
                logger.debug(
                    "approval_delay_calculation_skipped",
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
