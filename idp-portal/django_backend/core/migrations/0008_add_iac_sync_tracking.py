"""Story 64.11: Add IaC sync tracking columns to FeatureFlag."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_add_auth_dev_bypass_login_audit_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="featureflag",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="featureflag",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
    ]
