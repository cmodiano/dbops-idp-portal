# 0018_add_workflow_command.py
# Story 78.4 — Table WORKFLOW_COMMANDS pour commandes durables
# Note: schéma Oracle géré par Flyway V124. En production :
# python manage.py migrate --fake executions 0018

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("executions", "0017_align_config_step_id_charfield"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowCommand",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("execution", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="workflow_commands",
                    to="executions.execution",
                    db_column="EXECUTION_ID",
                )),
                ("command_type", models.CharField(max_length=50, db_column="COMMAND_TYPE")),
                ("payload", models.JSONField(null=True, blank=True, db_column="PAYLOAD")),
                ("status", models.CharField(
                    max_length=20,
                    choices=[("pending", "En attente"), ("processed", "Traité"), ("failed", "Échoué")],
                    default="pending",
                    db_column="STATUS",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="CREATED_AT")),
                ("processed_at", models.DateTimeField(null=True, blank=True, db_column="PROCESSED_AT")),
                ("created_by", models.CharField(max_length=255, null=True, blank=True, db_column="CREATED_BY")),
                ("error_message", models.TextField(null=True, blank=True, db_column="ERROR_MESSAGE")),
            ],
            options={
                "db_table": "WORKFLOW_COMMANDS",
                "ordering": ["created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="idx_wf_cmd_status_created"),
                ],
            },
        ),
    ]
