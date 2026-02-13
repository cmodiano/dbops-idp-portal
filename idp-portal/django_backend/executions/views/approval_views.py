"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError
from core.permissions import IsDBAOrDBOPS
from executions.models import Execution, ExecutionStatus
from executions.serializers import ExecutionSerializer
from executions.utils import parse_int

from drf_spectacular.utils import extend_schema


class PendingApprovalsView(APIView):
    """GET /executions/pending-approvals (DBA/DBOPS only)"""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]  # AC2: Story 26.8

    @extend_schema(tags=['executions'], summary='Approbations en attente', responses={200: ExecutionSerializer(many=True)})
    def get(self, request):
        # AC2: Story 26.8 — Permission vérifiée par DRF via permission_classes
        count_only = (request.query_params.get("count_only") or "").lower() == "true"
        qs = Execution.objects.select_related("action", "user", "action__integration").filter(
            status=ExecutionStatus.PENDING_APPROVAL
        ).order_by("-created_at")

        if count_only:
            return Response({"count": qs.count()})

        limit = parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        total = qs.count()
        page = (offset // limit) + 1
        total_pages = (total + limit - 1) // limit if limit else 1

        items = list(qs[offset: offset + limit])
        data = ExecutionSerializer(items, many=True).data

        return Response(
            {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": limit,
                    "total": total,
                    "total_pages": total_pages,
                },
            }
        )
