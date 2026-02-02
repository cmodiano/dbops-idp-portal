"""Scheduled Execution repository using raw SQL via python-oracledb (Story 11.3).

Handles CRUD operations for SCHEDULED_EXECUTIONS table with:
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
from app.models.scheduled_execution import (
    ScheduledExecutionStatus,
    ScheduledExecutionCreateResult,
    ScheduledExecutionWithAction,
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


async def create_scheduled_execution(
    user_id: int,
    action_id: int,
    environment: str,
    parameters: dict[str, Any] | None,
    scheduled_at: datetime,
) -> ScheduledExecutionCreateResult:
    """Create a scheduled execution record (Story 11.3, AC1).

    Args:
        user_id: ID of the user creating the schedule
        action_id: ID of the action to schedule
        environment: Target environment (dev, staging, prod)
        parameters: Execution parameters (validated against action's parameters_schema)
        scheduled_at: Future datetime when execution should run

    Returns:
        ScheduledExecutionCreateResult with id, status, created_at

    Fixes:
        - MEDIUM-4: Add error handling for database connection failures
        - HIGH-2: Foreign key constraints provide TOCTOU protection
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO SCHEDULED_EXECUTIONS
        (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, SCHEDULED_AT, STATUS)
        VALUES
        (:action_id, :user_id, :environment, :parameters, :scheduled_at, :status)
        RETURNING ID, CREATED_AT INTO :out_id, :out_created_at
    """
    params = {
        "action_id": action_id,
        "user_id": user_id,
        "environment": environment,
        "parameters": _json_to_str(parameters),
        "scheduled_at": scheduled_at,
        "status": ScheduledExecutionStatus.PENDING.value,
    }

    # MEDIUM-4 FIX: Add comprehensive error handling
    try:
        async with get_connection() as conn:
            cursor = conn.cursor()
            # Create output variables for RETURNING clause
            out_id = cursor.var(int)
            out_created_at = cursor.var(datetime)
            params["out_id"] = out_id
            params["out_created_at"] = out_created_at

            # HIGH-2 CLARIFICATION: FK_SCHEDULED_EXEC_ACTION constraint provides TOCTOU protection
            # If action is deleted between validation and INSERT, Oracle will raise integrity error
            await cursor.execute(query, params)
            await conn.commit()
            cursor.close()

            scheduled_execution_id = out_id.getvalue()[0]
            created_at = out_created_at.getvalue()[0]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "scheduled_execution_repository_create",
            duration_ms=duration_ms,
            scheduled_execution_id=scheduled_execution_id,
            action_id=action_id,
            user_id=user_id,
            environment=environment,
            scheduled_at=scheduled_at.isoformat(),
        )

        return ScheduledExecutionCreateResult(
            id=scheduled_execution_id,
            status=ScheduledExecutionStatus.PENDING,
            created_at=created_at,
        )

    except Exception as e:
        # MEDIUM-4 FIX: Log database errors with context
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "scheduled_execution_repository_create_failed",
            duration_ms=duration_ms,
            action_id=action_id,
            user_id=user_id,
            environment=environment,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Re-raise to let FastAPI handle it
        raise


async def get_by_id(scheduled_execution_id: int) -> ScheduledExecutionWithAction | None:
    """Get scheduled execution by ID with action metadata (Story 11.3, AC7).

    Args:
        scheduled_execution_id: The scheduled execution ID to fetch

    Returns:
        ScheduledExecutionWithAction if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT
            SE.ID, SE.ACTION_ID, SE.USER_ID, SE.ENVIRONMENT,
            SE.PARAMETERS, SE.SCHEDULED_AT, SE.STATUS,
            SE.CREATED_AT, SE.UPDATED_AT,
            A.NAME AS ACTION_NAME, A.DESCRIPTION AS ACTION_DESCRIPTION
        FROM SCHEDULED_EXECUTIONS SE
        INNER JOIN ACTIONS_CATALOG A ON A.ID = SE.ACTION_ID
        WHERE SE.ID = :scheduled_execution_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"scheduled_execution_id": scheduled_execution_id})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "scheduled_execution_repository_get_by_id",
        duration_ms=duration_ms,
        scheduled_execution_id=scheduled_execution_id,
        found=row is not None,
    )

    if row is None:
        return None

    # Row columns: 0:ID, 1:ACTION_ID, 2:USER_ID, 3:ENVIRONMENT, 4:PARAMETERS,
    # 5:SCHEDULED_AT, 6:STATUS, 7:CREATED_AT, 8:UPDATED_AT, 9:ACTION_NAME, 10:ACTION_DESCRIPTION
    return ScheduledExecutionWithAction(
        id=row[0],
        action_id=row[1],
        user_id=row[2],
        environment=row[3],
        parameters=_str_to_json(row[4]),
        scheduled_at=row[5],
        status=ScheduledExecutionStatus(row[6]),
        created_at=row[7],
        updated_at=row[8],
        action_name=row[9],
        action_description=row[10],
    )


async def action_exists(action_id: int) -> bool:
    """Check if action exists and is published (Story 11.3, AC5).

    Args:
        action_id: The action ID to check

    Returns:
        True if action exists and STATUS='published', False otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT COUNT(*)
        FROM ACTIONS_CATALOG
        WHERE ID = :action_id AND STATUS = 'published'
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()

    exists = row[0] > 0 if row else False

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "scheduled_execution_repository_action_exists",
        duration_ms=duration_ms,
        action_id=action_id,
        exists=exists,
    )

    return exists


async def get_action_parameters_schema(action_id: int) -> dict[str, Any] | None:
    """Get action's parameters_schema for validation (Story 11.3, AC4).

    Args:
        action_id: The action ID

    Returns:
        Parameters schema dict if exists, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT PARAMETERS_SCHEMA
        FROM ACTIONS_CATALOG
        WHERE ID = :action_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"action_id": action_id})
        row = await cursor.fetchone()
        cursor.close()

    if row is None or row[0] is None:
        return None

    schema = _str_to_json(row[0])

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "scheduled_execution_repository_get_action_schema",
        duration_ms=duration_ms,
        action_id=action_id,
        has_schema=schema is not None,
    )

    return schema
