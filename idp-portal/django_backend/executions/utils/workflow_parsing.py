"""
Module executions.utils.workflow_parsing — Extraction et validation des steps workflow.

Responsabilité unique : parser les execution_steps d'une action workflow, valider
les paramètres par étape et les actions référencées (existence, statut publié).
"""
from __future__ import annotations

import structlog

from catalog.models import Action, ActionStatus
from catalog.validators import validate_schedule_config
from core.exceptions import BadRequestError, NotFoundError
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from utils.json_helpers import validate_json_schema

try:
    import jsonschema  # type: ignore
    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    JSONSCHEMA_AVAILABLE = False

exec_logger = structlog.get_logger(__name__)


def extract_workflow_referenced_action_ids(workflow_action: Action) -> list[int]:
    """
    Extract referenced_action_id list from a workflow's execution_steps.
    Story 26.10: Renamed from _extract_workflow_referenced_action_ids to respect Python convention (PEP 8).

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


def extract_workflow_step_map(workflow_action: Action) -> dict[int, int]:
    """
    Build mapping step_order -> referenced_action_id for a workflow.
    Story 26.10: Renamed from _extract_workflow_step_map to respect Python convention (PEP 8).
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


def validate_workflow_step_parameters(
    *,
    workflow_action: Action,
    workflow_step_parameters: object,
) -> dict:
    """
    Story 4.12 (AC4):
      - Reject unknown step_order keys
      - Validate each step parameters against referenced action parameters_schema
    Story 26.10: Renamed from _validate_workflow_step_parameters to respect Python convention (PEP 8).
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

    step_map = extract_workflow_step_map(workflow_action)
    valid_orders = sorted(step_map.keys())

    # Batch-load all referenced actions upfront to avoid N+1 queries
    all_ref_ids = list(step_map.values())
    actions_bulk: dict[int, Action] = Action.objects.in_bulk(all_ref_ids)

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
        ref_action = actions_bulk.get(int(ref_action_id))
        if ref_action is None:
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
        valid_str = ", ".join(str(o) for o in valid_orders) if valid_orders else "(aucun)"
        invalid_str = ", ".join(sorted(invalid_orders))
        raise BadRequestError(
            code="INVALID_WORKFLOW_STEP_ORDER",
            message=(
                f"workflow_step_parameters contient des step_order inconnus : {invalid_str}. "
                f"Valeurs valides pour ce workflow : {valid_str}"
            ),
            details={"invalid_step_orders": sorted(invalid_orders), "valid_step_orders": valid_orders},
        )

    return normalized


def validate_workflow_referenced_actions(
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
    Story 26.10: Renamed from _validate_workflow_referenced_actions to respect Python convention (PEP 8).

    Returns the ordered list of referenced_action_ids.
    Raises:
      - NotFoundError if any referenced action is missing
      - BadRequestError if any referenced action is not published
    """
    # Story 57.15: Validate schedule_config for schedule_execution steps
    steps = workflow_action.execution_steps or []
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_type = step.get('step_type', 'platform')
            if step_type == 'schedule_execution':
                schedule_config = step.get('schedule_config')
                if not schedule_config:
                    raise BadRequestError(
                        code="MISSING_SCHEDULE_CONFIG",
                        message=f"Step {step.get('step_id')!r}: schedule_config requis pour step_type='schedule_execution'",
                        details={"step_id": step.get('step_id')},
                    )
                validate_schedule_config(schedule_config)

    referenced_action_ids = extract_workflow_referenced_action_ids(workflow_action)

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

    # Batch-load all referenced actions upfront to avoid N+1 queries
    int_ref_ids = [int(r) for r in referenced_action_ids]
    found_actions: dict[int, Action] = Action.objects.in_bulk(int_ref_ids)

    missing_ids: list[int] = []
    not_published: list[dict] = []

    for ref_id in int_ref_ids:
        ref_action = found_actions.get(ref_id)
        if ref_action is None:
            missing_ids.append(ref_id)
            continue

        if ref_action.status != ActionStatus.PUBLISHED:
            not_published.append(
                {
                    "referenced_action_id": ref_id,
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
