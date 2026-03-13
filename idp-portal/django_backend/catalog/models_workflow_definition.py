"""
Story 78.10: Normalized workflow definition models.

Maps the Flyway-managed tables WORKFLOW_DEFINITIONS, WORKFLOW_STEPS, WORKFLOW_STEP_EDGES
to Django ORM models (managed = False).
"""
from __future__ import annotations

from django.db import models
from core.fields import OracleJSONField


class WorkflowStepType(models.TextChoices):
    PLATFORM = 'platform', 'Platform'
    SERVICE_CALL = 'service_call', 'Service Call'
    HTTP_REQUEST = 'http_request', 'HTTP Request'
    EVALUATION = 'evaluation', 'Evaluation'
    GATE = 'gate', 'Gate'
    SCHEDULE_EXECUTION = 'schedule_execution', 'Schedule Execution'


class EdgeType(models.TextChoices):
    SUCCESS = 'success', 'Success'
    ERROR = 'error', 'Error'


class WorkflowDefinition(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    action = models.OneToOneField(
        'catalog.Action',
        on_delete=models.CASCADE,
        db_column='ACTION_ID',
        related_name='workflow_definition',
    )
    version = models.IntegerField(default=1, db_column='VERSION')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        managed = False
        db_table = 'WORKFLOW_DEFINITIONS'

    def __str__(self) -> str:
        return f"WorkflowDefinition(action_id={self.action_id}, v{self.version})"


class WorkflowStep(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    workflow_definition = models.ForeignKey(
        WorkflowDefinition,
        on_delete=models.CASCADE,
        db_column='WORKFLOW_DEFINITION_ID',
        related_name='steps',
    )
    step_id = models.CharField(max_length=255, db_column='STEP_ID')
    step_order = models.IntegerField(db_column='STEP_ORDER')
    step_name = models.CharField(max_length=255, db_column='STEP_NAME')
    step_type = models.CharField(
        max_length=50,
        choices=WorkflowStepType.choices,
        db_column='STEP_TYPE',
    )
    referenced_action = models.ForeignKey(
        'catalog.Action',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='REFERENCED_ACTION_ID',
        related_name='referencing_workflow_steps',
    )
    integration_type = models.CharField(max_length=100, null=True, blank=True, db_column='INTEGRATION_TYPE')
    operation = models.CharField(max_length=255, null=True, blank=True, db_column='OPERATION')
    input_mapping = OracleJSONField(null=True, blank=True, db_column='INPUT_MAPPING')
    output_mapping = OracleJSONField(null=True, blank=True, db_column='OUTPUT_MAPPING')
    condition = models.TextField(null=True, blank=True, db_column='CONDITION')
    retry_enabled = models.BooleanField(default=False, db_column='RETRY_ENABLED')
    retry_max_attempts = models.IntegerField(null=True, blank=True, db_column='RETRY_MAX_ATTEMPTS')
    retry_interval_seconds = models.IntegerField(null=True, blank=True, db_column='RETRY_INTERVAL_SECONDS')
    retry_backoff_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, db_column='RETRY_BACKOFF_MULTIPLIER',
    )
    join_policy = models.CharField(max_length=50, null=True, blank=True, db_column='JOIN_POLICY')

    class Meta:
        managed = False
        db_table = 'WORKFLOW_STEPS'
        unique_together = [['workflow_definition', 'step_id']]
        ordering = ['step_order']

    def __str__(self) -> str:
        return f"WorkflowStep({self.step_id}, order={self.step_order}, type={self.step_type})"


class WorkflowStepEdge(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    from_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        db_column='FROM_STEP_ID',
        related_name='outgoing_edges',
    )
    to_step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        db_column='TO_STEP_ID',
        related_name='incoming_edges',
    )
    edge_type = models.CharField(
        max_length=20,
        choices=EdgeType.choices,
        db_column='EDGE_TYPE',
    )

    class Meta:
        managed = False
        db_table = 'WORKFLOW_STEP_EDGES'
        unique_together = [['from_step', 'to_step', 'edge_type']]

    def __str__(self) -> str:
        return f"Edge({self.from_step_id} -[{self.edge_type}]-> {self.to_step_id})"
