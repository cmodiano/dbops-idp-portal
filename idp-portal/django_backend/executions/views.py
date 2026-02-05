from __future__ import annotations

from datetime import datetime, timedelta, date

from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action
from core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from executions.models import Execution, ExecutionStep, ExecutionStatus
from executions.serializers import ExecutionSerializer, ExecutionStepSerializer
from executions.services import ExecutionService


def _parse_int(value: str | None, default: int, *, name: str) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide", details={name: value})


def _parse_date(value: str | None, *, name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise BadRequestError(code="BAD_REQUEST", message=f"{name} invalide (YYYY-MM-DD)", details={name: value})


def _is_dba_or_dbops(user) -> bool:
    profile = (getattr(user, "profile", "") or "").lower()
    return profile == "dbops" or profile == "dba" or profile.startswith("dba")


def _apply_scope_filter(qs, *, user, scope: str) -> tuple[object, str]:
    """
    Return (qs, effective_scope) following FastAPI behavior:
    - scope defaults to mine
    - scope=all only if user is DBA/DBOPS, else fallback to mine
    """
    scope = (scope or "mine").lower()
    if scope not in ("mine", "all"):
        raise BadRequestError(code="BAD_REQUEST", message="scope invalide", details={"scope": scope})

    can_view_all = _is_dba_or_dbops(user)
    effective_scope = scope if (scope == "mine" or can_view_all) else "mine"
    if effective_scope == "mine":
        qs = qs.filter(user_id=user.id)
    return qs, effective_scope


def _apply_execution_filters(qs, *, request):
    """
    Apply advanced filters (Story 9.10) used by the frontend:
    start_date, end_date, action_id, engine, tags (AND), status, environment.
    """
    start_date_s = request.query_params.get("start_date")
    end_date_s = request.query_params.get("end_date")
    start_d = _parse_date(start_date_s, name="start_date")
    end_d = _parse_date(end_date_s, name="end_date")

    if start_d:
        start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()))
        qs = qs.filter(created_at__gte=start_dt)
    if end_d:
        # inclusive end_date
        end_exclusive = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()))
        qs = qs.filter(created_at__lt=end_exclusive)

    action_id = request.query_params.get("action_id")
    if action_id:
        qs = qs.filter(action_id=_parse_int(action_id, 0, name="action_id"))

    engine = request.query_params.get("engine")
    if engine:
        qs = qs.filter(action__engine=engine)

    tags = request.query_params.get("tags")
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t and t.strip()]
        if tag_list:
            action_ids = Action.objects.search_by_tags(tag_list).values("id")
            qs = qs.filter(action_id__in=action_ids)

    status = request.query_params.get("status")
    if status:
        qs = qs.filter(status=status)

    environment = request.query_params.get("environment")
    if environment:
        qs = qs.filter(environment=environment)

    return qs, start_d, end_d


class ExecutionsView(APIView):
    """
    GET /executions?limit&offset&scope + filters -> {data, pagination}
    POST /executions -> {data: ExecutionCreateResponse}

    For now, POST uses existing ExecutionService.create_execution (no background execution).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = _parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = _parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        qs = Execution.objects.select_related("action", "user", "action__integration")
        qs, _effective_scope = _apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, _start_d, _end_d = _apply_execution_filters(qs, request=request)
        qs = qs.order_by("-created_at")

        total_count = qs.count()
        page = (offset // limit) + 1
        total_pages = (total_count + limit - 1) // limit if limit else 1

        items = list(qs[offset: offset + limit])
        data = ExecutionSerializer(items, many=True).data

        return Response(
            {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": limit,
                    "total_count": total_count,
                    "total_pages": total_pages,
                },
            }
        )

    def post(self, request):
        payload = request.data or {}
        action_id = payload.get("action_id")
        environment = payload.get("environment")
        parameters = payload.get("parameters")
        parent_execution_id = payload.get("parent_execution_id")

        if not action_id or not environment:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="action_id et environment sont requis",
                details={"action_id": action_id, "environment": environment},
            )

        try:
            action = Action.objects.get(id=int(action_id), status="published")
        except (ValueError, TypeError):
            raise BadRequestError(code="BAD_REQUEST", message="action_id invalide", details={"action_id": action_id})
        except Action.DoesNotExist:
            raise NotFoundError(code="ACTION_NOT_FOUND", message="Action non trouvée", details={"action_id": action_id})

        correlation_id = request.headers.get("X-Idp-Request-Id")
        execution = ExecutionService().create_execution(
            user=request.user,
            action=action,
            environment=environment,
            parameters=parameters,
            parent_execution_id=parent_execution_id,
            correlation_id=correlation_id,
        )

        return Response(
            {
                "data": {
                    "execution_id": execution.id,
                    "status": execution.status,
                    "created_at": execution.created_at.isoformat() if execution.created_at else None,
                }
            },
            status=201,
        )


class ExecutionDetailView(APIView):
    """GET /executions/{id} -> {data: ExecutionResponse}"""

    permission_classes = [IsAuthenticated]

    def get(self, request, execution_id: int):
        try:
            execution = Execution.objects.select_related("action", "user", "action__integration").get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        # RBAC: owner or DBA/DBOPS
        if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        return Response({"data": ExecutionSerializer(execution).data})


class ExecutionStepsView(APIView):
    """GET /executions/{id}/steps -> {data: ExecutionStepResponse[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request, execution_id: int):
        try:
            execution = Execution.objects.get(id=execution_id)
        except Execution.DoesNotExist:
            raise NotFoundError(code="NOT_FOUND", message="Execution non trouvée", details={"execution_id": execution_id})

        if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        steps = ExecutionStep.objects.filter(execution_id=execution_id).order_by("step_order")
        return Response({"data": ExecutionStepSerializer(steps, many=True).data})


class ExecutionStepLogsView(APIView):
    """GET /executions/{id}/steps/{step_id}/logs -> {data: StepLogsResponse}"""

    permission_classes = [IsAuthenticated]

    def get(self, request, execution_id: int, step_id: int):
        try:
            step = ExecutionStep.objects.select_related("execution").get(id=step_id, execution_id=execution_id)
        except ExecutionStep.DoesNotExist:
            raise NotFoundError(
                code="NOT_FOUND",
                message="Step non trouvé",
                details={"execution_id": execution_id, "step_id": step_id},
            )

        execution = step.execution
        if execution.user_id != request.user.id and not _is_dba_or_dbops(request.user):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={"execution_id": execution_id})

        return Response(
            {
                "data": {
                    "step_id": step.id,
                    "output": step.get_output() if hasattr(step, "get_output") else None,
                    "error_message": step.error_message,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                }
            }
        )


class ExecutionStatsView(APIView):
    """GET /executions/stats -> {data: DashboardStats}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Execution.objects.select_related("action")
        qs, _effective_scope = _apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, start_d, end_d = _apply_execution_filters(qs, request=request)

        # executions_jour: today if no date filters, else total in period (already filtered)
        if start_d or end_d:
            executions_jour = qs.count()
        else:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            executions_jour = qs.filter(created_at__gte=today_start).count()

        finished = qs.filter(status__in=[ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]).count()
        completed = qs.filter(status=ExecutionStatus.COMPLETED).count()
        taux_succes_pct = round((completed / finished) * 100, 2) if finished > 0 else 0.0

        executions_en_cours = qs.filter(
            status__in=[ExecutionStatus.RUNNING, ExecutionStatus.SUBMITTED, ExecutionStatus.PENDING_APPROVAL]
        ).count()
        executions_en_erreur = qs.filter(status=ExecutionStatus.FAILED).count()

        return Response(
            {
                "data": {
                    "executions_jour": executions_jour,
                    "taux_succes_pct": taux_succes_pct,
                    "executions_en_cours": executions_en_cours,
                    "executions_en_erreur": executions_en_erreur,
                }
            }
        )


class ExecutionTimeSeriesView(APIView):
    """GET /executions/timeseries -> {data: DashboardTimeSeriesPoint[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Execution.objects.all()
        qs, _effective_scope = _apply_scope_filter(qs, user=request.user, scope=request.query_params.get("scope") or "mine")
        qs, start_d, end_d = _apply_execution_filters(qs, request=request)

        # Default period: last 7 days if no date filters
        if not start_d:
            start_d = (timezone.now() - timedelta(days=7)).date()
        if not end_d:
            end_d = timezone.now().date()

        start_dt = timezone.make_aware(datetime.combine(start_d, datetime.min.time()))
        end_exclusive = timezone.make_aware(datetime.combine(end_d + timedelta(days=1), datetime.min.time()))
        qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_exclusive)

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


class ExecutionTagsView(APIView):
    """GET /executions/tags -> {data: string[]}"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        action_ids = Execution.objects.values_list("action_id", flat=True).distinct()
        tags = (
            Action.objects.filter(id__in=action_ids)
            .values_list("actiontag__tag__name", flat=True)
            .distinct()
            .order_by("actiontag__tag__name")
        )
        tags_list = [t for t in tags if t]
        return Response({"data": tags_list})


class PendingApprovalsView(APIView):
    """GET /executions/pending-approvals (DBA/DBOPS only)"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_dba_or_dbops(request.user):
            raise ForbiddenError(code="FORBIDDEN", message="Accès interdit", details={})

        count_only = (request.query_params.get("count_only") or "").lower() == "true"
        qs = Execution.objects.select_related("action", "user", "action__integration").filter(
            status=ExecutionStatus.PENDING_APPROVAL
        ).order_by("-created_at")

        if count_only:
            return Response({"count": qs.count()})

        limit = _parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = _parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        total_count = qs.count()
        page = (offset // limit) + 1
        total_pages = (total_count + limit - 1) // limit if limit else 1

        items = list(qs[offset: offset + limit])
        data = ExecutionSerializer(items, many=True).data

        return Response(
            {
                "data": data,
                "pagination": {
                    "page": page,
                    "page_size": limit,
                    "total_count": total_count,
                    "total_pages": total_pages,
                },
            }
        )

