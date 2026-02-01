"""Execution repository using raw SQL via python-oracledb (Story 4.1, Task 1.2).

Handles CRUD operations for EXECUTIONS table with:
- CLOB columns for JSON (parameters)
- Parameterized queries for security
- Structured logging with correlation_id
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any

import structlog

from app.core.database import get_connection
from app.models.execution import (
    ExecutionStatus,
    ExecutionEnvironment,
    ExecutionResponse,
    ExecutionCreateResponse,
    StepStatus,
    StepType,
    ExecutionStepResponse,
    ExecutionStepCreate,
)

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


def _row_to_execution_response(
    row: tuple,
    action_name: str | None = None,
    user_display_name: str | None = None,
    approved_by: int | None = None,
    approved_at: datetime | None = None,
    approval_comment: str | None = None,
) -> ExecutionResponse:
    """Convert database row to ExecutionResponse model.

    Expected row order (10 columns):
    0:ID, 1:ACTION_ID, 2:USER_ID, 3:ENVIRONMENT, 4:PARAMETERS,
    5:STATUS, 6:SERVICENOW_CHANGE_ID, 7:STARTED_AT, 8:COMPLETED_AT, 9:CREATED_AT

    Story 7.4: Optional approval fields passed separately.
    """
    return ExecutionResponse(
        id=row[0],
        action_id=row[1],
        action_name=action_name,
        user_id=row[2],
        user_display_name=user_display_name,
        environment=ExecutionEnvironment(row[3]),
        parameters=_str_to_json(row[4]),
        status=ExecutionStatus(row[5]),
        servicenow_change_id=row[6],
        started_at=row[7],
        completed_at=row[8],
        created_at=row[9],
        approved_by=approved_by,
        approved_at=approved_at,
        approval_comment=approval_comment,
    )


async def create_execution(
    user_id: int,
    action_id: int,
    environment: str,
    parameters: dict[str, Any] | None,
) -> ExecutionCreateResponse:
    """Create a new execution record (Story 4.1, Task 1.2).

    Args:
        user_id: ID of the user initiating the execution
        action_id: ID of the action to execute
        environment: Target environment (dev, staging, prod)
        parameters: Execution parameters (validated against action's parameters_schema)

    Returns:
        ExecutionCreateResponse with execution_id, status, created_at
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO EXECUTIONS
        (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS)
        VALUES
        (:action_id, :user_id, :environment, :parameters, :status)
        RETURNING ID, CREATED_AT INTO :out_id, :out_created_at
    """
    params = {
        "action_id": action_id,
        "user_id": user_id,
        "environment": environment,
        "parameters": _json_to_str(parameters),
        "status": ExecutionStatus.SUBMITTED.value,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        # Create output variables for RETURNING clause (AsyncConnection has no .var; use cursor.var)
        out_id = cursor.var(int)
        out_created_at = cursor.var(datetime)
        params["out_id"] = out_id
        params["out_created_at"] = out_created_at
        await cursor.execute(query, params)
        await conn.commit()
        cursor.close()

        execution_id = out_id.getvalue()[0]
        created_at = out_created_at.getvalue()[0]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_params = {k: v for k, v in params.items() if k not in ("out_id", "out_created_at", "parameters")}
    logger.info(
        "execution_repository_create",
        duration_ms=duration_ms,
        execution_id=execution_id,
        action_id=action_id,
        user_id=user_id,
        environment=environment,
    )

    return ExecutionCreateResponse(
        execution_id=execution_id,
        status=ExecutionStatus.SUBMITTED,
        created_at=created_at,
    )


async def get_by_id(execution_id: int) -> ExecutionResponse | None:
    """Fetch an execution by ID with action name and approval fields (Story 4.1, Story 7.4).

    Args:
        execution_id: The execution ID to fetch

    Returns:
        ExecutionResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME,
               E.APPROVED_BY, E.APPROVED_AT, E.APPROVAL_COMMENT
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        WHERE E.ID = :execution_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"execution_id": execution_id})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_by_id",
        duration_ms=duration_ms,
        execution_id=execution_id,
        found=row is not None,
    )

    if row is None:
        return None

    # Row has 14 columns: 0-9 execution fields, 10 action_name, 11-13 approval fields
    return _row_to_execution_response(
        row[:10],
        action_name=row[10],
        approved_by=row[11],
        approved_at=row[12],
        approval_comment=row[13],
    )


async def list_by_user(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[ExecutionResponse]:
    """List executions for a user (Story 4.1, Story 7.4 approval fields).

    Args:
        user_id: User ID to filter by
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of ExecutionResponse ordered by created_at DESC
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME,
               E.APPROVED_BY, E.APPROVED_AT, E.APPROVAL_COMMENT
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        WHERE E.USER_ID = :user_id
        ORDER BY E.CREATED_AT DESC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """
    params = {"user_id": user_id, "limit": limit, "offset": offset}

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_list_by_user",
        duration_ms=duration_ms,
        user_id=user_id,
        count=len(rows),
    )

    return [
        _row_to_execution_response(
            row[:10],
            action_name=row[10],
            approved_by=row[11],
            approved_at=row[12],
            approval_comment=row[13],
        )
        for row in rows
    ]


async def count_by_user(user_id: int) -> int:
    """Return total number of executions for a user (Story 4.8, AC4 pagination)."""
    query = "SELECT COUNT(*) FROM EXECUTIONS WHERE USER_ID = :user_id"
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"user_id": user_id})
        row = await cursor.fetchone()
        cursor.close()
    return row[0] if row else 0


async def update_status(
    execution_id: int,
    status: ExecutionStatus,
    servicenow_change_id: str | None = None,
) -> bool:
    """Update execution status (Story 4.1).

    Args:
        execution_id: Execution ID to update
        status: New status
        servicenow_change_id: Optional ServiceNow change ID

    Returns:
        True if updated, False if not found
    """
    start_time = time.perf_counter()

    # Build update query with optional fields
    set_clauses = ["STATUS = :status"]
    params: dict[str, Any] = {"execution_id": execution_id, "status": status.value}

    if servicenow_change_id is not None:
        set_clauses.append("SERVICENOW_CHANGE_ID = :servicenow_change_id")
        params["servicenow_change_id"] = servicenow_change_id

    if status == ExecutionStatus.RUNNING:
        set_clauses.append("STARTED_AT = SYSTIMESTAMP")
    elif status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
        set_clauses.append("COMPLETED_AT = SYSTIMESTAMP")

    query = f"""
        UPDATE EXECUTIONS
        SET {", ".join(set_clauses)}
        WHERE ID = :execution_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_update_status",
        duration_ms=duration_ms,
        execution_id=execution_id,
        status=status.value,
        updated=rowcount > 0,
    )

    return rowcount > 0


async def action_exists(action_id: int) -> bool:
    """Check if an action exists and is published (Story 4.1, Task 1.4).

    Args:
        action_id: Action ID to check

    Returns:
        True if action exists and is published, False otherwise
    """
    query = """
        SELECT 1 FROM ACTIONS_CATALOG
        WHERE ID = :action_id AND STATUS = 'published'
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()
    return row is not None


async def get_action_parameters_schema(action_id: int) -> dict[str, Any] | None:
    """Get parameters_schema for an action (Story 4.1, Task 1.4).

    Args:
        action_id: Action ID

    Returns:
        parameters_schema dict if exists, None otherwise
    """
    query = """
        SELECT PARAMETERS_SCHEMA FROM ACTIONS_CATALOG
        WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()
    if row is None or row[0] is None:
        return None
    return _str_to_json(row[0])


async def get_action_execution_steps(action_id: int) -> list[dict[str, Any]]:
    """Get execution_steps definition for an action (Story 4.3, Task 3.4).

    Args:
        action_id: Action ID

    Returns:
        List of step definitions from ACTIONS_CATALOG.EXECUTION_STEPS CLOB
    """
    query = """
        SELECT EXECUTION_STEPS FROM ACTIONS_CATALOG
        WHERE ID = :action_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()
    if row is None or row[0] is None:
        return []
    return _str_to_json(row[0]) or []


async def get_action_with_integration(action_id: int) -> dict[str, Any] | None:
    """Get action with integration details for execution (Story 4.3, Task 4.3; Story 4.5, Task 2.2).

    Args:
        action_id: Action ID

    Returns:
        Dict with action and integration info, or None if not found
    """
    query = """
        SELECT A.ID, A.NAME, A.PLATFORM, A.EXECUTION_STEPS, A.CHANGE_MODEL_CODE,
               I.ID AS INTEGRATION_ID, I.NAME AS INTEGRATION_NAME,
               I.TYPE AS PLATFORM_TYPE, I.BASE_URL, I.CREDENTIAL_REF, I.AUTH_FLOW,
               I.TOKEN_URL, I.CONFIG
        FROM ACTIONS_CATALOG A
        LEFT JOIN INTEGRATIONS I ON A.INTEGRATION_ID = I.ID
        WHERE A.ID = :action_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()

    if row is None:
        return None

    # CONFIG CLOB: read as string if LOB (Story 5.3)
    config_raw = row[12]
    if config_raw is not None and hasattr(config_raw, "read"):
        config_raw = config_raw.read()
    config = _str_to_json(config_raw) if config_raw else None

    return {
        "id": row[0],
        "name": row[1],
        "platform": row[2],
        "execution_steps": _str_to_json(row[3]) if row[3] else [],
        "change_model_code": row[4],
        "integration": {
            "id": row[5],
            "name": row[6],
            "platform_type": row[7],
            "base_url": row[8],
            "credential_ref": row[9],
            "auth_flow": row[10],
            "token_url": row[11],
            "config": config,
        } if row[5] else None,
    }


# --- Execution Steps Repository Methods (Story 4.3, Task 2.2) ---


def _row_to_step_response(row: tuple) -> ExecutionStepResponse:
    """Convert database row to ExecutionStepResponse model.

    Expected row order (11 columns):
    0:ID, 1:EXECUTION_ID, 2:STEP_ORDER, 3:STEP_NAME, 4:STEP_TYPE,
    5:STATUS, 6:STARTED_AT, 7:COMPLETED_AT, 8:OUTPUT, 9:PLATFORM_JOB_ID, 10:ERROR_MESSAGE
    """
    return ExecutionStepResponse(
        id=row[0],
        execution_id=row[1],
        step_order=row[2],
        step_name=row[3],
        step_type=StepType(row[4]),
        status=StepStatus(row[5]),
        started_at=row[6],
        completed_at=row[7],
        output=_str_to_json(row[8]),
        platform_job_id=row[9],
        error_message=row[10],
    )


async def create_execution_steps(
    execution_id: int,
    steps: list[ExecutionStepCreate],
) -> list[int]:
    """Create execution step records (Story 4.3, Task 2.2).

    Args:
        execution_id: Parent execution ID
        steps: List of steps to create

    Returns:
        List of created step IDs
    """
    start_time = time.perf_counter()
    created_ids = []

    query = """
        INSERT INTO EXECUTION_STEPS
        (EXECUTION_ID, STEP_ORDER, STEP_NAME, STEP_TYPE, STATUS)
        VALUES
        (:execution_id, :step_order, :step_name, :step_type, :status)
        RETURNING ID INTO :out_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        for step in steps:
            out_id = cursor.var(int)
            params = {
                "execution_id": execution_id,
                "step_order": step.step_order,
                "step_name": step.step_name,
                "step_type": step.step_type.value,
                "status": StepStatus.PENDING.value,
                "out_id": out_id,
            }
            await cursor.execute(query, params)
            created_ids.append(out_id.getvalue()[0])
        cursor.close()

        await conn.commit()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_create_steps",
        duration_ms=duration_ms,
        execution_id=execution_id,
        step_count=len(steps),
    )

    return created_ids


async def get_steps_by_execution_id(execution_id: int) -> list[ExecutionStepResponse]:
    """Get all steps for an execution ordered by step_order (Story 4.3, Task 2.2).

    Args:
        execution_id: Execution ID

    Returns:
        List of ExecutionStepResponse ordered by step_order
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, EXECUTION_ID, STEP_ORDER, STEP_NAME, STEP_TYPE,
               STATUS, STARTED_AT, COMPLETED_AT, OUTPUT, PLATFORM_JOB_ID, ERROR_MESSAGE
        FROM EXECUTION_STEPS
        WHERE EXECUTION_ID = :execution_id
        ORDER BY STEP_ORDER
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"execution_id": execution_id})
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_steps",
        duration_ms=duration_ms,
        execution_id=execution_id,
        step_count=len(rows),
    )

    return [_row_to_step_response(row) for row in rows]


async def get_step_by_id(step_id: int) -> ExecutionStepResponse | None:
    """Fetch a single execution step by ID (Story 4.6, Task 1.4).

    Args:
        step_id: Step ID to fetch

    Returns:
        ExecutionStepResponse if found, None otherwise
    """
    query = """
        SELECT ID, EXECUTION_ID, STEP_ORDER, STEP_NAME, STEP_TYPE,
               STATUS, STARTED_AT, COMPLETED_AT, OUTPUT, PLATFORM_JOB_ID, ERROR_MESSAGE
        FROM EXECUTION_STEPS
        WHERE ID = :step_id
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"step_id": step_id})
        row = await cursor.fetchone()
        cursor.close()
    if row is None:
        return None
    return _row_to_step_response(row)


async def update_step_status(
    step_id: int,
    status: StepStatus,
    output: dict[str, Any] | None = None,
    platform_job_id: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Update execution step status (Story 4.3, Task 2.2).

    Args:
        step_id: Step ID to update
        status: New status
        output: Optional JSON output
        platform_job_id: Optional external job ID
        error_message: Optional error message

    Returns:
        True if updated, False if not found
    """
    start_time = time.perf_counter()

    # Build update query with optional fields
    set_clauses = ["STATUS = :status"]
    params: dict[str, Any] = {"step_id": step_id, "status": status.value}

    if status == StepStatus.RUNNING:
        set_clauses.append("STARTED_AT = SYSTIMESTAMP")
    elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
        set_clauses.append("COMPLETED_AT = SYSTIMESTAMP")

    if output is not None:
        set_clauses.append("OUTPUT = :output")
        params["output"] = _json_to_str(output)

    if platform_job_id is not None:
        set_clauses.append("PLATFORM_JOB_ID = :platform_job_id")
        params["platform_job_id"] = platform_job_id

    if error_message is not None:
        set_clauses.append("ERROR_MESSAGE = :error_message")
        params["error_message"] = error_message

    query = f"""
        UPDATE EXECUTION_STEPS
        SET {", ".join(set_clauses)}
        WHERE ID = :step_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_update_step_status",
        duration_ms=duration_ms,
        step_id=step_id,
        status=status.value,
        updated=rowcount > 0,
    )

    return rowcount > 0


async def skip_remaining_steps(execution_id: int) -> int:
    """Mark all pending steps as skipped (Story 4.3, Task 4.6).

    Called when a step fails to skip all subsequent steps.

    Args:
        execution_id: Execution ID

    Returns:
        Number of steps skipped
    """
    query = """
        UPDATE EXECUTION_STEPS
        SET STATUS = :skipped_status, COMPLETED_AT = SYSTIMESTAMP
        WHERE EXECUTION_ID = :execution_id AND STATUS = :pending_status
    """
    params = {
        "execution_id": execution_id,
        "skipped_status": StepStatus.SKIPPED.value,
        "pending_status": StepStatus.PENDING.value,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    logger.info(
        "execution_repository_skip_remaining_steps",
        execution_id=execution_id,
        skipped_count=rowcount,
    )

    return rowcount


# --- Dashboard Repository Methods (Story 5.1, Task 1.2; Story 8.4) ---


def _build_filter_clauses(
    engine: str | None = None,
    environment: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
    table_alias: str = "e",
    action_alias: str = "a",
) -> tuple[list[str], dict[str, Any]]:
    """Build WHERE clauses and bind params for dashboard filters (Story 8.4, Task 2.2).

    Args:
        engine: Filter by engine
        environment: Filter by environment
        tags: Filter by action tags
        status: Filter by execution status
        from_date: Custom period start
        to_date: Custom period end
        table_alias: Alias for EXECUTIONS table (default 'e')
        action_alias: Alias for ACTIONS_CATALOG table (default 'a')

    Returns:
        Tuple of (where_clauses list, bind_params dict)
    """
    where_clauses: list[str] = []
    bind_params: dict[str, Any] = {}

    if engine:
        where_clauses.append(f"{action_alias}.ENGINE = :filter_engine")
        bind_params["filter_engine"] = engine

    if environment:
        where_clauses.append(f"{table_alias}.ENVIRONMENT = :filter_environment")
        bind_params["filter_environment"] = environment

    if tags:
        # Tags via junction table ACTION_TAGS
        tag_placeholders = ", ".join([f":filter_tag{i}" for i in range(len(tags))])
        where_clauses.append(f"""
            {table_alias}.ACTION_ID IN (
                SELECT at.ACTION_ID FROM ACTION_TAGS at
                JOIN TAGS t ON t.ID = at.TAG_ID
                WHERE t.NAME IN ({tag_placeholders})
            )
        """)
        for i, tag in enumerate(tags):
            bind_params[f"filter_tag{i}"] = tag

    if status:
        where_clauses.append(f"{table_alias}.STATUS = :filter_status")
        bind_params["filter_status"] = status

    if from_date:
        where_clauses.append(f"TRUNC({table_alias}.CREATED_AT) >= :filter_from_date")
        bind_params["filter_from_date"] = from_date

    if to_date:
        where_clauses.append(f"TRUNC({table_alias}.CREATED_AT) <= :filter_to_date")
        bind_params["filter_to_date"] = to_date

    return where_clauses, bind_params


async def get_dashboard_stats(
    days: int = 14,
    engine: str | None = None,
    environment: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
) -> dict[str, Any]:
    """Get aggregated dashboard statistics (Story 5.1, AC1, AC4; Story 8.3, AC6; Story 8.4, AC7).

    Args:
        days: Number of days for period filter (default 14). Used when from_date/to_date not provided.
        engine: Filter by database engine (Story 8.4)
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days parameter (Story 8.4)
        to_date: Custom period end - overrides days parameter (Story 8.4)

    Returns:
        Dict with:
        - executions_jour: Count of executions created today (always current day, not filtered by period)
        - taux_succes_pct: Success rate % over selected period (COMPLETED / (COMPLETED + FAILED) * 100)
        - executions_en_cours: Count of running/pending executions (always current)
        - executions_en_erreur: Count of failed executions in selected period
    """
    start_time = time.perf_counter()

    # Build filter clauses (Story 8.4)
    # Note: status filter is intentionally excluded from base filters because:
    # - executions_jour counts all executions today regardless of status
    # - executions_en_cours specifically counts SUBMITTED/RUNNING/PENDING_APPROVAL
    # - executions_en_erreur specifically counts FAILED
    # - taux_succes counts COMPLETED/(COMPLETED+FAILED)
    # Adding a status filter would make these metrics inconsistent
    # If status filter is needed, it should be applied at the API level documentation
    filter_clauses, filter_params = _build_filter_clauses(
        engine=engine,
        environment=environment,
        tags=tags,
        status=None,  # Status filter intentionally excluded - see comment above
        from_date=None,  # Period filter handled separately
        to_date=None,
        table_alias="e",
        action_alias="a",
    )

    # Build period condition based on custom dates or days
    if from_date and to_date:
        period_condition = "TRUNC(e.CREATED_AT) >= :period_from AND TRUNC(e.CREATED_AT) <= :period_to"
        filter_params["period_from"] = from_date
        filter_params["period_to"] = to_date
    else:
        period_condition = "e.CREATED_AT >= SYSDATE - :days"
        filter_params["days"] = days

    # Base filter for JOIN (engine, environment, tags)
    base_filter = " AND ".join(filter_clauses) if filter_clauses else "1=1"

    # Query with dynamic filters
    # executions_jour: Always today, applies engine/environment/tags filters but NOT period
    # executions_en_cours: Always current running, applies all filters
    # executions_en_erreur, completed_period, failed_period: Apply all filters + period
    query = f"""
        SELECT
            (SELECT COUNT(*) FROM EXECUTIONS e
             LEFT JOIN ACTIONS_CATALOG a ON a.ID = e.ACTION_ID
             WHERE TRUNC(e.CREATED_AT) = TRUNC(SYSDATE)
             AND ({base_filter})) AS executions_jour,
            (SELECT COUNT(*) FROM EXECUTIONS e
             LEFT JOIN ACTIONS_CATALOG a ON a.ID = e.ACTION_ID
             WHERE e.STATUS IN ('SUBMITTED', 'RUNNING', 'PENDING_APPROVAL')
             AND ({base_filter})) AS executions_en_cours,
            (SELECT COUNT(*) FROM EXECUTIONS e
             LEFT JOIN ACTIONS_CATALOG a ON a.ID = e.ACTION_ID
             WHERE e.STATUS = 'FAILED' AND {period_condition}
             AND ({base_filter})) AS executions_en_erreur,
            (SELECT COUNT(*) FROM EXECUTIONS e
             LEFT JOIN ACTIONS_CATALOG a ON a.ID = e.ACTION_ID
             WHERE e.STATUS = 'COMPLETED' AND {period_condition}
             AND ({base_filter})) AS completed_period,
            (SELECT COUNT(*) FROM EXECUTIONS e
             LEFT JOIN ACTIONS_CATALOG a ON a.ID = e.ACTION_ID
             WHERE e.STATUS = 'FAILED' AND {period_condition}
             AND ({base_filter})) AS failed_period
        FROM DUAL
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, filter_params)
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    executions_jour = row[0] or 0
    executions_en_cours = row[1] or 0
    executions_en_erreur = row[2] or 0
    completed_period = row[3] or 0
    failed_period = row[4] or 0

    # Calculate success rate: avoid division by zero
    total_finished = completed_period + failed_period
    taux_succes_pct = round((completed_period / total_finished) * 100, 1) if total_finished > 0 else 0.0

    logger.debug(
        "execution_repository_get_dashboard_stats",
        duration_ms=duration_ms,
        days=days,
        engine=engine,
        environment=environment,
        executions_jour=executions_jour,
        taux_succes_pct=taux_succes_pct,
    )

    return {
        "executions_jour": executions_jour,
        "taux_succes_pct": taux_succes_pct,
        "executions_en_cours": executions_en_cours,
        "executions_en_erreur": executions_en_erreur,
    }


async def list_recent_executions(limit: int = 100) -> list[dict[str, Any]]:
    """List recent executions for dashboard (Story 5.1, AC2, AC4).

    Returns:
    - All executions from the **last 24 hours** (same window as stats: executions_en_erreur, taux_succes_pct).
    - Plus **all executions currently running/pending** (SUBMITTED, RUNNING, PENDING_APPROVAL),
      so the table shows the same "en cours" as the stat card even if they started >24h ago.
    From ALL users (DBA/DBOPS visibility). Includes platform and engine from the action.

    Args:
        limit: Maximum number of executions to return (default 100)

    Returns:
        List of dicts with: id, action_name, user_display_name, environment, status, created_at, platform, engine
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, A.NAME AS ACTION_NAME, U.DISPLAY_NAME AS USER_DISPLAY_NAME,
               E.ENVIRONMENT, E.STATUS, E.CREATED_AT, A.PLATFORM, A.ENGINE
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        LEFT JOIN USERS U ON U.ID = E.USER_ID
        WHERE (E.CREATED_AT >= SYSDATE - 1)
           OR (E.STATUS IN ('SUBMITTED', 'RUNNING', 'PENDING_APPROVAL'))
        ORDER BY E.CREATED_AT DESC
        FETCH FIRST :limit ROWS ONLY
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"limit": limit})
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_list_recent_executions",
        duration_ms=duration_ms,
        count=len(rows),
    )

    return [
        {
            "id": row[0],
            "action_name": row[1],
            "user_display_name": row[2] or "Unknown",
            "environment": row[3],
            "status": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "platform": row[6],
            "engine": row[7],
        }
        for row in rows
    ]


async def get_dashboard_timeseries(
    days: int = 14,
    engine: str | None = None,
    environment: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
) -> list[dict[str, Any]]:
    """Get execution counts over time for dashboard line chart (Story 8.4, AC7).

    Returns daily counts of COMPLETED (success) and FAILED for the last N days.

    Args:
        days: Number of days to include (default 14). Used when from_date/to_date not provided.
        engine: Filter by database engine (Story 8.4)
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4) - not used here since we track success/failed
        from_date: Custom period start - overrides days parameter (Story 8.4)
        to_date: Custom period end - overrides days parameter (Story 8.4)

    Returns:
        List of dicts with: date (YYYY-MM-DD), success, failed
    """
    start_time = time.perf_counter()

    # Build filter clauses (Story 8.4) - status excluded since we always count success/failed
    filter_clauses, filter_params = _build_filter_clauses(
        engine=engine,
        environment=environment,
        tags=tags,
        status=None,  # Not filtering by status - we count success/failed
        from_date=None,  # Period handled separately
        to_date=None,
        table_alias="e",
        action_alias="a",
    )

    # Determine date range
    if from_date and to_date:
        # Custom period
        period_condition = "TRUNC(e.CREATED_AT) >= :period_from AND TRUNC(e.CREATED_AT) <= :period_to"
        filter_params["period_from"] = from_date
        filter_params["period_to"] = to_date
        # Calculate actual days for filling date range
        from datetime import date as date_type
        if isinstance(from_date, date_type):
            start_date = from_date
            end_date = to_date
        else:
            start_date = from_date
            end_date = to_date
        use_custom_range = True
    else:
        period_condition = "e.CREATED_AT >= TRUNC(SYSDATE) - :days"
        filter_params["days"] = days
        use_custom_range = False

    # Combine period condition with filters
    where_parts = [period_condition] + filter_clauses
    where_clause = " AND ".join(where_parts)

    # Oracle: group by TRUNC(created_at), count by status
    query = f"""
        SELECT TRUNC(e.CREATED_AT) AS EXEC_DATE,
               SUM(CASE WHEN e.STATUS = 'COMPLETED' THEN 1 ELSE 0 END) AS SUCCESS,
               SUM(CASE WHEN e.STATUS = 'FAILED' THEN 1 ELSE 0 END) AS FAILED
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE {where_clause}
        GROUP BY TRUNC(e.CREATED_AT)
        ORDER BY EXEC_DATE ASC
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, filter_params)
        rows = await cursor.fetchall()
        cursor.close()

    # Build full date range with zeros for missing days
    today = datetime.now().date()
    date_to_counts: dict[str, dict[str, Any]] = {}

    if use_custom_range:
        # Use custom date range
        current = start_date
        while current <= end_date:
            key = current.strftime("%Y-%m-%d")
            date_to_counts[key] = {"date": key, "success": 0, "failed": 0}
            current += timedelta(days=1)
    else:
        # Use days parameter
        for i in range(days):
            dt = today - timedelta(days=days - 1 - i)
            key = dt.strftime("%Y-%m-%d")
            date_to_counts[key] = {"date": key, "success": 0, "failed": 0}

    for row in rows:
        exec_date = row[0]
        if hasattr(exec_date, "strftime"):
            key = exec_date.strftime("%Y-%m-%d")
        else:
            key = str(exec_date)[:10]
        if key in date_to_counts:
            date_to_counts[key]["success"] = row[1] or 0
            date_to_counts[key]["failed"] = row[2] or 0

    result = sorted(date_to_counts.values(), key=lambda x: x["date"])
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_dashboard_timeseries",
        duration_ms=duration_ms,
        days=days,
        engine=engine,
        environment=environment,
    )
    return result


# --- Story 7.4: Approval Workflow Repository Methods ---


async def create_execution_pending_approval(
    user_id: int,
    action_id: int,
    environment: str,
    parameters: dict[str, Any] | None,
) -> ExecutionCreateResponse:
    """Create execution with PENDING_APPROVAL status (Story 7.4, AC1).

    Does NOT trigger background execution - waits for DBA approval.

    Args:
        user_id: ID of the user initiating the execution
        action_id: ID of the action to execute
        environment: Target environment (dev, staging, prod)
        parameters: Execution parameters

    Returns:
        ExecutionCreateResponse with execution_id, status=PENDING_APPROVAL, created_at
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO EXECUTIONS
        (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS)
        VALUES
        (:action_id, :user_id, :environment, :parameters, :status)
        RETURNING ID, CREATED_AT INTO :out_id, :out_created_at
    """
    params = {
        "action_id": action_id,
        "user_id": user_id,
        "environment": environment,
        "parameters": _json_to_str(parameters),
        "status": ExecutionStatus.PENDING_APPROVAL.value,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        out_id = cursor.var(int)
        out_created_at = cursor.var(datetime)
        params["out_id"] = out_id
        params["out_created_at"] = out_created_at
        await cursor.execute(query, params)
        await conn.commit()
        cursor.close()

        execution_id = out_id.getvalue()[0]
        created_at = out_created_at.getvalue()[0]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_create_pending_approval",
        duration_ms=duration_ms,
        execution_id=execution_id,
        action_id=action_id,
        user_id=user_id,
        environment=environment,
    )

    return ExecutionCreateResponse(
        execution_id=execution_id,
        status=ExecutionStatus.PENDING_APPROVAL,
        created_at=created_at,
    )


async def approve(
    execution_id: int,
    approver_id: int,
    comment: str | None = None,
) -> bool:
    """Approve an execution pending approval (Story 7.4, AC3).

    Updates:
    - STATUS: PENDING_APPROVAL -> SUBMITTED
    - APPROVED_BY: approver user ID
    - APPROVED_AT: current timestamp
    - APPROVAL_COMMENT: optional comment

    Args:
        execution_id: Execution ID to approve
        approver_id: User ID of the DBA approving
        comment: Optional approval comment

    Returns:
        True if approved, False if not found or wrong status
    """
    start_time = time.perf_counter()

    query = """
        UPDATE EXECUTIONS
        SET STATUS = :new_status,
            APPROVED_BY = :approver_id,
            APPROVED_AT = SYSTIMESTAMP,
            APPROVAL_COMMENT = :comment
        WHERE ID = :execution_id AND STATUS = :current_status
    """
    params = {
        "execution_id": execution_id,
        "new_status": ExecutionStatus.SUBMITTED.value,
        "current_status": ExecutionStatus.PENDING_APPROVAL.value,
        "approver_id": approver_id,
        "comment": comment,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_approve",
        duration_ms=duration_ms,
        execution_id=execution_id,
        approver_id=approver_id,
        approved=rowcount > 0,
    )

    return rowcount > 0


async def reject(
    execution_id: int,
    rejector_id: int,
    comment: str | None = None,
) -> bool:
    """Reject an execution pending approval (Story 7.4, AC4).

    Updates:
    - STATUS: PENDING_APPROVAL -> REJECTED
    - APPROVED_BY: rejector user ID (who made the decision)
    - APPROVED_AT: current timestamp
    - APPROVAL_COMMENT: rejection reason

    Args:
        execution_id: Execution ID to reject
        rejector_id: User ID of the DBA rejecting
        comment: Optional rejection comment

    Returns:
        True if rejected, False if not found or wrong status
    """
    start_time = time.perf_counter()

    query = """
        UPDATE EXECUTIONS
        SET STATUS = :new_status,
            APPROVED_BY = :rejector_id,
            APPROVED_AT = SYSTIMESTAMP,
            APPROVAL_COMMENT = :comment,
            COMPLETED_AT = SYSTIMESTAMP
        WHERE ID = :execution_id AND STATUS = :current_status
    """
    params = {
        "execution_id": execution_id,
        "new_status": ExecutionStatus.REJECTED.value,
        "current_status": ExecutionStatus.PENDING_APPROVAL.value,
        "rejector_id": rejector_id,
        "comment": comment,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_reject",
        duration_ms=duration_ms,
        execution_id=execution_id,
        rejector_id=rejector_id,
        rejected=rowcount > 0,
    )

    return rowcount > 0


async def list_pending_approvals(
    limit: int = 50,
    offset: int = 0,
) -> list[ExecutionResponse]:
    """List executions pending approval (Story 7.4, AC2, AC6).

    Returns all PENDING_APPROVAL executions for DBA review.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of ExecutionResponse with PENDING_APPROVAL status
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME,
               U.DISPLAY_NAME AS USER_DISPLAY_NAME
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        LEFT JOIN USERS U ON U.ID = E.USER_ID
        WHERE E.STATUS = :status
        ORDER BY E.CREATED_AT ASC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """
    params = {
        "status": ExecutionStatus.PENDING_APPROVAL.value,
        "limit": limit,
        "offset": offset,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_list_pending_approvals",
        duration_ms=duration_ms,
        count=len(rows),
    )

    return [
        _row_to_execution_response(row[:10], action_name=row[10], user_display_name=row[11])
        for row in rows
    ]


async def count_pending_approvals() -> int:
    """Count pending approval executions (Story 7.4, AC6).

    Returns:
        Number of executions with PENDING_APPROVAL status
    """
    query = "SELECT COUNT(*) FROM EXECUTIONS WHERE STATUS = :status"
    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"status": ExecutionStatus.PENDING_APPROVAL.value})
        row = await cursor.fetchone()
        cursor.close()
    return row[0] if row else 0


async def get_by_id_with_approval(execution_id: int) -> dict[str, Any] | None:
    """Fetch execution by ID with approval details (Story 7.4, AC3, AC4).

    Args:
        execution_id: The execution ID to fetch

    Returns:
        Dict with execution fields + approved_by, approved_at, approval_comment
    """
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME,
               E.APPROVED_BY, E.APPROVED_AT, E.APPROVAL_COMMENT,
               U.DISPLAY_NAME AS REQUESTER_NAME,
               AU.DISPLAY_NAME AS APPROVER_NAME
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        LEFT JOIN USERS U ON U.ID = E.USER_ID
        LEFT JOIN USERS AU ON AU.ID = E.APPROVED_BY
        WHERE E.ID = :execution_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"execution_id": execution_id})
        row = await cursor.fetchone()
        cursor.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "action_id": row[1],
        "user_id": row[2],
        "environment": row[3],
        "parameters": _str_to_json(row[4]),
        "status": row[5],
        "servicenow_change_id": row[6],
        "started_at": row[7],
        "completed_at": row[8],
        "created_at": row[9],
        "action_name": row[10],
        "approved_by": row[11],
        "approved_at": row[12],
        "approval_comment": row[13],
        "requester_name": row[14],
        "approver_name": row[15],
    }


# --- Story 8.1: Action Stats Repository Methods ---

# Default period for action stats calculation (Story 8.1, AC5)
ACTION_STATS_DEFAULT_DAYS = 30


async def get_action_stats(action_id: int) -> dict[str, Any] | None:
    """Get aggregated execution stats for a specific action (Story 8.1, AC4, AC5).

    Calculates metrics over the last 30 days:
    - total_executions: Count of all executions
    - completed_count: Count of COMPLETED executions
    - failed_count: Count of FAILED executions (incidents)
    - success_rate: (completed / (completed + failed)) * 100, None if no executions
    - avg_execution_time_ms: Average execution time in milliseconds for COMPLETED executions

    Args:
        action_id: ID of the action to get stats for

    Returns:
        Dict with stats or None if action not found or no executions
    """
    start_time = time.perf_counter()
    query = """
        SELECT
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND CREATED_AT >= SYSDATE - :days) AS total_executions,
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND STATUS = 'COMPLETED' AND CREATED_AT >= SYSDATE - :days) AS completed_count,
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND STATUS = 'FAILED' AND CREATED_AT >= SYSDATE - :days) AS failed_count,
            (SELECT AVG(
                (CAST(COMPLETED_AT AS DATE) - CAST(STARTED_AT AS DATE)) * 24 * 60 * 60 * 1000
             ) FROM EXECUTIONS
             WHERE ACTION_ID = :action_id AND STATUS = 'COMPLETED'
             AND COMPLETED_AT IS NOT NULL AND STARTED_AT IS NOT NULL
             AND CREATED_AT >= SYSDATE - :days) AS avg_duration_ms
        FROM DUAL
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id, "days": ACTION_STATS_DEFAULT_DAYS})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    total_executions = row[0] or 0
    completed_count = row[1] or 0
    failed_count = row[2] or 0
    avg_duration_ms = row[3]

    # Calculate success rate: avoid division by zero
    total_finished = completed_count + failed_count
    success_rate = round((completed_count / total_finished) * 100, 1) if total_finished > 0 else None

    # Round avg_duration_ms if present
    avg_execution_time_ms = round(avg_duration_ms) if avg_duration_ms is not None else None

    logger.debug(
        "execution_repository_get_action_stats",
        duration_ms=duration_ms,
        action_id=action_id,
        total_executions=total_executions,
        success_rate=success_rate,
    )

    # Return None if no executions at all (AC3: "Pas encore de donnees")
    if total_executions == 0:
        return None

    return {
        "success_rate": success_rate,
        "avg_execution_time_ms": avg_execution_time_ms,
        "total_executions": total_executions,
        "incidents_count": failed_count,
    }


# --- Story 8.2: Admin Analytics Repository Methods ---

# Default period for admin analytics (Story 8.2, AC3)
ADMIN_ANALYTICS_DEFAULT_DAYS = 90


async def get_admin_analytics(days: int = ADMIN_ANALYTICS_DEFAULT_DAYS) -> dict[str, Any]:
    """Get aggregated admin analytics for dashboards (Story 8.2, AC1, AC4).

    Calculates metrics over the specified period:
    - total_published_actions: Count of published actions
    - executions_by_engine: Aggregated by engine (GROUP BY)
    - executions_by_profile: Aggregated by user profile (GROUP BY)
    - adoption_trend: Weekly trend per engine (TRUNC by ISO week)

    Args:
        days: Number of days for period filter (30, 90, 365)

    Returns:
        Dict with all analytics data for AdminAnalyticsResponse
    """
    start_time = time.perf_counter()

    # Query 1: Count published actions
    published_query = """
        SELECT COUNT(*) AS total FROM ACTIONS_CATALOG WHERE STATUS = 'published'
    """

    # Query 2: Executions by engine
    by_engine_query = """
        SELECT
            NVL(a.ENGINE, 'N/A') AS engine,
            COUNT(*) AS count
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE e.CREATED_AT >= SYSDATE - :days
        GROUP BY NVL(a.ENGINE, 'N/A')
        ORDER BY count DESC
    """

    # Query 3: Executions by profile
    by_profile_query = """
        SELECT
            NVL(p.NAME, 'unknown') AS profile,
            COUNT(*) AS count
        FROM EXECUTIONS e
        LEFT JOIN USERS u ON e.USER_ID = u.ID
        LEFT JOIN PROFILES p ON LOWER(u.PROFILE) = LOWER(p.NAME)
        WHERE e.CREATED_AT >= SYSDATE - :days
        GROUP BY NVL(p.NAME, 'unknown')
        ORDER BY count DESC
    """

    # Query 4: Weekly adoption trend per engine (ISO week via TRUNC IW)
    trend_query = """
        SELECT
            TO_CHAR(TRUNC(e.CREATED_AT, 'IW'), 'YYYY-MM-DD') AS week_start,
            NVL(a.ENGINE, 'N/A') AS engine,
            COUNT(*) AS count
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE e.CREATED_AT >= SYSDATE - :days
        GROUP BY TRUNC(e.CREATED_AT, 'IW'), NVL(a.ENGINE, 'N/A')
        ORDER BY week_start, engine
    """

    async with get_connection() as conn:
        cursor = conn.cursor()

        # Execute all queries
        await cursor.execute(published_query)
        published_row = await cursor.fetchone()
        total_published = published_row[0] if published_row else 0

        await cursor.execute(by_engine_query, {"days": days})
        engine_rows = await cursor.fetchall()

        await cursor.execute(by_profile_query, {"days": days})
        profile_rows = await cursor.fetchall()

        await cursor.execute(trend_query, {"days": days})
        trend_rows = await cursor.fetchall()

        cursor.close()

    # Transform results
    executions_by_engine = [
        {"engine": row[0], "count": row[1]}
        for row in engine_rows
    ]

    executions_by_profile = [
        {"profile": row[0], "count": row[1]}
        for row in profile_rows
    ]

    adoption_trend = [
        {"week_start": row[0], "engine": row[1], "count": row[2]}
        for row in trend_rows
    ]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "execution_repository_get_admin_analytics",
        duration_ms=duration_ms,
        days=days,
        total_published=total_published,
        engine_groups=len(executions_by_engine),
        profile_groups=len(executions_by_profile),
        trend_points=len(adoption_trend),
    )

    return {
        "total_published_actions": total_published,
        "executions_by_engine": executions_by_engine,
        "executions_by_profile": executions_by_profile,
        "adoption_trend": adoption_trend,
    }


# --- Story 8.3: Dashboard Reporting Repository Methods ---

# Default period for dashboard reporting stats
DASHBOARD_REPORTING_DEFAULT_DAYS = 14


async def get_stats_by_technology(
    days: int = DASHBOARD_REPORTING_DEFAULT_DAYS,
    environment: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
) -> list[dict[str, Any]]:
    """Get aggregated execution stats by database engine (Story 8.3, AC3, AC7; Story 8.4, AC7).

    Aggregates executions by engine from ACTIONS_CATALOG, calculating:
    - count: Total executions per engine
    - success_rate: Percentage of successful executions (COMPLETED / (COMPLETED + FAILED) * 100)

    Args:
        days: Number of days to include (default 14). Used when from_date/to_date not provided.
        environment: Filter by environment (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days parameter (Story 8.4)
        to_date: Custom period end - overrides days parameter (Story 8.4)

    Note: engine is not a filter here since it's the grouping key.

    Returns:
        List of dicts with: engine, count, success_rate (ordered by count DESC)
    """
    start_time = time.perf_counter()

    # Build filter clauses (Story 8.4) - engine excluded since it's the GROUP BY key
    filter_clauses, filter_params = _build_filter_clauses(
        engine=None,  # Not filtering by engine - it's the grouping
        environment=environment,
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
        table_alias="e",
        action_alias="a",
    )

    # Build period condition based on custom dates or days
    if from_date and to_date:
        period_condition = "TRUNC(e.CREATED_AT) >= :period_from AND TRUNC(e.CREATED_AT) <= :period_to"
        filter_params["period_from"] = from_date
        filter_params["period_to"] = to_date
    else:
        period_condition = "e.CREATED_AT >= SYSDATE - :days"
        filter_params["days"] = days

    # Combine period condition with filters
    where_parts = [period_condition] + filter_clauses
    where_clause = " AND ".join(where_parts)

    query = f"""
        SELECT
            NVL(a.ENGINE, 'N/A') AS engine,
            COUNT(*) AS total_count,
            SUM(CASE WHEN e.STATUS = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN e.STATUS = 'FAILED' THEN 1 ELSE 0 END) AS failed
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE {where_clause}
        GROUP BY NVL(a.ENGINE, 'N/A')
        ORDER BY total_count DESC
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, filter_params)
        rows = await cursor.fetchall()
        cursor.close()

    result = []
    for row in rows:
        engine = row[0]
        total_count = row[1] or 0
        completed = row[2] or 0
        failed = row[3] or 0

        # Calculate success rate: avoid division by zero
        total_finished = completed + failed
        success_rate = round((completed / total_finished) * 100, 1) if total_finished > 0 else None

        result.append({
            "engine": engine,
            "count": total_count,
            "success_rate": success_rate,
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_stats_by_technology",
        duration_ms=duration_ms,
        days=days,
        environment=environment,
        engine_count=len(result),
    )

    return result


async def get_stats_by_environment(
    days: int = DASHBOARD_REPORTING_DEFAULT_DAYS,
    engine: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    from_date: Any = None,
    to_date: Any = None,
) -> list[dict[str, Any]]:
    """Get aggregated execution stats by environment (Story 8.3, AC4, AC7; Story 8.4, AC7).

    Aggregates executions by environment, calculating:
    - count: Total executions per environment
    - success_rate: Percentage of successful executions (COMPLETED / (COMPLETED + FAILED) * 100)

    Results are ordered logically: dev, staging, prod, then alphabetical for others.

    Args:
        days: Number of days to include (default 14). Used when from_date/to_date not provided.
        engine: Filter by database engine (Story 8.4)
        tags: Filter by action tags (Story 8.4)
        status: Filter by execution status (Story 8.4)
        from_date: Custom period start - overrides days parameter (Story 8.4)
        to_date: Custom period end - overrides days parameter (Story 8.4)

    Note: environment is not a filter here since it's the grouping key.

    Returns:
        List of dicts with: environment, count, success_rate
    """
    start_time = time.perf_counter()

    # Build filter clauses (Story 8.4) - environment excluded since it's the GROUP BY key
    filter_clauses, filter_params = _build_filter_clauses(
        engine=engine,
        environment=None,  # Not filtering by environment - it's the grouping
        tags=tags,
        status=status,
        from_date=from_date,
        to_date=to_date,
        table_alias="e",
        action_alias="a",
    )

    # Build period condition based on custom dates or days
    if from_date and to_date:
        period_condition = "TRUNC(e.CREATED_AT) >= :period_from AND TRUNC(e.CREATED_AT) <= :period_to"
        filter_params["period_from"] = from_date
        filter_params["period_to"] = to_date
    else:
        period_condition = "e.CREATED_AT >= SYSDATE - :days"
        filter_params["days"] = days

    # Combine period condition with filters
    where_parts = [period_condition] + filter_clauses
    where_clause = " AND ".join(where_parts)

    query = f"""
        SELECT
            e.ENVIRONMENT,
            COUNT(*) AS total_count,
            SUM(CASE WHEN e.STATUS = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN e.STATUS = 'FAILED' THEN 1 ELSE 0 END) AS failed
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE {where_clause}
        GROUP BY e.ENVIRONMENT
        ORDER BY
            CASE e.ENVIRONMENT
                WHEN 'dev' THEN 1
                WHEN 'staging' THEN 2
                WHEN 'prod' THEN 3
                ELSE 4
            END,
            e.ENVIRONMENT
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, filter_params)
        rows = await cursor.fetchall()
        cursor.close()

    result = []
    for row in rows:
        environment = row[0]
        total_count = row[1] or 0
        completed = row[2] or 0
        failed = row[3] or 0

        # Calculate success rate: avoid division by zero
        total_finished = completed + failed
        success_rate = round((completed / total_finished) * 100, 1) if total_finished > 0 else None

        result.append({
            "environment": environment,
            "count": total_count,
            "success_rate": success_rate,
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_stats_by_environment",
        duration_ms=duration_ms,
        days=days,
        engine=engine,
        environment_count=len(result),
    )

    return result


async def get_filter_options() -> dict[str, list[str]]:
    """Get available filter options for dashboard (Story 8.4, Task 14).

    Returns distinct values for each filter type based on actual data.

    Returns:
        Dict with: engines, environments, tags, statuses
    """
    start_time = time.perf_counter()

    # Query distinct engines from actions with executions
    engines_query = """
        SELECT DISTINCT NVL(a.ENGINE, 'N/A') AS engine
        FROM ACTIONS_CATALOG a
        WHERE a.STATUS = 'published'
        ORDER BY engine
    """

    # Query distinct environments from recent executions
    environments_query = """
        SELECT DISTINCT e.ENVIRONMENT
        FROM EXECUTIONS e
        WHERE e.ENVIRONMENT IS NOT NULL
        ORDER BY
            CASE e.ENVIRONMENT
                WHEN 'dev' THEN 1
                WHEN 'staging' THEN 2
                WHEN 'prod' THEN 3
                ELSE 4
            END,
            e.ENVIRONMENT
    """

    # Query all tags
    tags_query = """
        SELECT t.NAME
        FROM TAGS t
        ORDER BY t.NAME
    """

    # Static list of statuses
    statuses = ["PENDING", "SUBMITTED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", "PENDING_APPROVAL", "REJECTED"]

    async with get_connection() as conn:
        cursor = conn.cursor()

        await cursor.execute(engines_query)
        engine_rows = await cursor.fetchall()

        await cursor.execute(environments_query)
        env_rows = await cursor.fetchall()

        await cursor.execute(tags_query)
        tag_rows = await cursor.fetchall()

        cursor.close()

    engines = [row[0] for row in engine_rows if row[0]]
    environments = [row[0] for row in env_rows if row[0]]
    tags = [row[0] for row in tag_rows if row[0]]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_filter_options",
        duration_ms=duration_ms,
        engines_count=len(engines),
        environments_count=len(environments),
        tags_count=len(tags),
    )

    return {
        "engines": engines,
        "environments": environments,
        "tags": tags,
        "statuses": statuses,
    }
