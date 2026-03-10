"""
Story 24.1: Service for Integration Type Catalogue read operations.
Follows ADR-003 Service pattern (no repository layer).
Code Review Fix Issue #9: Added structlog logging for operations.
"""

import structlog
from django.db.models import Prefetch
from integrations.models import IntegrationTypeCatalogue, IntegrationAction

logger = structlog.get_logger(__name__)


class IntegrationCatalogueService:
    """Service providing read access to the integration type catalogue."""

    @staticmethod
    def list_all_types(role: str | None = None):
        """List all active integration types with prefetched actions.

        Args:
            role: Optional filter by integration_role ('platform' or 'service').
        """
        logger.info("catalogue.list_all_types", operation="list_all_types", role=role)
        queryset = (
            IntegrationTypeCatalogue.objects
            .filter(is_active=True)
            .prefetch_related(Prefetch('actions', queryset=IntegrationAction.objects.filter(is_active=True)))
            .order_by('code')
        )
        if role in ('platform', 'service'):
            queryset = queryset.filter(integration_role=role)
        logger.info("catalogue.list_all_types.complete", type_count=queryset.count())
        return queryset

    @staticmethod
    def get_type_by_code(code: str):
        """Get an active integration type by code, with prefetched actions."""
        logger.info("catalogue.get_type_by_code", code=code)
        try:
            result = (
                IntegrationTypeCatalogue.objects
                .prefetch_related(Prefetch('actions', queryset=IntegrationAction.objects.filter(is_active=True)))
                .get(code=code, is_active=True)
            )
            logger.info("catalogue.get_type_by_code.found", code=code)
            return result
        except IntegrationTypeCatalogue.DoesNotExist:
            logger.warning("catalogue.get_type_by_code.not_found", code=code)
            return None

    @staticmethod
    def list_actions_by_type(type_code: str):
        """List active actions for a given integration type code."""
        logger.info("catalogue.list_actions_by_type", type_code=type_code)
        actions = (
            IntegrationAction.objects
            .filter(integration_type__code=type_code, is_active=True)
            .select_related('integration_type')
            .order_by('action_code')
        )
        logger.info("catalogue.list_actions_by_type.complete", type_code=type_code, action_count=actions.count())
        return actions

    @staticmethod
    def get_action(type_code: str, action_code: str):
        """Get a specific action by type code and action code."""
        logger.info("catalogue.get_action", type_code=type_code, action_code=action_code)
        try:
            result = (
                IntegrationAction.objects
                .select_related('integration_type')
                .get(
                    integration_type__code=type_code,
                    action_code=action_code,
                    is_active=True,
                )
            )
            logger.info("catalogue.get_action.found", type_code=type_code, action_code=action_code)
            return result
        except IntegrationAction.DoesNotExist:
            logger.warning("catalogue.get_action.not_found", type_code=type_code, action_code=action_code)
            return None
