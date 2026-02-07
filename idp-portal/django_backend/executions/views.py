from __future__ import annotations

from datetime import datetime, timedelta, date, timezone

# Fixed-offset UTC (no name): Oracle Thin Mode does not support named timezones (DPY-3022)
UTC = timezone(timedelta(0))

from django.db import transaction
from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Action, ActionStatus
from core.auth_utils import get_user_ad_groups
from core.exceptions import BadRequestError, NotFoundError, ForbiddenError, InvalidStateError
from core.middleware import get_correlation_id, get_client_ip
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from executions.models import (
    Execution,
    ExecutionStep,
    ExecutionStatus,
    ScheduledExecution,
    ScheduledExecutionStatus,
    RecurringPattern,
)
from executions.serializers import (
    ExecutionSerializer,
    ExecutionStepSerializer,
    ScheduledExecutionSerializer,
    ScheduledExecutionListItemSerializer,
    RecurringPatternSerializer,
)
from executions.services import ExecutionService, SchedulingService
from inventory.services import InventoryService, InventoryServiceError, MAX_TARGETS_FOR_RBAC_FILTER
from profiles.services import ProfileService
from core.throttling import ExecutionThrottle, GeneralAPIThrottle
from utils.json_helpers import validate_json_schema

try:
    import jsonschema  # type: ignore
    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    JSONSCHEMA_AVAILABLE = False


def _validate_environment_against_inventory(environment: str) -> None:
    """
    Validate environment against inventory (Story 13.7, AC2).
    Raises BadRequestError if environment is not in inventory.
    """
    if not environment:
        return
    
    try:
        inventory_service = InventoryService()
        valid_environments = inventory_service.list_environments()
        
        if environment.lower() not in [e.lower() for e in valid_environments]:
            raise BadRequestError(
                code="INVALID_ENVIRONMENT",
                message=f"Environnement invalide: {environment}",
                details={
                    "environment": environment,
                    "valid_environments": sorted(valid_environments)
                },
            )
    except InventoryServiceError as e:
        # If inventory service fails, log warning but don't block execution
        # (fallback behavior - allow execution with warning)
        exec_logger.warning(
            "inventory_validation_failed",
            environment=environment,
            error=str(e),
            correlation_id=get_correlation_id(),
            message="Failed to validate environment against inventory - allowing execution with warning"
        )

from croniter import croniter, CroniterBadCronError, CroniterBadDateError
import structlog

exec_logger = structlog.get_logger(__name__)


def _extract_workflow_referenced_action_ids(workflow_action: Action) -> list[int]:
    """
    Extract referenced_action_id list from a workflow's execution_steps.

    Expected format (Story 5.7 / 4.11):
        [
          {"order": 1, "name": "...", "referenced_action_id": 5},
          ...
        ]
    Returns IDs in step order, skipping invalid/missing entries.
    """
    steps = workflow_action.execution_steps or []
    if not isinstance(steps, list):
        return []

    # Ensure deterministic ordering: use 'order' if present, else keep input order
    def _order_key(step: object, idx: int) -> int:
        if isinstance(step, dict):
            try:
                return int(step.get("order", idx))
            except (ValueError, TypeError):
                return idx
        return idx

    sorted_steps = sorted(list(enumerate(steps)), key=lambda t: _order_key(t[1], t[0]))
    ids: list[int] = []
    for idx, step in sorted_steps:
        if not isinstance(step, dict):
            continue
        if "referenced_action_id" not in step:
            continue
        try:
            ids.append(int(step["referenced_action_id"]))
        except (ValueError, TypeError):
            exec_logger.warning(
                "invalid_referenced_action_id_in_workflow_steps",
                workflow_action_id=workflow_action.id,
                referenced_action_id=step.get("referenced_action_id"),
                step_index=idx,
                correlation_id=get_correlation_id(),
            )
            continue
    return ids


def _extract_workflow_step_map(workflow_action: Action) -> dict[int, int]:
    """
    Build mapping step_order -> referenced_action_id for a workflow.
    """
    steps = workflow_action.execution_steps or []
    if not isinstance(steps, list):
        return {}
    out: dict[int, int] = {}
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        try:
            order = int(step.get("order", idx + 1))
            ref_id = int(step["referenced_action_id"])
        except (KeyError, TypeError, ValueError):
            continue
        out[order] = ref_id
    return out


def _validate_workflow_step_parameters(
    *,
    workflow_action: Action,
    workflow_step_parameters: object,
) -> dict:
    """
    Story 4.12 (AC4):
      - Reject unknown step_order keys
      - Validate each step parameters against referenced action parameters_schema
    Returns normalized dict suitable for storage (keys as strings).
    """
    if workflow_step_parameters is None:
        return {}
    if not isinstance(workflow_step_parameters, dict):
        raise BadRequestError(
            code="INVALID_WORKFLOW_STEP_PARAMETERS",
            message="workflow_step_parameters doit être un objet",
            details={"workflow_step_parameters": workflow_step_parameters},
        )

    step_map = _extract_workflow_step_map(workflow_action)
    valid_orders = sorted(step_map.keys())

    invalid_orders: list[str] = []
    normalized: dict[str, dict] = {}
    for key, value in workflow_step_parameters.items():
        # Keys are expected to be strings in API contract
        try:
            order_int = int(key)
        except (TypeError, ValueError):
            invalid_orders.append(str(key))
            continue

        if order_int not in step_map:
            invalid_orders.append(str(key))
            continue

        entry = value if isinstance(value, dict) else {}
        params = entry.get("parameters") if isinstance(entry, dict) else None
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise BadRequestError(
                code="INVALID_PARAMETERS",
                message="Paramètres invalides (doivent être un objet)",
                details={"step_order": order_int, "field": "parameters"},
            )

        # Validate against referenced action schema (if any)
        ref_action_id = step_map[order_int]
        try:
            ref_action = Action.objects.get(id=int(ref_action_id))
        except Action.DoesNotExist:
            # Should be prevented by Story 4.11 delegation validation, but keep defensive.
            raise NotFoundError(
                code="REFERENCED_ACTION_NOT_FOUND",
                message="Action référencée introuvable",
                details={"step_order": order_int, "referenced_action_id": ref_action_id},
            )

        schema = ref_action.parameters_schema or {}
        if not schema:
            # No schema: accept only empty params
            if params:
                raise BadRequestError(
                    code="INVALID_PARAMETERS",
                    message="Cette étape n'accepte pas de paramètres",
                    details={"step_order": order_int},
                )
            normalized[str(order_int)] = {"parameters": {}}
            continue

        if JSONSCHEMA_AVAILABLE:
            try:
                jsonschema.validate(instance=params, schema=schema)  # type: ignore[attr-defined]
            except jsonschema.ValidationError as e:  # type: ignore[attr-defined]
                field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
                raise BadRequestError(
                    code="INVALID_PARAMETERS",
                    message=f"Paramètres invalides (étape {order_int}): {e.message}",
                    details={"step_order": order_int, "field": field_path, "error": e.message},
                ) from e
            except jsonschema.SchemaError as e:  # type: ignore[attr-defined]
                raise BadRequestError(
                    code="INVALID_SCHEMA",
                    message="Schema de paramètres invalide pour une action référencée",
                    details={"step_order": order_int, "referenced_action_id": ref_action_id, "error": str(e)},
                ) from e
        else:
            ok, err = validate_json_schema(params, schema)
            if not ok:
                raise BadRequestError(
                    code="INVALID_PARAMETERS",
                    message=f"Paramètres invalides (étape {order_int}): {err}",
                    details={"step_order": order_int, "error": err},
                )

        normalized[str(order_int)] = {"parameters": params}

    if invalid_orders:
        raise BadRequestError(
            code="INVALID_WORKFLOW_STEP_ORDER",
            message="workflow_step_parameters contient des step_order inconnus",
            details={"invalid_step_orders": sorted(invalid_orders), "valid_step_orders": valid_orders},
        )

    return normalized


def _validate_workflow_referenced_actions(
    *,
    workflow_action: Action,
    correlation_id: str | None,
    user_id: int,
    ip_address: str | None,
) -> list[int]:
    """
    Story 4.11:
    - Validate referenced actions EXIST and are PUBLISHED.
    - Do NOT perform per-action RBAC checks (delegation).
    - Validation must happen BEFORE creating an execution (no partial execution).

    Returns the ordered list of referenced_action_ids.
    Raises:
      - NotFoundError if any referenced action is missing
      - BadRequestError if any referenced action is not published
    """
    referenced_action_ids = _extract_workflow_referenced_action_ids(workflow_action)

    # MEDIUM: Reject workflow with no referenced actions (Story 4.11 edge case)
    if not referenced_action_ids:
        raise BadRequestError(
            code="WORKFLOW_EMPTY",
            message="Le workflow ne contient aucune action référencée",
            details={
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
            },
        )

    missing_ids: list[int] = []
    not_published: list[dict] = []

    for ref_id in referenced_action_ids:
        try:
            ref_action = Action.objects.get(id=int(ref_id))
        except Action.DoesNotExist:
            missing_ids.append(int(ref_id))
            continue

        if ref_action.status != ActionStatus.PUBLISHED:
            not_published.append(
                {
                    "referenced_action_id": int(ref_id),
                    "action_name": ref_action.name,
                    "status": ref_action.status,
                }
            )

    if missing_ids:
        # Audit attempt (no execution created yet)
        AuditService.create_entry(
            user_id=str(user_id),
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=0,
            details={
                "delegated": True,
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "referenced_action_ids": referenced_action_ids,
                "validation_result": "failed",
                "reason": "missing_referenced_action",
                "missing_referenced_action_ids": missing_ids,
            },
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        # AC4: list all missing actions in message
        if len(missing_ids) == 1:
            message = f"L'action référencée '{missing_ids[0]}' n'existe plus ou n'est plus disponible"
        else:
            ids_str = "', '".join(str(i) for i in missing_ids)
            message = f"Les actions référencées suivantes n'existent plus : '{ids_str}'"
        raise NotFoundError(
            code="REFERENCED_ACTION_NOT_FOUND",
            message=message,
            details={
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "referenced_action_id": missing_ids[0],
                "missing_referenced_action_ids": missing_ids,
            },
        )

    if not_published:
        AuditService.create_entry(
            user_id=str(user_id),
            action_type=AuditActionType.EXECUTION_SUBMITTED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=0,
            details={
                "delegated": True,
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "referenced_action_ids": referenced_action_ids,
                "validation_result": "failed",
                "reason": "referenced_action_not_published",
                "not_published": not_published,
            },
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        first = not_published[0]
        # AC4: list all not-published actions in message
        if len(not_published) == 1:
            message = f"L'action référencée '{first['action_name']}' n'est plus publiée (statut: {first['status']})"
        else:
            parts = [f"'{p['action_name']}' (statut: {p['status']})" for p in not_published]
            message = f"Les actions référencées suivantes ne sont plus publiées : {', '.join(parts)}"
        raise BadRequestError(
            code="REFERENCED_ACTION_NOT_PUBLISHED",
            message=message,
            details={
                "workflow_action_id": workflow_action.id,
                "workflow_action_name": workflow_action.name,
                "referenced_action_id": first["referenced_action_id"],
                "action_name": first["action_name"],
                "status": first["status"],
                "not_published": not_published,
            },
        )

    return referenced_action_ids


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


def _get_allowed_action_ids_for_user(user) -> set[int] | None:
    """
    Get action IDs the user has access to based on their profile permissions.

    Story 13.6: DBA sees scheduled executions for actions their profile gives access to.

    Returns:
        Set of action IDs, or None if user has 'all' access (no filtering needed).
    """
    if not user or not user.is_authenticated:
        return set()

    ad_groups = get_user_ad_groups(user)
    try:
        profile_service = ProfileService()
        permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)
    except Exception as e:
        # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
        exec_logger.warning(
            "profile_service_unavailable_access_denied",
            user_id=user.id,
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=get_correlation_id(),
            exc_info=True,
        )
        return set()

    if not permissions or not permissions.get('action_permissions'):
        return set()

    # Aggregate action permissions (union across profiles)
    action_ids = set()
    tag_patterns = set()

    for perm in permissions.get('action_permissions', []):
        if perm.get('actions_type') == 'all':
            # User has full access - no filtering needed
            return None
        action_ids.update(perm.get('action_ids', []) or [])
        tag_patterns.update(perm.get('tag_patterns', []) or [])

    # If there are tag patterns, we need to resolve them to action IDs
    if tag_patterns:
        from catalog.models import ActionTag
        tag_action_ids = ActionTag.objects.filter(
            tag__name__in=tag_patterns,
            action__status=ActionStatus.PUBLISHED
        ).values_list('action_id', flat=True)
        action_ids.update(tag_action_ids)

    return action_ids


def _detect_request_source(request) -> str:
    """
    Detect if request comes from UI (frontend) or API (standalone).

    Story 13.5, Subtask 3.2: Distinguish UI vs API requests for audit.

    Heuristics:
    - If Authorization: Bearer is present → "api" (API clients always send it)
    - Else if X-Requested-With: XMLHttpRequest → "ui"
    - Else if Referer or Origin present → "ui" (browser navigation)
    - Otherwise → "api"
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.strip().upper().startswith('BEARER '):
        return 'api'

    x_requested_with = request.META.get('HTTP_X_REQUESTED_WITH', '')
    if x_requested_with.lower() == 'xmlhttprequest':
        return 'ui'

    referer = request.META.get('HTTP_REFERER', '')
    origin = request.META.get('HTTP_ORIGIN', '')
    if referer or origin:
        return 'ui'

    return 'api'


def _apply_scope_filter(qs, *, user, scope: str) -> tuple[object, str]:
    """
    Return (qs, effective_scope):
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
    throttle_classes = [GeneralAPIThrottle, ExecutionThrottle]

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
        """
        Create a new execution.
        Story 13.2: Supports target_names parameter for target-based execution.
        Story 13.4: target_names is REQUIRED for actions with requires_target=True.
                   environment is ALWAYS derived from target(s), never passed directly.
        """
        payload = request.data or {}
        action_id = payload.get("action_id")
        environment = payload.get("environment")
        target_names = payload.get("target_names")
        parameters = payload.get("parameters") or {}
        workflow_step_parameters = payload.get("workflow_step_parameters")
        parent_execution_id = payload.get("parent_execution_id")

        correlation_id = request.META.get("HTTP_X_IDP_REQUEST_ID") or get_correlation_id()

        if not action_id:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="action_id est requis",
                details={"action_id": action_id},
            )

        try:
            action = Action.objects.get(id=int(action_id), status="published")
        except (ValueError, TypeError):
            raise BadRequestError(code="BAD_REQUEST", message="action_id invalide", details={"action_id": action_id})
        except Action.DoesNotExist:
            raise NotFoundError(code="ACTION_NOT_FOUND", message="Action non trouvée", details={"action_id": action_id})

        # Story 13.4, AC2: Validate target_names vs requires_target
        requires_target = getattr(action, 'requires_target', True)

        if requires_target:
            # Story 13.4, Subtask 2.2: target_names REQUIRED for actions requiring targets
            if not target_names:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="target_names est requis pour cette action",
                    details={"action_id": action_id, "requires_target": True},
                )
            # Story 13.4: Warn if environment passed with target_names (deprecated usage)
            if environment:
                exec_logger.warning(
                    "deprecated_environment_with_targets",
                    message="environment fourni avec target_names sera ignoré (dérivé du target)",
                    action_id=action_id,
                    environment=environment,
                    correlation_id=correlation_id
                )
        else:
            # Action does not require targets - environment OR target_names required
            if not environment and not target_names:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="environment ou target_names est requis",
                    details={"environment": environment, "target_names": target_names},
                )
            
            # Story 13.7, AC2: Validate environment against inventory
            if environment:
                _validate_environment_against_inventory(environment)

        # Story 13.2, Task 5 & 6: Handle target_names with RBAC validation
        if target_names:
            if not isinstance(target_names, list) or len(target_names) == 0:
                raise BadRequestError(
                    code="BAD_REQUEST",
                    message="target_names doit être une liste non vide",
                    details={"target_names": target_names},
                )

            # Get user's AD groups for RBAC (with profile fallback)
            ad_groups = get_user_ad_groups(request.user)

            # Validate targets via InventoryService (RBAC filtered)
            inventory_service = InventoryService()
            try:
                # Get all targets user can access (no environment filter - validate against full allowed set)
                allowed_targets, _total, inventory_truncated = inventory_service.list_targets_for_user(
                    user_id=request.user.id,
                    ad_groups=ad_groups,
                    page=1,
                    page_size=MAX_TARGETS_FOR_RBAC_FILTER
                )
            except InventoryServiceError as e:
                exec_logger.error(
                    "inventory_service_error_during_execution",
                    error=str(e),
                    user_id=request.user.id,
                    correlation_id=correlation_id
                )
                raise BadRequestError(
                    code="INVENTORY_UNAVAILABLE",
                    message="Service inventaire indisponible",
                    details={"error": str(e)},
                )

            # Build map of allowed targets by name
            allowed_targets_map = {t['name']: t for t in allowed_targets}

            # Validate all requested targets exist and are allowed
            validated_targets = []
            environments_found = set()
            for name in target_names:
                if name not in allowed_targets_map:
                    # Task 6.3: Log audit for unauthorized target attempt (SOC1 traceability)
                    exec_logger.warning(
                        "unauthorized_target_attempt",
                        user_id=request.user.id,
                        target_name=name,
                        action_id=action_id,
                        correlation_id=correlation_id
                    )
                    # entity_type=EXECUTION, entity_id=0: no execution created (attempt forbidden)
                    AuditService.create_entry(
                        user_id=str(request.user.id),
                        action_type=AuditActionType.EXECUTION_TARGET_FORBIDDEN,
                        entity_type=AuditEntityType.EXECUTION,
                        entity_id=0,
                        details={
                            "target_name": name,
                            "action_id": action_id,
                            "message": "Cible non autorisée pour cette action",
                        },
                        correlation_id=correlation_id,
                    )
                    details_403 = {"target_name": name}
                    if inventory_truncated:
                        details_403["inventory_truncated"] = True
                    raise ForbiddenError(
                        code="FORBIDDEN",
                        message=f"Cible non autorisée: {name}",
                        details=details_403,
                    )
                target = allowed_targets_map[name]
                validated_targets.append(target)
                environments_found.add(target['environment'])

            # Task 5.5: Validate all targets have the same environment
            if len(environments_found) > 1:
                raise BadRequestError(
                    code="MIXED_ENVIRONMENTS",
                    message="Les cibles doivent appartenir au même environnement",
                    details={"environments": list(environments_found)},
                )

            # Derive environment from targets
            environment = list(environments_found)[0]

            # Task 5.6: Store target_names in parameters
            parameters = parameters.copy() if parameters else {}
            parameters['_targets'] = target_names

            exec_logger.info(
                "execution_with_targets",
                user_id=request.user.id,
                action_id=action_id,
                target_count=len(target_names),
                derived_environment=environment,
                correlation_id=correlation_id
            )

        # Story 13.4, AC3: Get environment-specific config from action
        env_upper = (environment or "").upper()

        # Subtask 2.3: Get change_type_config for this environment
        change_type_config = action.change_type_config or {}
        env_change_config = change_type_config.get(env_upper, {})
        change_required = env_change_config.get("required", False)
        change_model_code = env_change_config.get("change_model_code")

        # Subtask 2.4: Get impact_rules for this environment
        impact_rules = action.impact_rules or {}
        env_impact_config = impact_rules.get(env_upper, {})
        impact_level = env_impact_config.get("impact_level") or env_impact_config.get("level") or action.default_impact_level

        exec_logger.info(
            "execution_environment_config",
            action_id=action_id,
            environment=environment,
            change_required=change_required,
            change_model_code=change_model_code,
            impact_level=impact_level,
            correlation_id=correlation_id
        )

        # Store environment config in parameters for downstream use
        parameters = parameters.copy() if parameters else {}
        parameters['_env_config'] = {
            'change_required': change_required,
            'change_model_code': change_model_code,
            'impact_level': impact_level,
        }

        # Story 13.5: Detect source and capture IP for audit traceability
        source = _detect_request_source(request)
        ip_address = get_client_ip(request)

        delegated_referenced_action_ids: list[int] | None = None
        if action.item_type == "workflow":
            # Story 4.11: delegation validation on workflow referenced actions
            delegated_referenced_action_ids = _validate_workflow_referenced_actions(
                workflow_action=action,
                correlation_id=correlation_id,
                user_id=request.user.id,
                ip_address=ip_address,
            )
        else:
            # Story 4.12: reject workflow_step_parameters on non-workflow actions
            if workflow_step_parameters is not None:
                raise BadRequestError(
                    code="INVALID_WORKFLOW_STEP_PARAMETERS",
                    message="workflow_step_parameters n'est autorisé que pour les workflows",
                    details={"action_id": action.id, "item_type": action.item_type},
                )

        if action.item_type == "workflow" and workflow_step_parameters is not None:
            normalized_wsp = _validate_workflow_step_parameters(
                workflow_action=action,
                workflow_step_parameters=workflow_step_parameters,
            )
            # Store for runtime (Story 4.12 AC5 will consume it)
            parameters = parameters.copy() if parameters else {}
            parameters["workflow_step_parameters"] = normalized_wsp

        execution = ExecutionService().create_execution(
            user=request.user,
            action=action,
            environment=environment,
            parameters=parameters if parameters else None,
            parent_execution_id=parent_execution_id,
            correlation_id=correlation_id,
            source=source,
            ip_address=ip_address,
            targets=target_names if target_names else None,
            delegated_referenced_action_ids=delegated_referenced_action_ids,
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


# =============================================================================
# Scheduled executions (Story 11.5 - 11.8)
# =============================================================================


def _parse_iso_datetime(value: str | None, *, name: str) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        raise BadRequestError(
            code="BAD_REQUEST",
            message=f"{name} invalide (ISO 8601)",
            details={name: value},
        )
    if timezone.is_naive(dt):
        # Assume UTC if no timezone info
        dt = timezone.make_aware(dt, timezone=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def _calculate_next_execution_date(pattern_type: str, pattern_config: dict, reference: datetime) -> datetime:
    """
    Compute next execution datetime in UTC for daily/weekly/cron patterns.
    """
    if timezone.is_naive(reference):
        reference = timezone.make_aware(reference, timezone=UTC)
    else:
        reference = reference.astimezone(UTC)

    pattern_type = (pattern_type or "").lower()

    if pattern_type == "daily":
        hour = int(pattern_config.get("hour", 0))
        minute = int(pattern_config.get("minute", 0))
        candidate = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= reference:
            candidate = candidate + timedelta(days=1)
        return candidate

    if pattern_type == "weekly":
        day_of_week = int(pattern_config.get("day_of_week", 1))  # 1=Mon .. 7=Sun
        hour = int(pattern_config.get("hour", 0))
        minute = int(pattern_config.get("minute", 0))
        # ISO weekday: Monday=1..Sunday=7
        current_dow = reference.isoweekday()
        days_ahead = (day_of_week - current_dow) % 7
        candidate = (reference + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= reference:
            candidate = candidate + timedelta(days=7)
        return candidate

    if pattern_type == "cron":
        expr = str(pattern_config.get("cron_expression", "")).strip()
        if not expr or not croniter.is_valid(expr):
            raise BadRequestError(
                code="INVALID_CRON_EXPRESSION",
                message="Expression cron invalide. Format attendu : minute hour day month day_of_week",
                details={"expression": expr},
            )
        it = croniter(expr, reference)
        nxt = it.get_next(datetime)
        if timezone.is_naive(nxt):
            nxt = timezone.make_aware(nxt, timezone=UTC)
        else:
            nxt = nxt.astimezone(UTC)
        return nxt

    raise BadRequestError(
        code="BAD_REQUEST",
        message="pattern_type invalide",
        details={"pattern_type": pattern_type},
    )


class ScheduledExecutionsView(APIView):
    """
    GET /scheduled-executions (Story 11.6)
    POST /scheduled-executions (Story 11.5, 11.7)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = _parse_int(request.query_params.get("limit"), 50, name="limit")
        offset = _parse_int(request.query_params.get("offset"), 0, name="offset")
        if limit <= 0 or offset < 0 or limit > 100:
            raise BadRequestError(code="BAD_REQUEST", message="Pagination invalide", details={"limit": limit, "offset": offset})

        status_filter = request.query_params.get("status")
        action_id = request.query_params.get("action_id")
        scheduled_from = _parse_iso_datetime(request.query_params.get("scheduled_from"), name="scheduled_from")
        scheduled_to = _parse_iso_datetime(request.query_params.get("scheduled_to"), name="scheduled_to")
        # Story 13.6: Additional filters for calendar view
        environment_filter = request.query_params.get("environment")
        engine_filter = request.query_params.get("engine")
        platform_filter = request.query_params.get("platform")

        qs = ScheduledExecution.objects.select_related("action", "user").select_related("recurringpattern")
        # Story 13.6: RBAC - DBOPS sees all; others see scheduled executions for actions their profile gives access to
        if (getattr(request.user, "profile", "") or "").lower() != "dbops":
            allowed_action_ids = _get_allowed_action_ids_for_user(request.user)
            if allowed_action_ids is not None:  # None means 'all' access
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
            qs = qs.filter(action_id=_parse_int(action_id, 0, name="action_id"))

        # Story 13.6: Filter by environment (from scheduled execution)
        # Story 13.7, AC2: Validate against inventory instead of hardcoded list
        if environment_filter:
            _validate_environment_against_inventory(environment_filter)
            qs = qs.filter(environment=environment_filter.lower())

        # Story 13.6: Filter by engine (from action)
        if engine_filter:
            qs = qs.filter(action__engine__iexact=engine_filter)

        # Story 13.6: Filter by platform (from action)
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
        total_count = qs.count()
        page = (offset // limit) + 1
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

        items = list(qs[offset: offset + limit])
        data_items = ScheduledExecutionListItemSerializer(items, many=True).data

        # AC8: Available actions (all that have scheduled executions, respecting RBAC)
        actions_qs = ScheduledExecution.objects.values("action_id", "action__name")
        if (getattr(request.user, "profile", "") or "").lower() != "dbops":
            actions_qs = actions_qs.filter(user_id=request.user.id)
        actions_qs = actions_qs.distinct().order_by("action__name")
        available_actions = [
            {"action_id": r["action_id"], "action_name": r["action__name"] or ""}
            for r in actions_qs
        ]

        inner = {
            "data": data_items,
            "pagination": {
                "page": page,
                "page_size": limit,
                "total_count": total_count,
                "total_pages": total_pages,
            },
            "available_actions": available_actions,
        }
        return Response({"data": inner})

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
        
        # Story 13.7, AC2: Validate environment against inventory
        _validate_environment_against_inventory(environment)

        # Validate mutual exclusivity
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

        scheduled_at = _parse_iso_datetime(scheduled_at_raw, name="scheduled_at") if scheduled_at_raw else None
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
            next_execution_date = _calculate_next_execution_date(pattern_type, pattern_config, timezone.now())
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

        # Store correlation id on the scheduled execution for traceability
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
            se = ScheduledExecution.objects.select_related("action").get(id=scheduled_execution_id)
            return Response(
                {
                    "data": {
                        "scheduled_execution_id": se.id,
                        "action_id": se.action_id,
                        "action_name": se.action.name if se.action else None,
                        "environment": se.environment,
                        "status": se.status,
                        "scheduled_at": se.scheduled_at.isoformat() if se.scheduled_at else None,
                        "created_at": se.created_at.isoformat() if se.created_at else None,
                    }
                }
            )

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

            # If recurring: recalc next date and keep status pending (next occurrence)
            # Wrap both operations in a single transaction to ensure atomicity
            with transaction.atomic():
                rp = getattr(se, "recurringpattern", None)
                if rp is not None and bool(rp.is_active):
                    rp.next_execution_date = _calculate_next_execution_date(
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
            se = ScheduledExecution.objects.select_related("action").get(id=scheduled_execution_id)
            return Response(
                {
                    "data": {
                        "scheduled_execution_id": se.id,
                        "action_id": se.action_id,
                        "action_name": se.action.name if se.action else None,
                        "environment": se.environment,
                        "status": se.status,
                        "scheduled_at": se.scheduled_at.isoformat() if se.scheduled_at else None,
                        "created_at": se.created_at.isoformat() if se.created_at else None,
                    }
                }
            )

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

        # One-time: allow updating scheduled_at
        rp = getattr(se, "recurringpattern", None)
        if scheduled_at_raw is not None and rp is None:
            scheduled_at = _parse_iso_datetime(scheduled_at_raw, name="scheduled_at")
            if scheduled_at <= timezone.now().astimezone(UTC):
                raise BadRequestError(
                    code="INVALID_SCHEDULED_DATE",
                    message="scheduled_at doit être dans le futur",
                    details={"scheduled_at": scheduled_at_raw},
                )
            se.scheduled_at = scheduled_at

        # Environment (validate against inventory)
        if environment is not None:
            _validate_environment_against_inventory(environment)
            se.environment = environment.lower()

        # Target names: RBAC validation and merge into parameters (empty list allowed = clear targets)
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
                    _validate_environment_against_inventory(environment)
                    se.environment = environment.lower()
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
                se.environment = list(environments_found)[0].lower()
                current_params = se.get_parameters() or {}
                if not isinstance(current_params, dict):
                    current_params = {}
                new_params = {**current_params, "_targets": target_names}
                se.set_parameters(new_params)
        elif parameters is not None:
            current_params = se.get_parameters() or {}
            if not isinstance(current_params, dict):
                current_params = {}
            # Security: do not allow client to set _targets via parameters; only via validated target_names
            incoming = parameters if isinstance(parameters, dict) else {}
            sanitized = {k: v for k, v in incoming.items() if not k.startswith("_")}
            merged = {**current_params, **sanitized}
            se.set_parameters(merged)

        # Recurring pattern update
        if recurring_pattern_payload is not None and rp is not None:
            pattern_type = (recurring_pattern_payload.get("pattern_type") or "").lower()
            pattern_config = recurring_pattern_payload.get("pattern_config") or {}
            next_execution_date = _calculate_next_execution_date(
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
            rp.next_execution_date = _calculate_next_execution_date(
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
            # semantic check
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
        count = _parse_int(request.query_params.get("count"), 5, name="count")
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
            if timezone.is_naive(nxt):
                nxt = timezone.make_aware(nxt, timezone=UTC)
            else:
                nxt = nxt.astimezone(UTC)
            executions.append(nxt.isoformat())

        return Response({"data": {"executions": executions}})

