"""
Story 78.15: Remove deprecated approval columns from Execution model.

Corresponding Flyway migration: V136__drop_legacy_permission_clobs.sql
(includes APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT on EXECUTIONS table).

Source of truth: ExecutionStep.approved_by/at/approval_comment (ADR-007, V099).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('executions', '0020_add_execution_outbox'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='execution',
            name='approved_by',
        ),
        migrations.RemoveField(
            model_name='execution',
            name='approved_at',
        ),
        migrations.RemoveField(
            model_name='execution',
            name='approval_comment',
        ),
    ]
