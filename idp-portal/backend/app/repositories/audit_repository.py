"""Audit repository for append-only AUDIT_LOG table (Story 2.4, AC #3).

Handles INSERT-only operations for audit trail.
No UPDATE or DELETE allowed by design.
"""

from __future__ import annotations

import json
import time
from enum import Enum

import structlog

from app.core.database import get_connection

logger = structlog.get_logger()


class AuditActionType(str, Enum):
    """Valid action types for audit log."""
    ACTION_CREATED = "ACTION_CREATED"
    ACTION_UPDATED = "ACTION_UPDATED"
    ACTION_PUBLISHED = "ACTION_PUBLISHED"
    ACTION_DISABLED = "ACTION_DISABLED"
    ACTION_ENABLED = "ACTION_ENABLED"


class AuditEntityType(str, Enum):
    """Valid entity types for audit log."""
    ACTION = "action"
    USER = "user"
    PERMISSION = "permission"


async def create_entry(
    user_id: str,
    action_type: AuditActionType,
    entity_type: AuditEntityType,
    entity_id: int,
    details: dict | None = None,
    ip_address: str | None = None,
) -> int:
    """Create a new audit log entry (append-only).

    Args:
        user_id: ID of the user performing the action
        action_type: Type of action (ACTION_CREATED, ACTION_UPDATED, etc.)
        entity_type: Type of entity (action, user, permission)
        entity_id: ID of the entity being modified
        details: Optional JSON details about the action
        ip_address: Optional IP address of the user

    Returns:
        The ID of the created audit entry
    """
    start_time = time.perf_counter()

    query = """
        INSERT INTO AUDIT_LOG
        (USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID, DETAILS, IP_ADDRESS)
        VALUES
        (:user_id, :action_type, :entity_type, :entity_id, :details, :ip_address)
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
    }

    async with get_connection() as conn:
        out_id = conn.var(int)
        params["out_id"] = out_id

        cursor = await conn.execute(query, params)
        await conn.commit()
        await cursor.close()

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
    )

    return entry_id
