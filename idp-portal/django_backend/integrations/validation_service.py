"""
Story 24.3: Service de validation des intégrations contre le catalogue des types.
Follows ADR-003 Service pattern (static methods, structlog logging).
"""

import uuid
import structlog

from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue
from core.models import AuditActionType, AuditEntityType
from core.services import AuditService

logger = structlog.get_logger(__name__)


class IntegrationValidationService:
    """Service for validating integrations against the type catalogue."""

    @staticmethod
    def validate_integration(integration: Integration) -> IntegrationStatus:
        """
        Validate an integration against the type catalogue.

        Rules:
        - Type does not exist in catalogue → INVALID
        - Type exists but is_active=False → DEPRECATED
        - Type exists and is_active=True → VALID
        """
        try:
            catalogue_type = IntegrationTypeCatalogue.objects.filter(
                code=integration.type
            ).first()

            if not catalogue_type:
                logger.warning(
                    "integration_validation_failed",
                    integration_id=integration.id,
                    integration_type=integration.type,
                    reason="type_not_found_in_catalogue",
                )
                return IntegrationStatus.INVALID

            if not catalogue_type.is_active:
                logger.warning(
                    "integration_deprecated",
                    integration_id=integration.id,
                    integration_type=integration.type,
                    catalogue_version=catalogue_type.version,
                )
                return IntegrationStatus.DEPRECATED

            logger.info(
                "integration_valid",
                integration_id=integration.id,
                integration_type=integration.type,
                catalogue_version=catalogue_type.version,
            )
            return IntegrationStatus.VALID

        except Exception as e:
            logger.error(
                "integration_validation_error",
                integration_id=integration.id,
                error=str(e),
            )
            return IntegrationStatus.INVALID

    @staticmethod
    def validate_all_integrations(
        dry_run: bool = False,
        triggered_by: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        """
        Validate all integrations and update their status.

        Args:
            dry_run: If True, do not update DB — just compute and return stats.
            triggered_by: User ID or 'system' for audit logs (defaults to 'system').
            correlation_id: Correlation ID for audit logs (generated if not provided).

        Returns:
            dict with keys: valid, invalid, deprecated, updated
        """
        # Use defaults if not provided
        if triggered_by is None:
            triggered_by = 'system'
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        integrations = Integration.objects.all()
        stats = {'valid': 0, 'invalid': 0, 'deprecated': 0, 'updated': 0}

        for integration in integrations:
            old_status = integration.status
            new_status = IntegrationValidationService.validate_integration(integration)

            stats[new_status] += 1

            if old_status != new_status and not dry_run:
                integration.status = new_status
                integration.save(update_fields=['status', 'updated_at'])
                stats['updated'] += 1

                AuditService.create_entry(
                    user_id=triggered_by,
                    action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
                    entity_type=AuditEntityType.INTEGRATION,
                    entity_id=integration.id,
                    details={
                        'previous_status': old_status,
                        'new_status': new_status,
                        'validation_reason': f"Catalogue type '{integration.type}' status check",
                    },
                    correlation_id=correlation_id,
                )
            elif old_status != new_status and dry_run:
                stats['updated'] += 1

        logger.info(
            "batch_validation_completed",
            total=len(integrations),
            dry_run=dry_run,
            **stats,
        )

        return stats

    @staticmethod
    def get_integration_validation_details(integration: Integration) -> dict:
        """
        Return structured validation details for an integration.
        """
        catalogue_type = IntegrationTypeCatalogue.objects.filter(
            code=integration.type
        ).first()

        if not catalogue_type:
            return {
                'status': IntegrationStatus.INVALID,
                'type_exists': False,
                'type_is_active': False,
                'catalogue_version': None,
                'validation_message': f"Type '{integration.type}' not found in catalogue",
            }

        is_active = catalogue_type.is_active
        status = IntegrationStatus.VALID if is_active else IntegrationStatus.DEPRECATED
        message = (
            f"Type '{integration.type}' is active and supported"
            if is_active
            else f"Type '{integration.type}' is deprecated"
        )

        return {
            'status': status,
            'type_exists': True,
            'type_is_active': is_active,
            'catalogue_version': catalogue_type.version,
            'validation_message': message,
        }
