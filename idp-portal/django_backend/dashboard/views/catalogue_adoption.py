"""Dashboard stats catalogue and adoption views."""
from __future__ import annotations

from django.db.models import Q, Count
from django.db.models.functions import TruncWeek
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action
from core.permissions import AdminProfilePermission
from dashboard.utils import filter_queryset_by_ownership, get_period_bounds
from executions.models import Execution


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

        period_start, period_end = get_period_bounds(request)
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
        period_start, period_end = get_period_bounds(request)
        exec_qs = Execution.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end,
        )
        exec_qs = filter_queryset_by_ownership(exec_qs, request, AdminProfilePermission)

        # NEW-BE-F: user__profile is the legacy CharField on User (populated by SAML).
        # Users authenticated via ad_groups or M2M profiles will show as "unknown".
        # A proper fix requires storing a user_profile snapshot on Execution at creation time.
        # Tracked as technical debt — acceptable for v1 (ad_groups auth is internal only).
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
