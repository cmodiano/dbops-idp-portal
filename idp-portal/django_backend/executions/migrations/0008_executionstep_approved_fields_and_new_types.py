# Story 57.1: ExecutionStep — nouveaux champs d'approbation et nouveaux types (ADR-007, V099)
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("executions", "0007_remove_execution_environment_choices"),
        ("idp_auth", "0001_initial"),
    ]

    operations = [
        # 1. AlterField step_type avec les 9 choix (5 existants + 4 ADR-007)
        migrations.AlterField(
            model_name="executionstep",
            name="step_type",
            field=models.CharField(
                choices=[
                    ("vault", "Vault"),
                    ("servicenow", "ServiceNow"),
                    ("platform", "Platform"),
                    ("prerequisite", "Prerequisite"),
                    ("verification", "Verification"),
                    ("service_call", "Service Call"),
                    ("http_request", "HTTP Request"),
                    ("evaluation", "Evaluation"),
                    ("gate", "Gate"),
                ],
                db_column="STEP_TYPE",
                max_length=50,
            ),
        ),
        # 2. AddField approved_by (FK → User)
        migrations.AddField(
            model_name="executionstep",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                db_column="APPROVED_BY",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="approved_steps",
                to="idp_auth.user",
            ),
        ),
        # 3. AddField approved_at
        migrations.AddField(
            model_name="executionstep",
            name="approved_at",
            field=models.DateTimeField(blank=True, db_column="APPROVED_AT", null=True),
        ),
        # 4. AddField approval_comment
        migrations.AddField(
            model_name="executionstep",
            name="approval_comment",
            field=models.CharField(
                blank=True,
                db_column="APPROVAL_COMMENT",
                max_length=1000,
                null=True,
            ),
        ),
    ]
