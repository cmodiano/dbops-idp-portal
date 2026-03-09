"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations (liste, approve, reject).
"""

from __future__ import annotations

from typing import cast

import structlog

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, NotFoundError
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.pagination import paginate_queryset
from core.permissions import IsDBAOrDBOPS, is_admin_user
from core.services import AuditService
from profiles.models import Profile
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
# Helpers Story 58.4 — approver permission check
# ---------------------------------------------------------------------------


def _get_user_profile_ids(user: User) -> set[int]:
    """Retourne les IDs de profils de l'utilisateur.

    Chemin 1 : Profile ORM direct
    Chemin 2 : M2M profiles
    Chemin 3 : ad_groups → Profile.objects.find_by_ad_groups()
    """
    profile_ids: set[int] = set()
    # Chemin 1
    profile_val = getattr(user, 'profile', None)
    if profile_val and hasattr(profile_val, 'id'):
        profile_ids.add(profile_val.id)
    # Chemin 2
    if hasattr(user, 'profiles'):
        for p in user.profiles.all():
            profile_ids.add(p.id)
    # Chemin 3
    if hasattr(user, 'ad_groups'):
        ad_groups = user.ad_groups or []
        for p in Profile.objects.find_by_ad_groups(ad_groups):
            profile_ids.add(p.id)
    return profile_ids



def _check_approver_permission(user: User, step_config: dict) -> bool:
    """Vérifie si l'utilisateur peut approuver ce step (Story 58.4 AC3, Story 59.1 SEC-1).

    Logique fail-secure :
    - Si step_config ne contient pas approver_profile_ids ou si la liste est vide :
        → False (fail-secure : en l'absence de restriction explicite, refuser)
    - Si step_config contient approver_profile_ids non vide :
        → True si l'utilisateur a au moins un profil dans la liste
    """
    approver_profile_ids = step_config.get('approver_profile_ids') or []
    if not approver_profile_ids:
        logger.warning(
            "approver_permission_fail_secure",
            reason="approver_profile_ids absent or empty in step_config",
            step_config_keys=list(step_config.keys()),
        )
        return False
    user_profile_ids = _get_user_profile_ids(user)
    return bool(user_profile_ids & set(approver_profile_ids))


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
    """Retourne la définition du step depuis action.execution_steps.

    Uses config_step_id (robust ID-based matching) with fallback to step_name
    for backward compatibility with older ExecutionStep records.
    """
    action = step.execution.action
    execution_steps = action.execution_steps or []
    for s in execution_steps:
        if isinstance(s, dict):
            # Primary: match by config_step_id (robust, always a UUID)
            if step.config_step_id and s.get("step_id") == step.config_step_id:
                return s
            # Fallback for old records without config_step_id
            if not step.config_step_id and (
                s.get("step_id") == step.step_name or s.get("name") == step.step_name
            ):
                return s
    logger.warning(
        "step_config_not_found",
        step_name=step.step_name,
        config_step_id=step.config_step_id,
        execution_id=step.execution_id,
        step_id=step.id,
    )
    return {}


def _get_next_step_id_by_order(execution_steps: list, current_step_config: dict) -> str | None:
    """Retourne le step_id du step suivant par ordre (fallback quand on_success_step_id absent).
    Exclut les members de parallel_group (non routables directement, comme dans le runtime).
    Utilise un fallback par identité (step_id/name) quand la comparaison par order échoue.
    """
    # Collect member step_ids from parallel_group steps
    member_step_ids: set[str] = set()
    for s in execution_steps:
        if isinstance(s, dict) and s.get("step_type") == "parallel_group":
            parallel_steps = s.get("parallel_steps")
            if isinstance(parallel_steps, list):
                for ps_id in parallel_steps:
                    if isinstance(ps_id, str) and ps_id:
                        member_step_ids.add(ps_id)
    # Filter to non-member steps only (same sequence the runtime uses for direct routing)
    candidate_steps = [
        s
        for s in execution_steps
        if isinstance(s, dict)
        and s.get("step_id")
        and s.get("step_id") not in member_step_ids
    ]
    sorted_steps = sorted(
        enumerate(candidate_steps),
        key=lambda ix: (ix[1].get("order", 0), ix[0]),
    )
    current_order = current_step_config.get("order", 0)
    current_sid = current_step_config.get("step_id")
    current_name = current_step_config.get("name")

    # Try identity-based match first: find current step in sorted list, return next
    if current_sid or current_name:
        for i, (_orig_idx, s) in enumerate(sorted_steps):
            if (current_sid and s.get("step_id") == current_sid) or (
                current_name and s.get("name") == current_name
            ):
                if i + 1 < len(sorted_steps):
                    return sorted_steps[i + 1][1].get("step_id")
                return None  # current step is last

    # Fallback: first step with strictly greater order
    for _orig_idx, s in sorted_steps:
        if s.get("order", 0) > current_order:
            return s.get("step_id")
    return None


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


def _get_execution_audit_context(execution: Execution) -> dict:
    """Contexte d'exécution pour l'audit : targets + parameters (déjà sanitisés).

    Retourne un dict avec les clés présentes seulement si non vides :
    - targets : liste de target_name des ExecutionTarget liées
    - parameters : dict des paramètres (déjà sanitisés en DB depuis _create_execution_atomic)
    """
    context: dict = {}
    targets = [t.target_name for t in execution.targets.all()]
    if targets:
        context["targets"] = targets
    params = execution.get_parameters()
    if params:
        context["parameters"] = params
    return context


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
            .prefetch_related("targets")  # Story 58.2: évite N+1 pour ExecutionTargetSerializer
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
    """POST /executions/{id}/approve — Approuver une exécution en attente.

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    Story 58.4 AC3/AC5: permission granulaire — admin requis pour PENDING_APPROVAL,
    _check_approver_permission pour step gate.
    """

    permission_classes = [IsAuthenticated]  # Story 58.4: permission vérifiée en interne

    _execution_service_class: type[ExecutionService] = ExecutionService

    def get_execution_service(self) -> ExecutionService:
        """Return an ExecutionService instance (overridable in tests)."""
        return self._execution_service_class()

    @extend_schema(
        tags=["executions"],
        summary="Approuver une exécution en attente",
        request=inline_serializer(
            name='ApproveExecutionRequest',
            fields={
                'comment': serializers.CharField(
                    required=False,
                    allow_blank=True,
                    help_text='Commentaire optionnel',
                ),
            },
        ),
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
                # Story 58.4 AC3: check approver permission for step gate path
                step_config = _get_step_config(step)
                if not _check_approver_permission(cast(User, request.user), step_config):
                    raise PermissionDenied("Vous n'avez pas les permissions pour approuver ce step")
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
                # Update output so gate_status reflects approval (UI shows correct state)
                output = step.get_output() or {}
                gate_status = output.get("gate_status", [])
                for gs in gate_status:
                    if isinstance(gs, dict) and gs.get("type") == "approval_granted":
                        gs["satisfied"] = True
                        gs["reason"] = f"Approuvé par utilisateur {user_id}"
                        break
                output["gate_status"] = gate_status
                step.set_output(output)
                step.save()
                # V113: Durable approval event + dequeue runnable step
                from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
                from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
                WorkflowEventService.emit_approval_granted(execution_id, step, approved_by=user_id)
                RunnableStepService.delete(step.id)
                on_success_step_id = step_config.get("on_success_step_id")
                if not on_success_step_id:
                    execution_steps = step.execution.action.execution_steps or []
                    on_success_step_id = _get_next_step_id_by_order(execution_steps, step_config)
                if on_success_step_id:
                    _eid, _sid = execution_id, on_success_step_id
                    transaction.on_commit(
                        lambda eid=_eid, sid=_sid: resume_container_workflow_from_gate.apply_async(  # type: ignore[misc]
                            args=[eid, sid], queue="default"
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
                        "action_name": step.execution.action.name if step.execution.action else None,
                        **_get_execution_audit_context(step.execution),
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

        # AC5: Legacy PENDING_APPROVAL → conserver la restriction admin (Story 58.4)
        if not is_admin_user(request.user):
            raise PermissionDenied("Seuls les administrateurs peuvent approuver une exécution PENDING_APPROVAL")

        old_status = execution.status
        correlation_id = get_correlation_id()
        # Code Review: capture optional approval comment for audit trail (parity with reject)
        approval_comment = (request.data or {}).get("comment", "") or ""
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
                "approval_comment": approval_comment or None,
                **_get_execution_audit_context(execution),
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
    """POST /executions/{id}/reject — Rejeter une exécution en attente.

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    Story 58.4 AC3/AC5: permission granulaire — admin requis pour PENDING_APPROVAL,
    _check_approver_permission pour step gate.
    """

    permission_classes = [IsAuthenticated]  # Story 58.4: permission vérifiée en interne

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
        # ADR-007 backward compat (Story 58.1): if execution not PENDING_APPROVAL, try step gate
        try:
            execution = _get_and_validate_pending_execution(execution_id)
        except BadRequestError:
            step = _find_first_waiting_approval_step(execution_id)
            if step is not None:
                _validate_approval_gate_step(step)
                # Story 58.4 AC3: check approver permission for step gate path
                step_config = _get_step_config(step)
                if not _check_approver_permission(cast(User, request.user), step_config):
                    raise PermissionDenied("Vous n'avez pas les permissions pour rejeter ce step")
                rejection_reason = (request.data or {}).get("rejection_reason", "")
                correlation_id = get_correlation_id()
                user_id = (
                    str(request.user.id)
                    if request.user and hasattr(request.user, "id")
                    else "unknown"
                )
                step.status = ExecutionStepStatus.FAILED
                step.completed_at = timezone.now()
                step.approval_comment = rejection_reason or ""
                step.save()
                # V113: Durable rejection event + dequeue runnable step
                from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
                from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
                WorkflowEventService.emit_approval_rejected(execution_id, step, rejected_by=user_id)
                RunnableStepService.delete(step.id)
                on_error_step_id = step_config.get("on_error_step_id")
                if on_error_step_id:
                    _eid, _eid_err = execution_id, on_error_step_id
                    transaction.on_commit(
                        lambda eid=_eid, sid=_eid_err: resume_container_workflow_from_gate.apply_async(  # type: ignore[misc]
                            args=[eid, sid], queue="default"
                        )
                    )
                else:
                    exec_ = step.execution
                    if exec_.status == ExecutionStatus.RUNNING:
                        exec_.status = ExecutionStatus.FAILED
                        exec_.completed_at = timezone.now()
                        exec_.error_message = rejection_reason or "Step approval rejected"
                        exec_.save()
                AuditService.create_entry(
                    user_id=user_id,
                    action_type=AuditActionType.EXECUTION_REJECTED,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=execution_id,
                    details={
                        "step_id": step.id,
                        "step_name": step.step_name,
                        "on_error_step_id": on_error_step_id,
                        "rejection_reason": rejection_reason or None,
                        "via_legacy_endpoint": True,
                        "action_name": step.execution.action.name if step.execution.action else None,
                        **_get_execution_audit_context(step.execution),
                    },
                    correlation_id=correlation_id,
                )
                logger.info(
                    "step_rejected_via_legacy_endpoint",
                    step_id=step.id,
                    execution_id=execution_id,
                    user_id=user_id,
                    correlation_id=correlation_id,
                )
                execution = step.execution
                execution.refresh_from_db()
                return Response({"data": ExecutionSerializer(execution).data})
            raise  # Re-raise original BadRequestError si aucun step WAITING trouvé

        # AC5: Legacy PENDING_APPROVAL → conserver la restriction admin (Story 58.4)
        if not is_admin_user(request.user):
            raise PermissionDenied("Seuls les administrateurs peuvent rejeter une exécution PENDING_APPROVAL")

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
                **_get_execution_audit_context(execution),
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
    """POST /executions/{id}/steps/{step_id}/approve/ — Story 57.8, 58.4."""

    permission_classes = [IsAuthenticated]  # Story 58.4: permission granulaire via _check_approver_permission

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

        # Story 58.4 AC3: vérifier la permission granulaire via approver_profile_ids
        step_config = _get_step_config(step)
        if not _check_approver_permission(cast(User, request.user), step_config):
            raise PermissionDenied("Vous n'avez pas les permissions pour approuver ce step")

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

        # Update output so gate_status reflects approval (UI shows correct state)
        output = step.get_output() or {}
        gate_status = output.get("gate_status", [])
        for gs in gate_status:
            if isinstance(gs, dict) and gs.get("type") == "approval_granted":
                gs["satisfied"] = True
                gs["reason"] = f"Approuvé par utilisateur {user_id}"
                break
        output["gate_status"] = gate_status
        step.set_output(output)

        step.save()

        # V113: Durable approval event + dequeue runnable step
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        WorkflowEventService.emit_approval_granted(execution_id, step, approved_by=user_id)
        RunnableStepService.delete(step.id)

        on_success_step_id = step_config.get("on_success_step_id")
        # Fallback: linear order when gate has no explicit on_success_step_id (common for simple workflows)
        if not on_success_step_id:
            execution_steps = step.execution.action.execution_steps or []
            on_success_step_id = _get_next_step_id_by_order(execution_steps, step_config)

        if on_success_step_id:
            _eid, _sid = execution_id, on_success_step_id
            transaction.on_commit(
                lambda eid=_eid, sid=_sid: resume_container_workflow_from_gate.apply_async(  # type: ignore[misc]
                    args=[eid, sid], queue="default"
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
                "action_name": step.execution.action.name if step.execution.action else None,
                **_get_execution_audit_context(step.execution),
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
    """POST /executions/{id}/steps/{step_id}/reject/ — Story 57.8, 58.4."""

    permission_classes = [IsAuthenticated]  # Story 58.4: permission granulaire via _check_approver_permission

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

        # Story 58.4 AC3: vérifier la permission granulaire via approver_profile_ids
        step_config = _get_step_config(step)
        if not _check_approver_permission(cast(User, request.user), step_config):
            raise PermissionDenied("Vous n'avez pas les permissions pour rejeter ce step")

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

        # V113: Durable rejection event + dequeue runnable step
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        WorkflowEventService.emit_approval_rejected(execution_id, step, rejected_by=user_id)
        RunnableStepService.delete(step.id)

        on_error_step_id = step_config.get("on_error_step_id")

        if on_error_step_id:
            _eid, _eid_err = execution_id, on_error_step_id
            transaction.on_commit(
                lambda eid=_eid, sid=_eid_err: resume_container_workflow_from_gate.apply_async(  # type: ignore[misc]
                    args=[eid, sid], queue="default"
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
                "rejection_reason": step.approval_comment or None,
                "action_name": step.execution.action.name if step.execution.action else None,
                **_get_execution_audit_context(step.execution),
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
