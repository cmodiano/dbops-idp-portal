"""Integration repository using raw SQL via python-oracledb (Story 2.27, 4.9, 5.3).

Handles CRUD operations for INTEGRATIONS table with:
- Parameterized queries for security
- Structured logging with correlation_id
- No secrets stored (credential_ref is a reference only, NFR7)
- Story 4.9: Type is free-form string, auth_flow added
- Story 5.3: token_url, config (CLOB as JSON)
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import oracledb
import structlog

from app.core.database import get_connection
from app.core.exceptions import IdpError, InvalidStateError
from app.models.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    AuthFlow,
)

logger = structlog.get_logger()


def _parse_config_clob(clob_value, integration_id: int | None = None) -> dict | None:
    """Parse CONFIG CLOB (JSON string or LOB object) to dict; return None if empty/null (Story 5.3).

    Args:
        clob_value: CONFIG column value (may be str or LOB object)
        integration_id: Optional integration ID for logging context

    Returns:
        Parsed dict or None if empty/null

    Note: Logs warning on JSON parse failure (code-review fix MED-2)
    """
    if clob_value is None:
        return None
    # Handle LOB object (code-review fix MED-4: consistency with execution_repository)
    if hasattr(clob_value, "read"):
        clob_value = clob_value.read()
    s = clob_value.strip() if isinstance(clob_value, str) else None
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        logger.warning(
            "integration_config_json_parse_error",
            integration_id=integration_id,
            error=str(e),
            clob_preview=s[:100] if s else None,
        )
        return None


def _row_to_integration_response(row: tuple) -> IntegrationResponse:
    """Convert database row to IntegrationResponse model (Story 4.9, 5.3).

    Expected row order (11 columns):
    0:ID, 1:TYPE, 2:NAME, 3:BASE_URL, 4:CREDENTIAL_REF, 5:ICON, 6:AUTH_FLOW,
    7:TOKEN_URL, 8:CONFIG, 9:CREATED_AT, 10:UPDATED_AT
    """
    integration_id = row[0]
    return IntegrationResponse(
        id=integration_id,
        type=row[1],
        name=row[2],
        base_url=row[3],
        credential_ref=row[4],
        icon=row[5],
        auth_flow=AuthFlow(row[6]) if row[6] is not None else None,
        token_url=row[7],
        config=_parse_config_clob(row[8], integration_id) if row[8] is not None else None,
        created_at=row[9],
        updated_at=row[10],
    )


async def get_all() -> list[IntegrationResponse]:
    """Return all integrations ordered by name (Story 2.27, 4.9).

    Returns:
        List of IntegrationResponse ordered by NAME ASC
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        ORDER BY NAME
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {})
        rows = await cursor.fetchall()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_get_all",
        query=query.strip(),
        duration_ms=duration_ms,
        count=len(rows),
    )

    return [_row_to_integration_response(row) for row in rows]


async def get_by_id(integration_id: int) -> IntegrationResponse | None:
    """Fetch an integration by ID (Story 2.27, 4.9).

    Args:
        integration_id: The integration ID to fetch

    Returns:
        IntegrationResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        WHERE ID = :integration_id
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"integration_id": integration_id})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_get_by_id",
        query=query.strip(),
        params={"integration_id": integration_id},
        duration_ms=duration_ms,
        found=row is not None,
    )

    if row is None:
        return None

    return _row_to_integration_response(row)


async def get_by_name(name: str) -> IntegrationResponse | None:
    """Fetch an integration by name (for uniqueness check, Story 4.9).

    Args:
        name: The integration name to fetch

    Returns:
        IntegrationResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        WHERE NAME = :name
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"name": name})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_get_by_name",
        query=query.strip(),
        params={"name": name},
        duration_ms=duration_ms,
        found=row is not None,
    )

    if row is None:
        return None

    return _row_to_integration_response(row)


class DuplicateNameError(Exception):
    """Raised when integration name already exists."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Integration avec le nom '{name}' existe deja")


async def create(integration: IntegrationCreate) -> IntegrationResponse:
    """Create a new integration (Story 2.27, 4.9).

    Args:
        integration: IntegrationCreate model with integration data

    Returns:
        IntegrationResponse with the created integration

    Raises:
        DuplicateNameError: If integration name already exists
    """
    start_time = time.perf_counter()
    config_json = json.dumps(integration.config) if integration.config is not None else None
    query = """
        INSERT INTO INTEGRATIONS
        (TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG)
        VALUES
        (:type, :name, :base_url, :credential_ref, :icon, :auth_flow, :token_url, :config)
        RETURNING ID INTO :out_id
    """
    params = {
        "type": integration.type,
        "name": integration.name,
        "base_url": integration.base_url,
        "credential_ref": integration.credential_ref,
        "icon": integration.icon,
        "auth_flow": integration.auth_flow.value if integration.auth_flow else None,
        "token_url": integration.token_url,
        "config": config_json,
    }

    async with get_connection() as conn:
        cursor = conn.cursor()
        out_id = cursor.var(int)
        params["out_id"] = out_id
        try:
            await cursor.execute(query, params)
            await conn.commit()
            cursor.close()
        except oracledb.IntegrityError as e:
            await conn.rollback()
            # Only unique constraint on INSERT is UK_INTEGRATIONS_NAME (NAME)
            raise DuplicateNameError(integration.name) from e

        integration_id = out_id.getvalue()[0]

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    log_params = {k: v for k, v in params.items() if k != "out_id"}
    logger.debug(
        "integration_repository_create",
        query=query.strip(),
        params=log_params,
        duration_ms=duration_ms,
        integration_id=integration_id,
        integration_name=integration.name,
    )

    # Fetch the created integration to return full response
    result = await get_by_id(integration_id)
    if result is None:
        raise IdpError(
            500,
            code="CREATION_FAILED",
            message="Impossible de récupérer l'intégration créée.",
            details={"integration_id": integration_id},
        )

    return result


async def update(integration_id: int, integration: IntegrationUpdate) -> IntegrationResponse | None:
    """Update an existing integration (Story 2.27, 4.9).

    Args:
        integration_id: The integration ID to update
        integration: IntegrationUpdate model with updated fields (partial update)

    Returns:
        IntegrationResponse if found and updated, None if not found

    Raises:
        DuplicateNameError: If new name already exists for another integration
    """
    start_time = time.perf_counter()

    # First check if integration exists
    existing = await get_by_id(integration_id)
    if existing is None:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.debug(
            "integration_repository_update",
            integration_id=integration_id,
            duration_ms=duration_ms,
            found=False,
        )
        return None

    # Build dynamic update query based on provided fields
    update_fields = []
    params = {"integration_id": integration_id}

    if integration.type is not None:
        update_fields.append("TYPE = :type")
        params["type"] = integration.type  # Story 4.9: type is now str (not enum)

    if integration.name is not None:
        update_fields.append("NAME = :name")
        params["name"] = integration.name

    if integration.base_url is not None:
        update_fields.append("BASE_URL = :base_url")
        params["base_url"] = integration.base_url

    # credential_ref, icon, and auth_flow can be set to None to clear them
    if "credential_ref" in integration.model_fields_set:
        update_fields.append("CREDENTIAL_REF = :credential_ref")
        params["credential_ref"] = integration.credential_ref

    if "icon" in integration.model_fields_set:
        update_fields.append("ICON = :icon")
        params["icon"] = integration.icon

    if "auth_flow" in integration.model_fields_set:
        update_fields.append("AUTH_FLOW = :auth_flow")
        params["auth_flow"] = integration.auth_flow.value if integration.auth_flow else None

    if "token_url" in integration.model_fields_set:
        update_fields.append("TOKEN_URL = :token_url")
        params["token_url"] = integration.token_url

    if "config" in integration.model_fields_set:
        update_fields.append("CONFIG = :config")
        params["config"] = json.dumps(integration.config) if integration.config is not None else None

    if not update_fields:
        # No fields to update, return existing
        return existing

    update_fields.append("UPDATED_AT = SYSTIMESTAMP")
    query = f"""
        UPDATE INTEGRATIONS
        SET {', '.join(update_fields)}
        WHERE ID = :integration_id
    """

    async with get_connection() as conn:
        try:
            cursor = conn.cursor()
            await cursor.execute(query, params)
            rowcount = cursor.rowcount
            cursor.close()

            if rowcount == 0:
                return None

            await conn.commit()
        except oracledb.IntegrityError as e:
            await conn.rollback()
            # Only unique constraint on INTEGRATIONS is NAME
            if integration.name is not None:
                raise DuplicateNameError(integration.name) from e
            raise InvalidStateError(
                code="CONSTRAINT_VIOLATION",
                message="Violation de contrainte unique (nom déjà existant).",
                details={"integration_id": integration_id},
            ) from e

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_update",
        query=query.strip(),
        params={k: v for k, v in params.items()},
        duration_ms=duration_ms,
        integration_id=integration_id,
    )

    # Fetch and return updated integration
    return await get_by_id(integration_id)


async def get_by_type(integration_type: str) -> IntegrationResponse | None:
    """Fetch an integration by type (Story 4.5, Task 6.2).

    Used to get the ServiceNow integration for change management.

    Args:
        integration_type: The integration type to fetch (e.g., "servicenow")

    Returns:
        IntegrationResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        WHERE TYPE = :integration_type
        ORDER BY CREATED_AT DESC
        FETCH FIRST 1 ROW ONLY
    """

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"integration_type": integration_type})
        row = await cursor.fetchone()
        cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_get_by_type",
        query=query.strip(),
        params={"integration_type": integration_type},
        duration_ms=duration_ms,
        found=row is not None,
    )

    if row is None:
        return None

    return _row_to_integration_response(row)


async def delete(integration_id: int) -> bool:
    """Delete an integration (Story 2.27, AC3).

    Args:
        integration_id: The integration ID to delete

    Returns:
        True if deleted, False if not found
    """
    start_time = time.perf_counter()
    query = "DELETE FROM INTEGRATIONS WHERE ID = :integration_id"

    async with get_connection() as conn:
        cursor = conn.cursor()
        await cursor.execute(query, {"integration_id": integration_id})
        rowcount = cursor.rowcount
        cursor.close()
        await conn.commit()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_delete",
        query=query.strip(),
        params={"integration_id": integration_id},
        duration_ms=duration_ms,
        deleted=rowcount > 0,
    )

    return rowcount > 0
