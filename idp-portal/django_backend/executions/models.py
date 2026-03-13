import json
import structlog
from datetime import datetime
from typing import Any, cast
from django.db import models
from django.utils import timezone
from idp_auth.models import User
from catalog.models import Action

logger = structlog.get_logger(__name__)


class ExecutionStatus(models.TextChoices):
    """
    Execution status enum matching Oracle CHECK constraint (V023, V030, V057).

    Status flow:
    - SUBMITTED: Successfully submitted to platform (AAP, ServiceNow, etc.)
    - INTEGRATION_ERROR: Failed to submit to platform (platform unreachable, API error, etc.)
      This is a PRE-execution failure — the execution never reached the platform.
      Distinct from FAILED which means the platform received and processed the request but it failed.
    - PENDING_APPROVAL: DEPRECATED (ADR-007) — kept for Oracle DB CHECK constraint compatibility.
      Approvals are now handled via ExecutionStep WAITING gates.
      Will be removed in a future migration.
    - RUNNING: Execution in progress on platform
    - COMPLETED: Execution finished successfully
    - FAILED: Execution failed during/after platform processing
    - CANCELLED: Execution cancelled by user
    - REJECTED: Approval rejected (step-level rejection can set execution to FAILED)
    """
    SUBMITTED = 'SUBMITTED', 'Submitted'
    INTEGRATION_ERROR = 'INTEGRATION_ERROR', 'Integration Error'  # Story 18.6 (V057)
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
    
    def list_by_user(self, user_id: int) -> models.QuerySet:
        """
        List executions for a specific user.

        Args:
            user_id: ID of the user

        Returns:
            QuerySet of executions for the user, ordered by created_at DESC
        """
        return self.filter(user_id=user_id).select_related('action', 'user').order_by('-created_at')

    def list_by_status(self, status: str) -> models.QuerySet:
        """
        Filter executions by status.

        Args:
            status: Status value (SUBMITTED, RUNNING, COMPLETED, etc.)

        Returns:
            QuerySet filtered by status
        """
        return self.filter(status=status).select_related('action', 'user')

    def get_recent(self, limit: int = 100) -> models.QuerySet:
        """
        Get recent executions for dashboard.
        Optimized with select_related to avoid N+1 queries.

        Args:
            limit: Maximum number of executions to return

        Returns:
            QuerySet of recent executions with action and user prefetched
        """
        return self.select_related('action', 'user').order_by('-created_at')[:limit]

    def with_action(self) -> models.QuerySet:
        """Select related action to avoid N+1 queries."""
        return self.select_related('action')

    def with_user(self) -> models.QuerySet:
        """Select related user to avoid N+1 queries."""
        return self.select_related('user')

    def with_steps(self) -> models.QuerySet:
        """Prefetch execution steps to avoid N+1 queries."""
        return self.prefetch_related('executionstep_set')


class Execution(models.Model):
    """
    Execution model mapping to Oracle EXECUTIONS table (V023, V030, V033).
    Represents an execution of an action.

    Champs dépréciés (ADR-007, Story 57.12) :
    - approved_by, approved_at, approval_comment : source de vérité migrée vers
      ExecutionStep (Story 57.1 / V099). Conservés pour données historiques et
      backward compat. Ne plus écrire dans ces champs, utiliser ExecutionStep.approved_* à la place.
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
    # DEPRECATED ADR-007 (Story 57.12) — La source de vérité est ExecutionStep.approved_by depuis Story 57.1.
    # Ce champ sera supprimé dans une release future. Ne plus écrire dans ce champ.
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_executions',
        db_column='APPROVED_BY'
    )
    # DEPRECATED ADR-007 (Story 57.12) — source de vérité: ExecutionStep.approved_at
    approved_at = models.DateTimeField(null=True, blank=True, db_column='APPROVED_AT')
    # DEPRECATED ADR-007 (Story 57.12) — source de vérité: ExecutionStep.approval_comment
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
    # Story 18.6: Error message for integration failures
    error_message = models.TextField(null=True, blank=True, db_column='ERROR_MESSAGE')
    # Story 72.1: Correlation ID pour traçabilité bout-en-bout (HTTP → Celery → audit)
    # Nullable pour rétrocompatibilité avec les exécutions existantes (V119).
    correlation_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_column='CORRELATION_ID',
    )
    started_at = models.DateTimeField(null=True, blank=True, db_column='STARTED_AT')
    completed_at = models.DateTimeField(null=True, blank=True, db_column='COMPLETED_AT')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    # Story 76.3: heartbeat pour détection de staleness précise (updated à chaque progression significative)
    updated_at = models.DateTimeField(null=True, blank=True, db_column='UPDATED_AT')

    # Custom manager
    objects = ExecutionManager()

    class Meta:
        db_table = 'EXECUTIONS'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at'], name='idx_exec_action_created'),
            # Story 76.3: index pour la détection de staleness via updated_at
            models.Index(fields=['updated_at'], name='idx_exec_updated_at'),
        ]

    def __str__(self) -> str:
        return f"Execution {self.id} - {self.action.name} ({self.status})"

    # JSON field helper
    def get_parameters(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.parameters:
            try:
                return json.loads(self.parameters)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize parameters for Execution {self.id}: {e}")
                return None
        return None

    def set_parameters(self, value: dict | None) -> None:
        """Serialize JSON to CLOB."""
        if value is not None:
            self.parameters = json.dumps(value)
        else:
            self.parameters = None

    @property
    def is_pending_approval(self) -> bool:
        """
        ADR-007 (Story 57.12) : Dérivé depuis les ExecutionSteps uniquement.
        True si l'exécution a au moins un ExecutionStep en statut WAITING.

        Note : la vérification step-based couvre tous les types de gate WAITING
        (gate_type=approval ET gate_type=maintenance_window). Cette approche est
        intentionnelle — les deux types représentent un blocage humain/opérationnel légitime.
        Vérifier gate_type=approval dans le champ JSON output de chaque step serait coûteux
        pour une propriété fréquemment appelée. Voir ADR-007 Phase 4.2 Dev Notes.

        Legacy PENDING_APPROVAL status is no longer used. All approvals go through
        ExecutionStep WAITING gates (see _create_execution_atomic).
        """
        return self.executionstep_set.filter(
            status=ExecutionStepStatus.WAITING
        ).exists()


class TargetType(models.TextChoices):
    """Target type enum for ExecutionTarget."""
    SERVER = 'SERVER', 'Server'
    DATABASE = 'DATABASE', 'Database'
    INSTANCE = 'INSTANCE', 'Instance'
    SCHEMA = 'SCHEMA', 'Schema'
    CLUSTER = 'CLUSTER', 'Cluster'
    OTHER = 'OTHER', 'Other'


class ExecutionTarget(models.Model):
    """
    ExecutionTarget model mapping to Oracle EXECUTION_TARGETS table.
    Stores the explicit link between an execution and its targets (servers, databases, etc.).
    Story 25.1: Foundation for condition gates, mutex, and RBAC validation.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    execution = models.ForeignKey(
        Execution,
        on_delete=models.CASCADE,
        related_name='targets',
        db_column='EXECUTION_ID'
    )
    target_type = models.CharField(
        max_length=50,
        choices=TargetType.choices,
        db_column='TARGET_TYPE'
    )
    target_id = models.CharField(max_length=200, db_column='TARGET_ID')
    target_name = models.CharField(max_length=255, db_column='TARGET_NAME')
    target_metadata = models.TextField(null=True, blank=True, db_column='TARGET_METADATA')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'EXECUTION_TARGETS'
        unique_together = [['execution', 'target_type', 'target_id']]

    def __str__(self) -> str:
        return f"ExecutionTarget {self.id} - {self.target_type}:{self.target_name}"

    def get_target_metadata(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.target_metadata:
            try:
                return cast("dict[Any, Any] | None", json.loads(self.target_metadata))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize target_metadata for ExecutionTarget {self.id}: {e}")
                return None
        return None

    def set_target_metadata(self, value: dict | None) -> None:
        """Serialize JSON to CLOB."""
        if value is not None:
            self.target_metadata = json.dumps(value, ensure_ascii=False)
        else:
            self.target_metadata = None


class ExecutionStepType(models.TextChoices):
    """Execution step type enum matching Oracle CHECK constraint (V025, V099, V107).

    Original values (5): vault, servicenow, platform, prerequisite, verification.
    ADR-007 values (4): service_call, http_request, evaluation, gate.
    Story 57.15 (1): schedule_execution.
    """
    VAULT = 'vault', 'Vault'
    SERVICENOW = 'servicenow', 'ServiceNow'
    PLATFORM = 'platform', 'Platform'
    PREREQUISITE = 'prerequisite', 'Prerequisite'
    VERIFICATION = 'verification', 'Verification'
    SERVICE_CALL = 'service_call', 'Service Call'
    HTTP_REQUEST = 'http_request', 'HTTP Request'
    EVALUATION = 'evaluation', 'Evaluation'
    GATE = 'gate', 'Gate'
    SCHEDULE_EXECUTION = 'schedule_execution', 'Schedule Execution'


class ExecutionStepStatus(models.TextChoices):
    """Execution step status enum matching Oracle CHECK constraint."""
    PENDING = 'PENDING', 'Pending'
    WAITING = 'WAITING', 'Waiting'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    SKIPPED = 'SKIPPED', 'Skipped'


class ExecutionStep(models.Model):
    """
    ExecutionStep model mapping to Oracle EXECUTION_STEPS table (V025).
    Represents a step within an execution.

    Approval fields (V099, ADR-007): approved_by, approved_at, approval_comment
    enable granular per-step approval (migration from Execution-level approval V030).
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
    # config_step_id: step_id from action.execution_steps config (UUID format).
    # Aligned to Oracle VARCHAR2(255) — see Flyway V116.
    config_step_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='CONFIG_STEP_ID',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    # Approval fields (V099, ADR-007) — granular per-step approval
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_steps',
        db_column='APPROVED_BY',
    )
    approved_at = models.DateTimeField(null=True, blank=True, db_column='APPROVED_AT')
    approval_comment = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        db_column='APPROVAL_COMMENT',
    )
    # Rejection fields (V118) — who rejected and when (gate step rejection)
    rejected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_steps',
        db_column='REJECTED_BY',
    )
    rejected_at = models.DateTimeField(null=True, blank=True, db_column='REJECTED_AT')

    class Meta:
        db_table = 'EXECUTION_STEPS'
        unique_together = [['execution', 'step_order']]
        ordering = ['execution', 'step_order']

    def __str__(self) -> str:
        return f"Step {self.step_order} - {self.step_name} ({self.status})"

    # JSON field helper
    def get_output(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.output:
            try:
                return json.loads(self.output)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize output for ExecutionStep {self.id}: {e}")
                return None
        return None

    def set_output(self, value: dict | None) -> None:
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
    
    def list_by_user(self, user_id: int) -> models.QuerySet:
        """List scheduled executions for a specific user."""
        return self.filter(user_id=user_id).order_by('-created_at')

    def list_by_status(self, status: str) -> models.QuerySet:
        """Filter scheduled executions by status."""
        return self.filter(status=status).order_by('-created_at')

    def list_pending(self, before_datetime: datetime) -> models.QuerySet:
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
    # Story 57.17: ID of the source Execution that triggered creation via a schedule_execution step
    source_execution_id = models.BigIntegerField(null=True, blank=True, db_column='SOURCE_EXECUTION_ID')

    # Custom manager
    objects = ScheduledExecutionManager()

    class Meta:
        db_table = 'SCHEDULED_EXECUTIONS'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Scheduled Execution {self.id} - {self.action.name} ({self.status})"

    # JSON field helper
    def get_parameters(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.parameters:
            try:
                return json.loads(self.parameters)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize parameters for ScheduledExecution {self.id}: {e}")
                return None
        return None

    def set_parameters(self, value: dict | None) -> None:
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

    @property
    def is_active_bool(self) -> bool:
        """Oracle NUMBER(1) → bool (1 = True, 0 = False)."""
        return self.is_active == 1

    def __str__(self) -> str:
        return f"Recurring Pattern {self.id} - {self.pattern_type}"

    # JSON field helper
    def get_pattern_config(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.pattern_config:
            try:
                return json.loads(self.pattern_config)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize pattern_config for RecurringPattern {self.id}: {e}")
                return None
        return None

    def set_pattern_config(self, value: dict | None) -> None:
        """Serialize JSON to CLOB."""
        if value is not None:
            self.pattern_config = json.dumps(value)
        else:
            self.pattern_config = None


class WorkflowEventType(models.TextChoices):
    """Event types for real-time UI sync (V113)."""
    EXECUTION_STATUS_CHANGED = 'EXECUTION_STATUS_CHANGED', 'Execution Status Changed'
    STEP_STATUS_CHANGED = 'STEP_STATUS_CHANGED', 'Step Status Changed'
    STEP_OUTPUT_UPDATED = 'STEP_OUTPUT_UPDATED', 'Step Output Updated'
    STEP_STARTED = 'STEP_STARTED', 'Step Started'
    STEP_COMPLETED = 'STEP_COMPLETED', 'Step Completed'
    STEP_FAILED = 'STEP_FAILED', 'Step Failed'
    APPROVAL_REQUESTED = 'APPROVAL_REQUESTED', 'Approval Requested'
    APPROVAL_GRANTED = 'APPROVAL_GRANTED', 'Approval Granted'
    APPROVAL_REJECTED = 'APPROVAL_REJECTED', 'Approval Rejected'
    TARGET_ADDED = 'TARGET_ADDED', 'Target Added'
    EXECUTION_COMPLETED = 'EXECUTION_COMPLETED', 'Execution Completed'
    EXECUTION_FAILED = 'EXECUTION_FAILED', 'Execution Failed'


class WorkflowEventEntityType(models.TextChoices):
    """Entity types for workflow events (V113)."""
    EXECUTION = 'execution', 'Execution'
    EXECUTION_STEP = 'execution_step', 'Execution Step'
    EXECUTION_TARGET = 'execution_target', 'Execution Target'


class WorkflowEvent(models.Model):
    """
    WorkflowEvent model mapping to Oracle WORKFLOW_EVENTS table (V113).

    Event sourcing table for real-time UI sync. Each state change in an
    execution or step produces an event row. The UI subscribes via WebSocket
    and uses sequence_num to detect missed events and request catch-up.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    execution = models.ForeignKey(
        Execution,
        on_delete=models.CASCADE,
        related_name='workflow_events',
        db_column='EXECUTION_ID'
    )
    event_type = models.CharField(
        max_length=50,
        choices=WorkflowEventType.choices,
        db_column='EVENT_TYPE'
    )
    entity_type = models.CharField(
        max_length=30,
        choices=WorkflowEventEntityType.choices,
        db_column='ENTITY_TYPE'
    )
    entity_id = models.BigIntegerField(db_column='ENTITY_ID')
    sequence_num = models.BigIntegerField(db_column='SEQUENCE_NUM')
    payload = models.TextField(null=True, blank=True, db_column='PAYLOAD')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'WORKFLOW_EVENTS'
        ordering = ['execution', 'sequence_num']
        unique_together = [['execution', 'sequence_num']]
        indexes = [
            models.Index(fields=['execution', 'created_at'], name='idx_wf_events_exec_created'),
            models.Index(fields=['entity_type', 'entity_id'], name='idx_wf_events_entity'),
        ]

    def __str__(self) -> str:
        return f"WorkflowEvent {self.id} - {self.event_type} (exec={self.execution_id}, seq={self.sequence_num})"

    def get_payload(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.payload:
            try:
                return json.loads(self.payload)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize payload for WorkflowEvent {self.id}: {e}")
                return None
        return None

    def set_payload(self, value: dict | None) -> None:
        """Serialize JSON to CLOB."""
        if value is not None:
            self.payload = json.dumps(value)
        else:
            self.payload = None


class WorkflowEventCounter(models.Model):
    """
    WorkflowEventCounter model mapping to Oracle WORKFLOW_EVENT_COUNTER table (V122).

    One row per execution. LAST_SEQUENCE_NUM is incremented atomically via
    SELECT FOR UPDATE (row-level lock) to eliminate sequence collisions under
    concurrent emitters (parallel workflow steps completing simultaneously).
    """
    execution = models.OneToOneField(
        Execution,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='event_counter',
        db_column='EXECUTION_ID'
    )
    last_sequence_num = models.BigIntegerField(default=0, db_column='LAST_SEQUENCE_NUM')

    class Meta:
        db_table = 'WORKFLOW_EVENT_COUNTER'

    def __str__(self) -> str:
        return f"WorkflowEventCounter(execution_id={self.execution_id}, last_seq={self.last_sequence_num})"


class RunnableStep(models.Model):
    """
    RunnableStep model mapping to Oracle RUNNABLE_STEPS table (V113).

    Work queue of execution steps ready for execution. When the workflow engine
    determines a step is eligible (prerequisites met, gates satisfied), it inserts
    a row here. Workers claim rows, transition the step to RUNNING, then delete
    the row. Avoids full-table scans of EXECUTION_STEPS for PENDING rows.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    execution_step = models.OneToOneField(
        ExecutionStep,
        on_delete=models.CASCADE,
        related_name='runnable_entry',
        db_column='EXECUTION_STEP_ID'
    )
    execution = models.ForeignKey(
        Execution,
        on_delete=models.CASCADE,
        related_name='runnable_steps',
        db_column='EXECUTION_ID'
    )
    step_order = models.IntegerField(db_column='STEP_ORDER')
    step_type = models.CharField(max_length=50, db_column='STEP_TYPE')
    priority = models.IntegerField(default=0, db_column='PRIORITY')
    eligible_at = models.DateTimeField(auto_now_add=True, db_column='ELIGIBLE_AT')
    claimed_at = models.DateTimeField(null=True, blank=True, db_column='CLAIMED_AT')
    claimed_by = models.CharField(max_length=255, null=True, blank=True, db_column='CLAIMED_BY')
    claimed_until = models.DateTimeField(null=True, blank=True, db_column='CLAIMED_UNTIL')
    attempt_no = models.IntegerField(default=0, db_column='ATTEMPT_NO')
    last_error = models.TextField(null=True, blank=True, db_column='LAST_ERROR')
    max_attempts = models.IntegerField(default=3, db_column='MAX_ATTEMPTS')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')

    class Meta:
        db_table = 'RUNNABLE_STEPS'
        ordering = ['-priority', 'eligible_at']
        indexes = [
            models.Index(fields=['eligible_at', 'claimed_until', '-priority'], name='idx_runnable_steps_lease'),
        ]

    def __str__(self) -> str:
        return f"RunnableStep {self.id} - step={self.execution_step_id} (priority={self.priority})"

    @property
    def is_claimed(self) -> bool:
        """Active si lease non expiré."""
        if self.claimed_until is None:
            return False
        return self.claimed_until > timezone.now()

    @property
    def is_lease_expired(self) -> bool:
        """True si un claim existe mais le lease a expiré (crash worker)."""
        if self.claimed_at is None or self.claimed_until is None:
            return False
        return self.claimed_until <= timezone.now()

    @property
    def has_exceeded_max_attempts(self) -> bool:
        return self.attempt_no >= self.max_attempts
