"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations (liste, approve, reject).
"""
from __future__ import annotations

import structlog

from django.db import transaction
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
from executions.services import ExecutionService
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
    """POST /executions/{id}/approve — Approuver une exécution en attente (DBA/DBOPS only).

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    """

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    _execution_service_class: type[ExecutionService] = ExecutionService

    def get_execution_service(self) -> ExecutionService:
        """Return an ExecutionService instance (overridable in tests)."""
        return self._execution_service_class()

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
        correlation_id = get_correlation_id()
        user_id = str(request.user.id) if request.user and hasattr(request.user, 'id') else "unknown"

        # State machine: PENDING_APPROVAL → RUNNING (Story 7.4). Transition then launch workflow.
        execution_service = self.get_execution_service()
        updated = execution_service.update_status(execution.id, ExecutionStatus.RUNNING, user_id)
        if not updated:
            raise NotFoundError(
                code="EXECUTION_NOT_FOUND",
                message="Exécution introuvable",
                details={"execution_id": execution_id},
            )
        execution = updated

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_APPROVED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution.id,
            details={
                "action_id": execution.action_id,
                "action_name": execution.action.name if execution.action else None,
                "previous_status": old_status,
                "new_status": ExecutionStatus.RUNNING,
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "execution_approved",
            execution_id=execution.id,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        # Launch the workflow (same as post-execution create when not PENDING_APPROVAL)
        try:
            ExecutionService.launch_workflow(execution, correlation_id)
        except Exception as e:  # noqa: BLE001 — catch-all-mark-failed: approval launch failure marks execution INTEGRATION_ERROR
            logger.error(
                "integration_error_on_approval_launch",
                execution_id=execution.id,
                error_type=type(e).__name__,
                error_message=str(e),
                correlation_id=correlation_id,
                exc_info=True,
            )
            execution_service.update_status(
                execution.id,
                ExecutionStatus.INTEGRATION_ERROR,
                user_id,
            )
            execution.refresh_from_db()
            raise BadRequestError(
                code="LAUNCH_FAILED",
                message=f"L'exécution a été approuvée mais le lancement a échoué : {e!s}",
                details={"execution_id": execution_id},
            )

        return Response({"data": ExecutionSerializer(execution).data})


class RejectExecutionView(APIView):
    """POST /executions/{id}/reject — Rejeter une exécution en attente (DBA/DBOPS only).

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    """

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    _execution_service_class: type[ExecutionService] = ExecutionService

    def get_execution_service(self) -> ExecutionService:
        """Return an ExecutionService instance (overridable in tests)."""
        return self._execution_service_class()

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
        # State machine: PENDING_APPROVAL → REJECTED (Story 7.4)
        execution_service = self.get_execution_service()
        updated = execution_service.update_status(
            execution.id, ExecutionStatus.REJECTED, str(request.user.id)
        )
        if updated:
            execution = updated
            execution.error_message = rejection_reason or "Execution rejected by user"
            execution.save(update_fields=["error_message"])
        else:
            execution.status = ExecutionStatus.REJECTED
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
                "new_status": ExecutionStatus.REJECTED,
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
