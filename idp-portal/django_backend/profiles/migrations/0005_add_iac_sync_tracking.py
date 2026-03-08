"""Story 64.11: Add IaC sync tracking columns to Profile."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0004_add_is_approver"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="profile",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
    ]
