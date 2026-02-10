"""
Helper functions for executions views.

Refactored from views.py (Story 22.7) to improve maintainability and testability.
Contains utility functions for:
- Configuration & validation (environment, inventory)
- Workflow helpers (action IDs extraction, step mapping, parameter validation)
- Parsing & conversion (int, date, datetime)
- RBAC & permissions (role checks, allowed actions)
- Filters & queries (request source detection, scope, execution filters)
- Scheduled executions (next execution date calculation)
"""
from __future__ import annotations

from datetime import datetime, timedelta, date
from datetime import timezone as dt_timezone

# Fixed-offset UTC (no name): Oracle Thin Mode does not support named timezones (DPY-3022)
UTC = dt_timezone(timedelta(0))

from typing import Any

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.request import Request
from django.utils.dateparse import parse_datetime

from catalog.models import Action, ActionStatus
from core.auth_utils import get_user_ad_groups
from core.exceptions import BadRequestError, NotFoundError, ConflictError
from core.middleware import get_correlation_id
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from inventory.services import InventoryService, InventoryServiceError
from profiles.services import ProfileService
from utils.json_helpers import validate_json_schema

from croniter import croniter

try:
    import jsonschema  # type: ignore
    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    JSONSCHEMA_AVAILABLE = False

import structlog

exec_logger = structlog.get_logger(__name__)

__all__ = [
    "_get_env_config_case_insensitive",
    "_validate_environment_against_inventory",
    "_extract_workflow_referenced_action_ids",
    "_extract_workflow_step_map",
    "_validate_workflow_step_parameters",
    "_validate_workflow_referenced_actions",
    "_parse_int",
    "_parse_date",
    "_is_dba_or_dbops",
    "_get_allowed_action_ids_for_user",
    "_detect_request_source",
    "_apply_scope_filter",
    "_apply_execution_filters",
    "_parse_iso_datetime",
    "_calculate_next_execution_date",
    "validate_action_mutex",
]


def _get_env_config_case_insensitive(config: dict, env: str) -> dict:
    """
    Story 21.2, Task 4.1: Helper to get environment-specific config with case-insensitive lookup.
    Story 25.4: Returned dict may include requires_maintenance_window, requires_approval, allowed.

    Args:
        config: Dictionary with environment keys (e.g., {"DEV": {...}, "STAGING": {...}})
        env: Environment string (case-insensitive)

    Returns:
        Config dict for the environment, or empty dict if not found.
        Per-env keys: required, change_model_code, change_type, template_id,
        requires_maintenance_window, requires_approval, allowed (Story 25.4).
    """
    if not config or not env:
        return {}

    env_lower = (env or '').strip().lower()
    for key, value in config.items():
        if (key or '').strip().lower() == env_lower:
            # HIGH-5 FIX: Log warning if config value is not a dict
            if not isinstance(value, dict):
                exec_logger.warning(
                    "invalid_env_config_value",
                    env=env,
                    key=key,
                    value_type=type(value).__name__,
                    correlation_id=get_correlation_id(),
                    message="Environment config value should be a dict, returning empty dict",
                )
                return {}
            return value

    return {}


def _validate_environment_against_inventory(environment: str, *, user_id: int | None = None) -> None:
    """
    Validate environment against inventory (Story 13.7, AC2).
    Story 21.2, AC2 / Task 3: Case-insensitive validation, no fallback to dev.
    Raises BadRequestError if environment is not in inventory.

    Args:
        environment: Environment string to validate
        user_id: Optional user ID for audit trail
    """
    if not environment:
        return

    correlation_id = get_correlation_id()

    try:
        inventory_service = InventoryService()
        valid_environments = inventory_service.list_environments()

        # HIGH-3 FIX: Use set comprehension for O(1) lookup instead of O(n) list comprehension
        valid_envs_lower = {e.lower() for e in valid_environments}
        if environment.lower() not in valid_envs_lower:
            # HIGH-4 FIX: Audit trail for invalid environment attempts (SOC1 compliance)
            AuditService.create_entry(
                user_id=str(user_id) if user_id else "system",
                action_type=AuditActionType.EXECUTION_SUBMITTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=0,
                details={
                    "environment": environment,
                    "valid_environments": sorted(valid_environments),
                    "validation_result": "failed",
                    "reason": "invalid_environment",
                },
                correlation_id=correlation_id,
            )
            raise BadRequestError(
                code="INVALID_ENVIRONMENT",
                message=f"Environnement invalide: {environment}",
                details={
                    "environment": environment,
                    "valid_environments": sorted(valid_environments)
                },
            )
    except InventoryServiceError as e:
        # HIGH-2 FIX: Block execution if inventory unavailable - can't validate safely
        exec_logger.error(
            "inventory_validation_failed_blocking_execution",
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise BadRequestError(
            code="INVENTORY_UNAVAILABLE",
            message="Impossible de valider l'environnement: service inventaire indisponible",
            details={"environment": environment, "error": str(e)},
        )


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
                jsonschema.validate(instance=params, schema=schema)
            except jsonschema.ValidationError as e:
                field_path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
                raise BadRequestError(
                    code="INVALID_PARAMETERS",
                    message=f"Paramètres invalides (étape {order_int}): {e.message}",
                    details={"step_order": order_int, "field": field_path, "error": e.message},
                ) from e
            except jsonschema.SchemaError as e:
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
    action_ids: set[int] = set()
    tag_patterns: set[str] = set()

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


def _apply_scope_filter(qs: QuerySet, *, user: Any, scope: str) -> tuple[QuerySet, str]:
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


def _apply_execution_filters(qs: QuerySet, *, request: Request) -> tuple[QuerySet, date | None, date | None]:
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
        nxt: datetime = it.get_next(datetime)
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


def validate_action_mutex(
    action: Action,
    target_ids: list[str],
    correlation_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """
    Story 25.5: Validate action mutex rules before execution creation.
    Checks for conflicting executions based on ACTION_MUTEX rules.

    Args:
        action: Action being submitted for execution
        target_ids: List of target_id strings (from validated_targets)
        correlation_id: Request correlation ID for logging
        user_id: User ID for audit trail

    Raises:
        BadRequestError: If a mutex violation is detected (code="MUTEX_VIOLATION", HTTP 409)

    Implementation notes:
    - Checks BOTH directions (A→B and B→A) for symmetric enforcement
    - Active statuses: RUNNING, PENDING_APPROVAL, SUBMITTED
    - same_target=True: blocks only if targets intersect
    - same_target=False: blocks globally regardless of targets
    """
    from catalog.models import ActionMutex
    from executions.models import Execution, ExecutionStatus, ExecutionTarget

    # Define active statuses that block new executions
    ACTIVE_STATUSES = [
        ExecutionStatus.RUNNING,
        ExecutionStatus.PENDING_APPROVAL,
        ExecutionStatus.SUBMITTED,
    ]

    # Fetch mutex rules where current action is involved (either side)
    # Option B from Dev Notes: check both directions (action=current OR incompatible_with=current)
    mutex_rules = ActionMutex.objects.filter(
        Q(action=action) | Q(incompatible_with=action)
    ).select_related('action', 'incompatible_with')

    if not mutex_rules.exists():
        # No mutex rules defined for this action
        return

    for rule in mutex_rules:
        # Determine which action is the incompatible one
        if rule.action.id == action.id:
            incompatible_action = rule.incompatible_with
        else:
            incompatible_action = rule.action

        # Check for active executions of the incompatible action
        conflicting_executions = Execution.objects.filter(
            action=incompatible_action,
            status__in=ACTIVE_STATUSES,
        )

        if rule.same_target and target_ids:
            # Mode: same_target=True
            # Only block if there's target intersection
            # Join ExecutionTarget to check for overlapping target_ids
            conflicting_executions = conflicting_executions.filter(
                targets__target_id__in=target_ids
            ).distinct()

        # Performance: use exists() instead of count() or fetching all
        if conflicting_executions.exists():
            # Mutex violation detected
            # Fetch one example for detailed error message
            first_conflict = conflicting_executions.select_related('action', 'user').first()
            
            exec_logger.warning(
                "mutex_violation_detected",
                action_id=action.id,
                action_name=action.name,
                incompatible_action_id=incompatible_action.id,
                incompatible_action_name=incompatible_action.name,
                same_target=rule.same_target,
                target_ids=target_ids,
                conflicting_execution_id=first_conflict.id if first_conflict else None,
                conflicting_status=first_conflict.status if first_conflict else None,
                correlation_id=correlation_id,
                user_id=user_id,
                message="Mutex rule blocks execution - incompatible action is currently running",
            )

            # Raise 409 CONFLICT with structured error
            scope_msg = "sur les mêmes cibles" if rule.same_target else "globalement"
            raise ConflictError(
                code="MUTEX_VIOLATION",
                message=(
                    f"Impossible d'exécuter '{action.name}' : une opération incompatible "
                    f"'{incompatible_action.name}' est déjà en cours {scope_msg}. "
                    f"Veuillez attendre la fin de l'opération en cours avant de relancer."
                ),
                details={
                    "action_id": action.id,
                    "action_name": action.name,
                    "incompatible_action_id": incompatible_action.id,
                    "incompatible_action_name": incompatible_action.name,
                    "same_target": rule.same_target,
                    "conflicting_execution_id": first_conflict.id if first_conflict else None,
                    "conflicting_status": first_conflict.status if first_conflict else None,
                    "mutex_rule_description": rule.description,
                },
            )
