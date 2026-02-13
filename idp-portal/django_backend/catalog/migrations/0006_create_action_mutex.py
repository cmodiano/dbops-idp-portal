# Generated manually for Story 25.5 (ACTION_MUTEX table)
# Django migration for tests (Oracle schema managed by Flyway V070)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_alter_action_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActionMutex",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "same_target",
                    models.BooleanField(
                        db_column="SAME_TARGET",
                        help_text="If True: mutex applies only when targeting same target_id. If False: mutex applies globally.",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        blank=True,
                        db_column="DESCRIPTION",
                        help_text="Human-readable explanation of why these actions are incompatible",
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_column="CREATED_AT"),
                ),
                (
                    "action",
                    models.ForeignKey(
                        db_column="ACTION_ID",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mutex_rules",
                        to="catalog.action",
                    ),
                ),
                (
                    "incompatible_with",
                    models.ForeignKey(
                        db_column="INCOMPATIBLE_WITH_ID",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incompatible_mutex_rules",
                        to="catalog.action",
                    ),
                ),
            ],
            options={
                "db_table": "ACTION_MUTEX",
                "ordering": ["action", "incompatible_with"],
                "unique_together": {("action", "incompatible_with")},
            },
        ),
    ]
