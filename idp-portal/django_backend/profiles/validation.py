"""
Profile environment validation against inventory (Story 21.6).

Centralized validation for profile environments.
Consistent with execution validation (Story 21.2) and SOC1 compliance.
"""

import structlog

from inventory.services import InventoryService, InventoryServiceError
from core.exceptions import BadRequestError, ServiceUnavailableError
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService

logger = structlog.get_logger(__name__)


def validate_environments_against_inventory(
    environments: list[str] | None,
    *,
    user_id: int | None = None,
    entity_id: int | None = None,
) -> list[str]:
    """
    Validate profile environments against inventory (Story 21.6, AC1-3).

    Case-insensitive validation. Returns normalized (lowercase) list.
    Blocks if inventory unavailable (SOC1, consistent with Story 21.2).
    Creates audit trail for invalid attempts (AC7).

    Args:
        environments: List of environment names from profile form
        user_id: Optional user ID for audit trail (from request.user.id)
        entity_id: Optional profile ID for audit trail (pass profile.id when available)

    Returns:
        Normalized (lowercase) valid environments

    Raises:
        BadRequestError: If invalid environments found
        ServiceUnavailableError: If inventory unavailable

    Examples:
        >>> # Basic validation with normalization
        >>> validate_environments_against_inventory(['LAB', 'dev'])
        ['lab', 'dev']

        >>> # With audit context
        >>> validate_environments_against_inventory(
        ...     ['invalid_env'],
        ...     user_id=123,
        ...     entity_id=456
        ... )
        BadRequestError: Environnements invalides : invalid_env
        # Audit trail created with user_id='123', entity_id=456

        >>> # Empty list (valid)
        >>> validate_environments_against_inventory([])
        []
    """
    # Early return for empty/null (AC4)
    if not environments:
        return []

    try:
        inventory_service = InventoryService()
        valid_environments = inventory_service.list_environments()
        valid_envs_lower = {e.lower() for e in valid_environments}

        # Normalize input to lowercase (AC2)
        normalized_envs = [env.lower() for env in environments]

        # Find invalid environments
        invalid_envs = [env for env in normalized_envs if env not in valid_envs_lower]

        if invalid_envs:
            # Audit trail BEFORE raising error (SOC1, AC7)
            AuditService.create_entry(
                user_id=str(user_id) if user_id else "system",
                action_type=AuditActionType.PROFILE_UPDATE_REJECTED,
                entity_type=AuditEntityType.PROFILE,
                entity_id=entity_id or 0,
                details={
                    "reason": "invalid_environments",
                    "invalid_environments": invalid_envs,
                    "available_environments": valid_environments,
                    "submitted_environments": environments,
                },
            )

            raise BadRequestError(
                code="INVALID_ENVIRONMENTS",
                message=f"Environnements invalides : {', '.join(invalid_envs)}",
                details={
                    "invalid_environments": invalid_envs,
                    "available_environments": valid_environments,
                },
            )

        return normalized_envs

    except InventoryServiceError as e:
        # Block if inventory unavailable (SOC1, AC3)
        logger.error(
            "profile_environment_validation_inventory_unavailable",
            environments=environments,
            error=str(e),
        )
        raise ServiceUnavailableError(
            code="INVENTORY_UNAVAILABLE",
            message="Inventaire indisponible. Impossible de valider les environnements.",
            details={"inventory_error": str(e)},
        )
