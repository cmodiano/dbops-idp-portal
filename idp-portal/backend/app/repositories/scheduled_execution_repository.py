"""Scheduled Execution repository using raw SQL via python-oracledb (Story 11.3, 11.7).

Handles CRUD operations for SCHEDULED_EXECUTIONS and RECURRING_PATTERNS tables with:
- CLOB columns for JSON (parameters, pattern_config)
- Parameterized queries for security
- Structured logging with correlation_id
- Recurring pattern support (Story 11.7)
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
    ScheduledExecutionListItem,
    RecurringPatternResponse,
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
    scheduled_at: datetime | None,
    correlation_id: str | None = None,
    recurring_pattern: dict[str, Any] | None = None,
) -> ScheduledExecutionCreateResult:
    """Create a scheduled execution record (Story 11.3, 11.7).

    Args:
        user_id: ID of the user creating the schedule
        action_id: ID of the action to schedule
        environment: Target environment (dev, staging, prod)
        parameters: Execution parameters (validated against action's parameters_schema)
        scheduled_at: Future datetime when execution should run (NULL for recurring)
        correlation_id: Correlation ID for request tracing
        recurring_pattern: Recurring pattern config dict (Story 11.7):
            - pattern_type: 'daily' or 'weekly'
            - pattern_config: {"hour": int, "minute": int} or {"day_of_week": int, ...}
            - next_execution_date: datetime
            - is_active: bool

    Returns:
        ScheduledExecutionCreateResult with id, status, created_at

    Fixes:
        - MEDIUM-4: Add error handling for database connection failures
        - HIGH-2: Foreign key constraints provide TOCTOU protection
    """
    start_time = time.perf_counter()
    # HIGH-1 FIX: Store correlation_id for AC10 request tracing
    query = """
        INSERT INTO SCHEDULED_EXECUTIONS
        (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, SCHEDULED_AT, STATUS, CORRELATION_ID)
        VALUES
        (:action_id, :user_id, :environment, :parameters, :scheduled_at, :status, :correlation_id)
        RETURNING ID, CREATED_AT INTO :out_id, :out_created_at
    """
    params = {
        "action_id": action_id,
        "user_id": user_id,
        "environment": environment,
        "parameters": _json_to_str(parameters),
        "scheduled_at": scheduled_at,  # NULL for recurring patterns (Story 11.7)
        "status": ScheduledExecutionStatus.PENDING.value,
        "correlation_id": correlation_id,  # HIGH-1 FIX
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

            scheduled_execution_id = out_id.getvalue()[0]
            created_at = out_created_at.getvalue()[0]

            # Story 11.7: Insert RECURRING_PATTERNS if provided
            if recurring_pattern:
                query_rp = """
                    INSERT INTO RECURRING_PATTERNS
                    (SCHEDULED_EXECUTION_ID, PATTERN_TYPE, PATTERN_CONFIG, NEXT_EXECUTION_DATE, IS_ACTIVE)
                    VALUES
                    (:scheduled_execution_id, :pattern_type, :pattern_config, :next_execution_date, :is_active)
                """
                await cursor.execute(
                    query_rp,
                    {
                        "scheduled_execution_id": scheduled_execution_id,
                        "pattern_type": recurring_pattern["pattern_type"],
                        "pattern_config": _json_to_str(recurring_pattern["pattern_config"]),
                        "next_execution_date": recurring_pattern["next_execution_date"],
                        "is_active": 1 if recurring_pattern["is_active"] else 0,
                    },
                )

            await conn.commit()
            cursor.close()

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "scheduled_execution_repository_create",
            duration_ms=duration_ms,
            scheduled_execution_id=scheduled_execution_id,
            action_id=action_id,
            user_id=user_id,
            environment=environment,
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
            has_recurring_pattern=recurring_pattern is not None,
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


async def list_scheduled_executions(
    user_id: int | None = None,
    status: str | None = None,
    action_id: int | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ScheduledExecutionListItem]:
    """List scheduled executions with filters and enrichment (Story 11.6, 11.7).

    Args:
        user_id: Filter by user ID (None = all users for DBOPS)
        status: Filter by status (pending, executed, cancelled)
        action_id: Filter by action ID
        scheduled_from: Filter scheduled_at >= scheduled_from (or next_execution_date for recurring)
        scheduled_to: Filter scheduled_at <= scheduled_to (or next_execution_date for recurring)
        limit: Max results to return
        offset: Results offset for pagination

    Returns:
        List of ScheduledExecutionListItem with action_name, user_name, and recurring_pattern enriched
    """
    start_time = time.perf_counter()

    # Story 11.7: LEFT JOIN with RECURRING_PATTERNS to include recurring pattern info
    query = """
        SELECT
            SE.ID AS SCHEDULED_EXECUTION_ID,
            SE.ACTION_ID,
            A.NAME AS ACTION_NAME,
            SE.USER_ID,
            U.DISPLAY_NAME AS USER_NAME,
            SE.ENVIRONMENT,
            SE.SCHEDULED_AT,
            SE.STATUS,
            SE.CREATED_AT,
            SE.PARAMETERS,
            SE.CORRELATION_ID,
            SE.EXECUTION_ID,
            RP.PATTERN_TYPE,
            RP.PATTERN_CONFIG,
            RP.NEXT_EXECUTION_DATE,
            RP.IS_ACTIVE AS RP_IS_ACTIVE
        FROM SCHEDULED_EXECUTIONS SE
        INNER JOIN ACTIONS_CATALOG A ON SE.ACTION_ID = A.ID
        INNER JOIN USERS U ON SE.USER_ID = U.ID
        LEFT JOIN RECURRING_PATTERNS RP ON SE.ID = RP.SCHEDULED_EXECUTION_ID
        WHERE 1=1
    """

    params: dict[str, Any] = {}

    if user_id is not None:
        query += " AND SE.USER_ID = :user_id"
        params["user_id"] = user_id

    if status is not None:
        query += " AND SE.STATUS = :status"
        params["status"] = status

    if action_id is not None:
        query += " AND SE.ACTION_ID = :action_id"
        params["action_id"] = action_id

    # Story 11.7: Filter by scheduled_at OR next_execution_date for recurring
    if scheduled_from is not None:
        query += " AND (SE.SCHEDULED_AT >= :scheduled_from OR RP.NEXT_EXECUTION_DATE >= :scheduled_from)"
        params["scheduled_from"] = scheduled_from

    if scheduled_to is not None:
        query += " AND (SE.SCHEDULED_AT <= :scheduled_to OR RP.NEXT_EXECUTION_DATE <= :scheduled_to)"
        params["scheduled_to"] = scheduled_to

    # Story 11.7: Order by effective date (scheduled_at or next_execution_date)
    query += " ORDER BY COALESCE(SE.SCHEDULED_AT, RP.NEXT_EXECUTION_DATE) ASC"
    query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "scheduled_execution_repository_list",
        duration_ms=duration_ms,
        user_id=user_id,
        status=status,
        action_id=action_id,
        scheduled_from=scheduled_from.isoformat() if scheduled_from else None,
        scheduled_to=scheduled_to.isoformat() if scheduled_to else None,
        result_count=len(rows),
    )

    results: list[ScheduledExecutionListItem] = []
    for row in rows:
        # Columns: 0:ID, 1:ACTION_ID, 2:ACTION_NAME, 3:USER_ID, 4:USER_NAME,
        # 5:ENVIRONMENT, 6:SCHEDULED_AT, 7:STATUS, 8:CREATED_AT, 9:PARAMETERS,
        # 10:CORRELATION_ID, 11:EXECUTION_ID, 12:PATTERN_TYPE, 13:PATTERN_CONFIG,
        # 14:NEXT_EXECUTION_DATE, 15:RP_IS_ACTIVE

        # Story 11.7: Build recurring_pattern if present
        recurring_pattern = None
        if row[12] is not None:  # PATTERN_TYPE
            pattern_config_raw = row[13]
            if hasattr(pattern_config_raw, "read"):
                pattern_config_raw = pattern_config_raw.read()
            recurring_pattern = RecurringPatternResponse(
                pattern_type=row[12],
                pattern_config=_str_to_json(pattern_config_raw),
                next_execution_date=row[14],
                is_active=bool(row[15]) if row[15] is not None else True,
            )

        results.append(
            ScheduledExecutionListItem(
                scheduled_execution_id=row[0],
                action_id=row[1],
                action_name=row[2],
                user_id=row[3],
                user_name=row[4] or "Unknown",
                environment=row[5],
                scheduled_at=row[6],  # NULL for recurring (Story 11.7)
                status=ScheduledExecutionStatus(row[7]),
                created_at=row[8],
                parameters=_str_to_json(row[9]),
                correlation_id=row[10],  # HIGH-1 FIX: AC10 requires correlation_id
                execution_id=row[11],  # HIGH-2 FIX: AC10 link to effective execution
                recurring_pattern=recurring_pattern,  # Story 11.7
            )
        )

    return results


async def count_scheduled_executions(
    user_id: int | None = None,
    status: str | None = None,
    action_id: int | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
) -> int:
    """Count scheduled executions with filters (Story 11.6, 11.7 - pagination).

    Args:
        Same as list_scheduled_executions

    Returns:
        Total count matching filters
    """
    start_time = time.perf_counter()

    # Story 11.7: LEFT JOIN with RECURRING_PATTERNS to include recurring pattern filtering
    query = """
        SELECT COUNT(*)
        FROM SCHEDULED_EXECUTIONS SE
        LEFT JOIN RECURRING_PATTERNS RP ON SE.ID = RP.SCHEDULED_EXECUTION_ID
        WHERE 1=1
    """

    params: dict[str, Any] = {}

    if user_id is not None:
        query += " AND SE.USER_ID = :user_id"
        params["user_id"] = user_id

    if status is not None:
        query += " AND SE.STATUS = :status"
        params["status"] = status

    if action_id is not None:
        query += " AND SE.ACTION_ID = :action_id"
        params["action_id"] = action_id

    # Story 11.7: Filter by scheduled_at OR next_execution_date for recurring
    if scheduled_from is not None:
        query += " AND (SE.SCHEDULED_AT >= :scheduled_from OR RP.NEXT_EXECUTION_DATE >= :scheduled_from)"
        params["scheduled_from"] = scheduled_from

    if scheduled_to is not None:
        query += " AND (SE.SCHEDULED_AT <= :scheduled_to OR RP.NEXT_EXECUTION_DATE <= :scheduled_to)"
        params["scheduled_to"] = scheduled_to

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        row = await cursor.fetchone()
        cursor.close()

    count = row[0] if row else 0

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "scheduled_execution_repository_count",
        duration_ms=duration_ms,
        count=count,
    )

    return count


async def update_status(
    scheduled_execution_id: int,
    new_status: str,
) -> bool:
    """Update scheduled execution status (Story 11.6, AC5).

    Args:
        scheduled_execution_id: ID of the scheduled execution
        new_status: New status to set (cancelled)

    Returns:
        True if updated, False if not found
    """
    start_time = time.perf_counter()

    query = """
        UPDATE SCHEDULED_EXECUTIONS
        SET STATUS = :new_status, UPDATED_AT = SYSDATE
        WHERE ID = :scheduled_execution_id
    """

    params = {
        "scheduled_execution_id": scheduled_execution_id,
        "new_status": new_status,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rowcount = cursor.rowcount
        await conn.commit()
        cursor.close()

    updated = rowcount > 0

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "scheduled_execution_repository_update_status",
        duration_ms=duration_ms,
        scheduled_execution_id=scheduled_execution_id,
        new_status=new_status,
        updated=updated,
    )

    return updated


# === Story 11.7: Recurring Patterns ===


async def get_recurring_pattern(
    scheduled_execution_id: int,
) -> RecurringPatternResponse | None:
    """Get recurring pattern for a scheduled execution (Story 11.7, AC8).

    Args:
        scheduled_execution_id: ID of the scheduled execution

    Returns:
        RecurringPatternResponse if exists, None otherwise
    """
    start_time = time.perf_counter()

    query = """
        SELECT PATTERN_TYPE, PATTERN_CONFIG, NEXT_EXECUTION_DATE, IS_ACTIVE
        FROM RECURRING_PATTERNS
        WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"scheduled_execution_id": scheduled_execution_id})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "scheduled_execution_repository_get_recurring_pattern",
        duration_ms=duration_ms,
        scheduled_execution_id=scheduled_execution_id,
        found=row is not None,
    )

    if row is None:
        return None

    pattern_config_raw = row[1]
    if hasattr(pattern_config_raw, "read"):
        pattern_config_raw = pattern_config_raw.read()
    pattern_config = _str_to_json(pattern_config_raw)

    return RecurringPatternResponse(
        pattern_type=row[0],
        pattern_config=pattern_config,
        next_execution_date=row[2],
        is_active=bool(row[3]),
    )


async def update_recurring_pattern_status(
    scheduled_execution_id: int,
    is_active: bool,
    new_next_execution_date: datetime | None = None,
) -> RecurringPatternResponse | None:
    """Update is_active status of recurring pattern (Story 11.7, AC9, AC10).

    Args:
        scheduled_execution_id: ID of the scheduled execution
        is_active: New active status
        new_next_execution_date: New next_execution_date (recalculated when re-enabling)

    Returns:
        Updated RecurringPatternResponse if exists, None if not found
    """
    start_time = time.perf_counter()

    # First get existing pattern to verify it exists
    existing = await get_recurring_pattern(scheduled_execution_id)
    if existing is None:
        return None

    # Build update query
    if is_active and new_next_execution_date:
        query = """
            UPDATE RECURRING_PATTERNS
            SET IS_ACTIVE = :is_active,
                NEXT_EXECUTION_DATE = :next_execution_date,
                UPDATED_AT = SYSTIMESTAMP
            WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
        """
        params = {
            "is_active": 1 if is_active else 0,
            "next_execution_date": new_next_execution_date,
            "scheduled_execution_id": scheduled_execution_id,
        }
    else:
        # When disabling, keep next_execution_date unchanged for history (AC9)
        query = """
            UPDATE RECURRING_PATTERNS
            SET IS_ACTIVE = :is_active,
                UPDATED_AT = SYSTIMESTAMP
            WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
        """
        params = {
            "is_active": 1 if is_active else 0,
            "scheduled_execution_id": scheduled_execution_id,
        }

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        await conn.commit()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "scheduled_execution_repository_update_recurring_pattern_status",
        duration_ms=duration_ms,
        scheduled_execution_id=scheduled_execution_id,
        is_active=is_active,
        new_next_execution_date=new_next_execution_date.isoformat() if new_next_execution_date else None,
    )

    # Return updated pattern
    return await get_recurring_pattern(scheduled_execution_id)
