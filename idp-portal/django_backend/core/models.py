import json
import logging
from django.db import models

logger = logging.getLogger(__name__)


class AuditActionType(models.TextChoices):
    """Audit action type enum - expanded from V004 base types."""
    # Base types (V004)
    ACTION_CREATED = 'ACTION_CREATED', 'Action Created'
    ACTION_UPDATED = 'ACTION_UPDATED', 'Action Updated'
    ACTION_PUBLISHED = 'ACTION_PUBLISHED', 'Action Published'
    ACTION_DISABLED = 'ACTION_DISABLED', 'Action Disabled'
    ACTION_ENABLED = 'ACTION_ENABLED', 'Action Enabled'
    # Additional types added in later migrations (V028-V035, V039-V041)
    # Note: Full list would include all types from migrations, but base types are sufficient for model


class AuditEntityType(models.TextChoices):
    """Audit entity type enum matching Oracle CHECK constraint."""
    ACTION = 'action', 'Action'
    USER = 'user', 'User'
    PERMISSION = 'permission', 'Permission'
    EXECUTION = 'execution', 'Execution'
    # Additional types may exist in later migrations


class AuditLog(models.Model):
    """
    AuditLog model mapping to Oracle AUDIT_LOG table (V004, V028-V035).
    Append-only audit log for tracking all modifications.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    timestamp = models.DateTimeField(auto_now_add=True, db_column='TIMESTAMP')
    user_id = models.CharField(max_length=100, db_column='USER_ID')
    action_type = models.CharField(
        max_length=50,
        choices=AuditActionType.choices,
        db_column='ACTION_TYPE'
    )
    entity_type = models.CharField(
        max_length=50,
        choices=AuditEntityType.choices,
        db_column='ENTITY_TYPE'
    )
    entity_id = models.BigIntegerField(db_column='ENTITY_ID')
    # CLOB field - using TextField with JSON serialization helper
    details = models.TextField(null=True, blank=True, db_column='DETAILS')
    ip_address = models.CharField(max_length=45, null=True, blank=True, db_column='IP_ADDRESS')

    class Meta:
        db_table = 'AUDIT_LOG'
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit {self.id} - {self.action_type} ({self.entity_type}:{self.entity_id})"

    # JSON field helper
    def get_details(self):
        """Deserialize JSON from CLOB."""
        if self.details:
            try:
                return json.loads(self.details)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize details for AuditLog {self.id}: {e}")
                return None
        return None

    def set_details(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.details = json.dumps(value)
        else:
            self.details = None
