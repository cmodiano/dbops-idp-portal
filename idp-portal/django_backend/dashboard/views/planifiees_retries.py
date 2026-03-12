"""Dashboard stats planifiees and retries views."""
from __future__ import annotations

from django.db.models import Count
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import structlog

from core.middleware import get_correlation_id
from core.exceptions import BadRequestError
from core.models import AuditEntityType, AuditLog
from dashboard.utils import (
    DASHBOARD_PARAMS,
    RETRY_ACTION_TYPES,
    apply_common_filters,
    filter_queryset_by_ownership,
    get_period_bounds,
    parse_int,
)
from executions.models import Execution, ScheduledExecution

logger = structlog.get_logger(__name__)


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
        parameters=DASHBOARD_PARAMS[:6],  # sans status
    )
    def get(self, request):
        period_start, period_end = get_period_bounds(request)

        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)
        qs = apply_common_filters(qs, request=request, include_status=False)
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
                    action_type__in=RETRY_ACTION_TYPES,
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
