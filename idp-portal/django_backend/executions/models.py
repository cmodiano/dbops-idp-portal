import json
import logging
from datetime import datetime
from django.db import models
from idp_auth.models import User
from catalog.models import Action

logger = logging.getLogger(__name__)


class ExecutionEnvironment(models.TextChoices):
    """Execution environment enum matching Oracle CHECK constraint."""
    DEV = 'dev', 'Development'
    STAGING = 'staging', 'Staging'
    PROD = 'prod', 'Production'


class ExecutionStatus(models.TextChoices):
    """Execution status enum matching Oracle CHECK constraint (V023, V030)."""
    SUBMITTED = 'SUBMITTED', 'Submitted'
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REJECTED = 'REJECTED', 'Rejected'  # Added in V030


class ExecutionManager(models.Manager):
    """
    Custom manager for Execution model.
    Provides query methods for common execution queries.
    """
    
    def list_by_user(self, user_id: int):
        """
        List executions for a specific user.
        
        Args:
            user_id: ID of the user
        
        Returns:
            QuerySet of executions for the user, ordered by created_at DESC
        """
        return self.filter(user_id=user_id).order_by('-created_at')
    
    def list_by_status(self, status: str):
        """
        Filter executions by status.
        
        Args:
            status: Status value (SUBMITTED, RUNNING, COMPLETED, etc.)
        
        Returns:
            QuerySet filtered by status
        """
        return self.filter(status=status)
    
    def get_recent(self, limit: int = 100):
        """
        Get recent executions for dashboard.
        Optimized with select_related to avoid N+1 queries.
        
        Args:
            limit: Maximum number of executions to return
        
        Returns:
            QuerySet of recent executions with action and user prefetched
        """
        return self.select_related('action', 'user').order_by('-created_at')[:limit]
    
    def with_action(self):
        """Select related action to avoid N+1 queries."""
        return self.select_related('action')
    
    def with_user(self):
        """Select related user to avoid N+1 queries."""
        return self.select_related('user')
    
    def with_steps(self):
        """Prefetch execution steps to avoid N+1 queries."""
        return self.prefetch_related('executionstep_set')


class Execution(models.Model):
    """
    Execution model mapping to Oracle EXECUTIONS table (V023, V030, V033).
    Represents an execution of an action.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='ACTION_ID'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='USER_ID'
    )
    environment = models.CharField(
        max_length=50,
        choices=ExecutionEnvironment.choices,
        db_column='ENVIRONMENT'
    )
    # CLOB field - using TextField with JSON serialization helper
    parameters = models.TextField(null=True, blank=True, db_column='PARAMETERS')
    status = models.CharField(
        max_length=20,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.SUBMITTED,
        db_column='STATUS'
    )
    servicenow_change_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='SERVICENOW_CHANGE_ID'
    )
    # Approval workflow fields (V030)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_executions',
        db_column='APPROVED_BY'
    )
    approved_at = models.DateTimeField(null=True, blank=True, db_column='APPROVED_AT')
    approval_comment = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        db_column='APPROVAL_COMMENT'
    )
    # Parent execution for remediation (V033)
    parent_execution = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_executions',
        db_column='PARENT_EXECUTION_ID'
    )
    started_at = models.DateTimeField(null=True, blank=True, db_column='STARTED_AT')
    completed_at = models.DateTimeField(null=True, blank=True, db_column='COMPLETED_AT')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    
    # Custom manager
    objects = ExecutionManager()

    class Meta:
        db_table = 'EXECUTIONS'
        ordering = ['-created_at']

    def __str__(self):
        return f"Execution {self.id} - {self.action.name} ({self.status})"

    # JSON field helper
    def get_parameters(self):
        """Deserialize JSON from CLOB."""
        if self.parameters:
            try:
                return json.loads(self.parameters)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize parameters for Execution {self.id}: {e}")
                return None
        return None

    def set_parameters(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.parameters = json.dumps(value)
        else:
            self.parameters = None


class ExecutionStepType(models.TextChoices):
    """Execution step type enum matching Oracle CHECK constraint."""
    VAULT = 'vault', 'Vault'
    SERVICENOW = 'servicenow', 'ServiceNow'
    PLATFORM = 'platform', 'Platform'
    PREREQUISITE = 'prerequisite', 'Prerequisite'
    VERIFICATION = 'verification', 'Verification'


class ExecutionStepStatus(models.TextChoices):
    """Execution step status enum matching Oracle CHECK constraint."""
    PENDING = 'PENDING', 'Pending'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    SKIPPED = 'SKIPPED', 'Skipped'


class ExecutionStep(models.Model):
    """
    ExecutionStep model mapping to Oracle EXECUTION_STEPS table (V025).
    Represents a step within an execution.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    execution = models.ForeignKey(
        Execution,
        on_delete=models.CASCADE,
        db_column='EXECUTION_ID'
    )
    step_order = models.IntegerField(db_column='STEP_ORDER')
    step_name = models.CharField(max_length=255, db_column='STEP_NAME')
    step_type = models.CharField(
        max_length=50,
        choices=ExecutionStepType.choices,
        db_column='STEP_TYPE'
    )
    status = models.CharField(
        max_length=20,
        choices=ExecutionStepStatus.choices,
        default=ExecutionStepStatus.PENDING,
        db_column='STATUS'
    )
    started_at = models.DateTimeField(null=True, blank=True, db_column='STARTED_AT')
    completed_at = models.DateTimeField(null=True, blank=True, db_column='COMPLETED_AT')
    # CLOB fields - using TextField with JSON serialization helpers
    output = models.TextField(null=True, blank=True, db_column='OUTPUT')
    platform_job_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='PLATFORM_JOB_ID'
    )
    error_message = models.TextField(null=True, blank=True, db_column='ERROR_MESSAGE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'EXECUTION_STEPS'
        unique_together = [['execution', 'step_order']]
        ordering = ['execution', 'step_order']

    def __str__(self):
        return f"Step {self.step_order} - {self.step_name} ({self.status})"

    # JSON field helper
    def get_output(self):
        """Deserialize JSON from CLOB."""
        if self.output:
            try:
                return json.loads(self.output)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize output for ExecutionStep {self.id}: {e}")
                return None
        return None

    def set_output(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.output = json.dumps(value)
        else:
            self.output = None


class ScheduledExecutionStatus(models.TextChoices):
    """Scheduled execution status enum matching Oracle CHECK constraint."""
    PENDING = 'pending', 'Pending'
    EXECUTED = 'executed', 'Executed'
    CANCELLED = 'cancelled', 'Cancelled'


class ScheduledExecutionManager(models.Manager):
    """
    Custom manager for ScheduledExecution model.
    Provides query methods for common scheduled execution queries.
    """
    
    def list_by_user(self, user_id: int):
        """List scheduled executions for a specific user."""
        return self.filter(user_id=user_id).order_by('-created_at')
    
    def list_by_status(self, status: str):
        """Filter scheduled executions by status."""
        return self.filter(status=status).order_by('-created_at')
    
    def list_pending(self, before_datetime: datetime):
        """
        List pending scheduled executions for external scheduler.
        Includes one-time (scheduled_at <= before) and active recurring (next_execution_date <= before).
        """
        from django.db.models import Q
        return self.select_related('recurringpattern').filter(
            Q(status=ScheduledExecutionStatus.PENDING) &
            (
                Q(scheduled_at__lte=before_datetime) |
                Q(recurringpattern__next_execution_date__lte=before_datetime, recurringpattern__is_active=1)
            )
        ).order_by('scheduled_at', 'recurringpattern__next_execution_date')


class ScheduledExecution(models.Model):
    """
    ScheduledExecution model mapping to Oracle SCHEDULED_EXECUTIONS table (V038).
    Represents a scheduled execution (one-time or recurring).
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    action = models.ForeignKey(
        Action,
        on_delete=models.CASCADE,
        db_column='ACTION_ID'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='USER_ID'
    )
    environment = models.CharField(
        max_length=50,
        choices=ExecutionEnvironment.choices,
        db_column='ENVIRONMENT'
    )
    # CLOB field - using TextField with JSON serialization helper
    parameters = models.TextField(null=True, blank=True, db_column='PARAMETERS')
    scheduled_at = models.DateTimeField(null=True, blank=True, db_column='SCHEDULED_AT')
    status = models.CharField(
        max_length=20,
        choices=ScheduledExecutionStatus.choices,
        default=ScheduledExecutionStatus.PENDING,
        db_column='STATUS'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='UPDATED_AT')

    # Story 11.6/11.10: optional tracing + effective execution link
    correlation_id = models.CharField(max_length=64, null=True, blank=True, db_column='CORRELATION_ID')
    execution_id = models.BigIntegerField(null=True, blank=True, db_column='EXECUTION_ID')
    
    # Custom manager
    objects = ScheduledExecutionManager()

    class Meta:
        db_table = 'SCHEDULED_EXECUTIONS'
        ordering = ['-created_at']

    def __str__(self):
        return f"Scheduled Execution {self.id} - {self.action.name} ({self.status})"

    # JSON field helper
    def get_parameters(self):
        """Deserialize JSON from CLOB."""
        if self.parameters:
            try:
                return json.loads(self.parameters)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize parameters for ScheduledExecution {self.id}: {e}")
                return None
        return None

    def set_parameters(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.parameters = json.dumps(value)
        else:
            self.parameters = None


class RecurringPatternType(models.TextChoices):
    """Recurring pattern type enum matching Oracle CHECK constraint."""
    ONE_TIME = 'one_time', 'One Time'
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    CRON = 'cron', 'Cron'


class RecurringPattern(models.Model):
    """
    RecurringPattern model mapping to Oracle RECURRING_PATTERNS table (V038).
    Represents recurrence configuration for scheduled executions.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    scheduled_execution = models.OneToOneField(
        ScheduledExecution,
        on_delete=models.CASCADE,
        db_column='SCHEDULED_EXECUTION_ID'
    )
    pattern_type = models.CharField(
        max_length=50,
        choices=RecurringPatternType.choices,
        db_column='PATTERN_TYPE'
    )
    # CLOB field - using TextField with JSON serialization helper
    pattern_config = models.TextField(null=True, blank=True, db_column='PATTERN_CONFIG')
    next_execution_date = models.DateTimeField(db_column='NEXT_EXECUTION_DATE')
    is_active = models.IntegerField(default=1, db_column='IS_ACTIVE')  # Oracle NUMBER(1) CHECK: 0, 1
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(null=True, blank=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'RECURRING_PATTERNS'

    def __str__(self):
        return f"Recurring Pattern {self.id} - {self.pattern_type}"

    # JSON field helper
    def get_pattern_config(self):
        """Deserialize JSON from CLOB."""
        if self.pattern_config:
            try:
                return json.loads(self.pattern_config)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize pattern_config for RecurringPattern {self.id}: {e}")
                return None
        return None

    def set_pattern_config(self, value):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.pattern_config = json.dumps(value)
        else:
            self.pattern_config = None
