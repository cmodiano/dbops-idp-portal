# Story 25.2: Add WAITING status to ExecutionStep

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("executions", "0005_add_execution_target"),
    ]

    operations = [
        migrations.AlterField(
            model_name="executionstep",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("WAITING", "Waiting"),
                    ("RUNNING", "Running"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                    ("SKIPPED", "Skipped"),
                ],
                db_column="STATUS",
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
