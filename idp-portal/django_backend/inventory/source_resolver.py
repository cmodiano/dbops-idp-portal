"""
InventorySourceResolver: Determines which inventory source to use.

Responsibility: Resolve WHERE to read inventory data from (API/DB/fallback).
Story 26.1 - AC1: Separation of concerns from InventoryService.
"""

from __future__ import annotations

from typing import cast

import structlog

from integrations.models import Integration, IntegrationType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class InventorySourceResolver:
    """
    Resolves the active inventory integration source.

    Determines which source to use for inventory data:
    - API-based inventory (IntegrationType.INVENTORY)
    - DB schema-based inventory (IntegrationType.INVENTORY_DB)
    - Fallback to DBOPS_INVENTORY synonym

    Story 26.1 - AC1: Extracted from InventoryService.
    """

    def get_active_inventory_integration(self) -> Integration | None:
        """
        Get the active inventory integration.
        Looks for integration of type 'inventory' (API) or 'inventory_db' (schema).

        Returns:
            Integration instance or None if no inventory integration configured
        """
        correlation_id = get_correlation_id()

        # Try API inventory first, then DB inventory
        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY)
        if integration:
            logger.info(
                "inventory_integration_found",
                integration_id=integration.id,
                integration_type=IntegrationType.INVENTORY,
                correlation_id=correlation_id
            )
            return cast("Integration | None", integration)

        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY_DB)
        if integration:
            logger.info(
                "inventory_integration_found",
                integration_id=integration.id,
                integration_type=IntegrationType.INVENTORY_DB,
                correlation_id=correlation_id
            )
            return cast("Integration | None", integration)

        logger.info(
            "no_inventory_integration_configured",
            correlation_id=correlation_id
        )
        return None
