"""Vues des approbations en attente.

Responsabilité : Endpoints liés aux approbations (liste, approve, reject).
"""

from __future__ import annotations

import time
from typing import cast

import structlog

from django.db import connection, transaction
from django.db.models import Q, Subquery
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
from core.permissions import IsAdminUser, is_admin_user
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
from executions.tasks.gates import _get_next_step_by_order, resume_container_workflow_from_gate
from executions.utils import parse_int
from idp_auth.models import User

from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer

logger = structlog.get_logger(__name__)


def _enqueue_resume_with_retries(execution_id: int, step_ids: list[str], max_retries: int = 3) -> None:
    """Enqueue resume_container_workflow_from_gate with retries on transient broker errors."""
    for attempt in range(max_retries):
        try:
            resume_container_workflow_from_gate.apply_async(
                args=[execution_id, step_ids], queue="default"
            )
            return
        except Exception as e:  # noqa: BLE001
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
            else:
                logger.error(
                    "approval_resume_enqueue_failed",
                    execution_id=execution_id,
                    step_ids=step_ids,
                    error=str(e),
                    exc_info=True,
                )


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
            .select_related("execution__action", "approved_by", "rejected_by")
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
    from executions.utils.step_config import find_step_config  # noqa: PLC0415
    action = step.execution.action
    execution_steps = action.execution_steps or []
    result = find_step_config(execution_steps, step)
    if result is None:
        logger.warning(
            "step_config_not_found",
            step_name=step.step_name,
            config_step_id=step.config_step_id,
            execution_id=step.execution_id,
            step_id=step.id,
        )
        return {}
    return result


def _get_on_success_step_ids(step_config: dict, execution_steps: list) -> list[str]:
    """Story 67.4: Retourne la liste des step_ids à reprendre après approbation.

    ADR-007 (step_type présent): on_success_step_ids si présent, sinon _get_next_step_by_order.
    Legacy (sans step_type): bypass on_success_step_ids, retourne le next step par ordre.
    """
    is_adr007_step = bool(step_config.get("step_type"))
    if not is_adr007_step:
        next_step = _get_next_step_by_order(execution_steps, step_config)
        next_id = next_step.get("step_id") if next_step else None
        return [next_id] if next_id else []

    ids = step_config.get("on_success_step_ids")
    if isinstance(ids, list) and len(ids) > 0:
        return [s for s in ids if isinstance(s, str) and s]
    next_step = _get_next_step_by_order(execution_steps, step_config)
    next_id = next_step.get("step_id") if next_step else None
    return [next_id] if next_id else []


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

    permission_classes = [IsAuthenticated, IsAdminUser]  # AC2: Story 26.8

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
        # ADR-007: Approval gate steps can exist on SUBMITTED or RUNNING executions.
        # SUBMITTED: auto-approval-gate created by _create_execution_atomic (requires_approval).
        # RUNNING: workflow mid-execution approval gates.
        active_statuses = [ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING]
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
            run_filter = Q(status__in=active_statuses) & Q(
                pk__in=approval_exec_ids
            )
        else:
            # Subquery to avoid duplicate Execution rows when multiple WAITING approval steps exist
            approval_exec_ids_subquery = ExecutionStep.objects.filter(
                status=ExecutionStepStatus.WAITING,
                output__contains="approval_granted",
            ).values("execution_id")
            run_filter = Q(status__in=active_statuses) & Q(
                pk__in=Subquery(approval_exec_ids_subquery)
            )
        # ADR-007: PENDING_APPROVAL status is no longer used. Only step-based filter.
        # Pas de .distinct() : Oracle ORA-22848 avec CLOB (Action.execution_steps, etc.)
        # Le filtre pk__in=Subquery ne produit pas de doublons.
        qs = (
            Execution.objects.select_related("action", "user", "action__integration")
            .prefetch_related("targets")  # Story 58.2: évite N+1 pour ExecutionTargetSerializer
            .filter(run_filter)
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

    ADR-007: All approvals go through ExecutionStep WAITING gates.
    The legacy PENDING_APPROVAL execution-level path has been removed.

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    Story 58.4 AC3: permission granulaire via _check_approver_permission for step gate.
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
        responses={200: ExecutionStepSerializer},
    )
    def post(self, request: Request, execution_id: int) -> Response:
        # Return 404 when the Execution does not exist
        if not Execution.objects.filter(id=execution_id).exists():
            raise NotFoundError(
                code="NOT_FOUND",
                message="Exécution introuvable",
                details={"execution_id": execution_id},
            )
        # ADR-007: Only step-based approval path. Find the first WAITING approval step.
        step = _find_first_waiting_approval_step(execution_id)
        if step is None:
            raise BadRequestError(
                code="NO_PENDING_APPROVAL",
                message="Aucun step d'approbation en attente pour cette exécution",
                details={"execution_id": execution_id},
            )

        _validate_approval_gate_step(step)

        # ADR-007: For auto-approval-gate (created by _create_execution_atomic),
        # require admin permission (same as legacy PENDING_APPROVAL).
        # For workflow step gates, use granular approver_profile_ids check.
        is_auto_gate = step.config_step_id == 'auto-approval-gate'
        if is_auto_gate:
            if not is_admin_user(request.user):
                raise PermissionDenied("Seuls les administrateurs peuvent approuver cette exécution")
            step_config = _get_step_config(step)
        else:
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
        step.approval_comment = (request.data or {}).get("comment", "") or ""
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

        # V113: Durable approval event + dequeue runnable step (deferred to on_commit)
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        _eid, _step_id, _user_id_val = execution_id, step.id, user_id

        def _emit_approval_and_dequeue() -> None:
            WorkflowEventService.emit_approval_granted(_eid, step, approved_by=_user_id_val)
            RunnableStepService.delete(_step_id)

        execution_steps = step.execution.action.execution_steps or []
        on_success_step_ids = _get_on_success_step_ids(step_config, execution_steps)

        execution = step.execution

        with transaction.atomic():
            transaction.on_commit(_emit_approval_and_dequeue)

            # ADR-007: Check is_auto_gate FIRST. The auto-approval-gate is a synthetic step
            # not in action.execution_steps, so find_step_config returns None and
            # _get_on_success_step_ids falls through to _get_next_step_by_order, returning
            # the first workflow step. That would incorrectly trigger resume_container_workflow_from_gate,
            # which exits early (execution is SUBMITTED, not RUNNING). We must launch the workflow.
            if is_auto_gate:
                # Auto-approval-gate: launch runs synchronously AFTER this block commits
                # (see below) so we can return HTTP 400 on failure for actionable user feedback.
                pass
            elif on_success_step_ids:
                _eid, _sids = execution_id, on_success_step_ids
                transaction.on_commit(lambda: _enqueue_resume_with_retries(_eid, _sids))
            else:
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
                    "on_success_step_ids": on_success_step_ids,
                    "action_name": step.execution.action.name if step.execution.action else None,
                    **_get_execution_audit_context(step.execution),
                },
                correlation_id=correlation_id,
            )

        # Auto-approval-gate: launch synchronously after commit so we can return HTTP 400
        # on failure. Previously launch ran in on_commit; failures were only logged and
        # the execution stayed stuck in SUBMITTED with no actionable feedback.
        if is_auto_gate:
            try:
                exec_obj = Execution.objects.select_related('action').get(id=execution_id)
                self.get_execution_service().launch_workflow(exec_obj, correlation_id)
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "integration_error_on_approval_launch",
                    execution_id=execution_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=correlation_id,
                    exc_info=True,
                )
                try:
                    self.get_execution_service().update_status(
                        execution_id,
                        ExecutionStatus.INTEGRATION_ERROR,
                        user_id,
                    )
                except ValueError as ve:
                    logger.error(
                        "unexpected_state_machine_error_after_approval_launch",
                        execution_id=execution_id,
                        error=str(ve),
                        correlation_id=correlation_id,
                    )
                    fallback_exec = Execution.objects.get(id=execution_id)
                    fallback_exec.status = ExecutionStatus.INTEGRATION_ERROR
                    if not fallback_exec.completed_at:
                        fallback_exec.completed_at = timezone.now()
                    fallback_exec.save(update_fields=["status", "completed_at"])

                Execution.objects.filter(id=execution_id).update(error_message=str(e))

                raise BadRequestError(
                    code="INTEGRATION_ERROR",
                    message="Échec du lancement du workflow après approbation",
                    details={"error": str(e), "execution_id": execution_id},
                )

        logger.info(
            "step_approved",
            step_id=step.id,
            execution_id=execution_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionStepSerializer(step).data})


class RejectExecutionView(APIView):
    """POST /executions/{id}/reject — Rejeter une exécution en attente.

    ADR-007: All rejections go through ExecutionStep WAITING gates.
    The legacy PENDING_APPROVAL execution-level path has been removed.

    Story 33.4 (DIP): uses _execution_service_class + get_execution_service() so
    tests can override the service class without monkey-patching.
    Story 58.4 AC3: permission granulaire via _check_approver_permission for step gate.
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
        # Return 404 when the Execution does not exist
        if not Execution.objects.filter(id=execution_id).exists():
            raise NotFoundError(
                code="NOT_FOUND",
                message="Exécution introuvable",
                details={"execution_id": execution_id},
            )
        # ADR-007: Only step-based rejection path. Find the first WAITING approval step.
        step = _find_first_waiting_approval_step(execution_id)
        if step is None:
            raise BadRequestError(
                code="NO_PENDING_APPROVAL",
                message="Aucun step d'approbation en attente pour cette exécution",
                details={"execution_id": execution_id},
            )

        _validate_approval_gate_step(step)

        # ADR-007: For auto-approval-gate, require admin permission.
        # For workflow step gates, use granular approver_profile_ids check.
        is_auto_gate = step.config_step_id == 'auto-approval-gate'
        if is_auto_gate:
            if not is_admin_user(request.user):
                raise PermissionDenied("Seuls les administrateurs peuvent rejeter cette exécution")
            step_config = _get_step_config(step)
        else:
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
        step.rejected_by = cast(User, request.user)
        step.rejected_at = timezone.now()
        step.save()

        # V113: Durable rejection event + dequeue runnable step (deferred to on_commit)
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        _eid_rej, _step_id_rej, _user_id_rej = execution_id, step.id, user_id

        def _emit_rejection_and_dequeue() -> None:
            WorkflowEventService.emit_approval_rejected(_eid_rej, step, rejected_by=_user_id_rej)
            RunnableStepService.delete(_step_id_rej)

        transaction.on_commit(_emit_rejection_and_dequeue)

        on_error_step_ids = step_config.get("on_error_step_ids") or []
        execution = step.execution

        if on_error_step_ids:
            _eid, _sids_err = execution_id, on_error_step_ids
            transaction.on_commit(lambda: _enqueue_resume_with_retries(_eid, _sids_err))
        else:
            # ADR-007: For auto-approval-gate rejection, mark execution as FAILED
            # (it was never launched, so it's in SUBMITTED status).
            if execution.status in (ExecutionStatus.RUNNING, ExecutionStatus.SUBMITTED):
                execution.status = ExecutionStatus.FAILED
                execution.completed_at = timezone.now()
                execution.error_message = rejection_reason or "Step approval rejected"
                execution.save()

        AuditService.create_entry(
            user_id=user_id,
            action_type=AuditActionType.EXECUTION_REJECTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=execution_id,
            details={
                "step_id": step.id,
                "step_name": step.step_name,
                "on_error_step_ids": on_error_step_ids,
                "rejection_reason": rejection_reason or None,
                "action_name": step.execution.action.name if step.execution.action else None,
                **_get_execution_audit_context(step.execution),
            },
            correlation_id=correlation_id,
        )

        logger.info(
            "step_rejected",
            step_id=step.id,
            execution_id=execution_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        execution.refresh_from_db()
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

        execution_steps = step.execution.action.execution_steps or []
        on_success_step_ids = _get_on_success_step_ids(step_config, execution_steps)
        if on_success_step_ids:
            _eid, _sids = execution_id, on_success_step_ids
            transaction.on_commit(
                lambda: resume_container_workflow_from_gate.apply_async(
                    args=[_eid, _sids], queue="default"
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
                "on_success_step_ids": on_success_step_ids,
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
            on_success_step_ids=on_success_step_ids,
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
        step.rejected_by = cast(User, request.user)
        step.rejected_at = timezone.now()
        step.save()

        # V113: Durable rejection event + dequeue runnable step
        from executions.services.workflow_events import WorkflowEventService  # noqa: PLC0415
        from executions.services.runnable_steps import RunnableStepService  # noqa: PLC0415
        WorkflowEventService.emit_approval_rejected(execution_id, step, rejected_by=user_id)
        RunnableStepService.delete(step.id)

        on_error_step_ids = step_config.get("on_error_step_ids") or []

        if on_error_step_ids:
            _eid, _sids_err = execution_id, on_error_step_ids
            transaction.on_commit(lambda: _enqueue_resume_with_retries(_eid, _sids_err))
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
                "on_error_step_ids": on_error_step_ids,
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
            on_error_step_ids=on_error_step_ids,
            correlation_id=correlation_id,
        )

        return Response({"data": ExecutionStepSerializer(step).data})
