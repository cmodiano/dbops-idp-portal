"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations (liste, approve, reject).
"""
from __future__ import annotations

import structlog

from django.db import transaction
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, NotFoundError
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.pagination import paginate_queryset
from core.permissions import IsDBAOrDBOPS
from core.services import AuditService
from executions.models import Execution, ExecutionStatus
from executions.serializers import ExecutionSerializer
from executions.utils import parse_int

from drf_spectacular.utils import extend_schema

logger = structlog.get_logger(__name__)


def _get_and_validate_pending_execution(execution_id: int) -> Execution:
    """
    Helper to get execution and validate PENDING_APPROVAL status.
    Uses select_for_update() to prevent race conditions.

    Code Review 30.1: Extracted to avoid duplication and added row-level locking.

    Args:
        execution_id: Execution ID to retrieve

    Returns:
        Execution instance in PENDING_APPROVAL status

    Raises:
        NotFoundError: If execution does not exist
        BadRequestError: If execution is not in PENDING_APPROVAL status
    """
    try:
        # select_for_update() locks the row until transaction commits
        execution = Execution.objects.select_for_update().select_related(
            "action", "user", "action__integration"
        ).get(id=execution_id)
    except Execution.DoesNotExist:
        raise NotFoundError(
            code="EXECUTION_NOT_FOUND",
            message="Exécution non trouvée",
            details={"execution_id": execution_id},
        )

    if execution.status != ExecutionStatus.PENDING_APPROVAL:
        raise BadRequestError(
            code="INVALID_STATUS",
            message=f"Impossible de modifier une exécution en statut '{execution.status}'",
            details={
                "current_status": execution.status,
                "expected_status": ExecutionStatus.PENDING_APPROVAL,
            },
        )

    return execution


class PendingApprovalsView(APIView):
    """GET /executions/pending-approvals (DBA/DBOPS only)"""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]  # AC2: Story 26.8

    @extend_schema(tags=['executions'], summary='Approbations en attente', responses={200: ExecutionSerializer(many=True)})
    def get(self, request: Request) -> Response:
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

        # Code Review Fix (HIGH-2): Story 26.11 — Utilisation utilitaire pagination
        result = paginate_queryset(qs, offset=offset, limit=limit)
        data = ExecutionSerializer(result["items"], many=True).data

        return Response({"data": data, "pagination": result["pagination"]})


class ApproveExecutionView(APIView):
    """POST /executions/{id}/approve — Approuver une exécution en attente (DBA/DBOPS only)."""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    @extend_schema(
        tags=['executions'],
        summary='Approuver une exécution en attente',
        responses={200: ExecutionSerializer},
    )
    @transaction.atomic
    def post(self, request: Request, execution_id: int) -> Response:
        # Code Review 30.1: Atomic transaction + row-level locking to prevent race conditions
        execution = _get_and_validate_pending_execution(execution_id)

        old_status = execution.status
        execution.status = ExecutionStatus.SUBMITTED
        execution.save(update_fields=["status"])

        correlation_id = get_correlation_id()
        user_id = str(request.user.id) if request.user and hasattr(request.user, 'id') else "unknown"

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_APPROVED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                "action_id": execution.action_id,
                "action_name": execution.action.name if execution.action else None,
                "previous_status": old_status,
                "new_status": ExecutionStatus.SUBMITTED,
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "execution_approved",
            execution_id=execution.id,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionSerializer(execution).data})


class RejectExecutionView(APIView):
    """POST /executions/{id}/reject — Rejeter une exécution en attente (DBA/DBOPS only)."""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    @extend_schema(
        tags=['executions'],
        summary='Rejeter une exécution en attente',
        responses={200: ExecutionSerializer},
    )
    @transaction.atomic
    def post(self, request: Request, execution_id: int) -> Response:
        # Code Review 30.1: Atomic transaction + row-level locking to prevent race conditions
        execution = _get_and_validate_pending_execution(execution_id)

        rejection_reason = (request.data or {}).get("rejection_reason", "")

        old_status = execution.status
        execution.status = ExecutionStatus.FAILED
        execution.error_message = rejection_reason or "Execution rejected by user"
        execution.save(update_fields=["status", "error_message"])

        correlation_id = get_correlation_id()
        user_id = str(request.user.id) if request.user and hasattr(request.user, 'id') else "unknown"

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_REJECTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                "action_id": execution.action_id,
                "action_name": execution.action.name if execution.action else None,
                "previous_status": old_status,
                "new_status": ExecutionStatus.FAILED,
                "rejection_reason": rejection_reason or None,
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "execution_rejected",
            execution_id=execution.id,
            user_id=user_id,
            rejection_reason=rejection_reason or None,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionSerializer(execution).data})
