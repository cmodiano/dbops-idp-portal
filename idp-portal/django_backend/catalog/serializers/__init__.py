"""Catalog serializers package — re-exports for backward compatibility.

Refactored from monolithic serializers.py into thematic modules.
"""
from catalog.serializers.validators import (
    VALID_INVENTORY_TYPES,
    VALID_INVENTORY_VALUE_COLUMNS,
    validate_parameters_schema_inventory,
    validate_platform_integration_consistency,
)
from catalog.serializers.action import (
    TagSerializer,
    ActionTagsUpdateSerializer,
    StatusUpdateSerializer,
    WorkflowEnrichmentMixin,
    ActionFieldValidationMixin,
    ActionSerializer,
    ActionCreateSerializer,
    ActionListSerializer,
)
from catalog.serializers.action_mutex import (
    ActionMutexSerializer,
    ActionMutexCreateSerializer,
)
from catalog.serializers.business_rule import (
    BusinessRulePolicyListSerializer,
    BusinessRulePolicySerializer,
)

# Backward compatibility: tests import _validate_platform_integration_consistency
_validate_platform_integration_consistency = validate_platform_integration_consistency

__all__ = [
    "validate_platform_integration_consistency",
    "_validate_platform_integration_consistency",
    "VALID_INVENTORY_TYPES",
    "VALID_INVENTORY_VALUE_COLUMNS",
    "validate_parameters_schema_inventory",
    "TagSerializer",
    "ActionTagsUpdateSerializer",
    "StatusUpdateSerializer",
    "WorkflowEnrichmentMixin",
    "ActionFieldValidationMixin",
    "ActionSerializer",
    "ActionCreateSerializer",
    "ActionListSerializer",
    "ActionMutexSerializer",
    "ActionMutexCreateSerializer",
    "BusinessRulePolicyListSerializer",
    "BusinessRulePolicySerializer",
]
