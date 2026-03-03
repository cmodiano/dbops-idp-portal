from __future__ import annotations

import csv
import io
from datetime import datetime
from math import ceil

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, ForbiddenError
from core.utils import ensure_utc_isoformat
from core.models import AuditLog, AuditEntityType, AuditActionType
from executions.models import Execution, ExecutionStatus
from idp_auth.models import User
from profiles.models import Profile


def _parse_int(value: str | None, default: int, *, name: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide", details={name: value})


def _parse_dt(value: str | None, *, name: str) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if not dt:
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide (ISO 8601)", details={name: value})
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _is_auditor(user) -> bool:
    """
    Determine if user is auditor based on resolved profiles.
    Mirrors logic used in /auth/me.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    ad_groups = getattr(user, "ad_groups", None)
    if not isinstance(ad_groups, list) or not ad_groups:
        profile_name = getattr(user, "profile", "") or ""
        if profile_name:
            ad_groups = [profile_name]
        else:
            ad_groups = []

    profiles = Profile.objects.find_by_ad_groups(ad_groups) if ad_groups else []
    return any(getattr(p, "is_auditor", 0) == 1 for p in profiles)


# Map audit filter value to current Execution.status (filter by execution state, not audit event type)
# Fix: "En cours" must show only executions currently in progress, not old RUNNING events for completed executions.
_EXECUTION_STATUS_BY_FILTER = {
    "success": [ExecutionStatus.COMPLETED],
    "failed": [
        ExecutionStatus.FAILED,
        ExecutionStatus.REJECTED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.INTEGRATION_ERROR,
    ],
    "running": [
        ExecutionStatus.SUBMITTED,
        ExecutionStatus.RUNNING,
        ExecutionStatus.PENDING_APPROVAL,
    ],
}


def _derive_status(action_type: str, details: dict | None) -> str:
    # Prefer explicit status in details when present
    if details and isinstance(details, dict):
        s = details.get("status")
        if isinstance(s, str):
            s_up = s.upper()
            if s_up in ("COMPLETED",):
                return "success"
            if s_up in ("FAILED", "REJECTED", "CANCELLED", "INTEGRATION_ERROR"):
                return "failed"
            if s_up in ("SUBMITTED", "RUNNING", "PENDING_APPROVAL"):
                return "running"

    # Fallback to action_type
    if action_type == AuditActionType.EXECUTION_COMPLETED:
        return "success"
    if action_type in (
        AuditActionType.EXECUTION_FAILED,
        AuditActionType.EXECUTION_REJECTED,
        AuditActionType.EXECUTION_CANCELLED,
        AuditActionType.EXECUTION_INTEGRATION_ERROR,
    ):
        return "failed"
    if action_type in (
        AuditActionType.EXECUTION_SUBMITTED,
        AuditActionType.EXECUTION_RUNNING,
        AuditActionType.EXECUTION_PENDING_APPROVAL,
    ):
        return "running"
    return "unknown"


def _resolve_user_names(user_ids: list[str]) -> dict[str, str]:
    """Resolve user_id list to display names (display_name or username). Returns map user_id -> name.

    Optimized: uses batch queries (1 for numeric IDs, 1 for usernames) instead of N individual queries.
    Performance: 2-pass algorithm (categorize + fill missing) instead of 3 loops.
    """
    result: dict[str, str] = {}
    if not user_ids:
        return result

    numeric_ids: list[int] = []
    non_numeric_ids: list[str] = []

    # Pass 1: Categorize and pre-fill result with fallback values
    for uid in user_ids:
        try:
            numeric_ids.append(int(uid))
            result[uid] = uid  # Fallback if not found in DB
        except (ValueError, TypeError):
            non_numeric_ids.append(uid)
            result[uid] = uid  # Fallback if not found in DB

    # Pass 2a: Batch query for numeric IDs and override fallback
    if numeric_ids:
        for u in User.objects.filter(id__in=numeric_ids).only("id", "display_name", "username"):
            result[str(u.id)] = u.display_name or u.username or str(u.id)

    # Pass 2b: Batch query for non-numeric IDs (usernames) and override fallback
    if non_numeric_ids:
        for u in User.objects.filter(username__in=non_numeric_ids).only("username", "display_name"):
            result[u.username] = u.display_name or u.username

    return result


def _build_audit_queryset(request):
    # Story 43.1: base sans filtre — toutes les entités
    qs = AuditLog.objects.all()

    # Filtre entity_type (optionnel, Story 43.1)
    entity_type_param = (request.query_params.get("entity_type") or "").strip()
    if entity_type_param:
        if entity_type_param not in AuditEntityType.values:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="entity_type invalide",
                details={"entity_type": entity_type_param},
            )
        qs = qs.filter(entity_type=entity_type_param)

    # Filtre action_type (optionnel, Story 43.1)
    action_type_param = (request.query_params.get("action_type") or "").strip()
    if action_type_param:
        if action_type_param not in AuditActionType.values:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="action_type invalide",
                details={"action_type": action_type_param},
            )
        qs = qs.filter(action_type=action_type_param)

    # Filtre user par recherche icontains (Story 43.1)
    user_search = (request.query_params.get("user") or "").strip()
    if user_search:
        matching_users = User.objects.filter(
            Q(username__icontains=user_search) | Q(display_name__icontains=user_search)
        ).values_list("id", flat=True)
        user_id_strs = [str(uid) for uid in matching_users]
        qs = qs.filter(
            Q(user_id__in=user_id_strs) | Q(user_id__icontains=user_search)
        )

    dt_from = _parse_dt(request.query_params.get("from"), name="from")
    dt_to = _parse_dt(request.query_params.get("to"), name="to")
    if dt_from:
        qs = qs.filter(timestamp__gte=dt_from)
    if dt_to:
        qs = qs.filter(timestamp__lte=dt_to)

    # Filtres execution-only : ne s'appliquent que si entity_type=execution ou non filtré (Story 43.1, AC6)
    # AC6: ignorés silencieusement pour les autres types
    is_execution_scope = entity_type_param in ("", "execution")
    if is_execution_scope:
        # Helper: applique un filtre execution-only sans exclure les entrées non-exécution
        # Quand entity_type=execution : filtre tout le queryset (déjà limité aux EXECUTION)
        # Quand aucun entity_type : ne filtre que les EXECUTION, laisse les autres intactes
        def _apply_exec_filter(qs, exec_ids_qs):
            if entity_type_param == "execution":
                return qs.filter(entity_id__in=exec_ids_qs)
            # Aucun entity_type fourni : garder les non-exécutions, filtrer les exécutions
            return qs.filter(
                ~Q(entity_type=AuditEntityType.EXECUTION) | Q(entity_id__in=exec_ids_qs)
            )

        environment = (request.query_params.get("environment") or "").strip()
        if environment:
            exec_ids = Execution.objects.filter(environment=environment).values_list("id", flat=True)
            qs = _apply_exec_filter(qs, exec_ids)

        action_id = request.query_params.get("action_id")
        if action_id is not None and action_id != "":
            aid = _parse_int(action_id, 0, name="action_id")
            exec_ids = Execution.objects.filter(action_id=aid).values_list("id", flat=True)
            qs = _apply_exec_filter(qs, exec_ids)

        # Filter by action engine (REF_ENGINES code)
        engine_type = (request.query_params.get("engine_type") or "").strip()
        if engine_type:
            exec_ids = Execution.objects.filter(action__engine=engine_type).values_list("id", flat=True)
            qs = _apply_exec_filter(qs, exec_ids)

        status_filter = (request.query_params.get("status") or "").strip()
        if status_filter:
            if status_filter not in _EXECUTION_STATUS_BY_FILTER:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="status invalide",
                    details={"status": status_filter},
                )
            # Filter by current execution status so "En cours" shows only executions still in progress
            exec_statuses = _EXECUTION_STATUS_BY_FILTER[status_filter]
            exec_ids = Execution.objects.filter(status__in=exec_statuses).values_list("id", flat=True)
            qs = _apply_exec_filter(qs, exec_ids)

    # Story 6.3: user_id exact match (rétro-compatibilité)
    user_id = (request.query_params.get("user_id") or "").strip()
    if user_id:
        qs = qs.filter(user_id=user_id)

    # Story 27.8: Filter by correlation_id (exact match)
    correlation_id = (request.query_params.get("correlation_id") or "").strip()
    if correlation_id:
        qs = qs.filter(correlation_id=correlation_id)

    sort = (request.query_params.get("sort") or "timestamp").strip()
    order = (request.query_params.get("order") or "desc").strip().lower()
    sort_map = {
        "timestamp": "timestamp",
        "user_id": "user_id",
        "action_type": "action_type",
        "entity_type": "entity_type",
    }
    if sort not in sort_map:
        raise BadRequestError(code="BAD_REQUEST", message="sort invalide", details={"sort": sort})
    if order not in ("asc", "desc"):
        raise BadRequestError(code="BAD_REQUEST", message="order invalide", details={"order": order})
    ordering = sort_map[sort]
    if order == "desc":
        ordering = f"-{ordering}"
    qs = qs.order_by(ordering)

    return qs


class AuditExecutionsView(APIView):
    """
    GET /audit/executions (Story 6.3, Story 27.8, Story 43.1)

    Query parameters:
      - entity_type: Filter by entity type (action, execution, user, integration, ...) [Story 43.1]
                     Sans filtre : retourne toutes les entrées d'audit.
      - action_type: Filter by audit action type (ACTION_CREATED, EXECUTION_COMPLETED, ...) [Story 43.1]
      - user: Recherche icontains sur username ou display_name [Story 43.1]
      - from/to: ISO 8601 date range filter
      - environment: Filter by execution environment (execution-only, ignoré si entity_type != execution)
      - action_id: Filter by action ID (execution-only)
      - engine_type: Filter by action engine (REF_ENGINES code) (execution-only)
      - user_id: Filter by exact user ID (rétro-compatibilité Story 6.3)
      - status: Filter by derived status (success, failed, running) (execution-only)
      - correlation_id: Filter by exact correlation ID (Story 27.8)
      - sort/order: Sort field and direction
      - limit/offset: Pagination

    Returns:
      { "data": AuditEntry[], "pagination": PaginationInfo }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['audit'],
        summary='Lister les entrées d\'audit',
        parameters=[
            OpenApiParameter('limit', int, description='Nombre de résultats par page (défaut: 25, max: 500)'),
            OpenApiParameter('offset', int, description='Décalage pour la pagination'),
            OpenApiParameter('entity_type', str, description='Filtre par type d\'entité (execution, action, user, ...)'),
            OpenApiParameter('action_type', str, description='Filtre par type d\'action d\'audit'),
            OpenApiParameter('user', str, description='Recherche icontains sur username ou display_name'),
            OpenApiParameter('user_id', str, description='Filtre par user_id exact'),
            OpenApiParameter('from', str, description='Date de début (ISO 8601)'),
            OpenApiParameter('to', str, description='Date de fin (ISO 8601)'),
            OpenApiParameter('environment', str, description='Filtre par environnement (execution-only)'),
            OpenApiParameter('action_id', int, description='Filtre par action ID (execution-only)'),
            OpenApiParameter('engine_type', str, description='Filtre par engine (execution-only)'),
            OpenApiParameter('status', str, description='success | failed | running (execution-only)'),
            OpenApiParameter('correlation_id', str, description='Filtre par correlation_id'),
            OpenApiParameter('sort', str, description='Champ de tri'),
            OpenApiParameter('order', str, description='asc | desc'),
        ],
    )
    def get(self, request):
        if not _is_auditor(request.user):
            raise ForbiddenError(
                code="FORBIDDEN",
                message="Accès réservé aux auditeurs",
                details={},
            )

        limit = _parse_int(request.query_params.get("limit"), 25, name="limit")
        offset = _parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or limit > 500:
            raise BadRequestError(code="BAD_REQUEST", message="limit invalide", details={"limit": limit})
        if offset < 0:
            raise BadRequestError(code="BAD_REQUEST", message="offset invalide", details={"offset": offset})

        qs = _build_audit_queryset(request)
        total = qs.count()

        rows = list(qs[offset : offset + limit])
        # Story 43.1 T3.2: batch query uniquement sur les IDs d'exécution
        execution_ids = [r.entity_id for r in rows if r.entity_type == AuditEntityType.EXECUTION and r.entity_id is not None]
        executions = (
            Execution.objects.filter(id__in=execution_ids)
            .select_related("action")
            .only("id", "environment", "status", "servicenow_change_id", "parameters", "action_id", "action__name", "parent_execution_id")
        )
        exec_by_id = {e.id: e for e in executions}

        user_name_by_id = _resolve_user_names(list({r.user_id for r in rows if r.user_id}))

        data = []
        for r in rows:
            details = r.get_details()
            # Story 43.1 T3.1: ne pas tenter de récupérer Execution pour les entrées non-exécution
            exec_obj = exec_by_id.get(r.entity_id) if r.entity_type == AuditEntityType.EXECUTION else None

            if details is None and exec_obj is not None:
                details = {
                    "action_id": exec_obj.action_id,
                    "environment": exec_obj.environment,
                    "status": exec_obj.status,
                    "parameters": exec_obj.get_parameters(),
                    "servicenow_change_id": exec_obj.servicenow_change_id,
                }
            elif details is not None and exec_obj is not None:
                # Always enrich with current execution status (not stale audit-time status)
                details["status"] = exec_obj.status

            # Story 43.1 T3.3: champs execution-only = None pour les entrées non-exécution
            if r.entity_type == AuditEntityType.EXECUTION:
                action_name = exec_obj.action.name if exec_obj is not None and getattr(exec_obj, "action", None) is not None else None
                derived_status = _derive_status(r.action_type, details)
                parent_execution_id = getattr(exec_obj, "parent_execution_id", None) if exec_obj else None
                item_type = getattr(exec_obj.action, "item_type", None) if exec_obj and getattr(exec_obj, "action", None) else None
            else:
                action_name = None
                derived_status = None
                parent_execution_id = None
                item_type = None

            data.append(
                {
                    "id": r.id,
                    "timestamp": ensure_utc_isoformat(r.timestamp),
                    "user_id": r.user_id,
                    "user_name": user_name_by_id.get(r.user_id) if r.user_id else None,
                    "action_type": r.action_type,
                    "entity_type": r.entity_type,
                    "entity_id": None if r.entity_id is None else int(r.entity_id),
                    "action_name": action_name,
                    "details": details,
                    "ip_address": r.ip_address,
                    "correlation_id": r.correlation_id,
                    "derived_status": derived_status,
                    "parent_execution_id": parent_execution_id,
                    "item_type": item_type,
                }
            )

        page = (offset // limit) + 1
        total_pages = int(ceil(total / limit)) if total else 1

        return Response(
            {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": limit,
                    "total": int(total),
                    "total_pages": total_pages,
                },
            }
        )


class AuditExportView(APIView):
    """
    GET /audit/export (Story 6.4)
    format=csv|pdf
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['audit'],
        summary='Exporter les entrées d\'audit (CSV ou PDF)',
        parameters=[
            OpenApiParameter('fmt', str, description='Format: csv | pdf (ou export_format)'),
            OpenApiParameter('export_format', str, description='Alias pour fmt'),
            OpenApiParameter('limit', int, description='Max 10000 lignes'),
            OpenApiParameter('offset', int, description='Décalage'),
            OpenApiParameter('entity_type', str, description='Filtre par type d\'entité'),
            OpenApiParameter('action_type', str, description='Filtre par type d\'action'),
            OpenApiParameter('user', str, description='Recherche user'),
            OpenApiParameter('from', str, description='Date début (ISO 8601)'),
            OpenApiParameter('to', str, description='Date fin (ISO 8601)'),
            OpenApiParameter('environment', str, description='Filtre environnement'),
            OpenApiParameter('action_id', int, description='Filtre action_id'),
            OpenApiParameter('engine_type', str, description='Filtre engine'),
            OpenApiParameter('status', str, description='success | failed | running'),
            OpenApiParameter('correlation_id', str, description='Filtre correlation_id'),
        ],
    )
    def get(self, request):
        if not _is_auditor(request.user):
            raise ForbiddenError(
                code="FORBIDDEN",
                message="Accès réservé aux auditeurs",
                details={},
            )

        # Use 'fmt' param (not 'format') to avoid DRF content negotiation conflict
        fmt = (request.query_params.get("fmt") or request.query_params.get("export_format") or "").strip().lower()
        if fmt not in ("csv", "pdf"):
            raise BadRequestError(code="BAD_REQUEST", message="format invalide (use ?fmt=csv or ?fmt=pdf)", details={"fmt": fmt})

        qs = _build_audit_queryset(request)
        total = qs.count()
        if total > 10_000:
            raise BadRequestError(
                code="EXPORT_LIMIT_EXCEEDED",
                message="Limite d'export dépassée (maximum 10 000 lignes). Veuillez appliquer des filtres supplémentaires.",
                details={"total": int(total), "max": 10_000},
            )

        # PDF export not implemented without a PDF library
        if fmt == "pdf":
            raise BadRequestError(
                code="NOT_IMPLEMENTED",
                message="Export PDF non disponible (utiliser CSV)",
                details={},
            )

        # Build CSV
        rows = list(qs[:10_000])
        # Story 43.1: batch query uniquement sur les IDs d'exécution (pas les autres entity_types)
        execution_ids = [r.entity_id for r in rows if r.entity_type == AuditEntityType.EXECUTION and r.entity_id is not None]
        executions = (
            Execution.objects.filter(id__in=execution_ids)
            .select_related("action")
            .only("id", "environment", "status", "servicenow_change_id", "action_id", "action__name")
        )
        exec_by_id = {e.id: e for e in executions}

        # Resolve user_id -> user_name for CSV
        user_ids_export = list({r.user_id for r in rows if r.user_id})
        user_name_by_id_export = _resolve_user_names(user_ids_export)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "timestamp",
                "user_id",
                "user_name",
                "action_type",
                "entity_type",          # Story 43.6
                "execution_id",
                "action_id",
                "action_name",
                "environment",
                "status",
                "servicenow_change_id",
                "ip_address",
                "correlation_id",
            ]
        )

        for r in rows:
            details = r.get_details() or {}
            # Story 43.1: ne récupérer l'Execution que pour les entrées de type EXECUTION
            exec_obj = exec_by_id.get(r.entity_id) if r.entity_type == AuditEntityType.EXECUTION else None
            writer.writerow(
                [
                    r.id,
                    ensure_utc_isoformat(r.timestamp) or "",
                    r.user_id or "",
                    user_name_by_id_export.get(r.user_id) or r.user_id or "",
                    r.action_type,
                    r.entity_type,          # Story 43.6
                    ("" if r.entity_id is None else int(r.entity_id)) if r.entity_type == AuditEntityType.EXECUTION else "",
                    details.get("action_id") or (exec_obj.action_id if exec_obj else ""),
                    (exec_obj.action.name if exec_obj and getattr(exec_obj, "action", None) else "")
                    or details.get("action_name", ""),      # Story 43.6 : fallback depuis details
                    details.get("environment") or (exec_obj.environment if exec_obj else ""),
                    (exec_obj.status if exec_obj else details.get("status") or ""),
                    details.get("servicenow_change_id") or (exec_obj.servicenow_change_id if exec_obj else ""),
                    r.ip_address or "",
                    r.correlation_id or "",
                ]
            )

        content = buf.getvalue().encode("utf-8")
        filename = f"audit-export-{timezone.now().date().isoformat()}.csv"

        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

