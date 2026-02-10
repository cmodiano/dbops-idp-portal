"""
Story 24.1: Audit trail signals for IntegrationTypeCatalogue and IntegrationAction.
Code Review Fix: Added correlation_id extraction and proper entity_id tracking.
"""

import hashlib
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import AuditActionType, AuditEntityType
from core.services import AuditService
from core.middleware import get_correlation_id
from integrations.models import IntegrationTypeCatalogue, IntegrationAction

logger = logging.getLogger(__name__)


def _get_user_id_from_context():
    """
    Extract user_id from request context if available.
    Falls back to 'system' for fixture/migration operations.
    """
    # TODO Story 24.2: Implement thread-local request context to capture actual user
    # For now, signals don't have direct access to request, so we use 'system'
    # Future: Use crum (Current Request User Middleware) or similar pattern
    return 'system'


@receiver(post_save, sender=IntegrationTypeCatalogue)
def audit_integration_type_catalogue(sender, instance, created, **kwargs):
    """Log audit entry when IntegrationTypeCatalogue is created or updated."""
    action_type = (
        AuditActionType.INTEGRATION_TYPE_CREATED if created
        else AuditActionType.INTEGRATION_TYPE_UPDATED
    )

    # Fix Issue #2: Use hash of code as entity_id (since code is PK string, not int)
    # Oracle AUDIT_LOG.entity_id is NUMBER, so we hash the string code to an integer
    entity_id = int(hashlib.md5(instance.code.encode()).hexdigest()[:8], 16) % (10**9)

    try:
        AuditService.create_entry(
            user_id=_get_user_id_from_context(),  # Fix Issue #1
            action_type=action_type,
            entity_type=AuditEntityType.INTEGRATION_TYPE_CATALOGUE,
            entity_id=entity_id,  # Fix Issue #2
            details={
                'code': instance.code,
                'name': instance.name,
                'version': instance.version,
                'is_active': instance.is_active,
            },
            correlation_id=get_correlation_id(),  # Fix Issue #3
        )
    except Exception:
        logger.exception("Failed to create audit entry for IntegrationTypeCatalogue %s", instance.code)


@receiver(post_save, sender=IntegrationAction)
def audit_integration_action(sender, instance, created, **kwargs):
    """Log audit entry when IntegrationAction is created or updated."""
    action_type = (
        AuditActionType.INTEGRATION_ACTION_CREATED if created
        else AuditActionType.INTEGRATION_ACTION_UPDATED
    )
    try:
        AuditService.create_entry(
            user_id=_get_user_id_from_context(),  # Fix Issue #1
            action_type=action_type,
            entity_type=AuditEntityType.INTEGRATION_ACTION,
            entity_id=instance.id or 0,
            details={
                'integration_type_code': instance.integration_type_id,
                'action_code': instance.action_code,
                'action_label': instance.action_label,
                'is_active': instance.is_active,
            },
            correlation_id=get_correlation_id(),  # Fix Issue #3
        )
    except Exception:
        logger.exception("Failed to create audit entry for IntegrationAction %s", instance.action_code)
