"""Integration repository using raw SQL via python-oracledb (Story 2.27).

Handles CRUD operations for INTEGRATIONS table with:
- Parameterized queries for security
- Structured logging with correlation_id
- No secrets stored (credential_ref is a reference only, NFR7)
"""

from __future__ import annotations

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
    IntegrationType,
)

logger = structlog.get_logger()


def _row_to_integration_response(row: tuple) -> IntegrationResponse:
    """Convert database row to IntegrationResponse model.

    Expected row order (8 columns):
    0:ID, 1:TYPE, 2:NAME, 3:BASE_URL, 4:CREDENTIAL_REF, 5:ICON, 6:CREATED_AT, 7:UPDATED_AT
    """
    return IntegrationResponse(
        id=row[0],
        type=IntegrationType(row[1]),
        name=row[2],
        base_url=row[3],
        credential_ref=row[4],
        icon=row[5],
        created_at=row[6],
        updated_at=row[7],
    )


async def get_all() -> list[IntegrationResponse]:
    """Return all integrations ordered by name (Story 2.27, AC2).

    Returns:
        List of IntegrationResponse ordered by NAME ASC
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        ORDER BY NAME
    """

    async with get_connection() as conn:
        cursor = await conn.execute(query, {})
        rows = await cursor.fetchall()
        await cursor.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    logger.debug(
        "integration_repository_get_all",
        query=query.strip(),
        duration_ms=duration_ms,
        count=len(rows),
    )

    return [_row_to_integration_response(row) for row in rows]


async def get_by_id(integration_id: int) -> IntegrationResponse | None:
    """Fetch an integration by ID (Story 2.27, AC2).

    Args:
        integration_id: The integration ID to fetch

    Returns:
        IntegrationResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        WHERE ID = :integration_id
    """

    async with get_connection() as conn:
        cursor = await conn.execute(query, {"integration_id": integration_id})
        row = await cursor.fetchone()
        await cursor.close()

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
    """Fetch an integration by name (for uniqueness check).

    Args:
        name: The integration name to fetch

    Returns:
        IntegrationResponse if found, None otherwise
    """
    start_time = time.perf_counter()
    query = """
        SELECT ID, TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, CREATED_AT, UPDATED_AT
        FROM INTEGRATIONS
        WHERE NAME = :name
    """

    async with get_connection() as conn:
        cursor = await conn.execute(query, {"name": name})
        row = await cursor.fetchone()
        await cursor.close()

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
    """Create a new integration (Story 2.27, AC3).

    Args:
        integration: IntegrationCreate model with integration data

    Returns:
        IntegrationResponse with the created integration

    Raises:
        DuplicateNameError: If integration name already exists
    """
    start_time = time.perf_counter()
    query = """
        INSERT INTO INTEGRATIONS
        (TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON)
        VALUES
        (:type, :name, :base_url, :credential_ref, :icon)
        RETURNING ID INTO :out_id
    """
    params = {
        "type": integration.type.value,
        "name": integration.name,
        "base_url": integration.base_url,
        "credential_ref": integration.credential_ref,
        "icon": integration.icon,
    }

    async with get_connection() as conn:
        out_id = conn.var(int)
        params["out_id"] = out_id

        try:
            cursor = await conn.execute(query, params)
            await conn.commit()
            await cursor.close()
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
    """Update an existing integration (Story 2.27, AC3).

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
        params["type"] = integration.type.value

    if integration.name is not None:
        update_fields.append("NAME = :name")
        params["name"] = integration.name

    if integration.base_url is not None:
        update_fields.append("BASE_URL = :base_url")
        params["base_url"] = integration.base_url

    # credential_ref and icon can be set to None to clear them
    if "credential_ref" in integration.model_fields_set:
        update_fields.append("CREDENTIAL_REF = :credential_ref")
        params["credential_ref"] = integration.credential_ref

    if "icon" in integration.model_fields_set:
        update_fields.append("ICON = :icon")
        params["icon"] = integration.icon

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
            cursor = await conn.execute(query, params)
            rowcount = cursor.rowcount
            await cursor.close()

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
        cursor = await conn.execute(query, {"integration_id": integration_id})
        rowcount = cursor.rowcount
        await cursor.close()
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
