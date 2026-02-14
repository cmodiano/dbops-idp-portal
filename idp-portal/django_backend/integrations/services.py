"""
IntegrationService for business logic related to integrations.
Handles complex operations like JSON Schema validation for config.
Story M.8 - Task 9: Structured logging with structlog.
"""

from typing import Any, cast

import structlog

from django.db import transaction
from django.db import IntegrityError
from integrations.models import Integration, IntegrationStatus
from integrations.validation_service import IntegrationValidationService
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.exceptions import InvalidStateError

logger = structlog.get_logger(__name__)


class IntegrationService:
    """
    Service for integration business logic.
    Handles complex operations like JSON Schema validation.
    """
    
    def validate_config_json_schema(self, config: dict, integration_type: str):
        """
        Validate integration config against JSON Schema.
        
        Args:
            config: Config dict to validate
            integration_type: Type of integration (determines schema)
        
        Returns:
            True if valid, raises InvalidStateError if invalid
        
        Raises:
            InvalidStateError: If config doesn't match schema (code INVALID_CONFIG)
        """
        # inventory_db uses schema/table for DB inventory - skip strict auth schema
        if (integration_type or '').lower() == 'inventory_db':
            if not isinstance(config, dict):
                raise InvalidStateError(
                    code="INVALID_CONFIG",
                    message="Config must be a JSON object",
                    details={"field": "root", "error": "Config must be a JSON object"}
                )
            for key in ('schema', 'table'):
                val = config.get(key)
                if val is not None and not isinstance(val, str):
                    raise InvalidStateError(
                        code="INVALID_CONFIG",
                        message=f"{key} must be a string",
                        details={"field": key}
                    )
            return True

        from integrations.validation import validate_integration_config
        validate_integration_config(config)
        return True
    
    def parse_config(self, integration: Integration) -> dict | None:
        """
        Parse config CLOB from integration.
        
        Args:
            integration: Integration instance
        
        Returns:
            Parsed config dict or None
        """
        return cast("dict[Any, Any] | None", integration.get_config())
    
    @transaction.atomic
    def create_integration(self, integration_data, user=None):
        """
        Create a new integration with JSON Schema validation.
        
        Args:
            integration_data: Dict with integration fields (type, name, base_url, etc.)
            user: Optional user instance for audit
        
        Returns:
            Integration instance
        
        Raises:
            ValueError: If config validation fails
            IntegrityError: If integration name already exists
        """
        # Validate config if provided
        if 'config' in integration_data and integration_data['config']:
            self.validate_config_json_schema(
                integration_data['config'],
                integration_data.get('type', '')
            )
        
        try:
            integration = Integration.objects.create(
                type=integration_data['type'],
                name=integration_data['name'],
                base_url=integration_data['base_url'],
                credential_ref=integration_data.get('credential_ref'),
                icon=integration_data.get('icon'),
                auth_flow=integration_data.get('auth_flow'),
                token_url=integration_data.get('token_url'),
            )
            
            # Set config if provided
            if 'config' in integration_data:
                integration.set_config(integration_data['config'])
                integration.save()

            # Story 24.3: Compute status from catalogue
            computed_status = IntegrationValidationService.validate_integration(integration)
            if integration.status != computed_status:
                integration.status = computed_status
                integration.save(update_fields=['status', 'updated_at'])

            warnings = []
            if computed_status != IntegrationStatus.VALID:
                msg = f"Integration created with non-valid status: {computed_status}"
                logger.warning("integration_created_non_valid", integration_id=integration.id, status=computed_status)
                warnings.append(msg)

            # Audit if user provided
            if user:
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type=AuditActionType.INTEGRATION_CREATED,
                    entity_type=AuditEntityType.INTEGRATION,
                    entity_id=integration.id,
                    details={'name': integration.name, 'type': integration.type}
                )

            # Attach warnings for API response
            integration._warnings = warnings  # type: ignore[attr-defined]

            return integration
        except IntegrityError:
            raise ValueError(f"Une intégration avec le nom '{integration_data['name']}' existe déjà")
    
    def list_all(self, integration_type=None, active=None):
        """
        List all integrations with optional filters.
        
        Args:
            integration_type: Optional filter by type
            active: Optional filter by active status (not implemented yet)
        
        Returns:
            QuerySet of integrations
        """
        queryset = Integration.objects.all()
        if integration_type:
            queryset = queryset.filter(type=integration_type)
        # Note: active filter not implemented (no active field in model)
        return queryset.order_by('name')
    
    def get_by_id(self, integration_id: int):
        """
        Get integration by ID with config parsing.
        
        Args:
            integration_id: ID of the integration
        
        Returns:
            Integration instance or None
        """
        try:
            integration = Integration.objects.get(id=integration_id)
            return integration
        except Integration.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_integration(self, integration_id: int, integration_update_data, user=None):
        """
        Update integration with validation.
        
        Args:
            integration_id: ID of the integration
            integration_update_data: Dict with fields to update
            user: Optional user instance for audit
        
        Returns:
            Updated Integration instance or None if not found
        
        Raises:
            ValueError: If config validation fails or name already exists
        """
        try:
            integration = Integration.objects.get(id=integration_id)
        except Integration.DoesNotExist:
            return None
        
        # Validate config if provided
        if 'config' in integration_update_data and integration_update_data['config']:
            self.validate_config_json_schema(
                integration_update_data['config'],
                integration_update_data.get('type', integration.type)
            )
        
        # Update fields
        if 'type' in integration_update_data:
            integration.type = integration_update_data['type']
        if 'name' in integration_update_data:
            integration.name = integration_update_data['name']
        if 'base_url' in integration_update_data:
            integration.base_url = integration_update_data['base_url']
        if 'credential_ref' in integration_update_data:
            integration.credential_ref = integration_update_data.get('credential_ref')
        if 'icon' in integration_update_data:
            integration.icon = integration_update_data.get('icon')
        if 'auth_flow' in integration_update_data:
            integration.auth_flow = integration_update_data.get('auth_flow')
        if 'token_url' in integration_update_data:
            integration.token_url = integration_update_data.get('token_url')
        if 'config' in integration_update_data:
            integration.set_config(integration_update_data['config'])
        
        old_status = integration.status

        try:
            integration.save()
        except IntegrityError:
            raise ValueError(f"Une intégration avec le nom '{integration_update_data.get('name', integration.name)}' existe déjà")

        # Story 24.3: Recompute status if type changed
        computed_status = IntegrationValidationService.validate_integration(integration)
        warnings = []
        if integration.status != computed_status:
            integration.status = computed_status
            integration.save(update_fields=['status', 'updated_at'])

        if old_status != integration.status:
            AuditService.create_entry(
                user_id=str(user.id) if user else 'system',
                action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={
                    'previous_status': old_status,
                    'new_status': integration.status,
                    'validation_reason': "Status recalculated on update",
                },
            )

        if computed_status != IntegrationStatus.VALID:
            msg = f"Integration updated with non-valid status: {computed_status}"
            logger.warning("integration_updated_non_valid", integration_id=integration.id, status=computed_status)
            warnings.append(msg)

        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.INTEGRATION_UPDATED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={'name': integration.name}
            )

        integration._warnings = warnings  # type: ignore[attr-defined]

        return integration

    @transaction.atomic
    def delete_integration(self, integration_id: int, user=None):
        """
        Delete integration after checking dependencies.
        
        Args:
            integration_id: ID of the integration
            user: Optional user instance for audit
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If integration has dependencies (actions linked)
        """
        try:
            integration = Integration.objects.get(id=integration_id)
        except Integration.DoesNotExist:
            return False
        
        # Check for dependencies: actions linked to this integration
        from catalog.models import Action
        linked_actions = Action.objects.filter(integration_id=integration_id).exists()
        
        if linked_actions:
            raise ValueError("Impossible de supprimer une intégration avec des actions liées")
        
        integration_name = integration.name  # Save name before deletion for audit
        integration.delete()
        
        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.INTEGRATION_DELETED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration_id,
                details={'name': integration_name}
            )
        
        return True
    
    def get_by_type(self, integration_type: str):
        """
        Get integration by type.
        
        Args:
            integration_type: Type of integration (aap, servicenow, etc.)
        
        Returns:
            Integration instance or None
        """
        return Integration.objects.get_by_type(integration_type)
