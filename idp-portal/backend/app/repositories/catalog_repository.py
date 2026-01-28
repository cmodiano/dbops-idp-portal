"""Catalog repository using raw SQL via python-oracledb (Story 2.1, AC #4).

Handles CRUD operations for ACTIONS_CATALOG table with:
- CLOB columns for JSON (parameters_schema, impact_rules, rbac_policies)
- Parameterized queries for security
- Structured logging with correlation_id
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import structlog

from app.core.database import get_connection
from app.models.catalog import (
    ActionCreate,
    ActionDetail,
    ActionResponse,
    ActionStatus,
    ActionCategory,
    ActionEngine,
    ActionPlatform,
    ExecutionStep,
    ExecutionStepType,
    ChangeType,
    UserProfile,
    EnvironmentPermission,
    RbacPolicies,
    StatusTransition,
    InvalidTransitionError,
    validate_transition,
    ActionListItem,
    PaginationInfo,
)
from app.repositories import audit_repository
from app.repositories.audit_repository import AuditActionType, AuditEntityType

logger = structlog.get_logger()


def _json_to_str(data: dict[str, Any] | None) -> str | None:
    """Convert dict to JSON string for CLOB storage."""
    if data is None:
        return None
    return json.dumps(data)


def _str_to_json(data: str | None) -> dict[str, Any] | None:
    """Convert JSON string from CLOB to dict."""
    if data is None:
        return None
    return json.loads(data)


def _row_to_action_response(row: tuple) -> ActionResponse:
    """Convert database row to ActionResponse model."""
    return ActionResponse(
        id=row[0],
        name=row[1],
        description=row[2],
        category=ActionCategory(row[3]),
        engine=ActionEngine(row[4]),
        platform=ActionPlatform(row[5]),
        parameters_schema=_str_to_json(row[6]),
        impact_rules=_str_to_json(row[7]),
        status=ActionStatus(row[8]),
        created_by=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


def _parse_execution_steps(data: str | None) -> list[ExecutionStep] | None:
    """Parse execution_steps JSON to list of ExecutionStep models."""
    if data is None:
        return None
    try:
        steps_data = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid execution_steps JSON in database: {e}") from e
    if not isinstance(steps_data, list):
        raise ValueError("execution_steps must be a JSON array")
    out = []
    for i, s in enumerate(steps_data):
        if not isinstance(s, dict):
            raise ValueError(f"execution_steps[{i}] must be an object")
        try:
            out.append(
                ExecutionStep(
                    order=s["order"],
                    name=s["name"],
                    type=ExecutionStepType(s["type"]),
                    is_servicenow_change=s.get("is_servicenow_change", False),
                    conditional_environments=s.get("conditional_environments"),
                )
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid execution_steps[{i}]: {e}") from e
    return out


def _parse_change_type_config(data: str | None) -> dict[str, ChangeType] | None:
    """Parse change_type_config JSON to dict of ChangeType."""
    if data is None:
        return None
    try:
        config_data = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid change_type_config JSON in database: {e}") from e
    if not isinstance(config_data, dict):
        raise ValueError("change_type_config must be a JSON object")
    try:
        return {env: ChangeType(ct) for env, ct in config_data.items()}
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid change_type_config: {e}") from e


def _execution_steps_to_json(steps: list[ExecutionStep] | None) -> str | None:
    """Convert list of ExecutionStep to JSON string for CLOB storage."""
    if steps is None:
        return None
    return json.dumps([
        {
            "order": s.order,
            "name": s.name,
            "type": s.type.value,
            "is_servicenow_change": s.is_servicenow_change,
            "conditional_environments": s.conditional_environments,
        }
        for s in steps
    ])


def _change_type_config_to_json(config: dict[str, ChangeType] | None) -> str | None:
    """Convert dict of ChangeType to JSON string for CLOB storage."""
    if config is None:
        return None
    return json.dumps({env: ct.value for env, ct in config.items()})


def _safe_parse_execution_steps(data: str | None) -> list[ExecutionStep] | None:
    """Parse execution_steps CLOB; on invalid JSON log and return None to avoid 500."""
    if data is None:
        return None
    try:
        return _parse_execution_steps(data)
    except ValueError as e:
        logger.warning("catalog_repository_invalid_execution_steps_json", raw=data[:200] if data else None, error=str(e))
        return None


def _safe_parse_change_type_config(data: str | None) -> dict[str, ChangeType] | None:
    """Parse change_type_config CLOB; on invalid JSON log and return None to avoid 500."""
    if data is None:
        return None
    try:
        return _parse_change_type_config(data)
    except ValueError as e:
        logger.warning("catalog_repository_invalid_change_type_config_json", raw=data[:200] if data else None, error=str(e))
        return None


# === Story 2.3: RBAC Policies Helpers ===


def _rbac_policies_to_json(policies: RbacPolicies | None) -> str | None:
    """Convert RbacPolicies to JSON string for CLOB storage."""
    if policies is None:
        return None
    return json.dumps({
        "environments": {
            env: {
                "profiles": [p.value for p in perm.profiles],
                "requires_approval": perm.requires_approval,
                "approver_profiles": [p.value for p in perm.approver_profiles] if perm.approver_profiles else None,
            }
            for env, perm in policies.environments.items()
        }
    })


def _parse_rbac_policies(data: str | None) -> RbacPolicies | None:
    """Parse RBAC policies JSON to RbacPolicies model."""
    if data is None:
        return None
    try:
        policies_data = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid rbac_policies JSON in database: {e}") from e

    if not isinstance(policies_data, dict) or "environments" not in policies_data:
        raise ValueError("rbac_policies must have 'environments' key")

    environments = {}
    for env, perm_data in policies_data["environments"].items():
        if not isinstance(perm_data, dict):
            raise ValueError(f"rbac_policies.environments[{env}] must be an object")

        profiles = [UserProfile(p) for p in perm_data.get("profiles", [])]
        requires_approval = perm_data.get("requires_approval", False)
        approver_profiles = None
        if perm_data.get("approver_profiles"):
            approver_profiles = [UserProfile(p) for p in perm_data["approver_profiles"]]

        environments[env] = EnvironmentPermission(
            profiles=profiles,
            requires_approval=requires_approval,
            approver_profiles=approver_profiles,
        )

    return RbacPolicies(environments=environments)


def _safe_parse_rbac_policies(data: str | None) -> RbacPolicies | None:
    """Parse rbac_policies CLOB; on invalid JSON log and return None to avoid 500."""
    if data is None:
        return None
    try:
        return _parse_rbac_policies(data)
    except (ValueError, KeyError) as e:
        logger.warning("catalog_repository_invalid_rbac_policies_json", raw=data[:200] if data else None, error=str(e))
        return None


def _row_to_action_detail(row: tuple) -> ActionDetail:
    """Convert database row to ActionDetail model (includes rbac_policies, execution_steps, change_type_config).

    Uses _safe_parse_rbac_policies for RBAC CLOB to avoid 500 on invalid JSON (Story 2.2 pattern).
    """
    rbac_parsed = _safe_parse_rbac_policies(row[12]) if len(row) > 12 else None
    rbac_policies = rbac_parsed.model_dump() if rbac_parsed else None
    return ActionDetail(
        id=row[0],
        name=row[1],
        description=row[2],
        category=ActionCategory(row[3]),
        engine=ActionEngine(row[4]),
        platform=ActionPlatform(row[5]),
        parameters_schema=_str_to_json(row[6]),
        impact_rules=_str_to_json(row[7]),
        status=ActionStatus(row[8]),
        created_by=row[9],
        created_at=row[10],
        updated_at=row[11],
        rbac_policies=rbac_policies,
        execution_steps=_safe_parse_execution_steps(row[13]) if len(row) > 13 else None,
        change_type_config=_safe_parse_change_type_config(row[14]) if len(row) > 14 else None,
    )


async def create(action: ActionCreate, user_id: int) -> ActionResponse:
    """Create a new action in the catalog.

    Args:
        action: ActionCreate model with action data
        user_id: ID of the user creating the action

    Returns:
        ActionResponse with the created action

    Note:
        Uses Oracle sequence for ID generation.
        Status defaults to 'draft' as per V002 migration.
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO ACTIONS_CATALOG
        (NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM,
         PARAMETERS_SCHEMA, IMPACT_RULES, STATUS, CREATED_BY)
        VALUES
        (:name, :description, :category, :engine, :platform,
         :parameters_schema, :impact_rules, :status, :created_by)
        RETURNING ID INTO :out_id
    """
    params = {
        "name": action.name,
        "description": action.description,
        "category": action.category.value,
        "engine": action.engine.value,
        "platform": action.platform.value,
        "parameters_schema": _json_to_str(action.parameters_schema),
        "impact_rules": _json_to_str(action.impact_rules),
        "status": ActionStatus.DRAFT.value,
        "created_by": user_id,
    }

    async with get_connection() as conn:
        # Create output variable for RETURNING clause
        out_id = conn.var(int)
        params["out_id"] = out_id

        cursor = await conn.execute(query, params)
        await conn.commit()
        await cursor.close()

        action_id = out_id.getvalue()[0]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_params = {k: v for k, v in params.items() if k != "out_id"}
    logger.debug(
        "catalog_repository_create",
        query=query.strip(),
        params=log_params,
        duration_ms=duration_ms,
        action_id=action_id,
        action_name=action.name,
    )

    # Fetch the created action to return full response
    result = await get_by_id(action_id)
    if result is None:
        raise RuntimeError(f"Failed to fetch created action {action_id}")

    return ActionResponse(
        id=result.id,
        name=result.name,
        description=result.description,
        category=result.category,
        engine=result.engine,
        platform=result.platform,
        parameters_schema=result.parameters_schema,
        impact_rules=result.impact_rules,
        status=result.status,
        created_by=result.created_by,
        created_at=result.created_at,
        updated_at=result.updated_at,
    )


async def get_by_id(action_id: int) -> ActionDetail | None:
    """Fetch an action by ID with full details including rbac_policies, execution_steps, change_type_config.

    Args:
        action_id: The action ID to fetch

    Returns:
        ActionDetail if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM,
               PARAMETERS_SCHEMA, IMPACT_RULES, STATUS, CREATED_BY,
               CREATED_AT, UPDATED_AT, RBAC_POLICIES, EXECUTION_STEPS, CHANGE_TYPE_CONFIG
        FROM ACTIONS_CATALOG
        WHERE ID = :action_id
    """

    async with get_connection() as conn:
        cursor = await conn.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_get_by_id",
        query=query.strip(),
        params={"action_id": action_id},
        duration_ms=duration_ms,
        action_id=action_id,
        found=row is not None,
    )

    if row is None:
        return None

    return _row_to_action_detail(row)


def _action_visible_for_profile(rbac_json: str | None, user_profile: UserProfile) -> bool:
    """Check if an action is visible for a given user profile based on RBAC policies.

    Args:
        rbac_json: RBAC policies JSON string from database (or None)
        user_profile: The user profile to check

    Returns:
        True if action is visible, False otherwise.
        If rbac_json is None, action is visible to all.
    """
    if rbac_json is None:
        return True  # No RBAC policies = visible to all

    policies = _safe_parse_rbac_policies(rbac_json)
    if policies is None:
        return True  # Invalid JSON = treat as visible to all (defensive)

    # Action is visible if user_profile is in at least one environment's profiles
    for env_perm in policies.environments.values():
        if user_profile in env_perm.profiles:
            return True

    return False


async def list_all(
    status: ActionStatus | None = None,
    user_profile: UserProfile | None = None,
) -> list[ActionResponse]:
    """List all actions, optionally filtered by status and RBAC profile.

    Args:
        status: Optional status filter
        user_profile: Optional user profile for RBAC filtering (invisible filtering)

    Returns:
        List of ActionResponse ordered by created_at DESC
    """
    start_time = time.perf_counter()

    # Include RBAC_POLICIES in query if filtering is needed
    if user_profile is not None:
        base_query = """
            SELECT ID, NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM,
                   PARAMETERS_SCHEMA, IMPACT_RULES, STATUS, CREATED_BY,
                   CREATED_AT, UPDATED_AT, RBAC_POLICIES
            FROM ACTIONS_CATALOG
        """
    else:
        base_query = """
            SELECT ID, NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM,
                   PARAMETERS_SCHEMA, IMPACT_RULES, STATUS, CREATED_BY,
                   CREATED_AT, UPDATED_AT
            FROM ACTIONS_CATALOG
        """

    if status is None:
        query = base_query + " ORDER BY CREATED_AT DESC"
        params: dict[str, Any] = {}
    else:
        query = base_query + " WHERE STATUS = :status ORDER BY CREATED_AT DESC"
        params = {"status": status.value}

    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    # Apply RBAC filtering in Python (cannot do JSON filtering in Oracle easily)
    if user_profile is not None:
        filtered_rows = []
        for row in rows:
            rbac_json = row[12] if len(row) > 12 else None
            if _action_visible_for_profile(rbac_json, user_profile):
                filtered_rows.append(row[:12])  # Remove RBAC_POLICIES column for ActionResponse
        rows = filtered_rows

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_list_all",
        query=query.strip(),
        params=params,
        duration_ms=duration_ms,
        status_filter=status.value if status else None,
        user_profile=user_profile.value if user_profile else None,
        count=len(rows),
    )

    return [_row_to_action_response(row) for row in rows]


class InvalidStateError(Exception):
    """Raised when action is not in valid state for operation."""

    def __init__(self, message: str, current_status: str):
        super().__init__(message)
        self.current_status = current_status


async def update_execution_steps(
    action_id: int,
    steps: list[ExecutionStep],
    change_type_config: dict[str, ChangeType] | None,
) -> ActionDetail | None:
    """Update execution steps and change type config for an action.

    Args:
        action_id: The action ID to update
        steps: List of execution steps
        change_type_config: Change type configuration per environment

    Returns:
        ActionDetail if found and updated, None if not found

    Raises:
        InvalidStateError: If action is not in 'draft' status
    """
    start_time = time.perf_counter()

    # First check if action exists and get its status
    check_query = """
        SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(check_query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.debug(
            "catalog_repository_update_execution_steps",
            query=check_query.strip(),
            params={"action_id": action_id},
            duration_ms=duration_ms,
            action_id=action_id,
            found=False,
        )
        return None

    current_status = row[0]
    if current_status != ActionStatus.DRAFT.value:
        raise InvalidStateError(
            f"Les etapes ne peuvent etre modifiees que pour une action en brouillon",
            current_status=current_status,
        )

    # Update the action (check rowcount to avoid race: published between check and update)
    update_query = """
        UPDATE ACTIONS_CATALOG
        SET EXECUTION_STEPS = :execution_steps,
            CHANGE_TYPE_CONFIG = :change_type_config,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id AND STATUS = 'draft'
    """
    params = {
        "action_id": action_id,
        "execution_steps": _execution_steps_to_json(steps),
        "change_type_config": _change_type_config_to_json(change_type_config),
    }

    async with get_connection() as conn:
        cursor = await conn.execute(update_query, params)
        rowcount = cursor.rowcount
        if rowcount == 0:
            status_cursor = await conn.execute(
                "SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id",
                {"action_id": action_id},
            )
            status_row = await status_cursor.fetchone()
            await status_cursor.close()
            await cursor.close()
            new_status = status_row[0] if status_row else "unknown"
            raise InvalidStateError(
                "L'action n'est plus en brouillon ou a été modifiée entre-temps",
                current_status=new_status,
            )
        await conn.commit()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_params = {k: v for k, v in params.items()}
    logger.debug(
        "catalog_repository_update_execution_steps",
        query=update_query.strip(),
        params=log_params,
        duration_ms=duration_ms,
        action_id=action_id,
        steps_count=len(steps),
    )

    # Fetch and return updated action
    return await get_by_id(action_id)


async def update_rbac_policies(
    action_id: int,
    policies: RbacPolicies,
) -> ActionDetail | None:
    """Update RBAC policies for an action (Story 2.3, AC #4).

    Args:
        action_id: The action ID to update
        policies: RBAC policies configuration

    Returns:
        ActionDetail if found and updated, None if not found

    Raises:
        InvalidStateError: If action is not in 'draft' status
    """
    start_time = time.perf_counter()

    # First check if action exists and get its status
    check_query = """
        SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(check_query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.debug(
            "catalog_repository_update_rbac_policies",
            query=check_query.strip(),
            params={"action_id": action_id},
            duration_ms=duration_ms,
            action_id=action_id,
            found=False,
        )
        return None

    current_status = row[0]
    if current_status != ActionStatus.DRAFT.value:
        raise InvalidStateError(
            "Les politiques RBAC ne peuvent etre modifiees que pour une action en brouillon",
            current_status=current_status,
        )

    # Update the action (check rowcount to avoid race: published between check and update)
    update_query = """
        UPDATE ACTIONS_CATALOG
        SET RBAC_POLICIES = :rbac_policies,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id AND STATUS = 'draft'
    """
    params = {
        "action_id": action_id,
        "rbac_policies": _rbac_policies_to_json(policies),
    }

    async with get_connection() as conn:
        cursor = await conn.execute(update_query, params)
        rowcount = cursor.rowcount
        if rowcount == 0:
            status_cursor = await conn.execute(
                "SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id",
                {"action_id": action_id},
            )
            status_row = await status_cursor.fetchone()
            await status_cursor.close()
            await cursor.close()
            new_status = status_row[0] if status_row else "unknown"
            raise InvalidStateError(
                "L'action n'est plus en brouillon ou a ete modifiee entre-temps",
                current_status=new_status,
            )
        await conn.commit()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_update_rbac_policies",
        query=update_query.strip(),
        params={"action_id": action_id, "rbac_policies": "..."},
        duration_ms=duration_ms,
        action_id=action_id,
    )

    # Fetch and return updated action
    return await get_by_id(action_id)


# === Story 2.4: Status Transition and Lifecycle ===


async def update_action(
    action_id: int,
    action_update: ActionCreate,
    user_id: str,
) -> ActionDetail | None:
    """Update action metadata (name, description, category, etc.) (Story 2.4, AC #3).

    Allowed for published actions (metadata only).
    Execution steps and RBAC can only be changed in draft status.

    Args:
        action_id: The action ID to update
        action_update: ActionCreate model with updated metadata
        user_id: ID of the user performing the update (for audit)

    Returns:
        ActionDetail if found and updated, None if not found
    """
    start_time = time.perf_counter()

    # First check if action exists
    check_query = """
        SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(check_query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.debug(
            "catalog_repository_update_action",
            query=check_query.strip(),
            params={"action_id": action_id},
            duration_ms=duration_ms,
            action_id=action_id,
            found=False,
        )
        return None

    # Update the action metadata (allowed for all statuses)
    update_query = """
        UPDATE ACTIONS_CATALOG
        SET NAME = :name,
            DESCRIPTION = :description,
            CATEGORY = :category,
            ENGINE = :engine,
            PLATFORM = :platform,
            PARAMETERS_SCHEMA = :parameters_schema,
            IMPACT_RULES = :impact_rules,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id
    """
    params = {
        "action_id": action_id,
        "name": action_update.name,
        "description": action_update.description,
        "category": action_update.category.value,
        "engine": action_update.engine.value,
        "platform": action_update.platform.value,
        "parameters_schema": _json_to_str(action_update.parameters_schema),
        "impact_rules": _json_to_str(action_update.impact_rules),
    }

    async with get_connection() as conn:
        cursor = await conn.execute(update_query, params)
        rowcount = cursor.rowcount
        await cursor.close()

        if rowcount == 0:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.debug(
                "catalog_repository_update_action",
                query=update_query.strip(),
                params=params,
                duration_ms=duration_ms,
                action_id=action_id,
                found=False,
            )
            return None

        await conn.commit()

    # Create audit entry for metadata update
    await audit_repository.create_entry(
        user_id=user_id,
        action_type=AuditActionType.ACTION_UPDATED,
        entity_type=AuditEntityType.ACTION,
        entity_id=action_id,
        details={
            "action_name": action_update.name,
            "updated_fields": ["name", "description", "category", "engine", "platform", "parameters_schema", "impact_rules"],
        },
    )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_update_action",
        query=update_query.strip(),
        params={k: v for k, v in params.items() if k != "parameters_schema" and k != "impact_rules"},
        duration_ms=duration_ms,
        action_id=action_id,
        action_name=action_update.name,
    )

    # Fetch and return updated action
    return await get_by_id(action_id)


async def update_status(
    action_id: int,
    transition: StatusTransition,
    user_id: str,
) -> ActionDetail | None:
    """Update action status via a valid transition (Story 2.4, AC #1, #4, #5).

    Args:
        action_id: The action ID to update
        transition: The status transition to apply (publish, disable, enable)
        user_id: ID of the user performing the transition (for audit)

    Returns:
        ActionDetail if found and updated, None if not found

    Raises:
        InvalidTransitionError: If the transition is not valid for the current status
    """
    start_time = time.perf_counter()

    # First check if action exists and get its status
    check_query = """
        SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(check_query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.debug(
            "catalog_repository_update_status",
            query=check_query.strip(),
            params={"action_id": action_id},
            duration_ms=duration_ms,
            action_id=action_id,
            found=False,
        )
        return None

    current_status = ActionStatus(row[0])

    # Validate and get new status (raises InvalidTransitionError if invalid)
    new_status = validate_transition(current_status, transition)

    # Update the action status
    update_query = """
        UPDATE ACTIONS_CATALOG
        SET STATUS = :new_status,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id AND STATUS = :current_status
    """
    params = {
        "action_id": action_id,
        "new_status": new_status.value,
        "current_status": current_status.value,
    }

    async with get_connection() as conn:
        cursor = await conn.execute(update_query, params)
        rowcount = cursor.rowcount
        await cursor.close()

        if rowcount == 0:
            # Race condition: status changed between check and update
            status_cursor = await conn.execute(
                "SELECT STATUS FROM ACTIONS_CATALOG WHERE ID = :action_id",
                {"action_id": action_id},
            )
            status_row = await status_cursor.fetchone()
            await status_cursor.close()
            actual_status = status_row[0] if status_row else "unknown"
            raise InvalidTransitionError(
                current_status=actual_status,
                transition=transition.value,
                message="Le statut a change entre-temps, transition invalide",
            )

        await conn.commit()

    # Create audit entry for status change
    action_type_map = {
        StatusTransition.PUBLISH: AuditActionType.ACTION_PUBLISHED,
        StatusTransition.DISABLE: AuditActionType.ACTION_DISABLED,
        StatusTransition.ENABLE: AuditActionType.ACTION_ENABLED,
    }
    await audit_repository.create_entry(
        user_id=user_id,
        action_type=action_type_map[transition],
        entity_type=AuditEntityType.ACTION,
        entity_id=action_id,
        details={
            "previous_status": current_status.value,
            "new_status": new_status.value,
            "transition": transition.value,
        },
    )

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_update_status",
        query=update_query.strip(),
        params={"action_id": action_id, "transition": transition.value},
        duration_ms=duration_ms,
        action_id=action_id,
        previous_status=current_status.value,
        new_status=new_status.value,
    )

    # Fetch and return updated action
    return await get_by_id(action_id)


def _row_to_action_list_item(row: tuple) -> ActionListItem:
    """Convert database row to ActionListItem model for admin dashboard."""
    return ActionListItem(
        id=row[0],
        name=row[1],
        status=ActionStatus(row[2]),
        category=ActionCategory(row[3]),
        engine=ActionEngine(row[4]),
        created_at=row[5],
        execution_count=row[6] or 0,
    )


async def list_all_admin(
    status: ActionStatus | None = None,
    category: ActionCategory | None = None,
    engine: ActionEngine | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ActionListItem], PaginationInfo]:
    """List all actions for admin dashboard with execution counts (Story 2.4, AC #2).

    DBOPS only - no RBAC filtering. Returns all actions regardless of status.

    Args:
        status: Optional status filter
        category: Optional category filter
        engine: Optional engine filter
        page: Page number (1-based)
        page_size: Number of items per page

    Returns:
        Tuple of (list of ActionListItem, PaginationInfo) ordered by created_at DESC
    """
    start_time = time.perf_counter()

    # Build WHERE conditions
    conditions = []
    params: dict[str, Any] = {}

    if status is not None:
        conditions.append("STATUS = :status")
        params["status"] = status.value

    if category is not None:
        conditions.append("CATEGORY = :category")
        params["category"] = category.value

    if engine is not None:
        conditions.append("ENGINE = :engine")
        params["engine"] = engine.value

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total matching records
    count_query = f"SELECT COUNT(*) FROM ACTIONS_CATALOG AC{where_clause}"
    async with get_connection() as conn:
        cursor = await conn.execute(count_query, params)
        count_row = await cursor.fetchone()
        total_count = count_row[0] if count_row else 0
        await cursor.close()

    # Calculate pagination
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    offset = (page - 1) * page_size

    # Fetch paginated results
    base_query = """
        SELECT ID, NAME, STATUS, CATEGORY, ENGINE, CREATED_AT,
               COALESCE((SELECT COUNT(*) FROM EXECUTION_LOG EL WHERE EL.ACTION_ID = AC.ID), 0) AS EXECUTION_COUNT
        FROM ACTIONS_CATALOG AC
    """
    query = base_query + where_clause + " ORDER BY CREATED_AT DESC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"
    params["offset"] = offset
    params["page_size"] = page_size

    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_list_all_admin",
        query=query.strip(),
        params={k: v for k, v in params.items() if k not in ["offset", "page_size"]},
        duration_ms=duration_ms,
        count=len(rows),
        total_count=total_count,
        page=page,
        page_size=page_size,
    )

    pagination = PaginationInfo(
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )

    return [_row_to_action_list_item(row) for row in rows], pagination
