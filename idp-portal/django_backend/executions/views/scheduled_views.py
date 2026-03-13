"""Vues des exécutions planifiées.

Responsabilité : Gestion complète des scheduled_executions.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from functools import reduce
from operator import or_

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import BadRequestError, NotFoundError, ForbiddenError, InvalidStateError
from executions.validators.payload_validator import ExecutionPayloadValidator
from core.pagination import paginate_queryset
from core.middleware import get_correlation_id
from core.utils import ensure_utc_isoformat
from executions.models import (
    ScheduledExecution,
    ScheduledExecutionStatus,
)
from executions.serializers import (
    ScheduledExecutionSerializer,
    ScheduledExecutionListItemSerializer,
    RecurringPatternSerializer,
)
from core.environment import EnvironmentHelper
from core.permissions import IsAdminUser, is_admin_user
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from executions.scheduling_service import SchedulingService
from executions.utils import (
    parse_int,
    parse_iso_datetime,
    get_allowed_action_ids_for_user,
    validate_environment_against_inventory,
    calculate_next_execution_date,
)

from croniter import croniter, CroniterBadCronError, CroniterBadDateError
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
import structlog

UTC = dt_timezone(timedelta(0))

exec_logger = structlog.get_logger(__name__)

# AC2: Story 26.12 — Instance shared across views for owner-or-admin object-level checks
_dba_permission = IsAdminUser()


class ScheduledExecutionsView(APIView):
    """
    GET /scheduled-executions (Story 11.6)
    POST /scheduled-executions (Story 11.5, 11.7)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['scheduling'],
        summary='Lister les exécutions planifiées',
        parameters=[
            OpenApiParameter('limit', int, description='Résultats par page (défaut: 50, max: 100)'),
            OpenApiParameter('offset', int, description='Décalage pagination'),
            OpenApiParameter('status', str, description='Filtre par statut'),
            OpenApiParameter('action_id', int, description='Filtre par action'),
            OpenApiParameter('scheduled_from', str, description='Date/heure début (ISO 8601)'),
            OpenApiParameter('scheduled_to', str, description='Date/heure fin (ISO 8601)'),
            OpenApiParameter('environment', str, description='Filtre par environnement'),
            OpenApiParameter('engine', str, description='Filtre par technologie'),
            OpenApiParameter('platform', str, description='Filtre par plateforme'),
        ],
        responses={200: ScheduledExecutionListItemSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
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

        # Story 57.17: source_execution_id est un champ DB direct sur ScheduledExecution
        qs = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern")
        # Story 26.12 — View-level permission: admins see all, non-admins see only allowed actions
        # Note: This uses has_permission() (view-level), not has_object_permission() (object-level)
        if not _dba_permission.has_permission(request, self):
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
            env_values = EnvironmentHelper.values_for_filter(environment_filter)
            if env_values:
                qs = qs.filter(reduce(or_, [Q(environment__iexact=v) for v in env_values]))

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
        # Story 26.12 — View-level permission: admins see all actions, non-admins see only their own
        if not _dba_permission.has_permission(request, self):
            actions_qs = actions_qs.filter(user_id=request.user.id)  # type: ignore[misc]
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

    @extend_schema(
        tags=['scheduling'],
        summary='Créer une exécution planifiée',
        request=inline_serializer(
            name='ScheduledExecutionCreateRequest',
            fields={
                'action_id': serializers.IntegerField(help_text='ID de l\'action'),
                'environment': serializers.CharField(help_text='Environnement cible'),
                'parameters': serializers.DictField(required=False, help_text='Paramètres d\'exécution'),
                'scheduled_at': serializers.DateTimeField(help_text='Date/heure planifiée (ISO 8601)'),
                'recurring_pattern': serializers.DictField(
                    required=False,
                    help_text='Pattern récurrent: {pattern_type, pattern_config}',
                ),
            },
        ),
        responses={201: ScheduledExecutionSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = request.data or {}

        action_id = payload.get("action_id")
        environment = payload.get("environment")
        parameters = payload.get("parameters")
        scheduled_at_raw = payload.get("scheduled_at")
        recurring_pattern = payload.get("recurring_pattern")

        # Story 11.11 AC2/AC3: Recurring patterns are restricted to admin users
        if recurring_pattern and not is_admin_user(request.user):
            raise ForbiddenError(
                code="ADMIN_REQUIRED",
                message="Les exécutions récurrentes sont réservées aux administrateurs",
                details={},
            )

        if environment is None:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="environment est requis",
                details={"action_id": action_id, "environment": environment},
            )

        # Story 71.5: Reuse shared action validation (eliminates duplicated action fetch)
        action = ExecutionPayloadValidator.validate_action(action_id)

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
            user=request.user,  # type: ignore[arg-type]
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

    @extend_schema(
        tags=['scheduling'],
        summary='Annuler ou marquer exécutée une scheduled execution',
        request=inline_serializer(
            name='ScheduledExecutionPatchRequest',
            fields={
                'status': serializers.ChoiceField(
                    choices=['cancelled', 'executed'],
                    required=False,
                    default='cancelled',
                    help_text='cancelled ou executed',
                ),
                'execution_id': serializers.IntegerField(
                    required=False,
                    help_text='Requis si status=executed',
                ),
            },
        ),
        responses={200: ScheduledExecutionSerializer},
    )
    def patch(self, request: Request, scheduled_execution_id: int) -> Response:
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

        # Story 26.12 — Object-level permission: owner OR admin can modify
        if not _dba_permission.has_object_permission(request, self, se):
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
            se = SchedulingService().cancel_scheduled_execution(scheduled_execution_id, user_id=str(request.user.id))  # type: ignore[assignment]
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
                if rp is not None and rp.is_active == 1:
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

    @extend_schema(
        tags=['scheduling'],
        summary='Modifier la date d\'une exécution planifiée (PUT) — Story 11.11',
        description='Seule la date est modifiable : scheduled_at (one-time) ou next_execution_date (récurrent).',
        request=inline_serializer(
            name='ScheduledExecutionPutRequest',
            fields={
                'scheduled_at': serializers.DateTimeField(
                    required=False,
                    help_text='Date/heure planifiée (ISO 8601) — one-time uniquement',
                ),
                'next_execution_date': serializers.DateTimeField(
                    required=False,
                    help_text='Prochaine date d\'exécution (ISO 8601) — récurrent uniquement',
                ),
            },
        ),
        responses={200: ScheduledExecutionSerializer},
    )
    def put(self, request: Request, scheduled_execution_id: int) -> Response:
        """PUT /scheduled-executions/{id} - update pending scheduled execution date only (Story 11.11, AC1)."""
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

        # Story 26.12 — Object-level permission: owner OR admin can modify
        if not _dba_permission.has_object_permission(request, self, se):
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

        # Story 11.11 AC1: Only date fields are modifiable — reject forbidden fields
        FORBIDDEN_FIELDS = {'environment', 'target_names', 'parameters', 'recurring_pattern'}
        forbidden_present = FORBIDDEN_FIELDS & set(body.keys())
        if forbidden_present:
            raise BadRequestError(
                code="FIELD_NOT_MODIFIABLE",
                message="Seule la date peut être modifiée (scheduled_at pour one-time, next_execution_date pour récurrent)",
                details={"forbidden_fields": sorted(forbidden_present)},
            )

        rp = getattr(se, "recurringpattern", None)
        now = timezone.now()
        se.updated_at = now
        update_fields = ["updated_at"]

        if rp is None:
            # One-time: reject next_execution_date (wrong field for this type)
            if "next_execution_date" in body:
                raise BadRequestError(
                    code="FIELD_NOT_APPLICABLE",
                    message="next_execution_date n'est pas applicable pour une exécution one-time. Utilisez scheduled_at.",
                    details={},
                )
            # One-time: update scheduled_at
            scheduled_at_raw = body.get("scheduled_at")
            if scheduled_at_raw is not None:
                scheduled_at = parse_iso_datetime(scheduled_at_raw, name="scheduled_at")
                if scheduled_at is not None and scheduled_at <= timezone.now().astimezone(UTC):
                    raise BadRequestError(
                        code="INVALID_SCHEDULED_DATE",
                        message="scheduled_at doit être dans le futur",
                        details={"scheduled_at": scheduled_at_raw},
                    )
                se.scheduled_at = scheduled_at
                update_fields.append("scheduled_at")
        else:
            # Recurring: reject scheduled_at (wrong field for this type)
            if "scheduled_at" in body:
                raise BadRequestError(
                    code="FIELD_NOT_APPLICABLE",
                    message="scheduled_at n'est pas applicable pour une exécution récurrente. Utilisez next_execution_date.",
                    details={},
                )
            # Recurring: update next_execution_date
            next_exec_raw = body.get("next_execution_date")
            if next_exec_raw is not None:
                next_exec = parse_iso_datetime(next_exec_raw, name="next_execution_date")
                if next_exec is not None and next_exec <= timezone.now().astimezone(UTC):
                    raise BadRequestError(
                        code="INVALID_SCHEDULED_DATE",
                        message="next_execution_date doit être dans le futur",
                        details={"next_execution_date": next_exec_raw},
                    )
                rp.next_execution_date = next_exec
                rp.updated_at = now
                rp.save(update_fields=["next_execution_date", "updated_at"])

        se.save(update_fields=list(dict.fromkeys(update_fields)))

        se = ScheduledExecution.objects.select_related("action").select_related("recurringpattern").get(
            id=scheduled_execution_id
        )
        return Response({"data": ScheduledExecutionSerializer(se).data})


class ScheduledExecutionRecurringPatternView(APIView):
    """PATCH /scheduled-executions/{id}/recurring-pattern - toggle is_active."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['scheduling'],
        summary='Activer/désactiver le pattern récurrent',
        request=inline_serializer(
            name='RecurringPatternPatchRequest',
            fields={
                'is_active': serializers.BooleanField(
                    help_text='Activer (true) ou désactiver (false) le pattern',
                ),
            },
        ),
        responses={200: RecurringPatternSerializer},
    )
    def patch(self, request: Request, scheduled_execution_id: int) -> Response:
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

        # AC2: Story 26.12 — owner-or-admin check via IsAdminUser permission
        if not _dba_permission.has_object_permission(request, self, se):
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

        # AC: audit trail sur toggle is_active (story 66-16 finding HIGH — SCHED-BE-002)
        # story 66-16 review: CREATED est réservé à l'INSERT d'un nouveau pattern ;
        # ENABLED est le type sémantiquement correct pour la réactivation d'un pattern existant
        action_type = (
            AuditActionType.SCHEDULED_EXECUTION_RECURRING_DISABLED
            if not is_active
            else AuditActionType.SCHEDULED_EXECUTION_RECURRING_ENABLED
        )
        # story 66-16 code-review fix NEW-HIGH-01: entity_type SCHEDULED_EXECUTION (pas EXECUTION)
        # se est un ScheduledExecution — utiliser EXECUTION ici cassait list_by_entity('scheduled_execution', ...)
        AuditService.create_entry(
            user_id=str(request.user.id),
            action_type=action_type,
            entity_type=AuditEntityType.SCHEDULED_EXECUTION,
            entity_id=se.id,
            details={
                'recurring_pattern_id': rp.id,
                'is_active': is_active,
                'next_execution_date': ensure_utc_isoformat(rp.next_execution_date),
            },
            correlation_id=get_correlation_id(),
        )

        return Response({"data": RecurringPatternSerializer(rp).data})


class ScheduledExecutionValidateCronView(APIView):
    """GET /scheduled-executions/validate-cron"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['scheduling'],
        summary='Valider une expression cron',
        parameters=[OpenApiParameter('expression', str, description='Expression cron (minute hour day month day_of_week)')],
    )
    def get(self, request: Request) -> Response:
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

    @extend_schema(
        tags=['scheduling'],
        summary='Prochaines dates d\'exécution pour une expression cron',
        parameters=[
            OpenApiParameter('expression', str, description='Expression cron'),
            OpenApiParameter('count', int, description='Nombre de dates à retourner (1-10, défaut: 5)'),
        ],
    )
    def get(self, request: Request) -> Response:
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
