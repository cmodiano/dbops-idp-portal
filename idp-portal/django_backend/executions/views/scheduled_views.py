"""Vues des exécutions planifiées.

Responsabilité : Gestion complète des scheduled_executions.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

UTC = dt_timezone(timedelta(0))

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action, ActionStatus
from core.auth_utils import get_user_ad_groups
from core.exceptions import BadRequestError, NotFoundError, ForbiddenError, InvalidStateError
from core.pagination import paginate_queryset
from core.middleware import get_correlation_id
from core.utils import ensure_utc_isoformat
from executions.models import (
    ScheduledExecution,
    ScheduledExecutionStatus,
    RecurringPattern,
)
from executions.serializers import (
    ScheduledExecutionSerializer,
    ScheduledExecutionListItemSerializer,
    RecurringPatternSerializer,
)
from core.environment import EnvironmentHelper
from executions.services import SchedulingService
from executions.utils import (
    parse_int,
    parse_iso_datetime,
    get_allowed_action_ids_for_user,
    validate_environment_against_inventory,
    calculate_next_execution_date,
)
from inventory.services import InventoryService, InventoryServiceError, MAX_TARGETS_FOR_RBAC_FILTER

from croniter import croniter, CroniterBadCronError, CroniterBadDateError
from drf_spectacular.utils import extend_schema
import structlog

exec_logger = structlog.get_logger(__name__)


class ScheduledExecutionsView(APIView):
    """
    GET /scheduled-executions (Story 11.6)
    POST /scheduled-executions (Story 11.5, 11.7)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['scheduling'], summary='Lister les exécutions planifiées', responses={200: ScheduledExecutionListItemSerializer(many=True)})
    def get(self, request):
        limit = parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0 or limit > 100:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        status_filter = request.query_params.get("status")
        action_id = request.query_params.get("action_id")
        scheduled_from = parse_iso_datetime(request.query_params.get("scheduled_from"), name="scheduled_from")
        scheduled_to = parse_iso_datetime(request.query_params.get("scheduled_to"), name="scheduled_to")
        environment_filter = request.query_params.get("environment")
        engine_filter = request.query_params.get("engine")
        platform_filter = request.query_params.get("platform")

        qs = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern")
        if (getattr(request.user, "profile", "") or "").lower() != "dbops":
            allowed_action_ids = get_allowed_action_ids_for_user(request.user)
            if allowed_action_ids is not None:
                qs = qs.filter(action_id__in=allowed_action_ids)

        if status_filter:
            valid_statuses = {c[0] for c in ScheduledExecutionStatus.choices}
            if status_filter not in valid_statuses:
                raise InvalidStateError(
                    code="INVALID_STATUS",
                    message=f"Statut invalide: {status_filter}",
                    details={"status": status_filter, "valid_statuses": sorted(valid_statuses)},
                )
            qs = qs.filter(status=status_filter)

        if action_id:
            qs = qs.filter(action_id=parse_int(action_id, 0, name="action_id"))

        if environment_filter:
            validate_environment_against_inventory(environment_filter, user_id=request.user.id)
            qs = qs.filter(environment=EnvironmentHelper.normalize(environment_filter))

        if engine_filter:
            qs = qs.filter(action__engine__iexact=engine_filter)

        if platform_filter:
            qs = qs.filter(action__platform__iexact=platform_filter)

        if scheduled_from:
            qs = qs.filter(
                Q(scheduled_at__gte=scheduled_from) | Q(recurringpattern__next_execution_date__gte=scheduled_from)
            )
        if scheduled_to:
            qs = qs.filter(
                Q(scheduled_at__lte=scheduled_to) | Q(recurringpattern__next_execution_date__lte=scheduled_to)
            )

        qs = qs.order_by("-created_at")

        # AC2: Story 26.11 — Utilisation utilitaire pagination
        result = paginate_queryset(qs, offset=offset, limit=limit)
        data_items = ScheduledExecutionListItemSerializer(result["items"], many=True).data

        actions_qs = ScheduledExecution.objects.values("action_id", "action__name")
        if (getattr(request.user, "profile", "") or "").lower() != "dbops":
            actions_qs = actions_qs.filter(user_id=request.user.id)
        actions_qs = actions_qs.distinct().order_by("action__name")
        available_actions = [
            {"action_id": r["action_id"], "action_name": r["action__name"] or ""}
            for r in actions_qs
        ]

        # AC1: Story 26.9 — Format standardisé (pas d'imbrication data.data)
        return Response({
            "data": data_items,
            "pagination": result["pagination"],
            "available_actions": available_actions,
        })

    @extend_schema(tags=['scheduling'], summary='Créer une exécution planifiée', responses={201: ScheduledExecutionSerializer})
    def post(self, request):
        payload = request.data or {}

        action_id = payload.get("action_id")
        environment = payload.get("environment")
        parameters = payload.get("parameters")
        scheduled_at_raw = payload.get("scheduled_at")
        recurring_pattern = payload.get("recurring_pattern")

        if action_id is None or environment is None:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="action_id et environment sont requis",
                details={"action_id": action_id, "environment": environment},
            )

        validate_environment_against_inventory(environment, user_id=request.user.id)

        if scheduled_at_raw and recurring_pattern:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="scheduled_at et recurring_pattern sont mutuellement exclusifs",
                details={},
            )
        if not scheduled_at_raw and not recurring_pattern:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="scheduled_at ou recurring_pattern est requis",
                details={},
            )

        try:
            action = Action.objects.get(id=int(action_id), status=ActionStatus.PUBLISHED)
        except (ValueError, TypeError):
            raise BadRequestError(code="BAD_REQUEST", message="action_id invalide", details={"action_id": action_id})
        except Action.DoesNotExist:
            raise NotFoundError(code="ACTION_NOT_FOUND", message="Action non trouvée", details={"action_id": action_id})

        correlation_id = get_correlation_id()

        scheduled_at = parse_iso_datetime(scheduled_at_raw, name="scheduled_at") if scheduled_at_raw else None
        if scheduled_at and scheduled_at <= timezone.now().astimezone(UTC):
            raise BadRequestError(
                code="INVALID_SCHEDULED_DATE",
                message="scheduled_at doit être dans le futur",
                details={"scheduled_at": scheduled_at_raw},
            )

        recurring_pattern_data = None
        if recurring_pattern:
            pattern_type = (recurring_pattern.get("pattern_type") or "").lower()
            pattern_config = recurring_pattern.get("pattern_config") or {}
            next_execution_date = calculate_next_execution_date(pattern_type, pattern_config, timezone.now())
            recurring_pattern_data = {
                "pattern_type": pattern_type,
                "pattern_config": pattern_config,
                "next_execution_date": next_execution_date,
                "is_active": 1,
            }

        scheduled_execution = SchedulingService().create_scheduled_execution(
            user=request.user,
            action=action,
            environment=environment,
            parameters=parameters,
            scheduled_at=scheduled_at,
            recurring_pattern_data=recurring_pattern_data,
        )

        if correlation_id:
            scheduled_execution.correlation_id = correlation_id
            scheduled_execution.save(update_fields=["correlation_id"])

        scheduled_execution = ScheduledExecution.objects.select_related("action").select_related("recurringpattern").get(
            id=scheduled_execution.id
        )

        return Response({"data": ScheduledExecutionSerializer(scheduled_execution).data}, status=201)


class ScheduledExecutionUpdateView(APIView):
    """PATCH /scheduled-executions/{id} - cancel or mark executed."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['scheduling'], summary='Annuler ou marquer exécutée une scheduled execution', responses={200: ScheduledExecutionSerializer})
    def patch(self, request, scheduled_execution_id: int):
        try:
            se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
                id=scheduled_execution_id
            )
        except ScheduledExecution.DoesNotExist:
            raise NotFoundError(
                code="SCHEDULED_EXECUTION_NOT_FOUND",
                message="Exécution planifiée introuvable",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        if (getattr(request.user, "profile", "") or "").lower() != "dbops" and se.user_id != request.user.id:
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission de modifier cette exécution planifiée",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        body = request.data if isinstance(request.data, dict) else {}
        new_status = (body.get("status") or "cancelled").lower()
        execution_id = body.get("execution_id")

        if se.status != ScheduledExecutionStatus.PENDING:
            raise InvalidStateError(
                code="INVALID_STATUS",
                message="Seules les exécutions planifiées en attente peuvent être modifiées",
                details={"scheduled_execution_id": scheduled_execution_id, "status": se.status},
            )

        if new_status == "cancelled":
            se = SchedulingService().cancel_scheduled_execution(scheduled_execution_id, user_id=str(request.user.id))
            if se is None:
                raise NotFoundError(
                    code="SCHEDULED_EXECUTION_NOT_FOUND",
                    message="Exécution planifiée introuvable",
                    details={"scheduled_execution_id": scheduled_execution_id},
                )
            # AC2: Story 26.9 — Use ScheduledExecutionSerializer for consistency
            se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
                id=scheduled_execution_id
            )
            return Response({"data": ScheduledExecutionSerializer(se).data})

        if new_status == "executed":
            if execution_id is None:
                raise BadRequestError(
                    code="VALIDATION_ERROR",
                    message="execution_id est requis quand status=executed",
                    details={"scheduled_execution_id": scheduled_execution_id},
                )
            try:
                execution_id_int = int(execution_id)
            except (ValueError, TypeError):
                raise BadRequestError(code="BAD_REQUEST", message="execution_id invalide", details={"execution_id": execution_id})

            with transaction.atomic():
                rp = getattr(se, "recurringpattern", None)
                if rp is not None and bool(rp.is_active):
                    rp.next_execution_date = calculate_next_execution_date(
                        rp.pattern_type, rp.get_pattern_config() or {}, timezone.now()
                    )
                    rp.updated_at = timezone.now()
                    rp.save(update_fields=["next_execution_date", "updated_at"])
                    se.status = ScheduledExecutionStatus.PENDING
                else:
                    se.status = ScheduledExecutionStatus.EXECUTED

                se.execution_id = execution_id_int
                se.updated_at = timezone.now()
                se.save(update_fields=["status", "execution_id", "updated_at"])
            # AC2: Story 26.9 — Use ScheduledExecutionSerializer for consistency
            se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
                id=scheduled_execution_id
            )
            return Response({"data": ScheduledExecutionSerializer(se).data})

        raise BadRequestError(code="INVALID_STATUS", message="Statut invalide", details={"status": new_status})

    def put(self, request, scheduled_execution_id: int):
        """PUT /scheduled-executions/{id} - update pending scheduled execution (Story 13.8, AC4)."""
        try:
            se = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern").get(
                id=scheduled_execution_id
            )
        except ScheduledExecution.DoesNotExist:
            raise NotFoundError(
                code="SCHEDULED_EXECUTION_NOT_FOUND",
                message="Exécution planifiée introuvable",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        if (getattr(request.user, "profile", "") or "").lower() != "dbops" and se.user_id != request.user.id:
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission de modifier cette exécution planifiée",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        if se.status != ScheduledExecutionStatus.PENDING:
            raise InvalidStateError(
                code="INVALID_STATUS",
                message="Seules les exécutions planifiées en attente peuvent être modifiées",
                details={"scheduled_execution_id": scheduled_execution_id, "status": se.status},
            )

        body = request.data if isinstance(request.data, dict) else {}
        action = se.action
        if not action:
            raise NotFoundError(
                code="ACTION_NOT_FOUND",
                message="Action introuvable",
                details={"action_id": se.action_id},
            )

        scheduled_at_raw = body.get("scheduled_at")
        parameters = body.get("parameters")
        environment = body.get("environment")
        target_names = body.get("target_names")
        recurring_pattern_payload = body.get("recurring_pattern")
        now = timezone.now()
        se.updated_at = now

        rp = getattr(se, "recurringpattern", None)
        if scheduled_at_raw is not None and rp is None:
            scheduled_at = parse_iso_datetime(scheduled_at_raw, name="scheduled_at")
            if scheduled_at is not None and scheduled_at <= timezone.now().astimezone(UTC):
                raise BadRequestError(
                    code="INVALID_SCHEDULED_DATE",
                    message="scheduled_at doit être dans le futur",
                    details={"scheduled_at": scheduled_at_raw},
                )
            se.scheduled_at = scheduled_at

        if environment is not None:
            validate_environment_against_inventory(environment, user_id=request.user.id)
            se.environment = EnvironmentHelper.normalize(environment)

        if target_names is not None:
            if not isinstance(target_names, list):
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="target_names doit être une liste",
                    details={"target_names": target_names},
                )
            if len(target_names) == 0:
                current_params = se.get_parameters() or {}
                if not isinstance(current_params, dict):
                    current_params = {}
                new_params = {k: v for k, v in current_params.items() if k != "_targets"}
                new_params["_targets"] = []
                se.set_parameters(new_params)
                if environment is not None:
                    validate_environment_against_inventory(environment, user_id=request.user.id)
                    se.environment = EnvironmentHelper.normalize(environment)
            else:
                ad_groups = get_user_ad_groups(request.user)
                inventory_service = InventoryService()
                try:
                    allowed_targets, _total, inventory_truncated = inventory_service.list_targets_for_user(
                        user_id=request.user.id,
                        ad_groups=ad_groups,
                        page=1,
                        page_size=MAX_TARGETS_FOR_RBAC_FILTER,
                    )
                except InventoryServiceError as e:
                    exec_logger.error(
                        "inventory_service_error_during_scheduled_update",
                        error=str(e),
                        user_id=request.user.id,
                    )
                    raise BadRequestError(
                        code="INVENTORY_UNAVAILABLE",
                        message="Service inventaire indisponible",
                        details={"error": str(e)},
                    )
                allowed_targets_map = {t["name"]: t for t in allowed_targets}
                environments_found = set()
                for name in target_names:
                    if name not in allowed_targets_map:
                        raise ForbiddenError(
                            code="FORBIDDEN",
                            message=f"Cible non autorisée: {name}",
                            details={"target_name": name, "inventory_truncated": inventory_truncated},
                        )
                    environments_found.add(allowed_targets_map[name]["environment"])
                if len(environments_found) > 1:
                    raise BadRequestError(
                        code="MIXED_ENVIRONMENTS",
                        message="Les cibles doivent appartenir au même environnement",
                        details={"environments": list(environments_found)},
                    )
                se.environment = EnvironmentHelper.normalize(list(environments_found)[0])
                current_params = se.get_parameters() or {}
                if not isinstance(current_params, dict):
                    current_params = {}
                new_params = {**current_params, "_targets": target_names}
                se.set_parameters(new_params)
        elif parameters is not None:
            current_params = se.get_parameters() or {}
            if not isinstance(current_params, dict):
                current_params = {}
            incoming = parameters if isinstance(parameters, dict) else {}
            sanitized = {k: v for k, v in incoming.items() if not k.startswith("_")}
            merged = {**current_params, **sanitized}
            se.set_parameters(merged)

        if recurring_pattern_payload is not None and rp is not None:
            pattern_type = (recurring_pattern_payload.get("pattern_type") or "").lower()
            pattern_config = recurring_pattern_payload.get("pattern_config") or {}
            next_execution_date = calculate_next_execution_date(
                pattern_type, pattern_config, timezone.now()
            )
            rp.pattern_type = pattern_type
            rp.set_pattern_config(pattern_config)
            rp.next_execution_date = next_execution_date
            rp.updated_at = now
            rp.save(update_fields=["pattern_type", "pattern_config", "next_execution_date", "updated_at"])

        update_fields = ["updated_at"]
        if scheduled_at_raw is not None and rp is None:
            update_fields.append("scheduled_at")
        if environment is not None or target_names is not None:
            update_fields.extend(["environment", "parameters"])
        elif parameters is not None:
            update_fields.append("parameters")
        se.save(update_fields=list(dict.fromkeys(update_fields)))

        se = ScheduledExecution.objects.select_related("action").select_related("recurringpattern").get(
            id=scheduled_execution_id
        )
        return Response({"data": ScheduledExecutionSerializer(se).data})


class ScheduledExecutionRecurringPatternView(APIView):
    """PATCH /scheduled-executions/{id}/recurring-pattern - toggle is_active."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, scheduled_execution_id: int):
        try:
            se = ScheduledExecution.objects.select_related("user").select_related("recurringpattern").get(
                id=scheduled_execution_id
            )
        except ScheduledExecution.DoesNotExist:
            raise NotFoundError(
                code="SCHEDULED_EXECUTION_NOT_FOUND",
                message="Exécution planifiée introuvable",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        if (getattr(request.user, "profile", "") or "").lower() != "dbops" and se.user_id != request.user.id:
            raise ForbiddenError(
                code="PERMISSION_DENIED",
                message="Vous n'avez pas la permission de modifier cette récurrence",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        rp = getattr(se, "recurringpattern", None)
        if rp is None:
            raise NotFoundError(
                code="RECURRING_PATTERN_NOT_FOUND",
                message="Cette exécution planifiée n'a pas de pattern de récurrence",
                details={"scheduled_execution_id": scheduled_execution_id},
            )

        body = request.data if isinstance(request.data, dict) else {}
        if "is_active" not in body:
            raise BadRequestError(code="BAD_REQUEST", message="is_active est requis", details={})

        is_active = bool(body.get("is_active"))
        rp.is_active = 1 if is_active else 0

        if is_active:
            rp.next_execution_date = calculate_next_execution_date(
                rp.pattern_type, rp.get_pattern_config() or {}, timezone.now()
            )

        rp.updated_at = timezone.now()
        rp.save(update_fields=["is_active", "next_execution_date", "updated_at"])

        return Response({"data": RecurringPatternSerializer(rp).data})


class ScheduledExecutionValidateCronView(APIView):
    """GET /scheduled-executions/validate-cron"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        expr = (request.query_params.get("expression") or "").strip()
        if not expr:
            raise BadRequestError(code="BAD_REQUEST", message="expression est requise", details={})

        try:
            if not croniter.is_valid(expr):
                return Response(
                    {
                        "data": {
                            "valid": False,
                            "error": "Expression cron invalide. Format attendu : minute hour day month day_of_week",
                        }
                    }
                )
            it = croniter(expr, datetime.now(UTC))
            _ = it.get_next(datetime)
            return Response({"data": {"valid": True, "error": ""}})
        except (CroniterBadCronError, CroniterBadDateError, ValueError) as e:
            exec_logger.debug(
                "cron_expression_validation_failed",
                expression=expr,
                error=str(e),
                correlation_id=get_correlation_id(),
            )
            return Response({"data": {"valid": False, "error": f"Expression cron invalide : {str(e)}"}})


class ScheduledExecutionCronNextExecutionsView(APIView):
    """GET /scheduled-executions/cron-next-executions"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        expr = (request.query_params.get("expression") or "").strip()
        count = parse_int(request.query_params.get("count"), 5, name="count")
        if count < 1 or count > 10:
            raise BadRequestError(code="BAD_REQUEST", message="count invalide (1-10)", details={"count": count})

        if not expr or not croniter.is_valid(expr):
            raise BadRequestError(
                code="INVALID_CRON_EXPRESSION",
                message="Expression cron invalide. Format attendu : minute hour day month day_of_week",
                details={"expression": expr},
            )

        it = croniter(expr, datetime.now(UTC))
        executions = []
        for _ in range(count):
            nxt = it.get_next(datetime)
            executions.append(ensure_utc_isoformat(nxt))

        return Response({"data": {"executions": executions}})
