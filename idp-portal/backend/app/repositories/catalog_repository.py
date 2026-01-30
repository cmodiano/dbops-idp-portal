"""Catalog repository using raw SQL via python-oracledb (Story 2.1, AC #4).

Handles CRUD operations for ACTIONS_CATALOG table with:
- CLOB columns for JSON (parameters_schema, impact_rules, execution_steps, change_type_config)
- Parameterized queries for security
- Structured logging with correlation_id

Story 2.14: rbac_policies column removed — RBAC now managed via profiles.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import oracledb
import structlog

from app.core.database import get_connection
from app.models.catalog import (
    ActionCreate,
    ActionDetail,
    ActionResponse,
    ActionStatus,
    ActionEngine,
    ActionPlatform,
    ImpactLevel,
    ConnectorType,
    ExecutionStep,
    ExecutionStepType,
    ChangeTypeConfigEntry,
    StatusTransition,
    InvalidTransitionError,
    validate_transition,
    ActionListItem,
    PaginationInfo,
    TagCreate,
    TagResponse,
    normalize_tag_name,
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


def _parse_impact_level(value: str | None) -> ImpactLevel | None:
    """Parse impact level string to ImpactLevel enum, returning None if invalid."""
    if value is None:
        return None
    try:
        return ImpactLevel(value)
    except ValueError:
        return None


def _row_to_action_response(row: tuple, tags: list[str] | None = None) -> ActionResponse:
    """Convert database row to ActionResponse model.

    Story 2.6: optional tags.
    Story 2.18 AC5: default_impact_level.
    Story 2.24: change_model_code column removed — change_type_config per env only in detail.
    Story 2.23: category removed — use tags instead.

    Expected row order (12 columns after V019):
    0:ID, 1:NAME, 2:DESCRIPTION, 3:ENGINE, 4:PLATFORM,
    5:PARAMETERS_SCHEMA, 6:IMPACT_RULES, 7:DEFAULT_IMPACT_LEVEL,
    8:STATUS, 9:CREATED_BY, 10:CREATED_AT, 11:UPDATED_AT
    """
    return ActionResponse(
        id=row[0],
        name=row[1],
        description=row[2],
        engine=ActionEngine(row[3]),
        platform=ActionPlatform(row[4]),
        parameters_schema=_str_to_json(row[5]),
        impact_rules=_str_to_json(row[6]),
        default_impact_level=_parse_impact_level(row[7]),
        status=ActionStatus(row[8]),
        created_by=row[9],
        created_at=row[10],
        updated_at=row[11],
        tags=tags if tags is not None else [],
    )


def _parse_execution_steps(data: str | None) -> list[ExecutionStep] | None:
    """Parse execution_steps JSON to list of ExecutionStep models (Story 2.7: legacy is_servicenow_change)."""
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
            # New format: connector_type + connector_config (Story 2.7)
            if "connector_type" in s:
                connector_type = ConnectorType(s["connector_type"])
                connector_config = s.get("connector_config")
            else:
                # Legacy: is_servicenow_change → connector_type (AC3)
                is_sn = s.get("is_servicenow_change", False)
                connector_type = ConnectorType.SERVICENOW if is_sn else ConnectorType.NONE
                connector_config = None
            out.append(
                ExecutionStep(
                    order=s["order"],
                    name=s["name"],
                    type=ExecutionStepType(s["type"]),
                    connector_type=connector_type,
                    connector_config=connector_config,
                    conditional_environments=s.get("conditional_environments"),
                )
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid execution_steps[{i}]: {e}") from e
    return out


class LegacyChangeTypeConfigError(ValueError):
    """Raised when change_type_config uses legacy format (env -> string). Story 2.24: use {env: {required, change_model_code}}."""


def _parse_change_type_config(data: str | None) -> dict[str, ChangeTypeConfigEntry] | None:
    """Parse change_type_config JSON to dict of ChangeTypeConfigEntry (Story 2.24).

    New format: {"PROD": {"required": true, "change_model_code": "1516B"}, "DEV": {"required": false}}.
    Raises LegacyChangeTypeConfigError if legacy format (env -> "pre_approved" string) is found.
    """
    if data is None:
        return None
    try:
        config_data = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid change_type_config JSON in database: {e}") from e
    if not isinstance(config_data, dict):
        raise ValueError("change_type_config must be a JSON object")
    out: dict[str, ChangeTypeConfigEntry] = {}
    for env, val in config_data.items():
        if isinstance(val, str):
            raise LegacyChangeTypeConfigError(
                "change_type_config uses legacy format (environment -> string). "
                "Use new format: {\"ENV\": {\"required\": true|false, \"change_model_code\": \"...\"}}."
            )
        if not isinstance(val, dict):
            raise ValueError(f"change_type_config[{env}] must be an object with required, optional change_model_code")
        out[env] = ChangeTypeConfigEntry(
            required=val.get("required", False),
            change_model_code=val.get("change_model_code"),
        )
    return out


def _execution_steps_to_json(steps: list[ExecutionStep] | None) -> str | None:
    """Convert list of ExecutionStep to JSON string for CLOB storage (Story 2.7: connector_type only)."""
    if steps is None:
        return None
    return json.dumps([
        {
            "order": s.order,
            "name": s.name,
            "type": s.type.value,
            "connector_type": s.connector_type.value,
            "connector_config": s.connector_config,
            "conditional_environments": s.conditional_environments,
        }
        for s in steps
    ])


def _change_type_config_to_json(config: dict[str, ChangeTypeConfigEntry] | None) -> str | None:
    """Convert dict of ChangeTypeConfigEntry to JSON string for CLOB storage (Story 2.24)."""
    if config is None:
        return None
    return json.dumps({
        env: {"required": entry.required, "change_model_code": entry.change_model_code}
        for env, entry in config.items()
    })


def _safe_parse_execution_steps(data: str | None) -> list[ExecutionStep] | None:
    """Parse execution_steps CLOB; on invalid JSON log and return None to avoid 500."""
    if data is None:
        return None
    try:
        return _parse_execution_steps(data)
    except ValueError as e:
        logger.warning("catalog_repository_invalid_execution_steps_json", raw=data[:200] if data else None, error=str(e))
        return None


def _safe_parse_change_type_config(data: str | None) -> dict[str, ChangeTypeConfigEntry] | None:
    """Parse change_type_config CLOB; on invalid/legacy JSON log and return None to avoid 500."""
    if data is None:
        return None
    try:
        return _parse_change_type_config(data)
    except (ValueError, LegacyChangeTypeConfigError) as e:
        logger.warning("catalog_repository_invalid_change_type_config_json", raw=data[:200] if data else None, error=str(e))
        return None


def _row_to_action_detail(row: tuple, tags: list[str] | None = None) -> ActionDetail:
    """Convert database row to ActionDetail model (includes execution_steps, change_type_config).

    Story 2.6: optional tags (tag names).
    Story 2.14: rbac_policies removed — RBAC now managed via profiles.
    Story 2.18 AC5: default_impact_level.
    Story 2.24: change_model_code column removed; change_type_config per env.
    Story 2.23: category removed — use tags instead.

    Expected row order (14 columns after V019):
    0:ID, 1:NAME, 2:DESCRIPTION, 3:ENGINE, 4:PLATFORM,
    5:PARAMETERS_SCHEMA, 6:IMPACT_RULES, 7:DEFAULT_IMPACT_LEVEL,
    8:STATUS, 9:CREATED_BY, 10:CREATED_AT, 11:UPDATED_AT,
    12:EXECUTION_STEPS, 13:CHANGE_TYPE_CONFIG
    """
    return ActionDetail(
        id=row[0],
        name=row[1],
        description=row[2],
        engine=ActionEngine(row[3]),
        platform=ActionPlatform(row[4]),
        parameters_schema=_str_to_json(row[5]),
        impact_rules=_str_to_json(row[6]),
        default_impact_level=_parse_impact_level(row[7]),
        status=ActionStatus(row[8]),
        created_by=row[9],
        created_at=row[10],
        updated_at=row[11],
        execution_steps=_safe_parse_execution_steps(row[12]) if len(row) > 12 else None,
        change_type_config=_safe_parse_change_type_config(row[13]) if len(row) > 13 else None,
        tags=tags if tags is not None else [],
    )


# === Story 2.6: Tags (FR11c) ===


def _row_to_tag_response(row: tuple) -> TagResponse:
    """Convert database row to TagResponse."""
    return TagResponse(id=row[0], name=row[1], created_at=row[2])


async def get_all_tags() -> list[TagResponse]:
    """Return all tags ordered by name (Story 2.6, AC #5)."""
    query = "SELECT ID, NAME, CREATED_AT FROM TAGS ORDER BY NAME"
    async with get_connection() as conn:
        cursor = await conn.execute(query, {})
        rows = await cursor.fetchall()
        await cursor.close()
    return [_row_to_tag_response(row) for row in rows]


async def get_tags_for_action(action_id: int) -> list[str]:
    """Return tag names for an action (Story 2.6)."""
    query = """
        SELECT t.NAME FROM TAGS t
        INNER JOIN ACTION_TAGS at ON at.TAG_ID = t.ID
        WHERE at.ACTION_ID = :action_id
        ORDER BY t.NAME
    """
    async with get_connection() as conn:
        cursor = await conn.execute(query, {"action_id": action_id})
        rows = await cursor.fetchall()
        await cursor.close()
    return [row[0] for row in rows]


async def get_tags_for_actions(action_ids: list[int]) -> dict[int, list[str]]:
    """Return tag names per action_id for many actions (Story 2.6, avoids N+1)."""
    if not action_ids:
        return {}
    # Oracle IN clause: bind list as multiple params or use a subquery
    placeholders = ", ".join(f":id{i}" for i in range(len(action_ids)))
    query = f"""
        SELECT at.ACTION_ID, t.NAME FROM ACTION_TAGS at
        INNER JOIN TAGS t ON t.ID = at.TAG_ID
        WHERE at.ACTION_ID IN ({placeholders})
        ORDER BY at.ACTION_ID, t.NAME
    """
    params = {f"id{i}": aid for i, aid in enumerate(action_ids)}
    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
    result: dict[int, list[str]] = {aid: [] for aid in action_ids}
    for action_id, name in rows:
        result[action_id].append(name)
    return result


async def list_tags_with_counts(
    action_ids_filter: list[int] | None = None,
) -> list[dict[str, Any]]:
    """List tag names with action counts for published actions (Story 3.3, AC3, AC10).

    Args:
        action_ids_filter: Optional list of action IDs to restrict to (RBAC). When None, all published actions.

    Returns:
        List of { "name": str, "action_count": int } ordered by name ASC.
    """
    base_query = """
        SELECT t.NAME, COUNT(DISTINCT at.ACTION_ID) AS ACTION_COUNT
        FROM TAGS t
        INNER JOIN ACTION_TAGS at ON at.TAG_ID = t.ID
        INNER JOIN ACTIONS_CATALOG AC ON AC.ID = at.ACTION_ID AND AC.STATUS = :status
    """
    params: dict[str, Any] = {"status": ActionStatus.PUBLISHED.value}
    if action_ids_filter:
        placeholders = ", ".join(f":aid{i}" for i in range(len(action_ids_filter)))
        base_query += f" AND AC.ID IN ({placeholders})"
        for i, aid in enumerate(action_ids_filter):
            params[f"aid{i}"] = aid
    base_query += " GROUP BY t.NAME ORDER BY t.NAME ASC"

    async with get_connection() as conn:
        cursor = await conn.execute(base_query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    return [{"name": row[0], "action_count": row[1]} for row in rows]


async def create_tag_if_not_exists(name: str) -> int:
    """Create tag if not exists, return tag id. Normalizes name: lowercase, no spaces (Story 2.6, AC #5).

    Handles race: concurrent inserts may raise IntegrityError (UK_TAGS_NAME);
    retry with SELECT and return existing id.
    """
    normalized = normalize_tag_name(name)
    if not normalized:
        raise ValueError("tag name cannot be empty or whitespace only")
    select_query = "SELECT ID FROM TAGS WHERE NAME = :name"
    insert_query = """
        INSERT INTO TAGS (NAME) VALUES (:name)
        RETURNING ID INTO :out_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(select_query, {"name": normalized})
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return row[0]
        try:
            out_id = conn.var(int)
            cursor = await conn.execute(insert_query, {"name": normalized, "out_id": out_id})
            await conn.commit()
            await cursor.close()
            return out_id.getvalue()[0]
        except oracledb.IntegrityError:
            await conn.rollback()
            cursor = await conn.execute(select_query, {"name": normalized})
            row = await cursor.fetchone()
            await cursor.close()
            if row:
                return row[0]
            raise


async def set_action_tags(action_id: int, tag_ids: list[int]) -> None:
    """Replace all tags for an action (Story 2.6, AC #5)."""
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM ACTION_TAGS WHERE ACTION_ID = :action_id",
            {"action_id": action_id},
        )
        for tag_id in tag_ids:
            await conn.execute(
                "INSERT INTO ACTION_TAGS (ACTION_ID, TAG_ID) VALUES (:action_id, :tag_id)",
                {"action_id": action_id, "tag_id": tag_id},
            )
        await conn.commit()


async def create(action: ActionCreate, user_id: int) -> ActionResponse:
    """Create a new action in the catalog.

    Args:
        action: ActionCreate model with action data
        user_id: ID of the user creating the action

    Returns:
        ActionResponse with the created action

    Note:
        Uses Oracle identity column for ID (Story 2.20); RETURNING ID.
        Status defaults to 'draft' as per V002 migration.
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO ACTIONS_CATALOG
        (NAME, DESCRIPTION, ENGINE, PLATFORM,
         PARAMETERS_SCHEMA, IMPACT_RULES, DEFAULT_IMPACT_LEVEL, STATUS, CREATED_BY)
        VALUES
        (:name, :description, :engine, :platform,
         :parameters_schema, :impact_rules, :default_impact_level, :status, :created_by)
        RETURNING ID INTO :out_id
    """
    params = {
        "name": action.name,
        "description": action.description,
        "engine": action.engine.value,
        "platform": action.platform.value,
        "parameters_schema": _json_to_str(action.parameters_schema),
        "impact_rules": _json_to_str(action.impact_rules),
        "default_impact_level": action.default_impact_level.value if action.default_impact_level else None,
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

    # Fetch the created action to return full response (includes tags)
    result = await get_by_id(action_id)
    if result is None:
        raise RuntimeError(f"Failed to fetch created action {action_id}")

    return ActionResponse(
        id=result.id,
        name=result.name,
        description=result.description,
        engine=result.engine,
        platform=result.platform,
        parameters_schema=result.parameters_schema,
        impact_rules=result.impact_rules,
        default_impact_level=result.default_impact_level,
        status=result.status,
        created_by=result.created_by,
        created_at=result.created_at,
        updated_at=result.updated_at,
        tags=result.tags,
    )  # Story 2.24: change_model_code removed from ActionResponse


async def get_by_id(action_id: int) -> ActionDetail | None:
    """Fetch an action by ID with full details including execution_steps, change_type_config.

    Story 2.14: rbac_policies removed — RBAC now managed via profiles.

    Args:
        action_id: The action ID to fetch

    Returns:
        ActionDetail if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, NAME, DESCRIPTION, ENGINE, PLATFORM,
               PARAMETERS_SCHEMA, IMPACT_RULES, DEFAULT_IMPACT_LEVEL, STATUS, CREATED_BY,
               CREATED_AT, UPDATED_AT, EXECUTION_STEPS, CHANGE_TYPE_CONFIG
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

    tags = await get_tags_for_action(row[0])
    return _row_to_action_detail(row, tags=tags)


async def list_all(
    status: ActionStatus | None = None,
    tags_filter: list[str] | None = None,
) -> list[ActionResponse]:
    """List all actions, optionally filtered by status and tags (Story 2.6, AC4).

    Story 2.14: RBAC filtering by action removed — use profile-based permissions instead.

    Args:
        status: Optional status filter
        tags_filter: Optional list of tag names (normalized). Actions with at least one match.

    Returns:
        List of ActionResponse ordered by created_at DESC
    """
    start_time = time.perf_counter()

    base_query = """
        SELECT ID, NAME, DESCRIPTION, ENGINE, PLATFORM,
               PARAMETERS_SCHEMA, IMPACT_RULES, DEFAULT_IMPACT_LEVEL, STATUS, CREATED_BY,
               CREATED_AT, UPDATED_AT
        FROM ACTIONS_CATALOG
    """

    conditions = []
    params: dict[str, Any] = {}
    if status is not None:
        conditions.append("STATUS = :status")
        params["status"] = status.value
    if tags_filter:
        placeholders = ", ".join(f":tag{i}" for i in range(len(tags_filter)))
        conditions.append(
            f"ID IN (SELECT at.ACTION_ID FROM ACTION_TAGS at "
            f"INNER JOIN TAGS t ON t.ID = at.TAG_ID WHERE t.NAME IN ({placeholders}))"
        )
        for i, t in enumerate(tags_filter):
            params[f"tag{i}"] = normalize_tag_name(t) or t

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = base_query + where_clause + " ORDER BY CREATED_AT DESC"

    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    # Story 2.6: attach tags per action (batch query)
    action_ids = [row[0] for row in rows]
    tags_map = await get_tags_for_actions(action_ids)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_list_all",
        query=query.strip(),
        params=params,
        duration_ms=duration_ms,
        status_filter=status.value if status else None,
        tags_filter=tags_filter,
        count=len(rows),
    )

    return [_row_to_action_response(row, tags=tags_map.get(row[0], [])) for row in rows]


async def list_catalog(
    status: ActionStatus | None = None,
    tags_filter: list[str] | None = None,
    action_ids_filter: list[int] | None = None,
    q: str | None = None,
    engine: str | None = None,
    environment: str | None = None,
    impact: str | None = None,
) -> list[dict]:
    """List actions for catalog with execution_count (Story 3.1, 3.3, AC1, AC3, AC9, AC10, AC11).

    Args:
        status: Optional status filter (default: published)
        tags_filter: Optional list of tag names (normalized). Actions with at least one match.
        action_ids_filter: Optional list of action IDs to restrict results (RBAC filtering)
        q: Optional text search on NAME, DESCRIPTION, and tag names (LIKE, OR).
        engine: Optional filter on AC.ENGINE (e.g. Oracle, SQL Server).
        environment: Optional filter: actions whose impact_rules has this key (e.g. PROD, DEV).
        impact: Optional filter on AC.DEFAULT_IMPACT_LEVEL (e.g. low, medium, high).

    Returns:
        List of action dicts with execution_count, ordered by name ASC
    """
    start_time = time.perf_counter()

    base_query = """
        SELECT AC.ID, AC.NAME, AC.DESCRIPTION, AC.ENGINE, AC.PLATFORM,
               AC.PARAMETERS_SCHEMA, AC.IMPACT_RULES, AC.DEFAULT_IMPACT_LEVEL, AC.STATUS, AC.CREATED_BY,
               AC.CREATED_AT, AC.UPDATED_AT,
               COALESCE((SELECT COUNT(*) FROM EXECUTION_LOG EL WHERE EL.ACTION_ID = AC.ID), 0) AS EXECUTION_COUNT
        FROM ACTIONS_CATALOG AC
    """

    conditions = []
    params: dict[str, Any] = {}
    if status is not None:
        conditions.append("AC.STATUS = :status")
        params["status"] = status.value
    if tags_filter:
        placeholders = ", ".join(f":tag{i}" for i in range(len(tags_filter)))
        conditions.append(
            f"AC.ID IN (SELECT at.ACTION_ID FROM ACTION_TAGS at "
            f"INNER JOIN TAGS t ON t.ID = at.TAG_ID WHERE t.NAME IN ({placeholders}))"
        )
        for i, t in enumerate(tags_filter):
            params[f"tag{i}"] = normalize_tag_name(t) or t
    if action_ids_filter:
        placeholders = ", ".join(f":aid{i}" for i in range(len(action_ids_filter)))
        conditions.append(f"AC.ID IN ({placeholders})")
        for i, aid in enumerate(action_ids_filter):
            params[f"aid{i}"] = aid
    if q and q.strip():
        # Story 3.3: Case-insensitive search using UPPER() for Oracle compatibility
        q_pattern = f"%{q.strip().upper()}%"
        params["q_name"] = q_pattern
        params["q_desc"] = q_pattern
        params["q_tag"] = q_pattern
        conditions.append(
            "(UPPER(AC.NAME) LIKE :q_name OR UPPER(AC.DESCRIPTION) LIKE :q_desc OR "
            "AC.ID IN (SELECT at.ACTION_ID FROM ACTION_TAGS at INNER JOIN TAGS t ON t.ID = at.TAG_ID WHERE UPPER(t.NAME) LIKE :q_tag))"
        )
    if engine:
        conditions.append("AC.ENGINE = :engine")
        params["engine"] = engine
    if environment:
        conditions.append("JSON_EXISTS(AC.IMPACT_RULES, '$.' || :environment) = 1")
        params["environment"] = environment
    if impact:
        conditions.append("AC.DEFAULT_IMPACT_LEVEL = :impact")
        params["impact"] = impact

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = base_query + where_clause + " ORDER BY AC.NAME ASC"

    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    # Attach tags per action (batch query)
    action_ids = [row[0] for row in rows]
    tags_map = await get_tags_for_actions(action_ids)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "catalog_repository_list_catalog",
        query=query.strip()[:200],
        params={k: v for k, v in params.items() if not k.startswith("aid")},
        duration_ms=duration_ms,
        status_filter=status.value if status else None,
        tags_filter=tags_filter,
        action_ids_filter_count=len(action_ids_filter) if action_ids_filter else 0,
        q=q,
        engine=engine,
        environment=environment,
        impact=impact,
        count=len(rows),
    )

    results = []
    for row in rows:
        action = _row_to_action_response(row[:12], tags=tags_map.get(row[0], []))
        results.append({
            **action.model_dump(mode="json"),
            "execution_count": row[12],
        })
    return results


class InvalidStateError(Exception):
    """Raised when action is not in valid state for operation."""

    def __init__(self, message: str, current_status: str):
        super().__init__(message)
        self.current_status = current_status


async def update_execution_steps(
    action_id: int,
    steps: list[ExecutionStep],
    change_type_config: dict[str, ChangeTypeConfigEntry] | None,
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


# === Story 2.4: Status Transition and Lifecycle ===


async def update_action(
    action_id: int,
    action_update: ActionCreate,
    user_id: str,
) -> ActionDetail | None:
    """Update action metadata (name, description, category, etc.) (Story 2.4, AC #3).

    Allowed for published actions (metadata only).
    Execution steps can only be changed in draft status.

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

    # Update the action metadata (allowed for all statuses). Story 2.24: change_model_code removed.
    update_query = """
        UPDATE ACTIONS_CATALOG
        SET NAME = :name,
            DESCRIPTION = :description,
            ENGINE = :engine,
            PLATFORM = :platform,
            PARAMETERS_SCHEMA = :parameters_schema,
            IMPACT_RULES = :impact_rules,
            DEFAULT_IMPACT_LEVEL = :default_impact_level,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id
    """
    params = {
        "action_id": action_id,
        "name": action_update.name,
        "description": action_update.description,
        "engine": action_update.engine.value,
        "platform": action_update.platform.value,
        "parameters_schema": _json_to_str(action_update.parameters_schema),
        "impact_rules": _json_to_str(action_update.impact_rules),
        "default_impact_level": action_update.default_impact_level.value if action_update.default_impact_level else None,
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
            "updated_fields": ["name", "description", "engine", "platform", "parameters_schema", "impact_rules", "default_impact_level"],
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


def _row_to_action_list_item(row: tuple, tags: list[str] | None = None) -> ActionListItem:
    """Convert database row to ActionListItem model for admin dashboard (Story 2.6: optional tags).

    Story 2.23: category removed — use tags instead.
    Expected row order (6 columns): 0:ID, 1:NAME, 2:STATUS, 3:ENGINE, 4:CREATED_AT, 5:EXECUTION_COUNT
    """
    return ActionListItem(
        id=row[0],
        name=row[1],
        status=ActionStatus(row[2]),
        engine=ActionEngine(row[3]),
        created_at=row[4],
        execution_count=row[5] or 0,
        tags=tags if tags is not None else [],
    )


async def list_all_admin(
    status: ActionStatus | None = None,
    engine: ActionEngine | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[ActionListItem], PaginationInfo]:
    """List all actions for admin dashboard with execution counts (Story 2.4, AC #2).

    DBOPS only - no RBAC filtering. Returns all actions regardless of status.
    Story 2.23: category filter removed — use tags instead.

    Args:
        status: Optional status filter
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
        SELECT ID, NAME, STATUS, ENGINE, CREATED_AT,
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

    # Story 2.6: attach tags per action (batch query)
    action_ids = [row[0] for row in rows]
    tags_map = await get_tags_for_actions(action_ids)

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

    return [_row_to_action_list_item(row, tags=tags_map.get(row[0], [])) for row in rows], pagination
