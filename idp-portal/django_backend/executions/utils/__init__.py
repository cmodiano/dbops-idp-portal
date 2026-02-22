"""
Package executions.utils — re-exports pour compatibilité descendante.
Chaque symbole est défini dans son module thématique.

Les noms suivants sont importés ici (hors __all__) pour permettre le patch
via `patch('executions.utils.X')` dans les tests existants (backward compat).
"""
from core.services import AuditService  # noqa: F401
from inventory.services import InventoryService, InventoryServiceError  # noqa: F401
from profiles.services import ProfileService  # noqa: F401

from executions.utils.environment import (
    get_env_config_case_insensitive,
    validate_environment_against_inventory,
)
from executions.utils.workflow_parsing import (
    extract_workflow_referenced_action_ids,
    extract_workflow_step_map,
    validate_workflow_step_parameters,
    validate_workflow_referenced_actions,
)
from executions.utils.filters import (
    parse_int,
    parse_date,
    parse_iso_datetime,
    detect_request_source,
    apply_scope_filter,
    apply_execution_filters,
)
from executions.utils.scheduling import calculate_next_execution_date
from executions.utils.rbac_helpers import get_allowed_action_ids_for_user
from executions.utils.mutex_validation import validate_action_mutex

__all__ = [
    "get_env_config_case_insensitive",
    "validate_environment_against_inventory",
    "extract_workflow_referenced_action_ids",
    "extract_workflow_step_map",
    "validate_workflow_step_parameters",
    "validate_workflow_referenced_actions",
    "parse_int",
    "parse_date",
    "get_allowed_action_ids_for_user",
    "detect_request_source",
    "apply_scope_filter",
    "apply_execution_filters",
    "parse_iso_datetime",
    "calculate_next_execution_date",
    "validate_action_mutex",
]
