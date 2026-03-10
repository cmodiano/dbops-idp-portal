from __future__ import annotations

from django.db.models import Count
from django.db.models.functions import TruncWeek
from datetime import timedelta

import structlog
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiParameter
from catalog.models import Action, ActionStatus
from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.permissions import AdminProfilePermission
from executions.models import Execution

logger = structlog.get_logger(__name__)


class AdminAnalyticsView(APIView):
    """
    GET /api/v1/admin/analytics?days=90
    Story 8.2 - Admin analytics dashboard for admin users.
    """

    permission_classes = [IsAuthenticated, AdminProfilePermission]

    @extend_schema(
        tags=['dashboard'],
        summary='Statistiques admin',
        parameters=[
            OpenApiParameter('days', int, description='Période en jours (défaut: 90, max: 3650)'),
        ],
    )
    def get(self, request: Request) -> Response:
        days_raw = request.query_params.get("days", "90")
        # DASH-LOW-05: int parsing inline (fonctionnellement équivalent à _parse_int() de dashboard/views.py).
        # Incohérence documentée : préférer _parse_int() dans une future uniformisation.
        try:
            days = int(days_raw)
        except (ValueError, TypeError):
            raise BadRequestError(code="BAD_REQUEST", message="days invalide", details={"days": days_raw})

        if days <= 0 or days > 3650:
            raise BadRequestError(code="BAD_REQUEST", message="days invalide", details={"days": days})

        # DASH-MED-03: structlog logging for consistency with other dashboard views
        logger.info(
            "admin_analytics_requested",
            days=days,
            user_id=request.user.id,
            correlation_id=get_correlation_id(),
        )

        now = timezone.now()
        date_from = now - timedelta(days=days)

        total_published_actions = Action.objects.filter(status=ActionStatus.PUBLISHED).count()

        exec_qs = Execution.objects.select_related("action", "user").filter(created_at__gte=date_from)

        # --- executions_by_engine ---
        by_engine_rows = (
            exec_qs.values("action__engine")
            .annotate(count=Count("id"))
            .order_by("action__engine")
        )
        executions_by_engine = [
            {"engine": (r["action__engine"] or "N/A"), "count": int(r["count"] or 0)}
            for r in by_engine_rows
        ]

        # --- executions_by_profile (from USERS.PROFILE) ---
        by_profile_rows = (
            exec_qs.values("user__profile")
            .annotate(count=Count("id"))
            .order_by("user__profile")
        )
        executions_by_profile = [
            {"profile": (r["user__profile"] or "unknown"), "count": int(r["count"] or 0)}
            for r in by_profile_rows
        ]

        # --- adoption_trend (weekly counts by engine) ---
        trend_rows = (
            exec_qs.annotate(week_start=TruncWeek("created_at"))
            .values("week_start", "action__engine")
            .annotate(count=Count("id"))
            .order_by("week_start", "action__engine")
        )
        adoption_trend = [
            {
                "week_start": r["week_start"].date().isoformat() if r["week_start"] else None,
                "engine": (r["action__engine"] or "N/A"),
                "count": int(r["count"] or 0),
            }
            for r in trend_rows
            if r["week_start"] is not None
        ]

        return Response(
            {
                "data": {
                    "total_published_actions": total_published_actions,
                    "executions_by_engine": executions_by_engine,
                    "executions_by_profile": executions_by_profile,
                    "adoption_trend": adoption_trend,
                }
            }
        )

