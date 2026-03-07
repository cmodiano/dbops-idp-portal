"""
IntegrationService for business logic related to integrations.
Handles complex operations like JSON Schema validation for config.
Story M.8 - Task 9: Structured logging with structlog.
"""

from pathlib import Path
from typing import Any, cast

import structlog

from django.db import transaction
from django.db import IntegrityError
from django.conf import settings
from integrations.models import Integration, IntegrationStatus
from integrations.validation_service import IntegrationValidationService
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.exceptions import InvalidStateError

logger = structlog.get_logger(__name__)


_SENSITIVE_INTEGRATION_FIELDS = frozenset({'credential_ref', 'config'})

_AUDITED_FIELDS = ('type', 'name', 'base_url', 'credential_ref', 'icon',
                   'auth_flow', 'token_url', 'secret_service_id', 'config')


def _delete_uploaded_icon(icon_path: str | None) -> None:
    """
    Delete a locally uploaded icon file (best-effort, never raises).
    Only acts on paths that start with '/static/icons/' — ignores external URLs
    and preset icon names that have no corresponding file.
    """
    if not icon_path or not icon_path.startswith('/static/icons/'):
        return
    filename = icon_path.removeprefix('/static/icons/').lstrip('/')
    if not filename:
        return
    static_root = Path(getattr(settings, 'STATIC_ROOT', None) or (Path(settings.BASE_DIR) / 'static'))
    file_path = static_root / 'icons' / filename
    try:
        file_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("icon_delete_failed", path=str(file_path), error=str(exc))


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

        # CRIT-8 fix: Validate secret_service_id FK exists before creating
        if 'secret_service_id' in integration_data and integration_data['secret_service_id']:
            if not Integration.objects.filter(id=integration_data['secret_service_id']).exists():
                raise ValueError(f"secret_service with ID {integration_data['secret_service_id']} not found")

        try:
            integration = Integration.objects.create(
                type=integration_data['type'],
                name=integration_data['name'],
                base_url=integration_data['base_url'],
                credential_ref=integration_data.get('credential_ref'),
                icon=integration_data.get('icon'),
                auth_flow=integration_data.get('auth_flow'),
                token_url=integration_data.get('token_url'),
                secret_service_id=integration_data.get('secret_service_id'),
            )
            
            # NEW-BE-7: Fusionner les saves post-create en un seul appel
            needs_save = False
            update_fields = []

            if 'config' in integration_data:
                integration.set_config(integration_data['config'])
                update_fields.append('config')
                needs_save = True

            # Story 24.3: Compute status from catalogue
            computed_status = IntegrationValidationService.validate_integration(integration)
            if integration.status != computed_status:
                integration.status = computed_status
                update_fields.extend(['status', 'updated_at'])
                needs_save = True

            if needs_save:
                # Toujours inclure updated_at : auto_now=True ne se déclenche pas via
                # save(update_fields=[...]) sauf si le champ est explicitement listé.
                if 'updated_at' not in update_fields:
                    update_fields.append('updated_at')
                integration.save(update_fields=update_fields)

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
        
        # Capturer les anciennes valeurs AVANT modification (Story 61.1)
        old_values = {}
        for field in _AUDITED_FIELDS:
            if field in integration_update_data:
                if field == 'config':
                    old_values[field] = integration.get_config()
                elif field == 'secret_service_id':
                    old_values[field] = integration.secret_service_id
                else:
                    old_values[field] = getattr(integration, field)

        # Update fields — track changed fields for update_fields optimization
        update_fields = []
        if 'type' in integration_update_data:
            integration.type = integration_update_data['type']
            update_fields.append('type')
        if 'name' in integration_update_data:
            integration.name = integration_update_data['name']
            update_fields.append('name')
        if 'base_url' in integration_update_data:
            integration.base_url = integration_update_data['base_url']
            update_fields.append('base_url')
        if 'credential_ref' in integration_update_data:
            integration.credential_ref = integration_update_data.get('credential_ref')
            update_fields.append('credential_ref')
        if 'icon' in integration_update_data:
            new_icon = integration_update_data.get('icon')
            if new_icon != integration.icon:
                _delete_uploaded_icon(integration.icon)
            integration.icon = new_icon
            update_fields.append('icon')
        if 'auth_flow' in integration_update_data:
            integration.auth_flow = integration_update_data.get('auth_flow')
            update_fields.append('auth_flow')
        if 'token_url' in integration_update_data:
            integration.token_url = integration_update_data.get('token_url')
            update_fields.append('token_url')
        if 'secret_service_id' in integration_update_data:
            # MED-3 fix: Validate secret_service_id FK exists
            secret_service_id = integration_update_data.get('secret_service_id')
            if secret_service_id is not None:
                if not Integration.objects.filter(id=secret_service_id).exists():
                    raise ValueError(f"secret_service with ID {secret_service_id} not found")
            integration.secret_service_id = secret_service_id
            update_fields.append('secret_service_id')
        if 'config' in integration_update_data:
            integration.set_config(integration_update_data['config'])
            update_fields.append('config')

        old_status = integration.status

        # NEW-BE-8: Calculer le status AVANT le save pour éviter le double save
        computed_status = IntegrationValidationService.validate_integration(integration)
        warnings = []
        if integration.status != computed_status:
            integration.status = computed_status
            update_fields.append('status')

        # Toujours inclure updated_at (auto_now=True ne se déclenche pas avec update_fields)
        update_fields.append('updated_at')

        try:
            integration.save(update_fields=update_fields)
        except IntegrityError:
            raise ValueError(f"Une intégration avec le nom '{integration_update_data.get('name', integration.name)}' existe déjà")

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

        # Construire changes pour l'audit (Story 61.1)
        changes = {}
        for field, old_val in old_values.items():
            if field == 'config':
                new_val = integration_update_data.get('config')
            elif field == 'secret_service_id':
                new_val = integration_update_data.get('secret_service_id')
            else:
                new_val = getattr(integration, field)

            if field in _SENSITIVE_INTEGRATION_FIELDS:
                if old_val != new_val:
                    changes[field] = {"old": "***", "new": "***"}
            elif old_val != new_val:
                changes[field] = {"old": old_val, "new": new_val}

        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.INTEGRATION_UPDATED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration.id,
                details={'name': integration.name, 'changes': changes}
            )

        integration._warnings = warnings  # type: ignore[attr-defined]

        return integration

    @transaction.atomic
    def delete_integration(self, integration_id: int, user=None):
        """
        Delete integration and disable all linked actions.

        Args:
            integration_id: ID of the integration
            user: Optional user instance for audit

        Returns:
            dict with 'deleted' (bool) and 'disabled_actions_count' (int),
            or False if not found
        """
        try:
            integration = Integration.objects.get(id=integration_id)
        except Integration.DoesNotExist:
            return False

        integration_name = integration.name
        icon_to_delete = integration.icon

        # Disable all linked actions before deletion (status + updated_at only; no soft-delete fields)
        from catalog.models import Action, ActionStatus
        from django.utils import timezone

        linked_actions = list(Action.objects.filter(integration_id=integration_id))
        now = timezone.now()

        # NEW-BE-6: Bulk update en 1 requête SQL (N+1 → 1)
        Action.objects.filter(integration_id=integration_id).update(
            status=ActionStatus.DISABLED,
            updated_at=now
        )
        disabled_count = len(linked_actions)

        # Audit individuel par action (SOC1 — inchangé)
        for action in linked_actions:
            if user:
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type=AuditActionType.ACTION_DISABLED_INTEGRATION_DELETED,
                    entity_type=AuditEntityType.ACTION,
                    entity_id=action.id,
                    details={
                        'action_name': action.name,
                        'integration_id': integration_id,
                        'integration_name': integration_name,
                        'reason': 'integration_deleted',
                    }
                )

        # Delete integration (SET_NULL sets integration_id=NULL on actions)
        integration.delete()
        # Best-effort cleanup of the uploaded icon file
        _delete_uploaded_icon(icon_to_delete)

        # Audit the deletion with disabled count
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.INTEGRATION_DELETED,
                entity_type=AuditEntityType.INTEGRATION,
                entity_id=integration_id,
                details={
                    'name': integration_name,
                    'disabled_actions_count': disabled_count,
                }
            )

        return {'deleted': True, 'disabled_actions_count': disabled_count}
    
    def get_by_type(self, integration_type: str):
        """
        Get integration by type.
        
        Args:
            integration_type: Type of integration (aap, servicenow, etc.)
        
        Returns:
            Integration instance or None
        """
        return Integration.objects.get_by_type(integration_type)
