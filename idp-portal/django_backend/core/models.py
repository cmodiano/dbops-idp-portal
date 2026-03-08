from __future__ import annotations

import json
import logging
from typing import Any
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
    ACTION_DISABLED_INTEGRATION_DELETED = 'ACTION_DISABLED_INTEGRATION_DELETED', 'Action Disabled - Integration Deleted'
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
    EXECUTION_STARTED = 'EXECUTION_STARTED', 'Execution Started'  # Legacy: in Oracle constraint, use EXECUTION_RUNNING for new writes
    EXECUTION_INTEGRATION_ERROR = 'EXECUTION_INTEGRATION_ERROR', 'Execution Integration Error'  # Story 18.6
    EXECUTION_RUNNING = 'EXECUTION_RUNNING', 'Execution Running'
    EXECUTION_COMPLETED = 'EXECUTION_COMPLETED', 'Execution Completed'
    EXECUTION_FAILED = 'EXECUTION_FAILED', 'Execution Failed'
    EXECUTION_CANCELLED = 'EXECUTION_CANCELLED', 'Execution Cancelled'
    EXECUTION_PENDING_APPROVAL = 'EXECUTION_PENDING_APPROVAL', 'Execution Pending Approval'
    EXECUTION_APPROVED = 'EXECUTION_APPROVED', 'Execution Approved'  # Story 30.1
    EXECUTION_REJECTED = 'EXECUTION_REJECTED', 'Execution Rejected'
    # Story 13.2, Task 6.3: Unauthorized target attempt (audit trail for SOC1)
    EXECUTION_TARGET_FORBIDDEN = 'EXECUTION_TARGET_FORBIDDEN', 'Execution Target Forbidden'
    # Scheduled execution types (added for SchedulingService)
    SCHEDULED_EXECUTION_CREATED = 'SCHEDULED_EXECUTION_CREATED', 'Scheduled Execution Created'
    SCHEDULED_EXECUTION_RECURRING_CREATED = 'SCHEDULED_EXECUTION_RECURRING_CREATED', 'Scheduled Execution Recurring Created'
    SCHEDULED_EXECUTION_EXECUTED = 'SCHEDULED_EXECUTION_EXECUTED', 'Scheduled Execution Executed'
    SCHEDULED_EXECUTION_CANCELLED = 'SCHEDULED_EXECUTION_CANCELLED', 'Scheduled Execution Cancelled'
    SCHEDULED_EXECUTION_RECURRING_DISABLED = 'SCHEDULED_EXECUTION_RECURRING_DISABLED', 'Scheduled Execution Recurring Disabled'
    # Story 42.1: Celery Beat triggered a scheduled execution
    SCHEDULED_EXECUTION_CELERY_TRIGGERED = 'SCHEDULED_EXECUTION_CELERY_TRIGGERED', 'Scheduled Execution Celery Triggered'
    # User types (added for AuthService)
    USER_CREATED = 'USER_CREATED', 'User Created'
    USER_UPDATED = 'USER_UPDATED', 'User Updated'
    USER_LOGIN = 'USER_LOGIN', 'User Login'
    USER_LOGOUT = 'USER_LOGOUT', 'User Logout'
    USER_REFRESH = 'USER_REFRESH', 'User Refresh Token'
    API_KEY_TOKEN_EXCHANGE = 'API_KEY_TOKEN_EXCHANGE', 'API Key Token Exchange'  # pragma: allowlist secret
    # Story 49.3: Service account LDAP login
    SERVICE_LOGIN = 'SERVICE_LOGIN', 'Service Account Login'
    # Story 59.6 SEC-6: Dev bypass authentication audit type
    AUTH_DEV_BYPASS_LOGIN = 'AUTH_DEV_BYPASS_LOGIN', 'Dev Bypass Authentication'
    FAVORITE_ADDED = 'FAVORITE_ADDED', 'Favorite Added'
    FAVORITE_REMOVED = 'FAVORITE_REMOVED', 'Favorite Removed'
    # Story 16.4: Retry audit types
    EXECUTION_STEP_RETRY_ATTEMPT = 'EXECUTION_STEP_RETRY_ATTEMPT', 'Execution Step Retry Attempt'
    EXECUTION_STEP_RETRY_SUCCESS = 'EXECUTION_STEP_RETRY_SUCCESS', 'Execution Step Retry Success'
    EXECUTION_STEP_RETRY_EXHAUSTED = 'EXECUTION_STEP_RETRY_EXHAUSTED', 'Execution Step Retry Exhausted'
    EXECUTION_STEP_RETRY_ABORTED = 'EXECUTION_STEP_RETRY_ABORTED', 'Execution Step Retry Aborted'
    # Story 25.2: Condition gates audit types
    EXECUTION_STEP_WAITING = 'EXECUTION_STEP_WAITING', 'Execution Step Waiting'
    # Story 25.3: Gate evaluation audit types
    EXECUTION_STEP_GATE_SATISFIED = 'EXECUTION_STEP_GATE_SATISFIED', 'Execution Step Gate Satisfied'
    EXECUTION_STEP_GATE_TIMEOUT = 'EXECUTION_STEP_GATE_TIMEOUT', 'Execution Step Gate Timeout'
    # Story 17.12: Feature flag audit types
    FEATURE_FLAG_UPDATED = 'FEATURE_FLAG_UPDATED', 'Feature Flag Updated'
    FEATURE_FLAG_CREATED = 'FEATURE_FLAG_CREATED', 'Feature Flag Created'
    # Story 21.6: Profile environment validation audit
    PROFILE_UPDATE_REJECTED = 'PROFILE_UPDATE_REJECTED', 'Profile Update Rejected'
    # Story 24.1: Integration type catalogue audit types
    INTEGRATION_TYPE_CREATED = 'INTEGRATION_TYPE_CREATED', 'Integration Type Created'
    INTEGRATION_TYPE_UPDATED = 'INTEGRATION_TYPE_UPDATED', 'Integration Type Updated'
    INTEGRATION_ACTION_CREATED = 'INTEGRATION_ACTION_CREATED', 'Integration Action Created'
    INTEGRATION_ACTION_UPDATED = 'INTEGRATION_ACTION_UPDATED', 'Integration Action Updated'
    # Story 24.3: Integration status validation audit
    INTEGRATION_STATUS_UPDATED = 'INTEGRATION_STATUS_UPDATED', 'Integration Status Updated'
    # Story 51.2: Integration health check manual test
    INTEGRATION_HEALTH_CHECK_TESTED = 'INTEGRATION_HEALTH_CHECK_TESTED', 'Integration Health Check Tested'
    # Story 24.4: Migration and execution guard-rail audit types
    INTEGRATION_MARKED_LEGACY = 'INTEGRATION_MARKED_LEGACY', 'Integration Marked Legacy'
    EXECUTION_BLOCKED_INVALID_INTEGRATION = 'EXECUTION_BLOCKED_INVALID_INTEGRATION', 'Execution Blocked Invalid Integration'
    EXECUTION_DEPRECATED_INTEGRATION_WARNING = 'EXECUTION_DEPRECATED_INTEGRATION_WARNING', 'Execution Deprecated Integration Warning'
    WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION = 'WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION', 'Workflow Step Blocked Invalid Integration'
    # Story 28.2: Policy evaluation audit types
    EXECUTION_STEP_POLICY_APPROVAL_REQUIRED = 'EXECUTION_STEP_POLICY_APPROVAL_REQUIRED', 'Execution Step Policy Approval Required'
    EXECUTION_STEP_POLICY_AUTO_APPROVED = 'EXECUTION_STEP_POLICY_AUTO_APPROVED', 'Execution Step Policy Auto Approved'
    EXECUTION_STEP_POLICY_EVALUATION_FAILED = 'EXECUTION_STEP_POLICY_EVALUATION_FAILED', 'Execution Step Policy Evaluation Failed'
    # Story 57.15: Workflow schedule step audit type
    WORKFLOW_STEP_SCHEDULE_CREATED = 'WORKFLOW_STEP_SCHEDULE_CREATED', 'Workflow Step Schedule Created'
    # Story 28.4: Business rule policy CRUD audit types
    POLICY_CREATED = 'POLICY_CREATED', 'Policy Created'
    POLICY_UPDATED = 'POLICY_UPDATED', 'Policy Updated'
    POLICY_DELETED = 'POLICY_DELETED', 'Policy Deleted'
    # Story 30.7: Polling exhaustion audit type
    EXECUTION_POLLING_EXHAUSTED = 'EXECUTION_POLLING_EXHAUSTED', 'Execution Polling Exhausted'
    # Story 64.1: IaC Config Sync audit types
    CONFIG_SYNC_REFERENCE_IMPORT = 'CONFIG_SYNC_REFERENCE_IMPORT', 'Config Sync - Reference Data Import'
    # Story 64.2: IaC Config Sync - Tags and Feature Flags
    CONFIG_SYNC_TAGS_IMPORT = 'CONFIG_SYNC_TAGS_IMPORT', 'Config Sync - Tags Import'
    CONFIG_SYNC_FEATURE_FLAGS_IMPORT = 'CONFIG_SYNC_FEATURE_FLAGS_IMPORT', 'Config Sync - Feature Flags Import'
    # Story 64.3: IaC Config Sync - Integration Type Catalogue
    CONFIG_SYNC_INTEGRATION_TYPE_IMPORT = 'CONFIG_SYNC_INTEGRATION_TYPE_IMPORT', 'Config Sync - Integration Type Import'
    # Story 64.4: IaC Config Sync - Integration
    CONFIG_SYNC_INTEGRATION_IMPORT = 'CONFIG_SYNC_INTEGRATION_IMPORT', 'Config Sync - Integration Import'
    # Story 64.5: IaC Config Sync - Business Rule Policy
    CONFIG_SYNC_POLICY_IMPORT = 'CONFIG_SYNC_POLICY_IMPORT', 'Config Sync - Policy Import'
    # Story 64.6: IaC Config Sync - Action
    CONFIG_SYNC_ACTION_IMPORT = 'CONFIG_SYNC_ACTION_IMPORT', 'Config Sync - Action Import'
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
    # Story 24.1: Integration type catalogue entity types
    INTEGRATION_TYPE_CATALOGUE = 'integration_type_catalogue', 'Integration Type Catalogue'
    INTEGRATION_ACTION = 'integration_action', 'Integration Action'
    # Story 28.4: Business rule policy entity type
    BUSINESS_RULE_POLICY = 'business_rule_policy', 'Business Rule Policy'
    # Story 64.1: IaC Reference Data entity type
    REFERENCE_DATA = 'reference_data', 'Reference Data'
    # Story 64.2: IaC Tags entity type
    TAGS = 'tags', 'Tags'
    # Additional types may exist in later migrations


class ImmutableQuerySet(models.QuerySet):
    """QuerySet that forbids update() and delete() for immutable audit logs (SOC1/NFR8)."""

    def update(self, **kwargs: Any) -> None:  # type: ignore[override]
        raise IntegrityError("AUDIT_LOG is immutable - bulk updates are forbidden (SOC1/NFR8)")

    def delete(self) -> None:  # type: ignore[override]
        raise IntegrityError("AUDIT_LOG is immutable - bulk deletions are forbidden (SOC1/NFR8)")


class AuditLogManager(models.Manager):
    """
    Custom manager for AuditLog model.
    Provides query methods for common audit log queries.
    Uses ImmutableQuerySet to prevent bulk update/delete.
    """

    def get_queryset(self) -> ImmutableQuerySet:
        return ImmutableQuerySet(self.model, using=self._db)

    def create_entry(self, user_id: str, action_type: str, entity_type: str,
                     entity_id: int, details: dict | None = None,
                     ip_address: str | None = None, correlation_id: str | None = None) -> AuditLog:
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
            details_json = json.dumps(details)
        
        return self.create(  # type: ignore[return-value]
            user_id=user_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details_json,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
    
    def list_by_entity(self, entity_type: str, entity_id: int) -> models.QuerySet[AuditLog]:
        """
        List audit entries for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            QuerySet of audit entries for the entity, ordered by timestamp DESC
        """
        return self.filter(entity_type=entity_type, entity_id=entity_id).order_by('-timestamp')  # type: ignore[return-value]
    
    def list_by_user(self, user_id: str) -> models.QuerySet[AuditLog]:
        """
        List audit entries for a specific user.

        Args:
            user_id: ID of the user

        Returns:
            QuerySet of audit entries for the user, ordered by timestamp DESC
        """
        return self.filter(user_id=user_id).order_by('-timestamp')  # type: ignore[return-value]
    
    def list_by_date_range(self, from_date: Any = None, to_date: Any = None) -> models.QuerySet[AuditLog]:
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
        return queryset.order_by('-timestamp')  # type: ignore[return-value]


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

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise IntegrityError("AUDIT_LOG is immutable - updates are forbidden (SOC1/NFR8)")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        raise IntegrityError("AUDIT_LOG is immutable - deletions are forbidden (SOC1/NFR8)")

    def __str__(self) -> str:
        return f"Audit {self.id} - {self.action_type} ({self.entity_type}:{self.entity_id})"

    def get_details(self) -> dict | list | None:
        """Deserialize JSON from CLOB."""
        if self.details:
            try:
                return json.loads(self.details)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize details for AuditLog {self.id}: {e}")
                return None
        return None

    def set_details(self, value: dict | list | None) -> None:
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
    # Story 64.11: IaC sync tracking
    last_synced_at = models.DateTimeField(null=True, blank=True, db_column='LAST_SYNCED_AT')
    last_synced_hash = models.CharField(max_length=64, null=True, blank=True, db_column='LAST_SYNCED_HASH')

    class Meta:
        db_table = 'CORE_FEATURE_FLAGS'
        ordering = ['flag_key']

    def __str__(self) -> str:
        status = 'ON' if self.enabled else 'OFF'
        return f"{self.flag_key} ({status}, {self.rollout_percent}%)"

    def clean(self) -> None:
        """Validate rollout_percent is 0-100."""
        from django.core.exceptions import ValidationError
        if self.rollout_percent < 0 or self.rollout_percent > 100:
            raise ValidationError({
                'rollout_percent': 'Rollout percent must be between 0 and 100.',
            })

    def save(self, *args: Any, **kwargs: Any) -> None:
        """HIGH-3 fix: Call full_clean() before save to ensure validation."""
        self.full_clean()
        super().save(*args, **kwargs)
