"""Validation des targets avec RBAC via InventoryService."""
from __future__ import annotations

from core.exceptions import BadRequestError, ForbiddenError
from core.middleware import get_correlation_id
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from inventory.services import InventoryService, InventoryServiceError, MAX_TARGETS_FOR_RBAC_FILTER

import structlog

logger = structlog.get_logger(__name__)


class TargetValidator:
    """Valide les targets via InventoryService avec RBAC."""

    @staticmethod
    def validate_targets(
        target_names: list,
        action_id,
        user,
        ad_groups: list,
        correlation_id: str,
    ) -> tuple[list[dict], str]:
        """
        Validate targets via InventoryService (RBAC filtered).

        Returns:
            Tuple of (validated_targets, derived_environment).

        Raises:
            BadRequestError: If target_names format is invalid or inventory unavailable.
            ForbiddenError: If target is not authorized.
        """
        if not isinstance(target_names, list) or len(target_names) == 0:
            raise BadRequestError(
                code="BAD_REQUEST",
                message="target_names doit être une liste non vide",
                details={"target_names": target_names},
            )

        inventory_service = InventoryService()
        try:
            allowed_targets, _total, inventory_truncated = inventory_service.list_targets_for_user(
                user_id=user.id,
                ad_groups=ad_groups,
                page=1,
                page_size=MAX_TARGETS_FOR_RBAC_FILTER,
            )
        except InventoryServiceError as e:
            logger.error(
                "inventory_service_error_during_execution",
                error=str(e),
                user_id=user.id,
                correlation_id=correlation_id,
            )
            raise BadRequestError(
                code="INVENTORY_UNAVAILABLE",
                message="Service inventaire indisponible",
                details={"error": str(e)},
            )

        allowed_targets_map = {t['name']: t for t in allowed_targets}

        validated_targets = []
        environments_found = set()
        for name in target_names:
            if name not in allowed_targets_map:
                logger.warning(
                    "unauthorized_target_attempt",
                    user_id=user.id,
                    target_name=name,
                    action_id=action_id,
                    correlation_id=correlation_id,
                )
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type=AuditActionType.EXECUTION_TARGET_FORBIDDEN,
                    entity_type=AuditEntityType.EXECUTION,
                    entity_id=0,
                    details={
                        "target_name": name,
                        "action_id": action_id,
                        "message": "Cible non autorisée pour cette action",
                    },
                    correlation_id=correlation_id,
                )
                details_403 = {"target_name": name}
                if inventory_truncated:
                    details_403["inventory_truncated"] = True
                raise ForbiddenError(
                    code="FORBIDDEN",
                    message=f"Cible non autorisée: {name}",
                    details=details_403,
                )
            target = allowed_targets_map[name]
            validated_targets.append(target)
            environments_found.add(target['environment'])

        if len(environments_found) > 1:
            raise BadRequestError(
                code="MIXED_ENVIRONMENTS",
                message="Les cibles doivent appartenir au même environnement",
                details={"environments": list(environments_found)},
            )

        environment = list(environments_found)[0]
        return validated_targets, environment
