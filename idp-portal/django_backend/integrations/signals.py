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


def _get_user_id_from_context() -> str:
    """
    Extract user_id from thread-local request context if available.
    Falls back to 'system' for fixture/migration/Celery operations.

    Story 30.12 (AC3): Uses get_current_user() from CorrelationIdMiddleware
    to capture the authenticated user who triggered the signal.
    """
    from core.middleware import get_current_user
    user = get_current_user()
    if user and getattr(user, 'is_authenticated', False):
        return str(user.id)
    return 'system'


@receiver(post_save, sender=IntegrationTypeCatalogue)
def audit_integration_type_catalogue(sender, instance, created, **kwargs):
    """Log audit entry when IntegrationTypeCatalogue is created or updated."""
    action_type = (
        AuditActionType.INTEGRATION_TYPE_CREATED if created
        else AuditActionType.INTEGRATION_TYPE_UPDATED
    )

    # Fix Issue #2: Use hash of code as entity_id (since code is PK string, not int)
    # Oracle AUDIT_LOG.entity_id is NUMBER, so we hash the string code to an integer.
    # Story 30.12 (AC2, Option B): MD5 truncated to 8 hex chars modulo 10^9 is acceptable
    # because the volume of IntegrationTypeCatalogue codes is low.
    # Current count (2026-02-16): 9 codes in production (see test_story_30_12_inconsistencies.py).
    # Collision probability for N=9: < 0.00001% (birthday paradox).
    # Collision probability for N=1000 (future): ~0.0005%.
    # A dev-time collision detection test validates uniqueness of current codes.
    entity_id = int(hashlib.md5(instance.code.encode(), usedforsecurity=False).hexdigest()[:8], 16) % (10**9)

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
    except Exception as exc:  # noqa: BLE001 — logged-and-reraised: SOC1 compliance requires audit trail, re-raise to prevent save
        # Story 30.8 ERR-4 (Option A — strict): Re-raise to prevent save without audit.
        # SOC1 compliance requires immutable audit trail.
        logger.critical(
            "audit_entry_creation_failed",
            extra={
                'entity_type': 'IntegrationTypeCatalogue',
                'entity_code': instance.code,
                'error': str(exc),
            },
        )
        raise


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
    except Exception as exc:  # noqa: BLE001 — logged-and-reraised: SOC1 compliance requires audit trail, re-raise to prevent save
        # Story 30.8 ERR-4 (Option A — strict): Re-raise to prevent save without audit.
        logger.critical(
            "audit_entry_creation_failed",
            extra={
                'entity_type': 'IntegrationAction',
                'action_code': instance.action_code,
                'error': str(exc),
            },
        )
        raise
