"""Validators and helpers for catalog serializers.

Story 62.4: Dynamic inventory column validation via DIP factory.
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from integrations.models import Integration, IntegrationTypeCatalogue, IntegrationRole
from inventory.services import InventoryService, InventoryServiceError as _InventoryServiceError

import structlog

logger = structlog.get_logger(__name__)

# Story 31.9: Alias mapping for legacy platform codes → catalogue codes
# Canonical source — also used by business_rule_views.py
PLATFORM_ALIAS: dict[str, str] = {
    'terraform': 'terraform_cloud',
    'tower': 'aap',
}

VALID_INVENTORY_TYPES = ('servers', 'instances', 'databases')

VALID_INVENTORY_VALUE_COLUMNS: dict[str, tuple[str, ...]] = {
    'servers':   ('name', 'id', 'environment', 'engine_type'),
    'instances': ('name', 'id', 'server_ref', 'db_ref'),
    'databases': ('name', 'id'),
}

# Story 62.4: DIP factory — overridable in tests (same pattern as inventory/views.py Story 33.4)
_catalog_inventory_service_factory = InventoryService


def get_allowed_inventory_columns(inventory_type: str) -> tuple[str, ...]:
    """
    Story 62.4: Get allowed inventory_value_column values dynamically from
    the active inventory integration config.

    Falls back to VALID_INVENTORY_VALUE_COLUMNS if:
    - No active inventory_db integration is configured (mapper is None)
    - Integration is in flat_table mode (not multi_table)
    - InventoryServiceError is raised by the service

    Args:
        inventory_type: One of 'servers', 'instances', 'databases'

    Returns:
        Tuple of allowed column concept names (id always first when dynamic)
    """
    try:
        service = _catalog_inventory_service_factory()
        mapper = service._get_inventory_mapper()
        if mapper and mapper.is_multi_table:
            entity_config = mapper.get_entity_config(inventory_type)
            if entity_config:
                # Build column list: 'id' first, then remaining concepts from config
                columns = ['id'] + [
                    k for k in entity_config.get('columns', {}).keys() if k != 'id'
                ]
                return tuple(columns)
    except _InventoryServiceError:
        pass  # Fallback below

    # Fallback: use hardcoded list (backward compat — no inventory integration configured)
    return VALID_INVENTORY_VALUE_COLUMNS.get(inventory_type, ('id', 'name'))


def validate_platform_integration_consistency(
    platform: str | None,
    integration: Integration | None,
    integration_id: int | None = None
) -> None:
    """
    Story 29.4: Validate platform ↔ integration.type consistency (DRY helper).

    Raises:
        serializers.ValidationError: If platform and integration are inconsistent.
    """
    # Skip validation if either field is missing
    if not platform or not integration:
        return

    # Get integration type catalogue entry
    try:
        integration_type_cat = IntegrationTypeCatalogue.objects.get(code=integration.type)
    except IntegrationTypeCatalogue.DoesNotExist:
        # If type not in catalogue, skip validation (backward compatibility)
        logger.warning("integration_type_not_in_catalogue", integration_type=integration.type, integration_id=integration.id)
        return

    # Only validate if integration is a platform (not a service)
    if integration_type_cat.integration_role != IntegrationRole.PLATFORM:
        raise serializers.ValidationError({
            'integration_id': (
                f"Integration '{integration.name}' is a service (type '{integration.type}'), "
                f"but action.platform is set. Use integration for platforms only "
                f"(AAP, GitHub Actions, etc.)."
            )
        })

    # Story 31.9: Normalize platform code for matching (lower, spaces→underscores, alias)
    normalized_platform = platform.lower().replace(' ', '_')
    normalized_platform = PLATFORM_ALIAS.get(normalized_platform, normalized_platform)

    # Check if normalized platform matches integration.type
    if normalized_platform != integration.type:
        raise serializers.ValidationError({
            'platform': (
                f"Platform '{platform}' is inconsistent with integration type '{integration.type}'. "
                f"Expected platform '{integration_type_cat.name}' for integration '{integration.name}'."
            )
        })


def validate_parameters_schema_inventory(value: Any) -> Any:
    """
    Story 23.5 + 37.4: Validate inventory parameters in parameters_schema.

    If a parameter property has source='inventory':
    - inventory_type must be one of 'servers', 'instances', 'databases'.
    - inventory_value_column (optional) must be an allowed column for the inventory_type.
    """
    if not value or not isinstance(value, dict):
        return value

    properties = value.get('properties')
    if not properties or not isinstance(properties, dict):
        return value

    for param_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        source = prop.get('source')
        if source != 'inventory':
            continue
        inventory_type = prop.get('inventory_type')
        if not inventory_type:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type is required when source is 'inventory'"
            )
        if inventory_type not in VALID_INVENTORY_TYPES:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type must be one of: "
                f"{', '.join(VALID_INVENTORY_TYPES)}"
            )
        # Story 37.4 / 62.4 — validate optional inventory_value_column (dynamic from mapper)
        inventory_value_column = prop.get('inventory_value_column')
        if inventory_value_column is not None:
            allowed = get_allowed_inventory_columns(inventory_type)
            if inventory_value_column not in allowed:
                raise serializers.ValidationError(
                    f"Parameter '{param_name}': inventory_value_column must be one of: "
                    f"{', '.join(allowed)} for inventory_type '{inventory_type}'"
                )

    return value
