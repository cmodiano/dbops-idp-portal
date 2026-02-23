"""
Module executions.utils.environment — Validation de l'environnement contre l'inventaire.

Responsabilité unique : vérifier qu'un environnement soumis existe dans l'inventaire
et récupérer la configuration d'environnement de façon insensible à la casse.
"""
from __future__ import annotations

from datetime import timedelta
from datetime import timezone as dt_timezone

import structlog

from core.exceptions import BadRequestError
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
from core.environment import EnvironmentHelper
from inventory.services import InventoryServiceError

exec_logger = structlog.get_logger(__name__)

# Fixed-offset UTC — Oracle Thin Mode ne supporte pas les named timezones (DPY-3022)
UTC = dt_timezone(timedelta(0))


def get_env_config_case_insensitive(config: dict, env: str) -> dict:
    """
    Story 21.2, Task 4.1: Helper to get environment-specific config with case-insensitive lookup.
    Story 25.4: Returned dict may include requires_maintenance_window, requires_approval, allowed.
    Story 26.7 AC2: Migrated to use EnvironmentHelper.find_in_dict().
    Story 26.10: Renamed from _get_env_config_case_insensitive to respect Python convention (PEP 8).

    Args:
        config: Dictionary with environment keys (e.g., {"DEV": {...}, "STAGING": {...}})
        env: Environment string (case-insensitive)

    Returns:
        Config dict for the environment, or empty dict if not found.
        Per-env keys: required, change_model_code, change_type, template_id,
        requires_maintenance_window, requires_approval, allowed (Story 25.4).
    """
    if not config or not env:
        return {}

    value = EnvironmentHelper.find_in_dict(config, env)
    if value is None:
        return {}

    # HIGH-5 FIX: Log warning if config value is not a dict
    if not isinstance(value, dict):
        exec_logger.warning(  # type: ignore[unreachable]
            "invalid_env_config_value",
            env=env,
            value_type=type(value).__name__,
            correlation_id=get_correlation_id(),
            message="Environment config value should be a dict, returning empty dict",
        )
        return {}

    return value


def validate_environment_against_inventory(environment: str, *, user_id: int | None = None) -> None:
    """
    Validate environment against inventory (Story 13.7, AC2).
    Story 21.2, AC2 / Task 3: Case-insensitive validation, no fallback to dev.
    Story 26.7 AC2: Migrated to use EnvironmentHelper.is_in().
    Story 26.10: Renamed from _validate_environment_against_inventory to respect Python convention (PEP 8).
    Raises BadRequestError if environment is not in inventory.

    Args:
        environment: Environment string to validate
        user_id: Optional user ID for audit trail

    Note: InventoryService and AuditService are accessed via `import executions.utils` (lazy)
    so that `patch('executions.utils.InventoryService')` in tests correctly intercepts calls.
    """
    if not environment:
        return

    import executions.utils as _eu  # noqa: PLC0415

    correlation_id = get_correlation_id()

    try:
        inventory_service = _eu.InventoryService()
        valid_environments = inventory_service.list_environments()

        if not EnvironmentHelper.is_in(environment, valid_environments):
            # HIGH-4 FIX: Audit trail for invalid environment attempts (SOC1 compliance)
            _eu.AuditService.create_entry(
                user_id=str(user_id) if user_id else "system",
                action_type=AuditActionType.EXECUTION_SUBMITTED,
                entity_type=AuditEntityType.EXECUTION,
                entity_id=0,
                details={
                    "environment": environment,
                    "valid_environments": sorted(valid_environments),
                    "validation_result": "failed",
                    "reason": "invalid_environment",
                },
                correlation_id=correlation_id,
            )
            raise BadRequestError(
                code="INVALID_ENVIRONMENT",
                message=f"Environnement invalide: {environment}",
                details={
                    "environment": environment,
                    "valid_environments": sorted(valid_environments)
                },
            )
    except InventoryServiceError as e:
        # HIGH-2 FIX: Block execution if inventory unavailable - can't validate safely
        exec_logger.error(
            "inventory_validation_failed_blocking_execution",
            environment=environment,
            error=str(e),
            correlation_id=correlation_id,
        )
        raise BadRequestError(
            code="INVENTORY_UNAVAILABLE",
            message="Impossible de valider l'environnement: service inventaire indisponible",
            details={"environment": environment, "error": str(e)},
        )
