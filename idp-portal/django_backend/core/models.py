import json
import logging
from django.db import models
from django.db import IntegrityError

logger = logging.getLogger(__name__)


class AuditActionType(models.TextChoices):
    """Audit action type enum - expanded from V004 base types."""
    # Base types (V004)
    ACTION_CREATED = 'ACTION_CREATED', 'Action Created'
    ACTION_UPDATED = 'ACTION_UPDATED', 'Action Updated'
    ACTION_PUBLISHED = 'ACTION_PUBLISHED', 'Action Published'
    ACTION_DISABLED = 'ACTION_DISABLED', 'Action Disabled'
    ACTION_ENABLED = 'ACTION_ENABLED', 'Action Enabled'
    ACTION_DELETED = 'ACTION_DELETED', 'Action Deleted'
    # Story 18.1: Deactivation/reactivation audit types
    ACTION_DEACTIVATED = 'ACTION_DEACTIVATED', 'Action Deactivated'
    ACTION_REACTIVATED = 'ACTION_REACTIVATED', 'Action Reactivated'
    # Profile types (added for ProfileService)
    PROFILE_CREATED = 'PROFILE_CREATED', 'Profile Created'
    PROFILE_UPDATED = 'PROFILE_UPDATED', 'Profile Updated'
    PROFILE_DELETED = 'PROFILE_DELETED', 'Profile Deleted'
    # Integration types (added for IntegrationService)
    INTEGRATION_CREATED = 'INTEGRATION_CREATED', 'Integration Created'
    INTEGRATION_UPDATED = 'INTEGRATION_UPDATED', 'Integration Updated'
    INTEGRATION_DELETED = 'INTEGRATION_DELETED', 'Integration Deleted'
    # Execution types (added for ExecutionService)
    EXECUTION_SUBMITTED = 'EXECUTION_SUBMITTED', 'Execution Submitted'
    EXECUTION_RUNNING = 'EXECUTION_RUNNING', 'Execution Running'
    EXECUTION_COMPLETED = 'EXECUTION_COMPLETED', 'Execution Completed'
    EXECUTION_FAILED = 'EXECUTION_FAILED', 'Execution Failed'
    EXECUTION_CANCELLED = 'EXECUTION_CANCELLED', 'Execution Cancelled'
    EXECUTION_PENDING_APPROVAL = 'EXECUTION_PENDING_APPROVAL', 'Execution Pending Approval'
    EXECUTION_REJECTED = 'EXECUTION_REJECTED', 'Execution Rejected'
    # Story 13.2, Task 6.3: Unauthorized target attempt (audit trail for SOC1)
    EXECUTION_TARGET_FORBIDDEN = 'EXECUTION_TARGET_FORBIDDEN', 'Execution Target Forbidden'
    # Scheduled execution types (added for SchedulingService)
    SCHEDULED_EXECUTION_CREATED = 'SCHEDULED_EXECUTION_CREATED', 'Scheduled Execution Created'
    SCHEDULED_EXECUTION_RECURRING_CREATED = 'SCHEDULED_EXECUTION_RECURRING_CREATED', 'Scheduled Execution Recurring Created'
    SCHEDULED_EXECUTION_EXECUTED = 'SCHEDULED_EXECUTION_EXECUTED', 'Scheduled Execution Executed'
    SCHEDULED_EXECUTION_CANCELLED = 'SCHEDULED_EXECUTION_CANCELLED', 'Scheduled Execution Cancelled'
    SCHEDULED_EXECUTION_RECURRING_DISABLED = 'SCHEDULED_EXECUTION_RECURRING_DISABLED', 'Scheduled Execution Recurring Disabled'
    # User types (added for AuthService)
    USER_CREATED = 'USER_CREATED', 'User Created'
    USER_UPDATED = 'USER_UPDATED', 'User Updated'
    USER_LOGIN = 'USER_LOGIN', 'User Login'
    USER_LOGOUT = 'USER_LOGOUT', 'User Logout'
    USER_REFRESH = 'USER_REFRESH', 'User Refresh Token'
    FAVORITE_ADDED = 'FAVORITE_ADDED', 'Favorite Added'
    FAVORITE_REMOVED = 'FAVORITE_REMOVED', 'Favorite Removed'
    # Story 16.4: Retry audit types
    EXECUTION_STEP_RETRY_ATTEMPT = 'EXECUTION_STEP_RETRY_ATTEMPT', 'Execution Step Retry Attempt'
    EXECUTION_STEP_RETRY_SUCCESS = 'EXECUTION_STEP_RETRY_SUCCESS', 'Execution Step Retry Success'
    EXECUTION_STEP_RETRY_EXHAUSTED = 'EXECUTION_STEP_RETRY_EXHAUSTED', 'Execution Step Retry Exhausted'
    EXECUTION_STEP_RETRY_ABORTED = 'EXECUTION_STEP_RETRY_ABORTED', 'Execution Step Retry Aborted'
    # Story 17.12: Feature flag audit types
    FEATURE_FLAG_UPDATED = 'FEATURE_FLAG_UPDATED', 'Feature Flag Updated'
    FEATURE_FLAG_CREATED = 'FEATURE_FLAG_CREATED', 'Feature Flag Created'
    # Additional types added in later migrations (V028-V035, V039-V041)
    # Note: Full list would include all types from migrations, but base types are sufficient for model


class AuditEntityType(models.TextChoices):
    """Audit entity type enum matching Oracle CHECK constraint."""
    ACTION = 'action', 'Action'
    USER = 'user', 'User'
    PERMISSION = 'permission', 'Permission'
    EXECUTION = 'execution', 'Execution'
    INTEGRATION = 'integration', 'Integration'
    SCHEDULED_EXECUTION = 'scheduled_execution', 'Scheduled Execution'
    PROFILE = 'profile', 'Profile'
    FEATURE_FLAG = 'feature_flag', 'Feature Flag'
    # Additional types may exist in later migrations


class ImmutableQuerySet(models.QuerySet):
    """QuerySet that forbids update() and delete() for immutable audit logs (SOC1/NFR8)."""

    def update(self, **kwargs):
        raise IntegrityError("AUDIT_LOG is immutable - bulk updates are forbidden (SOC1/NFR8)")

    def delete(self):
        raise IntegrityError("AUDIT_LOG is immutable - bulk deletions are forbidden (SOC1/NFR8)")


class AuditLogManager(models.Manager):
    """
    Custom manager for AuditLog model.
    Provides query methods for common audit log queries.
    Uses ImmutableQuerySet to prevent bulk update/delete.
    """

    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)

    def create_entry(self, user_id: str, action_type: str, entity_type: str,
                     entity_id: int, details: dict | None = None,
                     ip_address: str | None = None, correlation_id: str | None = None):
        """
        Create a new audit log entry.
        
        Args:
            user_id: ID of the user performing the action
            action_type: Type of action (ACTION_CREATED, etc.)
            entity_type: Type of entity (action, execution, etc.)
            entity_id: ID of the entity
            details: Optional JSON details
            ip_address: Optional IP address
            correlation_id: Optional correlation ID
        
        Returns:
            AuditLog instance
        """
        # Serialize details to JSON string if provided
        details_json = None
        if details is not None:
            import json
            details_json = json.dumps(details)
        
        return self.create(
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_json,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
    
    def list_by_entity(self, entity_type: str, entity_id: int):
        """
        List audit entries for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
        
        Returns:
            QuerySet of audit entries for the entity, ordered by timestamp DESC
        """
        return self.filter(entity_type=entity_type, entity_id=entity_id).order_by('-timestamp')
    
    def list_by_user(self, user_id: str):
        """
        List audit entries for a specific user.
        
        Args:
            user_id: ID of the user
        
        Returns:
            QuerySet of audit entries for the user, ordered by timestamp DESC
        """
        return self.filter(user_id=user_id).order_by('-timestamp')
    
    def list_by_date_range(self, from_date=None, to_date=None):
        """
        List audit entries within a date range.
        
        Args:
            from_date: Start date (datetime)
            to_date: End date (datetime)
        
        Returns:
            QuerySet of audit entries in the date range, ordered by timestamp DESC
        """
        queryset = self.all()
        if from_date:
            queryset = queryset.filter(timestamp__gte=from_date)
        if to_date:
            queryset = queryset.filter(timestamp__lte=to_date)
        return queryset.order_by('-timestamp')


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
    correlation_id = models.CharField(max_length=64, null=True, blank=True, db_column='CORRELATION_ID')
    
    # Custom manager
    objects = AuditLogManager()

    class Meta:
        db_table = 'AUDIT_LOG'
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        if self.pk:
            raise IntegrityError("AUDIT_LOG is immutable - updates are forbidden (SOC1/NFR8)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise IntegrityError("AUDIT_LOG is immutable - deletions are forbidden (SOC1/NFR8)")

    def __str__(self):
        return f"Audit {self.id} - {self.action_type} ({self.entity_type}:{self.entity_id})"

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


class FeatureFlag(models.Model):
    """
    Story 17.12: Feature flag model for centralized flag management.
    Maps to Oracle CORE_FEATURE_FLAGS table.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    flag_key = models.CharField(
        max_length=100,
        unique=True,
        db_column='FLAG_KEY',
        help_text='Unique key for the feature flag (e.g., new_workflow_builder)',
    )
    enabled = models.BooleanField(default=False, db_column='ENABLED')
    rollout_percent = models.IntegerField(
        default=100,
        db_column='ROLLOUT_PERCENT',
        help_text='Percentage of users to enable (0-100)',
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        default='',
        db_column='DESCRIPTION',
    )
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    updated_by = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='UPDATED_BY',
    )

    class Meta:
        db_table = 'CORE_FEATURE_FLAGS'
        ordering = ['flag_key']

    def __str__(self):
        status = 'ON' if self.enabled else 'OFF'
        return f"{self.flag_key} ({status}, {self.rollout_percent}%)"

    def clean(self):
        """Validate rollout_percent is 0-100."""
        from django.core.exceptions import ValidationError
        if self.rollout_percent < 0 or self.rollout_percent > 100:
            raise ValidationError({
                'rollout_percent': 'Rollout percent must be between 0 and 100.',
            })

    def save(self, *args, **kwargs):
        """HIGH-3 fix: Call full_clean() before save to ensure validation."""
        self.full_clean()
        super().save(*args, **kwargs)
