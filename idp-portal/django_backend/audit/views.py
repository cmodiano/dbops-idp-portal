from __future__ import annotations

import csv
import io
from datetime import datetime
from math import ceil

from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, ForbiddenError
from core.models import AuditLog, AuditEntityType, AuditActionType
from executions.models import Execution
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


_STATUS_ACTION_TYPES = {
    "success": [AuditActionType.EXECUTION_COMPLETED],
    "failed": [
        AuditActionType.EXECUTION_FAILED,
        AuditActionType.EXECUTION_REJECTED,
        AuditActionType.EXECUTION_CANCELLED,
    ],
    "running": [
        AuditActionType.EXECUTION_SUBMITTED,
        AuditActionType.EXECUTION_RUNNING,
        AuditActionType.EXECUTION_PENDING_APPROVAL,
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
            if s_up in ("FAILED", "REJECTED", "CANCELLED"):
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
    ):
        return "failed"
    if action_type in (
        AuditActionType.EXECUTION_SUBMITTED,
        AuditActionType.EXECUTION_RUNNING,
        AuditActionType.EXECUTION_PENDING_APPROVAL,
    ):
        return "running"
    return "unknown"


def _build_audit_queryset(request):
    qs = AuditLog.objects.filter(entity_type=AuditEntityType.EXECUTION)

    dt_from = _parse_dt(request.query_params.get("from"), name="from")
    dt_to = _parse_dt(request.query_params.get("to"), name="to")
    if dt_from:
        qs = qs.filter(timestamp__gte=dt_from)
    if dt_to:
        qs = qs.filter(timestamp__lte=dt_to)

    environment = (request.query_params.get("environment") or "").strip()
    if environment:
        exec_ids = Execution.objects.filter(environment=environment).values("id")
        qs = qs.filter(entity_id__in=exec_ids)

    action_id = request.query_params.get("action_id")
    if action_id is not None and action_id != "":
        aid = _parse_int(action_id, 0, name="action_id")
        exec_ids = Execution.objects.filter(action_id=aid).values("id")
        qs = qs.filter(entity_id__in=exec_ids)

    user_id = (request.query_params.get("user_id") or "").strip()
    if user_id:
        qs = qs.filter(user_id=user_id)

    status_filter = (request.query_params.get("status") or "").strip()
    if status_filter:
        if status_filter not in _STATUS_ACTION_TYPES:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="status invalide",
                details={"status": status_filter},
            )
        qs = qs.filter(action_type__in=_STATUS_ACTION_TYPES[status_filter])

    sort = (request.query_params.get("sort") or "timestamp").strip()
    order = (request.query_params.get("order") or "desc").strip().lower()
    sort_map = {
        "timestamp": "timestamp",
        "user_id": "user_id",
        "action_type": "action_type",
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
    GET /audit/executions (Story 6.3)

    Returns:
      { "data": AuditExecutionEntry[], "pagination": PaginationInfo }
    """

    permission_classes = [IsAuthenticated]

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
        total_count = qs.count()

        rows = list(qs[offset : offset + limit])
        execution_ids = [r.entity_id for r in rows if r.entity_id]
        executions = (
            Execution.objects.filter(id__in=execution_ids)
            .select_related("action")
            .only("id", "environment", "status", "servicenow_change_id", "parameters", "action_id", "action__name")
        )
        exec_by_id = {e.id: e for e in executions}

        data = []
        for r in rows:
            details = r.get_details()
            exec_obj = exec_by_id.get(r.entity_id)

            if details is None and exec_obj is not None:
                details = {
                    "action_id": exec_obj.action_id,
                    "environment": exec_obj.environment,
                    "status": exec_obj.status,
                    "parameters": exec_obj.get_parameters(),
                    "servicenow_change_id": exec_obj.servicenow_change_id,
                }

            action_name = None
            if exec_obj is not None and getattr(exec_obj, "action", None) is not None:
                action_name = exec_obj.action.name

            data.append(
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "user_id": r.user_id,
                    "action_type": r.action_type,
                    "entity_type": r.entity_type,
                    "entity_id": int(r.entity_id),
                    "action_name": action_name,
                    "details": details,
                    "ip_address": r.ip_address,
                    "correlation_id": r.correlation_id,
                    "derived_status": _derive_status(r.action_type, details),
                }
            )

        page = (offset // limit) + 1
        total_pages = int(ceil(total_count / limit)) if total_count else 1

        return Response(
            {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": limit,
                    "total_count": int(total_count),
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

    def get(self, request):
        if not _is_auditor(request.user):
            raise ForbiddenError(
                code="FORBIDDEN",
                message="Accès réservé aux auditeurs",
                details={},
            )

        fmt = (request.query_params.get("format") or "").strip().lower()
        if fmt not in ("csv", "pdf"):
            raise BadRequestError(code="BAD_REQUEST", message="format invalide", details={"format": fmt})

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
        execution_ids = [r.entity_id for r in rows if r.entity_id]
        executions = (
            Execution.objects.filter(id__in=execution_ids)
            .select_related("action")
            .only("id", "environment", "status", "servicenow_change_id", "action_id", "action__name")
        )
        exec_by_id = {e.id: e for e in executions}

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "id",
                "timestamp",
                "user_id",
                "action_type",
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
            exec_obj = exec_by_id.get(r.entity_id)
            writer.writerow(
                [
                    r.id,
                    r.timestamp.isoformat() if r.timestamp else "",
                    r.user_id,
                    r.action_type,
                    int(r.entity_id),
                    details.get("action_id") or (exec_obj.action_id if exec_obj else ""),
                    (exec_obj.action.name if exec_obj and getattr(exec_obj, "action", None) else ""),
                    details.get("environment") or (exec_obj.environment if exec_obj else ""),
                    details.get("status") or (exec_obj.status if exec_obj else ""),
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

