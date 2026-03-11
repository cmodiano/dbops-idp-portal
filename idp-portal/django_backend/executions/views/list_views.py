"""Vues de listing et statistiques des exécutions.

Responsabilité : Opérations de lecture bulk (listes, stats, timeseries, tags).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from django.db.models import Exists, OuterRef, Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action
from core.exceptions import BadRequestError
from core.pagination import paginate_queryset
from core.throttling import ExecutionThrottle, GeneralAPIThrottle
from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from executions.serializers import ExecutionSerializer
from executions.utils import (
    parse_int,
    apply_scope_filter,
    apply_execution_filters,
)

from drf_spectacular.utils import extend_schema, OpenApiParameter
import structlog

UTC = dt_timezone(timedelta(0))
exec_logger = structlog.get_logger(__name__)


class ExecutionsListView(APIView):
    """GET /executions?limit&offset&scope + filters -> {data, pagination}"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [GeneralAPIThrottle, ExecutionThrottle]

    @extend_schema(
        tags=['executions'],
        summary='Lister les exécutions',
        description='Retourne la liste paginée des exécutions avec filtrage par scope, dates et statut.',
        parameters=[
            OpenApiParameter('limit', int, description='Nombre de résultats par page (défaut: 50)'),
            OpenApiParameter('offset', int, description='Décalage pour la pagination'),
            OpenApiParameter('scope', str, description='Scope: mine (défaut) ou all'),
            OpenApiParameter('status', str, description='Filtrage par statut'),
            OpenApiParameter('action_id', int, description='Filtrage par action'),
            OpenApiParameter('start_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('end_date', str, description='Date de fin (YYYY-MM-DD)'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('tags', str, description='Tags séparés par virgules (AND)'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
        ],
        responses={200: ExecutionSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        limit = parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        qs = Execution.objects.select_related(
            "action", "user", "action__integration", "parent_execution__action"
        ).prefetch_related("targets")
        qs, _effective_scope = apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, _start_d, _end_d = apply_execution_filters(qs, request=request)
        qs = qs.order_by("-created_at")

        # AC3: Story 26.11 — Utilisation utilitaire pagination
        result = paginate_queryset(qs, offset=offset, limit=limit)
        data = ExecutionSerializer(result["items"], many=True).data

        return Response({"data": data, "pagination": result["pagination"]})


class ExecutionStatsView(APIView):
    """GET /executions/stats -> {data: DashboardStats}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['executions'],
        summary='Statistiques des exécutions',
        parameters=[
            OpenApiParameter('scope', str, description='Scope: mine (défaut) ou all'),
            OpenApiParameter('start_date', str, description='Date de début (YYYY-MM-DD)'),
            OpenApiParameter('end_date', str, description='Date de fin (YYYY-MM-DD)'),
            OpenApiParameter('action_id', int, description='Filtrage par action'),
            OpenApiParameter('status', str, description='Filtrage par statut'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
            OpenApiParameter('tags', str, description='Tags séparés par virgules (AND)'),
        ],
    )
    def get(self, request: Request) -> Response:
        qs = Execution.objects.select_related("action")
        qs, _effective_scope = apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, start_d, end_d = apply_execution_filters(qs, request=request)

        if start_d or end_d:
            executions_jour = qs.count()
        else:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            executions_jour = qs.filter(created_at__gte=today_start).count()

        finished = qs.filter(status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).count()
        completed = qs.filter(status=ExecutionStatus.COMPLETED).count()
        taux_succes_pct = round((completed / finished) * 100, 2) if finished > 0 else 0.0

        # ADR-007: PENDING_APPROVAL removed — approval is now step-based.
        # Exclude child executions: only count top-level executions.
        # Exclude executions where all steps are COMPLETED/FAILED (stale Execution.status
        # when workflow finished but parent was never updated).
        en_cours_base = qs.filter(
            status__in=[ExecutionStatus.RUNNING, ExecutionStatus.SUBMITTED],
            parent_execution__isnull=True,
        )
        has_no_steps = ~Exists(ExecutionStep.objects.filter(execution_id=OuterRef("id")))
        has_non_terminal_step = Exists(
            ExecutionStep.objects.filter(execution_id=OuterRef("id")).exclude(
                status__in=[ExecutionStepStatus.COMPLETED, ExecutionStepStatus.FAILED]
            )
        )
        executions_en_cours = en_cours_base.filter(has_no_steps | has_non_terminal_step).count()
        executions_en_erreur = qs.filter(status=ExecutionStatus.FAILED).count()

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


class ExecutionTimeSeriesView(APIView):
    """GET /executions/timeseries -> {data: DashboardTimeSeriesPoint[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['executions'],
        summary='Série temporelle des exécutions',
        parameters=[
            OpenApiParameter('scope', str, description='Scope: mine (défaut) ou all'),
            OpenApiParameter('start_date', str, description='Date de début (YYYY-MM-DD, défaut: -7 jours)'),
            OpenApiParameter('end_date', str, description='Date de fin (YYYY-MM-DD, défaut: aujourd\'hui)'),
            OpenApiParameter('action_id', int, description='Filtrage par action'),
            OpenApiParameter('engine', str, description='Filtrage par technologie'),
            OpenApiParameter('environment', str, description='Filtrage par environnement'),
            OpenApiParameter('tags', str, description='Tags séparés par virgules (AND)'),
        ],
    )
    def get(self, request: Request) -> Response:
        qs = Execution.objects.all()
        qs, _effective_scope = apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, start_d, end_d = apply_execution_filters(qs, request=request)

        if not start_d:
            start_d = (timezone.now() - timedelta(days=7)).date()
        if not end_d:
            end_d = timezone.now().date()

        start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()))
        end_exclusive = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()))
        qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_exclusive)

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


class ExecutionTagsView(APIView):
    """GET /executions/tags -> {data: string[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['executions'], summary='Tags des actions exécutées')
    def get(self, request: Request) -> Response:
        action_ids = Execution.objects.values_list("action_id", flat=True).distinct()
        tags = (
            Action.objects.filter(id__in=action_ids)
            .values_list("actiontag__tag__name", flat=True)
            .distinct()
            .order_by("actiontag__tag__name")
        )
        tags_list = [t for t in tags if t]
        return Response({"data": tags_list})
