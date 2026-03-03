"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations (liste, approve, reject).
"""

from __future__ import annotations

from typing import cast

import structlog

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
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
from executions.models import (
    Execution,
    ExecutionStatus,
    ExecutionStep,
    ExecutionStepStatus,
)
from executions.serializers import ExecutionSerializer, ExecutionStepSerializer
from executions.services import ExecutionService
from executions.tasks.gates import resume_container_workflow_from_gate
from executions.utils import parse_int
from idp_auth.models import User

from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers Story 57.8 — step approval gate
# ---------------------------------------------------------------------------


def _get_step_or_404(execution_id: int, step_id: int) -> ExecutionStep:
    """Charge le step et vérifie l'appartenance à l'exécution.

    select_for_update() verrouille la ligne pour éviter les approbations simultanées
    (race condition : deux approbateurs concurrents).
    """
    try:
        return (
            ExecutionStep.objects.select_for_update()
            .select_related("execution__action", "approved_by")
            .get(id=step_id, execution_id=execution_id)
        )
    except ExecutionStep.DoesNotExist:
        raise NotFoundError(
            code="STEP_NOT_FOUND",
            message="Step introuvable dans cette exécution",
            details={"execution_id": execution_id, "step_id": step_id},
        )


def _validate_approval_gate_step(step: ExecutionStep) -> None:
    """Valide que le step est bien un gate approval WAITING.

    Lève BadRequestError si :
    - step.status != WAITING
    - gate_conditions ne contient pas de condition {type: approval_granted}
    """
    if step.status != ExecutionStepStatus.WAITING:
        raise BadRequestError(
            code="STEP_NOT_WAITING",
            message=f"Le step '{step.step_name}' n'est pas en attente (statut: {step.status})",
            details={"step_id": step.id, "status": step.status},
        )

    output = step.get_output() or {}
    gate_conditions = output.get("gate_conditions", [])
    has_approval = any(
        isinstance(c, dict) and c.get("type") == "approval_granted"
        for c in gate_conditions
    )
    if not has_approval:
        raise BadRequestError(
            code="STEP_NOT_APPROVAL_GATE",
            message=f"Le step '{step.step_name}' n'est pas un gate d'approbation",
            details={"step_id": step.id, "gate_conditions": gate_conditions},
        )


def _get_step_config(step: ExecutionStep) -> dict:
    """Retourne la définition du step depuis action.execution_steps."""
    action = step.execution.action
    execution_steps = action.execution_steps or []
    for s in execution_steps:
        if isinstance(s, dict):
            if s.get("step_id") == step.step_name or s.get("name") == step.step_name:
                return s
    logger.warning(
        "step_config_not_found",
        step_name=step.step_name,
        execution_id=step.execution_id,
        step_id=step.id,
    )
    return {}


def _find_first_waiting_approval_step(execution_id: int) -> ExecutionStep | None:
    """Trouve le premier step WAITING avec gate_conditions approval_granted.

    select_for_update() verrouille les rows pour éviter la double-approbation
    dans le chemin backward compat.
    """
    steps = (
        ExecutionStep.objects.select_for_update()
        .filter(execution_id=execution_id, status=ExecutionStepStatus.WAITING)
        .select_related("execution__action")
        .order_by("step_order")
    )

    for step in steps:
        output = step.get_output() or {}
        conditions = output.get("gate_conditions", [])
        if any(
            isinstance(c, dict) and c.get("type") == "approval_granted"
            for c in conditions
        ):
            return step
    return None


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
        execution = (
            Execution.objects.select_for_update()
            .select_related("action", "user", "action__integration")
            .get(id=execution_id)
        )
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

    @extend_schema(
        tags=["executions"],
        summary="Approbations en attente",
        parameters=[
            OpenApiParameter('count_only', bool, description='Si true, retourne uniquement {count}'),
            OpenApiParameter('limit', int, description='Résultats par page (défaut: 50)'),
            OpenApiParameter('offset', int, description='Décalage pagination'),
        ],
        responses={200: ExecutionSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        # AC2: Story 26.8 — Permission vérifiée par DRF via permission_classes
        # Story 57.12: Inclure aussi les exécutions RUNNING avec step WAITING approval_granted
        # Pattern catalog/services._find_workflows_referencing_action: Oracle CLOB ne supporte
        # pas __contains dans JOIN/DISTINCT (ORA-22848). Sous-requête Exists + extra() pour Oracle.
        count_only = (request.query_params.get("count_only") or "").lower() == "true"
        if connection.vendor == "oracle":
            # Sous-requête IN (pas EXISTS) pour éviter ORA-22848 : le CLOB reste dans
            # la sous-requête qui retourne uniquement execution_id (scalaire).
            # DBMS_LOB.INSTR fonctionne sur CLOB sans contrainte IS JSON (contrairement
            # à JSON_EXISTS qui peut échouer silencieusement sans IS JSON sur la colonne).
            approval_exec_ids = (
                ExecutionStep.objects.filter(status=ExecutionStepStatus.WAITING)
                .extra(
                    where=[
                        "OUTPUT IS NOT NULL AND DBMS_LOB.INSTR(OUTPUT, 'approval_granted') > 0"
                    ]
                )
                .values_list("execution_id", flat=True)
            )
            run_filter = Q(status=ExecutionStatus.RUNNING) & Q(
                pk__in=approval_exec_ids
            )
        else:
            run_filter = Q(
                status=ExecutionStatus.RUNNING,
                executionstep__status=ExecutionStepStatus.WAITING,
                executionstep__output__contains="approval_granted",
            )
        # Pas de .distinct() : Oracle ORA-22848 avec CLOB (Action.execution_steps, etc.)
        # Le filtre pk__in=Subquery ne produit pas de doublons.
        qs = (
            Execution.objects.select_related("action", "user", "action__integration")
            .filter(Q(status=ExecutionStatus.PENDING_APPROVAL) | run_filter)
            .order_by("-created_at")
        )

        if count_only:
            return Response({"count": qs.count()})

        limit = parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="Pagination invalide",
                details={"limit": limit, "offset": offset},
            )

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
        tags=["executions"],
        summary="Approuver une exécution en attente",
        responses={200: ExecutionSerializer},
    )
    @transaction.atomic
    def post(self, request: Request, execution_id: int) -> Response:
        # Code Review 30.1: Atomic transaction + row-level locking to prevent race conditions
        # ADR-007 backward compat (Story 57.8): if execution not PENDING_APPROVAL, try step gate
        try:
            execution = _get_and_validate_pending_execution(execution_id)
        except BadRequestError:
            step = _find_first_waiting_approval_step(execution_id)
            if step is not None:
                _validate_approval_gate_step(step)
                correlation_id = get_correlation_id()
                user_id = (
                    str(request.user.id)
                    if request.user and hasattr(request.user, "id")
                    else "unknown"
                )
                step.approved_by = cast(User, request.user)
                step.approved_at = timezone.now()
                step.approval_comment = ""
                step.status = ExecutionStepStatus.COMPLETED
                step.completed_at = timezone.now()
                step.save()
                step_config = _get_step_config(step)
                on_success_step_id = step_config.get("on_success_step_id")
                if on_success_step_id:
                    transaction.on_commit(
                        lambda: resume_container_workflow_from_gate.apply_async(
                            args=[execution_id, on_success_step_id]
                        )
                    )
                else:
                    exec_ = step.execution
                    if exec_.status == ExecutionStatus.RUNNING:
                        exec_.status = ExecutionStatus.COMPLETED
                        exec_.completed_at = timezone.now()
                        exec_.save()
                AuditService.create_entry(
                    user_id=user_id,
                    action_type=AuditActionType.EXECUTION_APPROVED,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=execution_id,
                    details={
                        "step_id": step.id,
                        "step_name": step.step_name,
                        "on_success_step_id": on_success_step_id,
                        "via_legacy_endpoint": True,
                    },
                    correlation_id=correlation_id,
                )
                logger.info(
                    "step_approved_via_legacy_endpoint",
                    step_id=step.id,
                    execution_id=execution_id,
                    user_id=user_id,
                    correlation_id=correlation_id,
                )
                return Response({"data": ExecutionStepSerializer(step).data})
            raise  # Re-raise original BadRequestError si aucun step WAITING trouvé

        old_status = execution.status
        correlation_id = get_correlation_id()
        user_id = (
            str(request.user.id)
            if request.user and hasattr(request.user, "id")
            else "unknown"
        )

        # State machine: PENDING_APPROVAL → RUNNING (Story 7.4). Transition then launch workflow.
        execution_service = self.get_execution_service()
        updated = execution_service.update_status(
            execution.id, ExecutionStatus.RUNNING, user_id
        )
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
        tags=["executions"],
        summary="Rejeter une exécution en attente",
        request=inline_serializer(
            name='RejectExecutionRequest',
            fields={
                'rejection_reason': serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text='Motif du rejet',
                ),
            },
        ),
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
        user_id = (
            str(request.user.id)
            if request.user and hasattr(request.user, "id")
            else "unknown"
        )

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


# ---------------------------------------------------------------------------
# Story 57.8 — Step-level approval views
# ---------------------------------------------------------------------------


class ApproveStepView(APIView):
    """POST /executions/{id}/steps/{step_id}/approve/ — Story 57.8."""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    @extend_schema(
        tags=["executions"],
        summary="Approuver un step en attente",
        request=inline_serializer(
            name='ApproveStepRequest',
            fields={
                'comment': serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text='Commentaire optionnel',
                ),
            },
        ),
        responses={200: ExecutionStepSerializer},
    )
    @transaction.atomic
    def post(self, request: Request, execution_id: int, step_id: int) -> Response:
        step = _get_step_or_404(execution_id, step_id)
        _validate_approval_gate_step(step)

        correlation_id = get_correlation_id()
        user_id = (
            str(request.user.id)
            if request.user and hasattr(request.user, "id")
            else "unknown"
        )

        step.approved_by = cast(User, request.user)
        step.approved_at = timezone.now()
        step.approval_comment = request.data.get("comment", "") or ""
        step.status = ExecutionStepStatus.COMPLETED
        step.completed_at = timezone.now()
        step.save()

        step_config = _get_step_config(step)
        on_success_step_id = step_config.get("on_success_step_id")

        if on_success_step_id:
            transaction.on_commit(
                lambda: resume_container_workflow_from_gate.apply_async(
                    args=[execution_id, on_success_step_id]
                )
            )
        else:
            execution = step.execution
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED
                execution.completed_at = timezone.now()
                execution.save()

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_APPROVED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                "step_id": step.id,
                "step_name": step.step_name,
                "on_success_step_id": on_success_step_id,
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "step_approved",
            step_id=step.id,
            step_name=step.step_name,
            execution_id=execution_id,
            user_id=user_id,
            on_success_step_id=on_success_step_id,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionStepSerializer(step).data})


class RejectStepView(APIView):
    """POST /executions/{id}/steps/{step_id}/reject/ — Story 57.8."""

    permission_classes = [IsAuthenticated, IsDBAOrDBOPS]

    @extend_schema(
        tags=["executions"],
        summary="Rejeter un step en attente",
        request=inline_serializer(
            name='RejectStepRequest',
            fields={
                'comment': serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text='Commentaire optionnel',
                ),
            },
        ),
        responses={200: ExecutionStepSerializer},
    )
    @transaction.atomic
    def post(self, request: Request, execution_id: int, step_id: int) -> Response:
        step = _get_step_or_404(execution_id, step_id)
        _validate_approval_gate_step(step)

        correlation_id = get_correlation_id()
        user_id = (
            str(request.user.id)
            if request.user and hasattr(request.user, "id")
            else "unknown"
        )

        step.status = ExecutionStepStatus.FAILED
        step.completed_at = timezone.now()
        step.approval_comment = request.data.get("comment", "") or ""
        step.save()

        step_config = _get_step_config(step)
        on_error_step_id = step_config.get("on_error_step_id")

        if on_error_step_id:
            transaction.on_commit(
                lambda: resume_container_workflow_from_gate.apply_async(
                    args=[execution_id, on_error_step_id]
                )
            )
        else:
            execution = step.execution
            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.FAILED
                execution.completed_at = timezone.now()
                execution.error_message = "Step approval rejected"
                execution.save()

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_REJECTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                "step_id": step.id,
                "step_name": step.step_name,
                "on_error_step_id": on_error_step_id,
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "step_rejected",
            step_id=step.id,
            step_name=step.step_name,
            execution_id=execution_id,
            user_id=user_id,
            on_error_step_id=on_error_step_id,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionStepSerializer(step).data})
