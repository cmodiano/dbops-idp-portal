"""Dashboard timeseries view."""
from __future__ import annotations

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
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
from executions.models import Execution, ExecutionStatus


class DashboardTimeSeriesView(APIView):
    """GET /dashboard/timeseries -> {data: DashboardTimeSeriesPoint[]}"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['dashboard'],
        summary='Série temporelle du dashboard',
        parameters=DASHBOARD_PARAMS,
    )
    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs = filter_queryset_by_ownership(qs, request)  # AC3: Story 26.8

        qs = apply_common_filters(qs, request=request, include_status=True)

        period_start, period_end_exclusive = get_period_bounds(request)
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
