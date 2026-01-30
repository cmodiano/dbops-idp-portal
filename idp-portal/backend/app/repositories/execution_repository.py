"""Execution repository using raw SQL via python-oracledb (Story 4.1, Task 1.2).

Handles CRUD operations for EXECUTIONS table with:
- CLOB columns for JSON (parameters)
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


def _row_to_execution_response(row: tuple, action_name: str | None = None) -> ExecutionResponse:
    """Convert database row to ExecutionResponse model.

    Expected row order (10 columns):
    0:ID, 1:ACTION_ID, 2:USER_ID, 3:ENVIRONMENT, 4:PARAMETERS,
    5:STATUS, 6:SERVICENOW_CHANGE_ID, 7:STARTED_AT, 8:COMPLETED_AT, 9:CREATED_AT
    """
    return ExecutionResponse(
        id=row[0],
        action_id=row[1],
        action_name=action_name,
        user_id=row[2],
        environment=ExecutionEnvironment(row[3]),
        parameters=_str_to_json(row[4]),
        status=ExecutionStatus(row[5]),
        servicenow_change_id=row[6],
        started_at=row[7],
        completed_at=row[8],
        created_at=row[9],
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
        # Create output variables for RETURNING clause
        out_id = conn.var(int)
        out_created_at = conn.var(datetime)
        params["out_id"] = out_id
        params["out_created_at"] = out_created_at

        cursor = await conn.execute(query, params)
        await conn.commit()
        await cursor.close()

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
    """Fetch an execution by ID with action name (Story 4.1).

    Args:
        execution_id: The execution ID to fetch

    Returns:
        ExecutionResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        WHERE E.ID = :execution_id
    """

    async with get_connection() as conn:
        cursor = await conn.execute(query, {"execution_id": execution_id})
        row = await cursor.fetchone()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_by_id",
        duration_ms=duration_ms,
        execution_id=execution_id,
        found=row is not None,
    )

    if row is None:
        return None

    # Row has 11 columns: 0-9 are execution fields, 10 is action_name
    return _row_to_execution_response(row[:10], action_name=row[10])


async def list_by_user(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[ExecutionResponse]:
    """List executions for a user (Story 4.1).

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
               A.NAME AS ACTION_NAME
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        WHERE E.USER_ID = :user_id
        ORDER BY E.CREATED_AT DESC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """
    params = {"user_id": user_id, "limit": limit, "offset": offset}

    async with get_connection() as conn:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_list_by_user",
        duration_ms=duration_ms,
        user_id=user_id,
        count=len(rows),
    )

    return [_row_to_execution_response(row[:10], action_name=row[10]) for row in rows]


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
        cursor = await conn.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        await cursor.close()

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
        cursor = await conn.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()
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
        cursor = await conn.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()
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
        cursor = await conn.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()
    if row is None or row[0] is None:
        return []
    return _str_to_json(row[0]) or []


async def get_action_with_integration(action_id: int) -> dict[str, Any] | None:
    """Get action with integration details for execution (Story 4.3, Task 4.3).

    Args:
        action_id: Action ID

    Returns:
        Dict with action and integration info, or None if not found
    """
    query = """
        SELECT A.ID, A.NAME, A.PLATFORM, A.EXECUTION_STEPS,
               I.ID AS INTEGRATION_ID, I.NAME AS INTEGRATION_NAME,
               I.PLATFORM_TYPE, I.BASE_URL, I.CREDENTIAL_REF, I.AUTH_FLOW
        FROM ACTIONS_CATALOG A
        LEFT JOIN INTEGRATIONS I ON A.INTEGRATION_ID = I.ID
        WHERE A.ID = :action_id
    """
    async with get_connection() as conn:
        cursor = await conn.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "platform": row[2],
        "execution_steps": _str_to_json(row[3]) if row[3] else [],
        "integration": {
            "id": row[4],
            "name": row[5],
            "platform_type": row[6],
            "base_url": row[7],
            "credential_ref": row[8],
            "auth_flow": row[9],
        } if row[4] else None,
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
        for step in steps:
            out_id = conn.var(int)
            params = {
                "execution_id": execution_id,
                "step_order": step.step_order,
                "step_name": step.step_name,
                "step_type": step.step_type.value,
                "status": StepStatus.PENDING.value,
                "out_id": out_id,
            }
            cursor = await conn.execute(query, params)
            await cursor.close()
            created_ids.append(out_id.getvalue()[0])

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
        cursor = await conn.execute(query, {"execution_id": execution_id})
        rows = await cursor.fetchall()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "execution_repository_get_steps",
        duration_ms=duration_ms,
        execution_id=execution_id,
        step_count=len(rows),
    )

    return [_row_to_step_response(row) for row in rows]


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
        cursor = await conn.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        await cursor.close()

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
        cursor = await conn.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        await cursor.close()

    logger.info(
        "execution_repository_skip_remaining_steps",
        execution_id=execution_id,
        skipped_count=rowcount,
    )

    return rowcount
