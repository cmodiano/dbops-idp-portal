"""
Output schemas model.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from django.db import models
from core.fields import OracleJSONField


class SchemaType(models.TextChoices):
    ACTION = 'action', 'Action'
    INTEGRATION = 'integration', 'Integration'
    PLATFORM_CONVENTION = 'platform_convention', 'Platform Convention'


class OutputSchema(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    schema_type = models.CharField(
        max_length=30,
        choices=SchemaType.choices,
        db_column='SCHEMA_TYPE'
    )
    target_name = models.CharField(
        max_length=255,
        db_column='TARGET_NAME',
        help_text='action_name, integration_type, or convention_name'
    )
    operation = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='OPERATION',
        help_text='operation name for integration schemas (e.g. create_change)'
    )
    inherits_from = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='INHERITS_FROM_ID',
        related_name='children'
    )
    schema_json = OracleJSONField(null=True, blank=True, db_column='SCHEMA_JSON')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'OUTPUT_SCHEMAS'
        constraints = [
            models.UniqueConstraint(
                fields=['schema_type', 'target_name', 'operation'],
                condition=models.Q(operation__isnull=False),
                name='uq_output_schema_type_target_op'
            )
        ]

    def __str__(self) -> str:
        if self.operation:
            return f"{self.schema_type}:{self.target_name}:{self.operation}"
        return f"{self.schema_type}:{self.target_name}"
