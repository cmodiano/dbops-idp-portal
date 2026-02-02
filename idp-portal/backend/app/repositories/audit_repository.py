"""Audit repository for append-only AUDIT_LOG table (Story 2.4, AC #3).

Handles INSERT-only operations for audit trail.
No UPDATE or DELETE allowed by design.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from enum import Enum

import structlog

from app.core.database import get_connection

logger = structlog.get_logger()


def _parse_iso_date(date_str: str) -> str:
    """Parse ISO date string and return Oracle-compatible format.

    Handles formats:
    - 2026-01-30T10:00:00 (no timezone)
    - 2026-01-30T10:00:00Z (UTC)
    - 2026-01-30T10:00:00+00:00 (with timezone offset)
    - 2026-01-30T10:00:00.123Z (with milliseconds)

    Returns:
        Date string in format 'YYYY-MM-DDTHH24:MI:SS' (19 chars, no timezone)
    """
    if not date_str:
        return date_str

    # Remove timezone info if present (Z, +00:00, -05:00, etc.)
    # Keep only date and time up to seconds
    date_str = date_str.strip()
    
    # Remove timezone offset patterns
    date_str = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)  # Remove +00:00 or -05:00
    date_str = re.sub(r'Z$', '', date_str, flags=re.IGNORECASE)  # Remove Z
    
    # Remove milliseconds if present
    date_str = re.sub(r'\.\d{3,}', '', date_str)
    
    # Ensure we have exactly 19 characters (YYYY-MM-DDTHH:MM:SS)
    if len(date_str) >= 19:
        return date_str[:19]
    
    # If shorter, try to parse and format
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except (ValueError, AttributeError):
        # Fallback: return truncated version
        return date_str[:19] if len(date_str) >= 19 else date_str


class AuditActionType(str, Enum):
    """Valid action types for audit log."""
    # Action lifecycle (Story 2.4)
    ACTION_CREATED = "ACTION_CREATED"
    ACTION_UPDATED = "ACTION_UPDATED"
    ACTION_PUBLISHED = "ACTION_PUBLISHED"
    ACTION_DISABLED = "ACTION_DISABLED"
    ACTION_ENABLED = "ACTION_ENABLED"
    # Execution lifecycle (Story 6.1)
    EXECUTION_SUBMITTED = "EXECUTION_SUBMITTED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    # ServiceNow change (Story 6.1, AC2)
    SERVICENOW_CHANGE_CREATED = "SERVICENOW_CHANGE_CREATED"
    # Approval workflow (Story 7.4)
    EXECUTION_PENDING_APPROVAL = "EXECUTION_PENDING_APPROVAL"
    EXECUTION_APPROVED = "EXECUTION_APPROVED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    # Remediation (Story 9.2, AC4)
    REMEDIATION_EXECUTION_CREATED = "REMEDIATION_EXECUTION_CREATED"
    # Auto-remediation (Story 9.3, AC5)
    AUTO_REMEDIATION_TRIGGERED = "AUTO_REMEDIATION_TRIGGERED"
    AUTO_REMEDIATION_SUCCESS = "AUTO_REMEDIATION_SUCCESS"
    AUTO_REMEDIATION_FAILED = "AUTO_REMEDIATION_FAILED"


class AuditEntityType(str, Enum):
    """Valid entity types for audit log."""
    ACTION = "action"
    USER = "user"
    PERMISSION = "permission"
    EXECUTION = "execution"


async def create_entry(
    user_id: str,
    action_type: AuditActionType,
    entity_type: AuditEntityType,
    entity_id: int,
    details: dict | None = None,
    ip_address: str | None = None,
    correlation_id: str | None = None,
) -> int:
    """Create a new audit log entry (append-only).

    Args:
        user_id: ID of the user performing the action
        action_type: Type of action (ACTION_CREATED, ACTION_UPDATED, EXECUTION_*, etc.)
        entity_type: Type of entity (action, user, permission, execution)
        entity_id: ID of the entity being modified
        details: Optional JSON details about the action
        ip_address: Optional IP address of the user
        correlation_id: Optional correlation ID for log linking (Story 6.1, AC6)

    Returns:
        The ID of the created audit entry
    """
    start_time = time.perf_counter()

    query = """
        INSERT INTO AUDIT_LOG
        (USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID, DETAILS, IP_ADDRESS, CORRELATION_ID)
        VALUES
        (:user_id, :action_type, :entity_type, :entity_id, :details, :ip_address, :correlation_id)
        RETURNING ID INTO :out_id
    """

    details_json = json.dumps(details) if details else None

    params = {
        "user_id": user_id,
        "action_type": action_type.value,
        "entity_type": entity_type.value,
        "entity_id": entity_id,
        "details": details_json,
        "ip_address": ip_address,
        "correlation_id": correlation_id,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        out_id = cursor.var(int)
        params["out_id"] = out_id
        await cursor.execute(query, params)
        await conn.commit()
        cursor.close()

        entry_id = out_id.getvalue()[0]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "audit_repository_create_entry",
        query=query.strip(),
        duration_ms=duration_ms,
        user_id=user_id,
        action_type=action_type.value,
        entity_type=entity_type.value,
        entity_id=entity_id,
        audit_id=entry_id,
        correlation_id=correlation_id,
    )

    return entry_id


async def list_entries(
    entity_type: AuditEntityType | None = None,
    entity_id: int | None = None,
    action_type: AuditActionType | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List audit log entries with optional filters (read-only, Story 6.1 AC7).

    Args:
        entity_type: Filter by entity type (action, execution, etc.)
        entity_id: Filter by specific entity ID
        action_type: Filter by action type
        limit: Maximum number of entries to return
        offset: Number of entries to skip

    Returns:
        List of audit entry dicts
    """
    start_time = time.perf_counter()

    conditions = []
    params: dict = {"limit_val": limit, "offset_val": offset}

    if entity_type is not None:
        conditions.append("ENTITY_TYPE = :entity_type")
        params["entity_type"] = entity_type.value

    if entity_id is not None:
        conditions.append("ENTITY_ID = :entity_id")
        params["entity_id"] = entity_id

    if action_type is not None:
        conditions.append("ACTION_TYPE = :action_type")
        params["action_type"] = action_type.value

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT ID, TIMESTAMP, USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
               DETAILS, IP_ADDRESS, CORRELATION_ID
        FROM AUDIT_LOG
        WHERE {where_clause}
        ORDER BY TIMESTAMP DESC
        OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()

    entries = []
    for row in rows:
        details_raw = row[6]
        details_parsed = None
        if details_raw:
            raw_content = details_raw.read() if hasattr(details_raw, "read") else details_raw
            if isinstance(raw_content, bytes):
                raw_content = raw_content.decode("utf-8")
            details_parsed = json.loads(raw_content)
        entries.append({
            "id": row[0],
            "timestamp": row[1].isoformat() if row[1] else None,
            "user_id": row[2],
            "action_type": row[3],
            "entity_type": row[4],
            "entity_id": row[5],
            "details": details_parsed,
            "ip_address": row[7],
            "correlation_id": row[8],
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "audit_repository_list_entries",
        duration_ms=duration_ms,
        entity_type=entity_type.value if entity_type else None,
        entity_id=entity_id,
        count=len(entries),
    )

    return entries


async def get_by_entity(
    entity_type: AuditEntityType,
    entity_id: int,
) -> list[dict]:
    """Get all audit entries for a specific entity (read-only, Story 6.1 AC7).

    Args:
        entity_type: Entity type (action, execution, etc.)
        entity_id: Entity ID

    Returns:
        List of audit entry dicts for the entity
    """
    return await list_entries(entity_type=entity_type, entity_id=entity_id)


# Story 6.3: Execution audit entries with extended filters


async def list_execution_audit_entries(
    from_date: str | None = None,
    to_date: str | None = None,
    user_id: str | None = None,
    environment: str | None = None,
    action_id: int | None = None,
    status: str | None = None,
    sort_field: str = "timestamp",
    sort_order: str = "desc",
    limit: int = 25,
    offset: int = 0,
) -> list[dict]:
    """List execution audit entries with filters (Story 6.3, AC6, AC7).

    Returns one row per execution (entity_id) with the latest terminal entry
    (EXECUTION_COMPLETED or EXECUTION_FAILED).

    Args:
        from_date: Filter by timestamp >= from_date (ISO format)
        to_date: Filter by timestamp <= to_date (ISO format)
        user_id: Filter by user_id (exact match)
        environment: Filter by environment in DETAILS JSON
        action_id: Filter by action_id in DETAILS JSON
        status: Filter by derived status: "success" (EXECUTION_COMPLETED),
                "failed" (EXECUTION_FAILED), "running" (EXECUTION_STARTED/SUBMITTED)
        limit: Maximum number of entries (default 25 for pagination)
        offset: Number of entries to skip

    Returns:
        List of audit entry dicts, one per execution, with derived fields
    """
    start_time = time.perf_counter()

    # Map status filter to ACTION_TYPE values
    status_action_types: list[str] | None = None
    if status == "success":
        status_action_types = ["EXECUTION_COMPLETED"]
    elif status == "failed":
        status_action_types = ["EXECUTION_FAILED"]
    elif status == "running":
        status_action_types = ["EXECUTION_STARTED", "EXECUTION_SUBMITTED"]

    # Build conditions and params
    conditions = ["ENTITY_TYPE = 'execution'"]
    params: dict = {"limit_val": limit, "offset_val": offset}

    if from_date:
        conditions.append("TIMESTAMP >= TO_TIMESTAMP(:from_date, 'YYYY-MM-DD\"T\"HH24:MI:SS')")
        params["from_date"] = _parse_iso_date(from_date)

    if to_date:
        conditions.append("TIMESTAMP <= TO_TIMESTAMP(:to_date, 'YYYY-MM-DD\"T\"HH24:MI:SS')")
        params["to_date"] = _parse_iso_date(to_date)

    if user_id:
        conditions.append("USER_ID = :user_id")
        params["user_id"] = user_id

    if environment:
        # Filter on DETAILS JSON using JSON_VALUE (Oracle 12c+)
        # Use NVL to handle NULL DETAILS gracefully
        conditions.append("NVL(JSON_VALUE(DETAILS, '$.environment'), '') = :environment")
        params["environment"] = environment

    if action_id:
        # Use NVL to handle NULL DETAILS gracefully
        conditions.append("NVL(JSON_VALUE(DETAILS, '$.action_id'), '') = :action_id")
        params["action_id"] = str(action_id)

    if status_action_types:
        # Build IN clause for action types
        type_placeholders = ", ".join(f":at{i}" for i in range(len(status_action_types)))
        conditions.append(f"ACTION_TYPE IN ({type_placeholders})")
        for i, at in enumerate(status_action_types):
            params[f"at{i}"] = at

    where_clause = " AND ".join(conditions)

    # Validate and map sort field to SQL column
    sort_column_map = {
        "timestamp": "TIMESTAMP",
        "user_id": "USER_ID",
        "action_type": "ACTION_TYPE",
    }
    sql_sort_field = sort_column_map.get(sort_field.lower(), "TIMESTAMP")
    sql_sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    # Query: get the latest entry per execution (ENTITY_ID) for terminal states
    # Use ROW_NUMBER to pick the most recent entry per execution
    # Note: Inner ORDER BY uses TIMESTAMP DESC to get latest entry per execution
    # Outer ORDER BY uses user-specified sort field
    query = f"""
        WITH ranked AS (
            SELECT ID, TIMESTAMP, USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
                   DETAILS, IP_ADDRESS, CORRELATION_ID,
                   ROW_NUMBER() OVER (PARTITION BY ENTITY_ID ORDER BY TIMESTAMP DESC) as rn
            FROM AUDIT_LOG
            WHERE {where_clause}
        )
        SELECT ID, TIMESTAMP, USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
               DETAILS, IP_ADDRESS, CORRELATION_ID
        FROM ranked
        WHERE rn = 1
        ORDER BY {sql_sort_field} {sql_sort_order}
        OFFSET :offset_val ROWS FETCH NEXT :limit_val ROWS ONLY
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        cursor.close()

    entries = []
    for row in rows:
        details_raw = row[6]
        details_parsed = None
        if details_raw:
            raw_content = details_raw.read() if hasattr(details_raw, "read") else details_raw
            if isinstance(raw_content, bytes):
                raw_content = raw_content.decode("utf-8")
            details_parsed = json.loads(raw_content)

        # Derive status from action_type
        action_type = row[3]
        derived_status = "unknown"
        if action_type == "EXECUTION_COMPLETED":
            derived_status = "success"
        elif action_type == "EXECUTION_FAILED":
            derived_status = "failed"
        elif action_type in ("EXECUTION_STARTED", "EXECUTION_SUBMITTED"):
            derived_status = "running"

        entries.append({
            "id": row[0],
            "timestamp": row[1].isoformat() if row[1] else None,
            "user_id": row[2],
            "action_type": action_type,
            "entity_type": row[4],
            "entity_id": row[5],  # This is the execution_id
            "details": details_parsed,
            "ip_address": row[7],
            "correlation_id": row[8],
            "derived_status": derived_status,
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "audit_repository_list_execution_entries",
        duration_ms=duration_ms,
        count=len(entries),
        filters={"from_date": from_date, "to_date": to_date, "user_id": user_id,
                 "environment": environment, "action_id": action_id, "status": status},
    )

    return entries


async def count_execution_audit_entries(
    from_date: str | None = None,
    to_date: str | None = None,
    user_id: str | None = None,
    environment: str | None = None,
    action_id: int | None = None,
    status: str | None = None,
) -> int:
    """Count execution audit entries with same filters as list (Story 6.3, Task 1.2).

    Args:
        Same as list_execution_audit_entries

    Returns:
        Total count of distinct executions matching filters
    """
    start_time = time.perf_counter()

    # Map status filter to ACTION_TYPE values
    status_action_types: list[str] | None = None
    if status == "success":
        status_action_types = ["EXECUTION_COMPLETED"]
    elif status == "failed":
        status_action_types = ["EXECUTION_FAILED"]
    elif status == "running":
        status_action_types = ["EXECUTION_STARTED", "EXECUTION_SUBMITTED"]

    conditions = ["ENTITY_TYPE = 'execution'"]
    params: dict = {}

    if from_date:
        conditions.append("TIMESTAMP >= TO_TIMESTAMP(:from_date, 'YYYY-MM-DD\"T\"HH24:MI:SS')")
        params["from_date"] = _parse_iso_date(from_date)

    if to_date:
        conditions.append("TIMESTAMP <= TO_TIMESTAMP(:to_date, 'YYYY-MM-DD\"T\"HH24:MI:SS')")
        params["to_date"] = _parse_iso_date(to_date)

    if user_id:
        conditions.append("USER_ID = :user_id")
        params["user_id"] = user_id

    if environment:
        # Use NVL to handle NULL DETAILS gracefully
        conditions.append("NVL(JSON_VALUE(DETAILS, '$.environment'), '') = :environment")
        params["environment"] = environment

    if action_id:
        # Use NVL to handle NULL DETAILS gracefully
        conditions.append("NVL(JSON_VALUE(DETAILS, '$.action_id'), '') = :action_id")
        params["action_id"] = str(action_id)

    if status_action_types:
        type_placeholders = ", ".join(f":at{i}" for i in range(len(status_action_types)))
        conditions.append(f"ACTION_TYPE IN ({type_placeholders})")
        for i, at in enumerate(status_action_types):
            params[f"at{i}"] = at

    where_clause = " AND ".join(conditions)

    # Count distinct ENTITY_ID (executions)
    query = f"""
        SELECT COUNT(DISTINCT ENTITY_ID)
        FROM AUDIT_LOG
        WHERE {where_clause}
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, params)
        row = await cursor.fetchone()
        cursor.close()

    count = row[0] if row else 0

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.info(
        "audit_repository_count_execution_entries",
        duration_ms=duration_ms,
        count=count,
    )

    return count


# === Story 9.2: Remediation Audit ===


async def log_remediation(
    parent_execution_id: int,
    child_execution_id: int,
    user_id: int,
    action_id: int,
    parent_action_id: int,
    parent_action_name: str | None,
    child_action_name: str | None,
    environment: str,
    error_context: dict | None = None,
    ip_address: str | None = None,
    correlation_id: str | None = None,
) -> int:
    """Create audit log entry for remediation execution (Story 9.2, AC4).

    Records the remediation link between parent (failed) and child (corrective) executions.

    Args:
        parent_execution_id: ID of the parent (failed) execution
        child_execution_id: ID of the child (corrective) execution
        user_id: ID of the user who triggered the remediation
        action_id: ID of the remediation action
        parent_action_id: ID of the original action that failed
        parent_action_name: Name of the original action that failed
        child_action_name: Name of the remediation action
        environment: Environment where remediation is running
        error_context: Optional dict with failed_step, error_message from parent
        ip_address: Optional IP address of the user
        correlation_id: Optional correlation ID for request tracing

    Returns:
        The ID of the created audit entry
    """
    details = {
        "parent_execution_id": parent_execution_id,
        "parent_action_id": parent_action_id,
        "parent_action_name": parent_action_name,
        "child_execution_id": child_execution_id,
        "child_action_id": action_id,
        "child_action_name": child_action_name,
        "environment": environment,
    }

    if error_context:
        details["error_context"] = error_context

    return await create_entry(
        user_id=str(user_id),
        action_type=AuditActionType.REMEDIATION_EXECUTION_CREATED,
        entity_type=AuditEntityType.EXECUTION,
        entity_id=child_execution_id,
        details=details,
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
